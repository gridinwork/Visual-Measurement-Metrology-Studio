"""Installer checks: packages, OpenH264, cameras, and the measurement smoke test."""

from __future__ import annotations

import bz2
import sys
import threading
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.paths import DIR_BIN, ensure_dirs
from tests.smoke_test import main as smoke_main


def ensure_openh264() -> None:
    ensure_dirs()
    dest = DIR_BIN / "openh264-2.5.0-win64.dll"
    if dest.exists() and dest.stat().st_size > 100_000:
        print(f"OpenH264 already present ({dest.stat().st_size} bytes)")
        return
    url = "http://ciscobinary.openh264.org/openh264-2.5.0-win64.dll.bz2"
    print("Downloading OpenH264 encoder for H.264 demo video...")
    try:
        data = urllib.request.urlopen(url, timeout=60).read()
        dest.write_bytes(bz2.decompress(data))
        print(f"OpenH264 saved ({dest.stat().st_size} bytes)")
    except Exception as exc:
        print(f"OpenH264 download skipped: {exc}")
        print("Demo video will use the MPEG-4 MP4 codec instead.")


def probe_cameras() -> None:
    found: dict = {}

    def work() -> None:
        try:
            from capture.camera_capture import list_cameras

            found["cameras"] = list_cameras(4)
        except Exception as exc:
            found["error"] = str(exc)

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    thread.join(12)
    if thread.is_alive():
        print("Camera probe timed out. Choose a camera inside the application.")
        return
    if "error" in found:
        print("Camera probe error:", found["error"])
        return
    cameras = found.get("cameras") or []
    if cameras:
        print("Cameras:", ", ".join(f"Camera {index}" for index in cameras))
    else:
        print("Cameras: none detected. Plug in a webcam and press Find Cameras in the app.")


def check_packages() -> None:
    import cv2
    from cv2 import aruco
    from PySide6 import QtWidgets
    import numpy

    names = [name for name in dir(aruco) if name.startswith("DICT_") and isinstance(getattr(aruco, name), int)]
    print("Python", sys.version.split()[0])
    print("OpenCV", cv2.__version__)
    print("NumPy", numpy.__version__)
    print("PySide6 widgets", hasattr(QtWidgets, "QMainWindow"))
    print("ArUco dictionaries", len(names))
    if len(names) < 4:
        raise SystemExit("ArUco dictionaries are not available. opencv-contrib-python is required.")
    try:
        from importlib import metadata

        installed = {dist.metadata["Name"].lower() for dist in metadata.distributions()}
    except Exception:
        installed = set()
    if "opencv-python" in installed and "opencv-contrib-python" in installed:
        raise SystemExit(
            "Both opencv-python and opencv-contrib-python are installed. "
            "Keep only opencv-contrib-python."
        )


def main() -> None:
    ensure_dirs()
    check_packages()
    ensure_openh264()
    probe_cameras()
    smoke_main()


if __name__ == "__main__":
    main()
