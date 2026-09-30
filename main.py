"""Visual Measurement & Metrology Studio."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2
from PySide6.QtWidgets import QApplication

from app.logging_setup import get_logger, setup_logging
from app.main_window import MainWindow
from app.paths import ensure_dirs
from app.theme import apply_theme


def main() -> int:
    ensure_dirs()
    setup_logging()
    log = get_logger()
    log.info("Application start")
    log.info("Python %s", sys.version.split()[0])
    log.info("OpenCV %s", cv2.__version__)
    try:
        app = QApplication(sys.argv)
        app.setApplicationName("Visual Measurement & Metrology Studio")
        apply_theme(app)
        window = MainWindow()
        window.show()
        code = app.exec()
    except Exception:
        log.exception("Fatal error")
        raise
    log.info("Shutdown code %s", code)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
