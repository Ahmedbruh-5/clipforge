# ClipForge

Local-first video clipping studio for turning long-form videos into short clips.

**Current status: Phase 6** — YouTube OAuth (connect later), uploads, and scheduling.

## Requirements

- Python 3.11+
- Node.js 18+
- FFmpeg on `PATH`
- FFprobe recommended (falls back to `ffmpeg -i` metadata parsing if missing)

## Project layout

```
clipforge/
  frontend/     React + Vite + Tailwind
  backend/      FastAPI + SQLAlchemy + SQLite
  storage/      originals, processed, thumbnails, temp
  database/     SQLite file
```

## Setup

### Backend

```bash
cd clipforge/backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # optional
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd clipforge/frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173 — the Vite dev server proxies `/api` to the backend.

## Current capabilities (through Phase 6)

- Upload MP4 / MOV / MKV / WEBM (2 GB limit)
- Metadata via FFprobe/FFmpeg + HTML5 preview
- Manual timestamps + improved zoomable timeline (candidates + clips markers)
- Vertical 9:16 crop (configurable crop_x/crop_y), 1080×1920 export
- Thumbnail generation on render
- Traditional highlight detection + candidate edit / delete / promote-to-clip
- Clip review dashboard with approve / reject filters
- YouTube OAuth connect (optional / connect later), Shorts upload, native `publishAt` scheduling

### Connect YouTube later

1. Enable **YouTube Data API v3** in Google Cloud Console
2. Create OAuth client credentials
3. Add redirect URI: `http://127.0.0.1:8000/api/youtube/callback`
4. Set `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` in `backend/.env`
5. Restart backend → **Settings → Connect YouTube**

Tokens are stored only under `storage/secrets/` (never sent to React).

## Not yet implemented

- Hardening, tests, docs polish (Phase 7)

## API smoke checks

```bash
curl http://127.0.0.1:8000/api/health
curl -F "file=@/path/to/video.mp4" http://127.0.0.1:8000/api/videos/upload
curl http://127.0.0.1:8000/api/videos
```
