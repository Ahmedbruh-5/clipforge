"""Aspect-ratio crop geometry.

crop_x / crop_y are normalized [0, 1] positions of the crop window
(0 = left/top edge, 0.5 = center, 1 = right/bottom). Designed so face
tracking or subject-aware cropping can later supply these values.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CropRect:
    x: int
    y: int
    width: int
    height: int
    target_width: int
    target_height: int

    @property
    def ffmpeg_crop(self) -> str:
        return f"crop={self.width}:{self.height}:{self.x}:{self.y}"

    @property
    def ffmpeg_scale(self) -> str:
        return f"scale={self.target_width}:{self.target_height}"

    @property
    def ffmpeg_filter(self) -> str:
        return f"{self.ffmpeg_crop},{self.ffmpeg_scale}"


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def parse_resolution(resolution: str) -> tuple[int, int] | None:
    text = resolution.strip().lower()
    if text in {"", "source"}:
        return None
    if "x" not in text:
        raise ValueError(f"Invalid resolution '{resolution}', expected WIDTHxHEIGHT")
    width_s, height_s = text.split("x", 1)
    width, height = int(width_s), int(height_s)
    if width < 16 or height < 16:
        raise ValueError("Resolution too small")
    return width, height


def aspect_ratio_value(aspect_ratio: str) -> float | None:
    text = aspect_ratio.strip().lower()
    if text in {"", "source"}:
        return None
    if text in {"9:16", "9/16"}:
        return 9 / 16
    if text in {"16:9", "16/9"}:
        return 16 / 9
    if text in {"1:1", "1/1"}:
        return 1.0
    if ":" in text:
        a, b = text.split(":", 1)
        return float(a) / float(b)
    if "/" in text:
        a, b = text.split("/", 1)
        return float(a) / float(b)
    raise ValueError(f"Unsupported aspect ratio '{aspect_ratio}'")


def compute_crop_rect(
    source_width: int,
    source_height: int,
    *,
    aspect_ratio: str = "9:16",
    resolution: str = "1080x1920",
    crop_x: float = 0.5,
    crop_y: float = 0.5,
) -> CropRect | None:
    """Return crop+scale geometry, or None when keeping source framing."""
    if source_width <= 0 or source_height <= 0:
        raise ValueError("Invalid source dimensions")

    target_aspect = aspect_ratio_value(aspect_ratio)
    parsed_res = parse_resolution(resolution)

    if target_aspect is None and parsed_res is None:
        return None

    if target_aspect is None:
        # Scale only
        assert parsed_res is not None
        tw, th = parsed_res
        return CropRect(
            x=0,
            y=0,
            width=source_width,
            height=source_height,
            target_width=tw,
            target_height=th,
        )

    src_aspect = source_width / source_height
    if src_aspect > target_aspect:
        crop_h = source_height
        crop_w = max(2, int(round(source_height * target_aspect)))
        crop_w -= crop_w % 2
        crop_h -= crop_h % 2
    else:
        crop_w = source_width
        crop_h = max(2, int(round(source_width / target_aspect)))
        crop_w -= crop_w % 2
        crop_h -= crop_h % 2

    crop_w = min(crop_w, source_width)
    crop_h = min(crop_h, source_height)

    max_x = max(0, source_width - crop_w)
    max_y = max(0, source_height - crop_h)
    x = int(round(max_x * _clamp01(crop_x)))
    y = int(round(max_y * _clamp01(crop_y)))

    if parsed_res is not None:
        tw, th = parsed_res
    else:
        tw, th = crop_w, crop_h

    # H.264 prefers even dimensions
    tw -= tw % 2
    th -= th % 2

    return CropRect(
        x=x,
        y=y,
        width=crop_w,
        height=crop_h,
        target_width=max(tw, 2),
        target_height=max(th, 2),
    )
