"""Highlight candidate generator — traditional signal fusion, not AI interest detection."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.core.config import Settings, get_settings
from app.engine.audio_analyzer import analyze_audio_activity
from app.engine.scene_detector import analyze_visual_signals
from app.utils.ffmpeg import detect_silences

logger = logging.getLogger(__name__)


@dataclass
class CandidateSegment:
    start_time: float
    end_time: float
    score: float
    audio_score: float
    scene_score: float
    visual_score: float
    label: str
    notes: str


def _normalize_weights(settings: Settings) -> tuple[float, float, float]:
    total = (
        settings.detect_weight_audio
        + settings.detect_weight_scene
        + settings.detect_weight_visual
    )
    if total <= 0:
        return 0.5, 0.2, 0.3
    return (
        settings.detect_weight_audio / total,
        settings.detect_weight_scene / total,
        settings.detect_weight_visual / total,
    )


def _silence_mask(
    n_windows: int,
    window: float,
    silences: list[tuple[float, float]],
) -> np.ndarray:
    mask = np.ones(n_windows, dtype=np.float32)
    for start, end in silences:
        i0 = max(int(start / window), 0)
        i1 = min(int(np.ceil(end / window)), n_windows)
        mask[i0:i1] = 0.0
    return mask


def _merge_nearby(
    segments: list[CandidateSegment],
    merge_gap: float,
    max_duration: float,
) -> list[CandidateSegment]:
    if not segments:
        return []
    ordered = sorted(segments, key=lambda s: s.start_time)
    merged: list[CandidateSegment] = [ordered[0]]
    for seg in ordered[1:]:
        prev = merged[-1]
        if seg.start_time - prev.end_time <= merge_gap:
            new_end = min(max(prev.end_time, seg.end_time), prev.start_time + max_duration)
            score = max(prev.score, seg.score)
            merged[-1] = CandidateSegment(
                start_time=prev.start_time,
                end_time=new_end,
                score=score,
                audio_score=max(prev.audio_score, seg.audio_score),
                scene_score=max(prev.scene_score, seg.scene_score),
                visual_score=max(prev.visual_score, seg.visual_score),
                label="merged_candidate",
                notes=(
                    "Merged nearby high-signal windows. "
                    "High score ≠ guaranteed interesting moment."
                ),
            )
        else:
            merged.append(seg)
    return merged


def generate_candidates(
    video_path: Path,
    duration: float | None,
    temp_dir: Path,
    settings: Settings | None = None,
) -> list[CandidateSegment]:
    settings = settings or get_settings()
    window = settings.detect_window_seconds
    w_audio, w_scene, w_visual = _normalize_weights(settings)

    temp_dir.mkdir(parents=True, exist_ok=True)
    wav_path = temp_dir / f"detect_audio_{video_path.stem}.wav"

    audio_centers, audio_scores = analyze_audio_activity(
        video_path,
        wav_path,
        window_seconds=window,
    )
    visual_centers, visual_scores, scene_scores, scene_times = analyze_visual_signals(
        video_path,
        window_seconds=window,
        scene_threshold=settings.detect_scene_threshold,
    )
    silences = detect_silences(
        video_path,
        noise_db=settings.detect_silence_noise_db,
        min_duration=settings.detect_silence_min_duration,
    )

    try:
        wav_path.unlink(missing_ok=True)
    except OSError:
        pass

    # Align to a common timeline length
    n = 0
    if audio_scores.size:
        n = max(n, audio_scores.size)
    if visual_scores.size:
        n = max(n, visual_scores.size)
    if scene_scores.size:
        n = max(n, scene_scores.size)
    if n == 0:
        return []

    def pad(arr: np.ndarray) -> np.ndarray:
        if arr.size == n:
            return arr
        out = np.zeros(n, dtype=np.float32)
        out[: arr.size] = arr
        return out

    audio = pad(audio_scores if audio_scores.size else np.zeros(0))
    visual = pad(visual_scores if visual_scores.size else np.zeros(0))
    scene = pad(scene_scores if scene_scores.size else np.zeros(0))
    silent = _silence_mask(n, window, silences)

    combined = (w_audio * audio + w_scene * scene + w_visual * visual) * silent

    # Prefer local peaks above mean+std
    mean = float(combined.mean()) if combined.size else 0.0
    std = float(combined.std()) if combined.size else 0.0
    threshold = mean + 0.35 * std
    if threshold <= 0:
        threshold = float(np.percentile(combined, 70)) if combined.size else 0.1

    min_len = settings.detect_min_clip_seconds
    max_len = settings.detect_max_clip_seconds
    video_duration = duration or (n * window)

    raw: list[CandidateSegment] = []
    for i, score in enumerate(combined):
        if score < threshold or silent[i] <= 0:
            continue
        center = (i + 0.5) * window
        half = min_len / 2
        start = max(0.0, center - half)
        end = min(video_duration, start + min_len)
        if end - start < min_len * 0.8:
            continue
        raw.append(
            CandidateSegment(
                start_time=round(start, 3),
                end_time=round(end, 3),
                score=float(score),
                audio_score=float(audio[i]),
                scene_score=float(scene[i]),
                visual_score=float(visual[i]),
                label="signal_peak",
                notes=(
                    "Ranked by audio activity, scene changes, and visual motion. "
                    "Not a judgment of editorial interest."
                ),
            )
        )

    # Also seed candidates around strong scene cuts
    for ts in scene_times:
        start = max(0.0, ts - min_len * 0.25)
        end = min(video_duration, start + min_len)
        idx = min(int(ts / window), n - 1)
        if silent[idx] <= 0:
            continue
        raw.append(
            CandidateSegment(
                start_time=round(start, 3),
                end_time=round(end, 3),
                score=float(combined[idx]),
                audio_score=float(audio[idx]),
                scene_score=1.0,
                visual_score=float(visual[idx]),
                label="scene_change",
                notes="Seeded near a detected scene transition.",
            )
        )

    merged = _merge_nearby(raw, settings.detect_merge_gap_seconds, max_len)

    # Drop overlaps keeping higher score
    merged.sort(key=lambda s: s.score, reverse=True)
    accepted: list[CandidateSegment] = []
    for seg in merged:
        overlaps = False
        for other in accepted:
            latest_start = max(seg.start_time, other.start_time)
            earliest_end = min(seg.end_time, other.end_time)
            if earliest_end - latest_start > 1.0:
                overlaps = True
                break
        if not overlaps and (seg.end_time - seg.start_time) <= max_len + 0.5:
            # Expand short segments toward max when surrounding score is high
            if seg.end_time - seg.start_time < min_len:
                continue
            accepted.append(seg)
        if len(accepted) >= settings.detect_max_candidates:
            break

    accepted.sort(key=lambda s: s.score, reverse=True)
    logger.info(
        "Detection produced %s candidates (silences=%s, scenes=%s)",
        len(accepted),
        len(silences),
        len(scene_times),
    )
    return accepted
