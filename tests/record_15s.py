"""Record a 15 second synthetic demo and check the file duration."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cv2
import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app.paths import DIR_DEMOS
from recording.demo_recorder import DemoRecorder

OUTPUT = DIR_DEMOS / "duration_check.mp4"


def main() -> None:
    app = QApplication([])
    frame = np.full((720, 1280, 3), 32, np.uint8)
    cv2.putText(frame, "MEASUREMENT", (80, 360), cv2.FONT_HERSHEY_SIMPLEX, 2, (230, 230, 230), 3)
    recorder = DemoRecorder(OUTPUT, (1280, 720), 30, 15.0)
    state = {"info": None, "error": ""}

    def feed() -> None:
        if recorder.accepts_frames:
            painted = frame.copy()
            recorder.submit(painted)

    def saved(info) -> None:
        state["info"] = info
        app.quit()

    def failed(message: str) -> None:
        state["error"] = message
        app.quit()

    timer = QTimer()
    timer.timeout.connect(feed)
    timer.start(15)
    recorder.saved.connect(saved)
    recorder.failed.connect(failed)
    recorder.start()
    app.exec()
    timer.stop()
    if state["error"]:
        raise SystemExit(state["error"])
    info = state["info"]
    print(info)
    duration = float(info["duration_s"])
    if not info["readable"] or not (14.0 <= duration <= 16.0):
        raise SystemExit(f"Unexpected demo duration: {duration}")
    cap = cv2.VideoCapture(str(OUTPUT))
    ok, image = cap.read()
    cap.release()
    if not ok or image is None:
        raise SystemExit("Could not open the recorded MP4")
    print(f"OPENED {OUTPUT} duration={duration:.2f}s size={image.shape}")


if __name__ == "__main__":
    main()
