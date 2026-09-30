"""A still image as a measurement source."""

from __future__ import annotations

import cv2


class ImageSource:
    def __init__(self) -> None:
        self.image = None
        self._pending = False

    def open(self, path: str) -> bool:
        image = cv2.imread(path, cv2.IMREAD_COLOR)
        if image is None:
            return False
        self.image = image
        self._pending = True
        return True

    def read(self):
        if self.image is None:
            return "error", None
        if not self._pending:
            return "wait", None
        self._pending = False
        return "frame", self.image.copy()

    def rewind(self) -> None:
        if self.image is not None:
            self._pending = True

    def grab(self) -> None:
        return

    def close(self) -> None:
        self.image = None
        self._pending = False
