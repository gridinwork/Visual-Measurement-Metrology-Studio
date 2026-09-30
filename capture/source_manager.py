"""One active source: webcam, video file, or still image."""

from __future__ import annotations

from capture.camera_capture import CameraCapture
from capture.image_source import ImageSource
from capture.video_capture import VideoFileCapture


class SourceManager:
    def __init__(self) -> None:
        self.kind = ""
        self._impl = None

    def open_camera(self, index: int, width: int, height: int) -> bool:
        camera = CameraCapture()
        if not camera.open(index, width, height):
            return False
        self._replace(camera, "webcam")
        return True

    def open_video(self, path: str) -> bool:
        video = VideoFileCapture()
        if not video.open(path):
            return False
        self._replace(video, "video")
        return True

    def open_image(self, path: str) -> bool:
        image = ImageSource()
        if not image.open(path):
            return False
        self._replace(image, "image")
        return True

    def read(self):
        if self._impl is None:
            return "idle", None
        return self._impl.read()

    def grab(self) -> None:
        if self._impl is not None:
            self._impl.grab()

    def rewind(self) -> None:
        if self._impl is not None and hasattr(self._impl, "rewind"):
            self._impl.rewind()

    def close(self) -> None:
        if self._impl is not None:
            self._impl.close()
        self._impl = None
        self.kind = ""

    def _replace(self, impl, kind: str) -> None:
        self.close()
        self._impl = impl
        self.kind = kind
