"""Open an MP4 writer. H.264 is used when the Cisco OpenH264 DLL is present."""

from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np

from app.paths import DIR_BIN


_DLL_READY = False


def ensure_openh264() -> bool:
    global _DLL_READY
    dll = DIR_BIN / "openh264-2.5.0-win64.dll"
    if not dll.exists():
        return False
    if not _DLL_READY:
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(DIR_BIN))
        os.environ["PATH"] = str(DIR_BIN) + os.pathsep + os.environ.get("PATH", "")
        _DLL_READY = True
    return True


def open_writer(path: Path, fps: float, size: tuple[int, int]):
    path.parent.mkdir(parents=True, exist_ok=True)
    has_h264 = ensure_openh264()
    codecs = ["avc1", "H264", "mp4v"] if has_h264 else ["mp4v"]
    for name in codecs:
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*name), float(fps), size)
        if writer.isOpened():
            return writer, name
        writer.release()
    raise RuntimeError("No MP4 codec could be opened. Install failed to prepare a video encoder.")


def fit_frame(frame: np.ndarray, width: int, height: int) -> np.ndarray:
    src_h, src_w = frame.shape[:2]
    if src_w == width and src_h == height:
        return frame
    scale = min(width / src_w, height / src_h)
    resized_w = max(1, int(round(src_w * scale)))
    resized_h = max(1, int(round(src_h * scale)))
    resized = cv2.resize(frame, (resized_w, resized_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    x = (width - resized_w) // 2
    y = (height - resized_h) // 2
    canvas[y : y + resized_h, x : x + resized_w] = resized
    return canvas


def probe_video(path: Path) -> dict:
    cap = cv2.VideoCapture(str(path))
    frames = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    readable = False
    if cap.isOpened():
        readable, _frame = cap.read()
    cap.release()
    duration = frames / fps if fps > 0 else 0.0
    return {
        "path": str(path),
        "frames": frames,
        "fps": fps,
        "width": width,
        "height": height,
        "duration_s": duration,
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "readable": bool(readable),
    }
