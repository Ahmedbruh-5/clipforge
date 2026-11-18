"""Scene-change and visual-activity signals using OpenCV frame sampling."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def _open_capture(video_path: Path) -> cv2.VideoCapture:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Unable to open video for analysis: {video_path}")
    return capture


def analyze_visual_signals(
    video_path: Path,
    *,
    window_seconds: float = 1.0,
    scene_threshold: float = 0.35,
    max_fps_sample: float = 4.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[float]]:
    """
    Returns:
      centers, visual_activity[0..1], scene_impulse[0..1], scene_timestamps

    visual_activity = normalized mean absolute frame difference
    scene_impulse = peaks where histogram/scene delta crosses threshold
    """
    capture = _open_capture(video_path)
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0) or 25.0
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration = frame_count / fps if frame_count > 0 else 0.0
        sample_every = max(int(round(fps / max_fps_sample)), 1)

        prev_gray = None
        prev_hist = None
        diffs: list[tuple[float, float]] = []
        scene_times: list[float] = []

        index = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if index % sample_every != 0:
                index += 1
                continue

            timestamp = index / fps
            small = cv2.resize(frame, (160, 90))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

            hist = cv2.calcHist([gray], [0], None, [32], [0, 256])
            cv2.normalize(hist, hist)

            activity = 0.0
            scene_delta = 0.0
            if prev_gray is not None:
                activity = float(np.mean(cv2.absdiff(gray, prev_gray))) / 255.0
                scene_delta = float(cv2.compareHist(prev_hist, hist, cv2.HISTCMP_BHATTACHARYYA))
                if scene_delta >= scene_threshold:
                    scene_times.append(timestamp)

            diffs.append((timestamp, activity))
            prev_gray = gray
            prev_hist = hist
            index += 1

        if not diffs:
            return np.array([]), np.array([]), np.array([]), []

        if duration <= 0:
            duration = diffs[-1][0] + window_seconds

        n_windows = max(int(np.ceil(duration / window_seconds)), 1)
        visual = np.zeros(n_windows, dtype=np.float32)
        counts = np.zeros(n_windows, dtype=np.float32)
        scene = np.zeros(n_windows, dtype=np.float32)
        centers = (np.arange(n_windows) + 0.5) * window_seconds

        for ts, activity in diffs:
            idx = min(int(ts / window_seconds), n_windows - 1)
            visual[idx] += activity
            counts[idx] += 1

        for ts in scene_times:
            idx = min(int(ts / window_seconds), n_windows - 1)
            scene[idx] = 1.0

        mask = counts > 0
        visual[mask] /= counts[mask]
        if visual.max() > 0:
            visual = visual / float(visual.max())

        return centers.astype(np.float32), visual, scene, scene_times
    finally:
        capture.release()
