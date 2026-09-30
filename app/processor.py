"""Background capture and measurement. The interface only receives finished frames."""

from __future__ import annotations

import threading
import time
from collections import deque

from PySide6.QtCore import QThread, Signal

from app.engine import MeasurementEngine
from app.logging_setup import get_logger
from app.models import parse_resolution
from capture.source_manager import SourceManager


class ProcessingWorker(QThread):
    frame_ready = Signal(object)
    source_started = Signal(str)
    source_stopped = Signal()
    source_error = Signal(str)

    def __init__(self, store) -> None:
        super().__init__()
        self.store = store
        self.source = SourceManager()
        self.engine = MeasurementEngine()
        self._running = True
        self._lock = threading.Lock()
        self._command = "idle"
        self._pending = None
        self._sink = None
        self._cam_times: deque[float] = deque(maxlen=30)
        self._failures = 0
        self._image_revision = -1
        self._logged_failure = False
        self._last_error_at = 0.0

    def request_start(self, spec: dict) -> None:
        with self._lock:
            self._pending = spec
            self._command = "start"

    def request_pause(self, paused: bool) -> None:
        with self._lock:
            if self._command in ("run", "pause"):
                self._command = "pause" if paused else "run"

    def request_stop(self) -> None:
        with self._lock:
            if self._command != "idle":
                self._command = "stop"

    def set_sink(self, callback) -> None:
        with self._lock:
            self._sink = callback

    def stop_thread(self) -> None:
        self._running = False
        with self._lock:
            self._command = "stop"

    def run(self) -> None:
        while self._running:
            with self._lock:
                command = self._command
                pending = self._pending
                sink = self._sink
                if command == "start":
                    self._pending = None
            if command == "start" and pending is not None:
                self._open(pending)
                continue
            if command == "stop":
                self.source.close()
                self.engine.reset()
                with self._lock:
                    if self._command == "stop":
                        self._command = "idle"
                self.source_stopped.emit()
                continue
            if command in ("idle",):
                time.sleep(0.02)
                continue
            if command == "pause":
                self.source.grab()
                time.sleep(0.02)
                continue
            settings = self.store.snapshot()
            if self.source.kind == "image" and settings.revision != self._image_revision:
                self.source.rewind()
                self._image_revision = settings.revision
            started = time.perf_counter()
            status, frame = self.source.read()
            capture_ms = (time.perf_counter() - started) * 1000.0
            if status == "wait":
                time.sleep(0.005)
                continue
            if status != "frame" or frame is None:
                self._failures += 1
                if self._failures >= 25 and not self._logged_failure:
                    self._logged_failure = True
                    self.source_error.emit("The source stopped producing frames.")
                time.sleep(0.05)
                continue
            self._failures = 0
            self._logged_failure = False
            now = time.perf_counter()
            self._cam_times.append(now)
            try:
                result = self.engine.process(
                    frame,
                    settings,
                    camera_fps=_rate(self._cam_times),
                    capture_ms=capture_ms,
                )
            except Exception:
                now_error = time.perf_counter()
                if now_error - self._last_error_at > 2.0:
                    self._last_error_at = now_error
                    get_logger().exception("Frame processing failed")
                time.sleep(0.05)
                continue
            if sink is not None:
                try:
                    sink(result.display_bgr)
                except Exception:
                    get_logger().exception("Recording sink failed")
            self.frame_ready.emit(result)
        self.source.close()

    def _open(self, spec: dict) -> None:
        self.engine.reset()
        self._cam_times.clear()
        self._failures = 0
        self._logged_failure = False
        kind = spec.get("kind")
        ok = False
        label = ""
        if kind == "webcam":
            width, height = parse_resolution(spec.get("resolution", "1280x720"))
            index = int(spec.get("index", 0))
            ok = self.source.open_camera(index, width, height)
            label = f"Camera {index} {width}x{height}"
        elif kind == "video":
            ok = self.source.open_video(spec.get("path", ""))
            label = spec.get("path", "video")
        elif kind == "image":
            ok = self.source.open_image(spec.get("path", ""))
            label = spec.get("path", "image")
            self._image_revision = -1
        if not ok:
            self.source_error.emit(f"Could not open {label or kind}.")
            with self._lock:
                self._command = "idle"
            return
        with self._lock:
            if self._command == "start":
                self._command = "run"
        self.source_started.emit(label)


def _rate(times: deque[float]) -> float:
    if len(times) < 2:
        return 0.0
    span = times[-1] - times[0]
    if span <= 0:
        return 0.0
    return (len(times) - 1) / span
