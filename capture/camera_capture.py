"""USB webcam capture on Windows."""

from __future__ import annotations

import cv2


class CameraCapture:
    def __init__(self) -> None:
        self.cap = None
        self.index = 0
        self.size = (1280, 720)

    def open(self, index: int, width: int, height: int) -> bool:
        self.close()
        self.index = int(index)
        self.size = (int(width), int(height))
        for backend in (cv2.CAP_DSHOW, cv2.CAP_MSMF):
            cap = cv2.VideoCapture(self.index, backend)
            if not cap.isOpened():
                cap.release()
                continue
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.size[0])
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.size[1])
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.cap = cap
            return True
        return False

    def read(self):
        if self.cap is None:
            return "error", None
        ok, frame = self.cap.read()
        if not ok or frame is None:
            return "error", None
        return "frame", frame

    def grab(self) -> None:
        if self.cap is not None:
            self.cap.grab()

    def close(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None


def list_cameras(max_index: int = 4) -> list[int]:
    found = []
    for index in range(max_index):
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        opened = cap.isOpened()
        cap.release()
        if opened:
            found.append(index)
    return found
