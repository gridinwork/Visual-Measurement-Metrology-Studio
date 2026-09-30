"""Playback of a video file at its own frame rate."""

from __future__ import annotations

import time

import cv2


class VideoFileCapture:
    def __init__(self) -> None:
        self.cap = None
        self.fps = 30.0
        self._next = 0.0

    def open(self, path: str) -> bool:
        self.close()
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            cap.release()
            return False
        self.cap = cap
        fps = cap.get(cv2.CAP_PROP_FPS)
        self.fps = fps if fps and fps > 1 else 30.0
        self._next = 0.0
        return True

    def read(self):
        if self.cap is None:
            return "error", None
        now = time.perf_counter()
        if now < self._next:
            return "wait", None
        ok, frame = self.cap.read()
        if not ok or frame is None:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self.cap.read()
            if not ok or frame is None:
                return "error", None
        self._next = now + 1.0 / self.fps
        return "frame", frame

    def grab(self) -> None:
        return

    def close(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None
