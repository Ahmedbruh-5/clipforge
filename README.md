# ClipForge

Local-first video clipping studio for turning long-form videos into short clips and scheduling YouTube Shorts — without paid AI APIs or mandatory cloud services.

**Current status: Phase 7** — hardening, tests, CI, documentation, and gap fixes.

## Requirements

- Python 3.11+
- Node.js 18+
- FFmpeg on `PATH`
- FFprobe recommended (falls back to `ffmpeg -i` metadata parsing if missing)

## Project layout

```
clipforge/
  frontend/     React + Vite + Tailwind
  backend/      FastAPI + SQLAlchemy + SQLite (Postgres-ready URL)
  storage/      originals, processed, thumbnails, temp, secrets
  database/     SQLite file (gitignored)
  scripts/      smoke helpers
```

## Setup

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # optional
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173 — the Vite dev server proxies `/api` to the backend.

## Capabilities (through Phase 7)

- Upload MP4 / MOV / MKV / WEBM (2 GB limit)
- Metadata via FFprobe/FFmpeg + HTML5 preview with HTTP Range seeking
- Manual timestamps + zoomable timeline (candidates + clip markers)
- Vertical 9:16 crop (configurable crop_x/crop_y), 1080×1920 export
- Thumbnail generation / custom thumbnail upload
- Traditional highlight detection (audio / silence / scene) — signal peaks, not “interestingness”
- Candidate edit / delete / promote-to-clip
- Clip review (approve / reject); **only approved clips can be scheduled**
- YouTube OAuth (connect later), Shorts upload, native `publishAt` scheduling
- Job recovery on restart + APScheduler stale-job sweep
- Backend pytest suite + GitHub Actions CI

### Connect YouTube later

1. Enable **YouTube Data API v3** in Google Cloud Console
2. Create OAuth client credentials
3. Add redirect URI: `http://127.0.0.1:8000/api/youtube/callback`
4. Set `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` in `backend/.env`
5. Restart backend → **Settings → Connect YouTube**

Tokens are stored only under `storage/secrets/` (never sent to React).

## Database

Default is local **SQLite** (`database/clipforge.db`). The SQLAlchemy layer is modular — set `DATABASE_URL` to a PostgreSQL URL when you outgrow SQLite:

```env
DATABASE_URL=postgresql+psycopg://clipforge:clipforge@localhost:5432/clipforge
```

(Install a Postgres driver such as `psycopg` when you switch.)

## Tests & CI

```bash
cd backend
pip install -r requirements-dev.txt
pytest -q
```

```bash
cd frontend
npm ci
npm run lint
npm run build
```

GitHub Actions runs both on push/PR (`.github/workflows/ci.yml`).

Against a running backend:

```bash
chmod +x scripts/smoke_api.sh
./scripts/smoke_api.sh
```

## API smoke checks

```bash
curl http://127.0.0.1:8000/api/health
curl -F "file=@/path/to/video.mp4" http://127.0.0.1:8000/api/videos/upload
curl http://127.0.0.1:8000/api/videos
```

## Known limitations

- Single-user local app — no login/auth yet (do not expose beyond localhost without adding auth)
- Background jobs use in-process threads; restarts mark in-flight work failed so you can retry
- Schema changes use `create_all` + light SQLite column patches (no Alembic yet)
- Detection ranks audio/scene/motion peaks — it does not know if a moment is “interesting”
