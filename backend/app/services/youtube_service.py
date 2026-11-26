"""YouTube OAuth + upload helpers.

Refresh tokens stay on disk under storage/secrets/ and are never returned to React.
OAuth client credentials can be left empty so the user can Connect later.
"""

from __future__ import annotations

import json
import logging
import re
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
    from google.auth.exceptions import RefreshError
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
        try:
            credentials.refresh(Request())
        except RefreshError as exc:
            raise YouTubeServiceError(
                "YouTube access expired or was revoked. Open Settings, disconnect, "
                "then Connect YouTube again.",
                status_code=401,
            ) from exc
        data["token"] = credentials.token
        data["expiry"] = credentials.expiry.isoformat() if credentials.expiry else None
        _token_path().write_text(json.dumps(data, indent=2), encoding="utf-8")

    return credentials


def _parse_iso8601_duration(value: str | None) -> int | None:
    """Parse YouTube ISO-8601 durations like PT1M5S into whole seconds."""
    if not value or not value.startswith("P"):
        return None

    match = re.fullmatch(
        r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?",
        value,
    )
    if not match:
        return None
    days, hours, minutes, seconds = (int(g or 0) for g in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# YouTube Shorts can be up to 3 minutes.
SHORTS_MAX_DURATION_SECONDS = 180


def fetch_channel_stats() -> dict[str, Any]:
    """Channel overview: subscribers, lifetime views, video count."""
    youtube = _youtube_client()
    response = youtube.channels().list(
        part="snippet,statistics,contentDetails",
        mine=True,
    ).execute()
    items = response.get("items") or []
    if not items:
        raise YouTubeServiceError("No YouTube channel found for this account.", status_code=404)

    item = items[0]
    snippet = item.get("snippet") or {}
    statistics = item.get("statistics") or {}
    thumbs = snippet.get("thumbnails") or {}
    thumb = (
        (thumbs.get("medium") or {}).get("url")
        or (thumbs.get("default") or {}).get("url")
    )
    uploads = ((item.get("contentDetails") or {}).get("relatedPlaylists") or {}).get(
        "uploads"
    )

    return {
        "channel_id": item.get("id"),
        "title": snippet.get("title"),
        "thumbnail_url": thumb,
        "subscriber_count": _safe_int(statistics.get("subscriberCount")),
        "hidden_subscriber_count": bool(statistics.get("hiddenSubscriberCount")),
        "view_count": _safe_int(statistics.get("viewCount")),
        "video_count": _safe_int(statistics.get("videoCount")),
        "uploads_playlist_id": uploads,
    }


def list_channel_shorts(
    *,
    max_results: int = 25,
    page_token: str | None = None,
) -> dict[str, Any]:
    """List recent uploads that look like Shorts, with per-video view counts."""
    max_results = max(1, min(max_results, 50))
    stats = fetch_channel_stats()
    uploads_playlist_id = stats.get("uploads_playlist_id")
    if not uploads_playlist_id:
        return {"items": [], "next_page_token": None, "total_returned": 0}

    youtube = _youtube_client()
    playlist = youtube.playlistItems().list(
        part="contentDetails,snippet",
        playlistId=uploads_playlist_id,
        maxResults=max_results,
        pageToken=page_token or None,
    ).execute()

    playlist_items = playlist.get("items") or []
    video_ids = [
        ((item.get("contentDetails") or {}).get("videoId"))
        for item in playlist_items
        if (item.get("contentDetails") or {}).get("videoId")
    ]

    details_by_id: dict[str, dict[str, Any]] = {}
    if video_ids:
        videos = youtube.videos().list(
            part="snippet,contentDetails,statistics",
            id=",".join(video_ids),
        ).execute()
        for video in videos.get("items") or []:
            vid = video.get("id")
            if vid:
                details_by_id[vid] = video

    shorts: list[dict[str, Any]] = []
    for video_id in video_ids:
        video = details_by_id.get(video_id)
        if not video:
            continue
        duration = _parse_iso8601_duration(
            (video.get("contentDetails") or {}).get("duration")
        )
        if duration is None or duration > SHORTS_MAX_DURATION_SECONDS or duration <= 0:
            continue

        snippet = video.get("snippet") or {}
        statistics = video.get("statistics") or {}
        thumbs = snippet.get("thumbnails") or {}
        thumb = (
            (thumbs.get("medium") or {}).get("url")
            or (thumbs.get("default") or {}).get("url")
        )
        shorts.append(
            {
                "video_id": video_id,
                "title": snippet.get("title") or "Untitled",
                "published_at": snippet.get("publishedAt"),
                "duration_seconds": duration,
                "view_count": _safe_int(statistics.get("viewCount")),
                "like_count": (
                    _safe_int(statistics["likeCount"])
                    if "likeCount" in statistics
                    else None
                ),
                "comment_count": (
                    _safe_int(statistics["commentCount"])
                    if "commentCount" in statistics
                    else None
                ),
                "thumbnail_url": thumb,
                "youtube_url": f"https://youtube.com/shorts/{video_id}",
            }
        )

    return {
        "items": shorts,
        "next_page_token": playlist.get("nextPageToken"),
        "total_returned": len(shorts),
        "channel_title": stats.get("title"),
        "channel_id": stats.get("channel_id"),
    }


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
