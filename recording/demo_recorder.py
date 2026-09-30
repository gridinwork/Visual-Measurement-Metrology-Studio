"""15 second demo recorder. Duration follows a monotonic clock, not frame count."""

from __future__ import annotations

import queue
import time
from pathlib import Path

import numpy as np
from PySide6.QtCore import QThread, Signal

from recording.recording_overlay import draw_rec_badge
from recording.video_encoder import fit_frame, open_writer, probe_video


class DemoRecorder(QThread):
    countdown = Signal(int)
    progress = Signal(float, float)
    saved = Signal(object)
    failed = Signal(str)
    phase_changed = Signal(str)

    def __init__(self, path: Path, size: tuple[int, int], fps: int, duration: float = 15.0) -> None:
        super().__init__()
        self.path = Path(path)
        self.size = (int(size[0]), int(size[1]))
        self.fps = int(fps)
        self.duration = float(duration)
        self._queue: queue.Queue = queue.Queue(maxsize=4)
        self._accept = False
        self._cancel = False

    @property
    def accepts_frames(self) -> bool:
        return self._accept

    def submit(self, frame) -> None:
        if not self._accept or frame is None:
            return
        if self._queue.full():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
        try:
            self._queue.put_nowait(frame.copy())
        except queue.Full:
            pass

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            self._record()
        except Exception as exc:
            self._accept = False
            self.failed.emit(str(exc))

    def _record(self) -> None:
        self.phase_changed.emit("countdown")
        start = time.perf_counter()
        for number in (3, 2, 1):
            if self._cancel:
                self.phase_changed.emit("cancelled")
                return
            self.countdown.emit(number)
            target = start + (4 - number)
            while time.perf_counter() < target:
                if self._cancel:
                    self.phase_changed.emit("cancelled")
                    return
                time.sleep(0.02)
        self.countdown.emit(0)
        self._accept = True
        self.phase_changed.emit("recording")

        writer, codec = open_writer(self.path, self.fps, self.size)
        t0 = time.perf_counter()
        interval = 1.0 / float(self.fps)
        next_slot = t0
        target_frames = int(round(self.fps * self.duration))
        written = 0
        last = None
        try:
            while written < target_frames:
                if self._cancel:
                    break
                now = time.perf_counter()
                elapsed = now - t0
                last = self._pull(last)
                if elapsed >= self.duration:
                    if last is None:
                        last = np.zeros((self.size[1], self.size[0], 3), dtype=np.uint8)
                    while written < target_frames:
                        frame = self._prepare(last, 0.0)
                        writer.write(frame)
                        written += 1
                    break
                if now < next_slot:
                    time.sleep(min(0.004, next_slot - now))
                    continue
                if last is None:
                    if elapsed > 1.0:
                        last = np.zeros((self.size[1], self.size[0], 3), dtype=np.uint8)
                    else:
                        time.sleep(0.005)
                        continue
                remaining = max(0.0, self.duration - elapsed)
                writer.write(self._prepare(last, remaining))
                written += 1
                next_slot += interval
                if next_slot < time.perf_counter() - interval:
                    next_slot = time.perf_counter()
                if written % 2 == 0:
                    self.progress.emit(remaining, written / target_frames)
        finally:
            self._accept = False
            writer.release()

        if self._cancel:
            self.phase_changed.emit("cancelled")
            return
        info = probe_video(self.path)
        info["codec"] = codec
        info["monotonic_s"] = time.perf_counter() - t0
        info["written_frames"] = written
        self.phase_changed.emit("saved")
        self.saved.emit(info)

    def _pull(self, last):
        try:
            while True:
                last = self._queue.get_nowait()
        except queue.Empty:
            return last

    def _prepare(self, frame, remaining: float):
        fitted = fit_frame(frame, self.size[0], self.size[1])
        draw_rec_badge(fitted, remaining)
        return fitted
