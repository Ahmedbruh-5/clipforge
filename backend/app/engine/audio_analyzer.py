"""Audio activity analysis via RMS energy over time windows."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from app.utils.ffmpeg import extract_audio_wav


def analyze_audio_activity(
    video_path: Path,
    temp_wav: Path,
    *,
    window_seconds: float = 1.0,
    sample_rate: int = 16000,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Returns (window_centers_seconds, normalized_rms_scores[0..1]).

    Loud windows score higher. This does NOT mean the moment is interesting —
    only that audio energy was elevated.
    """
    extract_audio_wav(video_path, temp_wav, sample_rate=sample_rate)

    with wave.open(str(temp_wav), "rb") as wav:
        channels = wav.getnchannels()
        sampwidth = wav.getsampwidth()
        rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())

    if sampwidth != 2:
        raise RuntimeError("Expected 16-bit PCM audio")

    samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32)
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)

    if samples.size == 0:
        return np.array([]), np.array([])

    samples /= 32768.0
    window = max(int(rate * window_seconds), 1)
    n_windows = max(int(np.ceil(samples.size / window)), 1)

    rms_values = []
    centers = []
    for i in range(n_windows):
        chunk = samples[i * window : (i + 1) * window]
        if chunk.size == 0:
            continue
        rms = float(np.sqrt(np.mean(chunk**2)))
        rms_values.append(rms)
        centers.append((i + 0.5) * window_seconds)

    if not rms_values:
        return np.array([]), np.array([])

    arr = np.asarray(rms_values, dtype=np.float32)
    # Soft normalize with percentile to reduce outlier domination
    p95 = float(np.percentile(arr, 95)) or 1e-6
    normalized = np.clip(arr / p95, 0.0, 1.0)
    return np.asarray(centers, dtype=np.float32), normalized
