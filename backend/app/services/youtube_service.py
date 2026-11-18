"""YouTube OAuth + upload helpers.

Refresh tokens stay on disk under storage/secrets/ and are never returned to React.
OAuth client credentials can be left empty so the user can Connect later.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


class YouTubeServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _token_path() -> Path:
    settings = get_settings()
    path = settings.resolved_youtube_token_path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def oauth_configured() -> bool:
    return get_settings().youtube_oauth_configured


def is_connected() -> bool:
    path = _token_path()
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(data.get("refresh_token") or data.get("token"))


def get_public_status() -> dict[str, Any]:
    """Safe status payload for the frontend (no secrets)."""
    settings = get_settings()
    configured = oauth_configured()
    connected = is_connected() if configured else False
    channel_title = None
    channel_id = None
    if connected:
        try:
            info = fetch_channel_info()
            channel_title = info.get("title")
            channel_id = info.get("id")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not fetch YouTube channel info: %s", exc)

    return {
        "configured": configured,
        "connected": connected,
        "channel_title": channel_title,
        "channel_id": channel_id,
        "redirect_uri": settings.youtube_redirect_uri,
        "can_connect_later": True,
        "setup_hint": (
            None
            if configured
            else (
                "Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to backend/.env, "
                "set the OAuth redirect URI in Google Cloud Console to "
                f"{settings.youtube_redirect_uri}, then click Connect YouTube."
            )
        ),
    }


def _client_config() -> dict[str, Any]:
    settings = get_settings()
    if not settings.youtube_oauth_configured:
        raise YouTubeServiceError(
            "YouTube OAuth is not configured yet. Add GOOGLE_CLIENT_ID and "
            "GOOGLE_CLIENT_SECRET to backend/.env when you are ready to connect.",
            status_code=400,
        )
    return {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.youtube_redirect_uri],
        }
    }


def build_auth_url(state: str = "clipforge") -> dict[str, str]:
    from google_auth_oauthlib.flow import Flow

    settings = get_settings()
    flow = Flow.from_client_config(
        _client_config(),
        scopes=YOUTUBE_SCOPES,
        redirect_uri=settings.youtube_redirect_uri,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return {"auth_url": auth_url, "state": state}


def exchange_code(code: str) -> dict[str, Any]:
    from google_auth_oauthlib.flow import Flow

    settings = get_settings()
    flow = Flow.from_client_config(
        _client_config(),
        scopes=YOUTUBE_SCOPES,
        redirect_uri=settings.youtube_redirect_uri,
    )
    flow.fetch_token(code=code)
    credentials = flow.credentials
    payload = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes or YOUTUBE_SCOPES),
        "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
    }
    path = _token_path()
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return {"connected": True}


def disconnect() -> None:
    path = _token_path()
    path.unlink(missing_ok=True)


def _load_credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    if not oauth_configured():
        raise YouTubeServiceError("YouTube OAuth is not configured.", status_code=400)
    if not is_connected():
        raise YouTubeServiceError(
            "YouTube is not connected. Open Settings and connect your channel.",
            status_code=401,
        )

    data = json.loads(_token_path().read_text(encoding="utf-8"))
    expiry = None
    if data.get("expiry"):
        try:
            expiry = datetime.fromisoformat(data["expiry"])
        except ValueError:
            expiry = None

    credentials = Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=data.get("client_id") or get_settings().google_client_id,
        client_secret=data.get("client_secret") or get_settings().google_client_secret,
        scopes=data.get("scopes") or YOUTUBE_SCOPES,
    )
    if expiry:
        credentials.expiry = expiry

    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        data["token"] = credentials.token
        data["expiry"] = credentials.expiry.isoformat() if credentials.expiry else None
        _token_path().write_text(json.dumps(data, indent=2), encoding="utf-8")

    return credentials


def _youtube_client():
    from googleapiclient.discovery import build

    return build("youtube", "v3", credentials=_load_credentials(), cache_discovery=False)


def fetch_channel_info() -> dict[str, str | None]:
    youtube = _youtube_client()
    response = youtube.channels().list(part="snippet", mine=True).execute()
    items = response.get("items") or []
    if not items:
        return {"id": None, "title": None}
    item = items[0]
    return {
        "id": item.get("id"),
        "title": (item.get("snippet") or {}).get("title"),
    }


def upload_video_file(
    file_path: Path,
    *,
    title: str,
    description: str,
    privacy_status: str = "private",
    publish_at_utc: datetime | None = None,
) -> dict[str, str]:
    """Upload a local MP4. Uses YouTube native publishAt when scheduling."""
    from googleapiclient.http import MediaFileUpload

    if not file_path.exists():
        raise YouTubeServiceError("Rendered clip file not found on disk", status_code=404)

    privacy = privacy_status if privacy_status in {"private", "unlisted", "public"} else "private"
    body: dict[str, Any] = {
        "snippet": {
            "title": title[:100],
            "description": description or "",
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }

    # YouTube requires private + publishAt for scheduled public release
    if publish_at_utc is not None:
        if publish_at_utc.tzinfo is None:
            publish_at_utc = publish_at_utc.replace(tzinfo=timezone.utc)
        else:
            publish_at_utc = publish_at_utc.astimezone(timezone.utc)
        # RFC3339
        body["status"]["privacyStatus"] = "private"
        body["status"]["publishAt"] = publish_at_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    youtube = _youtube_client()
    media = MediaFileUpload(str(file_path), mimetype="video/mp4", resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        _, response = request.next_chunk()

    video_id = response.get("id")
    if not video_id:
        raise YouTubeServiceError("YouTube upload did not return a video id", status_code=502)

    return {
        "youtube_video_id": video_id,
        "youtube_url": f"https://youtube.com/shorts/{video_id}",
    }
