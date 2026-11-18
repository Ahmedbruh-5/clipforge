"""Video processing entry points used by clip rendering jobs."""

from pathlib import Path

from app.engine.cropper import CropRect, compute_crop_rect
from app.utils.ffmpeg import cut_clip, extract_metadata, generate_thumbnail


def read_media_metadata(path: Path):
    return extract_metadata(path)


def process_clip_render(
    source_path: Path,
    output_path: Path,
    start_time: float,
    end_time: float,
    *,
    source_width: int | None,
    source_height: int | None,
    aspect_ratio: str = "9:16",
    resolution: str = "1080x1920",
    crop_x: float = 0.5,
    crop_y: float = 0.5,
) -> tuple[Path, CropRect | None]:
    crop = None
    video_filter = None
    if source_width and source_height:
        crop = compute_crop_rect(
            source_width,
            source_height,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            crop_x=crop_x,
            crop_y=crop_y,
        )
        if crop is not None:
            video_filter = crop.ffmpeg_filter

    cut_clip(
        source_path,
        output_path,
        start_time,
        end_time,
        video_filter=video_filter,
    )
    return output_path, crop


def process_thumbnail(
    source_path: Path,
    output_path: Path,
    timestamp: float,
    *,
    source_width: int | None,
    source_height: int | None,
    aspect_ratio: str = "9:16",
    resolution: str = "1080x1920",
    crop_x: float = 0.5,
    crop_y: float = 0.5,
) -> Path:
    video_filter = None
    if source_width and source_height:
        crop = compute_crop_rect(
            source_width,
            source_height,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            crop_x=crop_x,
            crop_y=crop_y,
        )
        if crop is not None:
            # Smaller still for UI
            thumb_w = min(crop.target_width, 540)
            thumb_h = int(thumb_w * crop.target_height / crop.target_width)
            thumb_h -= thumb_h % 2
            video_filter = f"{crop.ffmpeg_crop},scale={thumb_w}:{max(thumb_h, 2)}"

    return generate_thumbnail(
        source_path,
        output_path,
        timestamp,
        video_filter=video_filter,
    )


# Backwards-compatible alias used by earlier phase code
def process_clip_cut(
    source_path: Path,
    output_path: Path,
    start_time: float,
    end_time: float,
) -> Path:
    return cut_clip(source_path, output_path, start_time, end_time)
