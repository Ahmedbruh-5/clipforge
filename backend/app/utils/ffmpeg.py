"""FFmpeg / FFprobe helpers. Prefer ffprobe; fall back to parsing ffmpeg -i."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings


class FFmpegError(RuntimeError):
    pass


@dataclass
class MediaMetadata:
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    codec: str | None = None
    has_audio: bool = False


def _which(binary: str) -> str | None:
    return shutil.which(binary)


def resolve_ffmpeg() -> str:
    settings = get_settings()
    path = _which(settings.ffmpeg_path) or _which("ffmpeg")
    if not path:
        raise FFmpegError(
            "FFmpeg was not found. Install FFmpeg and ensure it is on PATH."
        )
    return path


def resolve_ffprobe() -> str | None:
    settings = get_settings()
    return _which(settings.ffprobe_path) or _which("ffprobe")


def _run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise FFmpegError(f"Executable not found: {cmd[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise FFmpegError(f"Command timed out: {' '.join(cmd)}") from exc


def _parse_fps(rate: str | None) -> float | None:
    if not rate or rate in {"0/0", "N/A"}:
        return None
    if "/" in rate:
        num, den = rate.split("/", 1)
        try:
            denominator = float(den)
            if denominator == 0:
                return None
            return float(num) / denominator
        except ValueError:
            return None
    try:
        return float(rate)
    except ValueError:
        return None


def probe_with_ffprobe(file_path: Path) -> MediaMetadata:
    ffprobe = resolve_ffprobe()
    if not ffprobe:
        raise FFmpegError("ffprobe not available")

    cmd = [
        ffprobe,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(file_path),
    ]
    result = _run(cmd)
    if result.returncode != 0:
        raise FFmpegError(result.stderr.strip() or "ffprobe failed")

    data = json.loads(result.stdout)
    streams = data.get("streams") or []
    format_info = data.get("format") or {}

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    duration = None
    if format_info.get("duration"):
        duration = float(format_info["duration"])
    elif video_stream and video_stream.get("duration"):
        duration = float(video_stream["duration"])

    fps = None
    if video_stream:
        fps = _parse_fps(video_stream.get("avg_frame_rate")) or _parse_fps(
            video_stream.get("r_frame_rate")
        )

    return MediaMetadata(
        duration=duration,
        width=int(video_stream["width"]) if video_stream and video_stream.get("width") else None,
        height=int(video_stream["height"]) if video_stream and video_stream.get("height") else None,
        fps=fps,
        codec=video_stream.get("codec_name") if video_stream else None,
        has_audio=audio_stream is not None,
    )


def probe_with_ffmpeg(file_path: Path) -> MediaMetadata:
    """Fallback metadata extraction by parsing `ffmpeg -i` stderr."""
    ffmpeg = resolve_ffmpeg()
    result = _run([ffmpeg, "-hide_banner", "-i", str(file_path)])
    stderr = result.stderr or ""

    duration = None
    duration_match = re.search(
        r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)",
        stderr,
    )
    if duration_match:
        hours, minutes, seconds = duration_match.groups()
        duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)

    width = height = None
    codec = None
    fps = None
    video_match = re.search(
        r"Video:\s*([^\s,]+).*?(\d{2,5})x(\d{2,5}).*?(\d+(?:\.\d+)?)\s*fps",
        stderr,
        re.IGNORECASE,
    )
    if video_match:
        codec = video_match.group(1)
        width = int(video_match.group(2))
        height = int(video_match.group(3))
        fps = float(video_match.group(4))
    else:
        size_match = re.search(r"(\d{2,5})x(\d{2,5})", stderr)
        codec_match = re.search(r"Video:\s*([^\s,]+)", stderr)
        if size_match:
            width = int(size_match.group(1))
            height = int(size_match.group(2))
        if codec_match:
            codec = codec_match.group(1)

    has_audio = bool(re.search(r"Audio:\s*", stderr))

    if duration is None and width is None:
        raise FFmpegError(stderr.strip() or "Unable to read media metadata")

    return MediaMetadata(
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        codec=codec,
        has_audio=has_audio,
    )


def extract_metadata(file_path: Path) -> MediaMetadata:
    if not file_path.exists():
        raise FFmpegError(f"File not found: {file_path}")

    if resolve_ffprobe():
        try:
            return probe_with_ffprobe(file_path)
        except (FFmpegError, json.JSONDecodeError, KeyError, ValueError):
            pass

    return probe_with_ffmpeg(file_path)


def cut_clip(
    input_path: Path,
    output_path: Path,
    start_time: float,
    end_time: float,
    *,
    video_filter: str | None = None,
    audio_mode: str = "original",
    music_path: Path | None = None,
    music_volume: float = 1.0,
) -> Path:
    """Extract a time range to a new MP4 without modifying the source.

    audio_mode:
      - original: keep source audio
      - mute: silent AAC (anullsrc) — drops source audio
      - music: replace source audio with music_path (looped/trimmed)
    """
    if end_time <= start_time:
        raise FFmpegError("end_time must be greater than start_time")

    mode = (audio_mode or "original").strip().lower()
    if mode not in {"original", "mute", "music"}:
        raise FFmpegError(f"Unsupported audio_mode '{audio_mode}'")
    if mode == "music":
        if music_path is None or not music_path.exists():
            raise FFmpegError("music_path is required when audio_mode=music")
    volume = max(0.0, min(float(music_volume), 2.0))

    ffmpeg = resolve_ffmpeg()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = end_time - start_time
    dur_s = f"{duration:.3f}"

    common_video = [
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
    ]
    common_audio = ["-c:a", "aac", "-b:a", "128k"]
    common_tail = ["-movflags", "+faststart", str(output_path)]

    if mode == "original":
        cmd = [
            ffmpeg,
            "-y",
            "-ss",
            f"{start_time:.3f}",
            "-i",
            str(input_path),
            "-t",
            dur_s,
        ]
        if video_filter:
            cmd.extend(["-vf", video_filter])
        cmd.extend([*common_video, *common_audio, *common_tail])
    elif mode == "mute":
        # Silent stereo AAC — never map source audio.
        cmd = [
            ffmpeg,
            "-y",
            "-ss",
            f"{start_time:.3f}",
            "-t",
            dur_s,
            "-i",
            str(input_path),
            "-f",
            "lavfi",
            "-t",
            dur_s,
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
        ]
        if video_filter:
            cmd.extend(["-vf", video_filter])
        cmd.extend(
            [
                *common_video,
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-shortest",
                *common_audio,
                *common_tail,
            ]
        )
    else:
        # music: drop source audio; loop/trim replacement track to clip length.
        # Apply a modest gain floor so quiet library beds stay audible.
        fade_dur = min(0.75, max(duration * 0.05, 0.1))
        fade_start = max(duration - fade_dur, 0.0)
        gain = max(volume, 0.05) * 1.8
        af = (
            f"volume={gain:.4f},"
            f"afade=t=in:st=0:d=0.05,"
            f"afade=t=out:st={fade_start:.3f}:d={fade_dur:.3f},"
            "aformat=sample_fmts=fltp:channel_layouts=stereo"
        )
        cmd = [
            ffmpeg,
            "-y",
            "-ss",
            f"{start_time:.3f}",
            "-t",
            dur_s,
            "-i",
            str(input_path),
            "-stream_loop",
            "-1",
            "-i",
            str(music_path),
        ]
        if video_filter:
            cmd.extend(["-vf", video_filter])
        cmd.extend(
            [
                "-filter_complex",
                f"[1:a]{af}[aout]",
                *common_video,
                "-map",
                "0:v:0",
                "-map",
                "[aout]",
                "-shortest",
                "-t",
                dur_s,
                *common_audio,
                *common_tail,
            ]
        )

    result = _run(cmd, timeout=600)
    if result.returncode != 0 or not output_path.exists():
        raise FFmpegError(result.stderr.strip() or "FFmpeg clipping failed")
    return output_path


def generate_thumbnail(
    input_path: Path,
    output_path: Path,
    timestamp: float,
    *,
    video_filter: str | None = None,
) -> Path:
    """Capture a single JPEG frame. Never touches the source file."""
    ffmpeg = resolve_ffmpeg()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-ss",
        f"{max(timestamp, 0):.3f}",
        "-i",
        str(input_path),
        "-frames:v",
        "1",
    ]
    if video_filter:
        cmd.extend(["-vf", video_filter])
    cmd.extend([str(output_path)])
    result = _run(cmd, timeout=120)
    if result.returncode != 0 or not output_path.exists():
        raise FFmpegError(result.stderr.strip() or "Thumbnail generation failed")
    return output_path


def convert_image_to_jpeg(
    input_path: Path,
    output_path: Path,
    *,
    max_width: int = 1080,
    max_height: int = 1920,
) -> Path:
    """Normalize an uploaded image into a JPEG thumbnail."""
    ffmpeg = resolve_ffmpeg()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        f"scale='min({max_width},iw)':'min({max_height},ih)'"
        ":force_original_aspect_ratio=decrease"
    )
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(input_path),
        "-frames:v",
        "1",
        "-vf",
        vf,
        "-q:v",
        "2",
        str(output_path),
    ]
    result = _run(cmd, timeout=60)
    if result.returncode != 0 or not output_path.exists():
        raise FFmpegError(result.stderr.strip() or "Thumbnail image conversion failed")
    return output_path


def detect_silences(
    input_path: Path,
    *,
    noise_db: float = -35.0,
    min_duration: float = 0.6,
) -> list[tuple[float, float]]:
    """Return silence ranges using FFmpeg silencedetect."""
    ffmpeg = resolve_ffmpeg()
    filter_expr = f"silencedetect=noise={noise_db}dB:d={min_duration}"
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-i",
        str(input_path),
        "-af",
        filter_expr,
        "-f",
        "null",
        "-",
    ]
    result = _run(cmd, timeout=600)
    stderr = result.stderr or ""
    starts: list[float] = []
    ranges: list[tuple[float, float]] = []
    for line in stderr.splitlines():
        start_match = re.search(r"silence_start:\s*([0-9.]+)", line)
        if start_match:
            starts.append(float(start_match.group(1)))
            continue
        end_match = re.search(
            r"silence_end:\s*([0-9.]+)\s*\|\s*silence_duration:\s*([0-9.]+)",
            line,
        )
        if end_match:
            end = float(end_match.group(1))
            start = starts.pop() if starts else end - float(end_match.group(2))
            ranges.append((start, end))
    return ranges


def extract_audio_wav(input_path: Path, output_path: Path, sample_rate: int = 16000) -> Path:
    ffmpeg = resolve_ffmpeg()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(input_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]
    result = _run(cmd, timeout=600)
    if result.returncode != 0 or not output_path.exists():
        raise FFmpegError(result.stderr.strip() or "Audio extraction failed")
    return output_path

