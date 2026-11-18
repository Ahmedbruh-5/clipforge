import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import clips, detection, schedules, videos
from app.core.config import get_settings
from app.core.database import init_db
from app.services.video_service import ensure_dirs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("clipforge")
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_dirs()
    init_db()
    logger.info("ClipForge backend ready (storage=%s)", settings.storage_path)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(videos.router)
app.include_router(clips.router)
app.include_router(detection.router)
app.include_router(schedules.router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "phase": "6",
        "features": [
            "upload",
            "metadata",
            "preview_stream",
            "manual_clips",
            "ffmpeg_render",
            "vertical_916",
            "crop_config",
            "thumbnails",
            "highlight_detection",
            "candidate_editing",
            "clip_review",
            "improved_timeline",
            "youtube_oauth",
            "youtube_schedule",
        ],
    }
