"""Synthetic checks for measurement, ArUco, quality control, export, and video writing."""

from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cv2
import numpy as np

from app.engine import MeasurementEngine
from app.models import HistoryRow, Settings
from calibration.aruco_calibration import dictionary_names
from calibration.camera_calibration import CameraCalibrator
from calibration.perspective import quad_warning
from export.csv_exporter import export_history
from export.measurement_exporter import save_measurement
from measurement.geometry import (
    angle_difference,
    assign_width_height,
    measure_ordered_box,
    order_points,
)
from measurement.object_tracker import ObjectTracker
from measurement.quality_control import evaluate
from measurement.smoothing import MeasurementSmoother
from recording.video_encoder import open_writer, probe_video


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("FAIL: " + message)
    print("OK", message)


def _rect(image, origin, size, color=(20, 20, 20)):
    x, y = origin
    w, h = size
    cv2.rectangle(image, (x, y), (x + w, y + h), color, -1)


def test_geometry() -> None:
    for angle in range(0, 180, 10):
        rect = ((240.0, 180.0), (300.0, 80.0), float(angle))
        box = cv2.boxPoints(rect)
        measured = measure_ordered_box(order_points(box))
        assigned = assign_width_height(
            measured["edge_top_px"],
            measured["edge_side_px"],
            measured["angle_top_deg"],
            measured["angle_side_deg"],
            1.0,
        )
        lengths = sorted([assigned["width_px"], assigned["height_px"]])
        check(abs(lengths[0] - 80) < 1.5 and abs(lengths[1] - 300) < 1.5, f"rotated sides at {angle}")
        edges = []
        for index in range(4):
            start, end = box[index], box[(index + 1) % 4]
            length = math.hypot(end[0] - start[0], end[1] - start[1])
            ang = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0]))
            edges.append((length, ang))
        expected = max(edges, key=lambda item: item[0])[1]
        check(angle_difference(assigned["angle_deg"], expected) < 1.0, f"angle at {angle}")


def test_reference_scene() -> None:
    image = np.full((700, 1100, 3), 235, np.uint8)
    _rect(image, (40, 260), (200, 80))
    _rect(image, (320, 220), (160, 100))
    _rect(image, (560, 200), (400, 160))
    settings = Settings()
    settings.calibration_mode = "reference"
    settings.reference_width_mm = 50.0
    settings.detection_method = "THRESHOLD"
    settings.min_area = 500
    settings.smoothing = "OFF"
    settings.ignore_border = True
    engine = MeasurementEngine()
    result = engine.process(image, settings)
    check(result.calibration.valid, "reference calibration valid")
    check(abs(result.calibration.pixels_per_mm - 4.0) < 0.15, f"ppm {result.calibration.pixels_per_mm}")
    check(len(result.objects) == 2, f"two objects, got {len(result.objects)}")
    sizes = sorted((round(item.width_mm, 1), round(item.height_mm, 1)) for item in result.objects)
    check(abs(sizes[0][0] - 40) < 2 and abs(sizes[0][1] - 25) < 2, f"small object {sizes[0]}")
    check(abs(sizes[1][0] - 100) < 2 and abs(sizes[1][1] - 40) < 2, f"large object {sizes[1]}")
    check(result.display_bgr.shape == image.shape, "annotated frame shape")


def test_rotated_object() -> None:
    image = np.full((640, 900, 3), 235, np.uint8)
    rect = ((520.0, 320.0), (360.0, 140.0), 28.0)
    cv2.fillConvexPoly(image, np.int32(cv2.boxPoints(rect)), (20, 20, 20))
    settings = Settings()
    settings.calibration_mode = "fixed"
    settings.fixed_pixels_per_mm = 4.0
    settings.detection_method = "THRESHOLD"
    settings.min_area = 500
    settings.smoothing = "OFF"
    engine = MeasurementEngine()
    result = engine.process(image, settings)
    check(len(result.objects) == 1, "one rotated object")
    obj = result.objects[0]
    check(abs(obj.width_mm - 90.0) < 2.0, f"rotated width {obj.width_mm}")
    check(abs(obj.height_mm - 35.0) < 2.0, f"rotated height {obj.height_mm}")
    check(angle_difference(obj.angle_deg, 28.0) < 3.0, f"rotated angle {obj.angle_deg}")


def test_aruco() -> None:
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker = np.zeros((200, 200), np.uint8)
    cv2.aruco.generateImageMarker(dictionary, 0, 200, marker, 1)
    image = np.full((640, 900, 3), 255, np.uint8)
    image[70:270, 60:260] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
    _rect(image, (420, 200), (300, 120))
    settings = Settings()
    settings.calibration_mode = "aruco"
    settings.marker_size_mm = 50.0
    settings.aruco_dictionary = "DICT_4X4_50"
    settings.detection_method = "THRESHOLD"
    settings.min_area = 400
    settings.smoothing = "OFF"
    engine = MeasurementEngine()
    result = engine.process(image, settings)
    check(result.calibration.valid, "aruco calibrated")
    check(result.calibration.aruco_id == 0, "aruco id 0")
    check(result.calibration.pixels_per_mm > 2.5, "aruco scale")
    check(len(result.objects) == 1, f"object beside marker, got {len(result.objects)}")
    ppm = result.calibration.pixels_per_mm
    obj = result.objects[0]
    check(abs(obj.width_mm - 300 / ppm) < 3.0, f"aruco object width {obj.width_mm}")
    check("ARUCO" in result.marker_label, "marker label")
    names = dictionary_names()
    check("DICT_4X4_50" in names and len(names) >= 8, "dictionary list")


def test_quality_and_smoothing() -> None:
    passed = evaluate(82.1, 46.4, 82.0, 46.5, 0.5, 0.5, 0.5, 0.5)
    failed = evaluate(82.8, 46.4, 82.0, 46.5, 0.3, 0.2, 0.5, 0.5)
    check(passed.overall == "PASS", "symmetric pass")
    check(failed.overall == "FAIL" and failed.width_pass is False, "asymmetric fail")
    smoother = MeasurementSmoother()
    noisy = [100 + ((-1) ** i) * 1.5 for i in range(12)]
    output = []
    for value in noisy:
        width, _height, _angle = smoother.apply(1, value, 50, 0.0, "HIGH")
        output.append(width)
    check(np.std(output[-6:]) < np.std(noisy[-6:]), "smoothing reduces jitter")
    jumped, _height, _angle = smoother.apply(1, 180, 50, 0.0, "HIGH")
    check(abs(jumped - 180) < 5, "large real change is not hidden")


def test_tracker() -> None:
    tracker = ObjectTracker()
    first = tracker.update(
        [{"center": (100, 100), "rect": ((100, 100), (40, 20), 0)}],
        1.0,
        1.0,
    )
    second = tracker.update(
        [{"center": (104, 101), "rect": ((104, 101), (40, 20), 0)}],
        1.1,
        1.0,
    )
    check(first[0].track_id == second[0].track_id, "tracker keeps id")
    tracker.update([], 3.0, 1.0)
    third = tracker.update(
        [{"center": (104, 101), "rect": ((104, 101), (40, 20), 0)}],
        3.1,
        1.0,
    )
    check(third[0].track_id != first[0].track_id, "tracker drops expired id")


def test_pause_without_reference() -> None:
    image = np.full((400, 600, 3), 235, np.uint8)
    _rect(image, (80, 80), (200, 80))
    settings = Settings()
    settings.calibration_mode = "aruco"
    settings.marker_size_mm = 50
    settings.detection_method = "THRESHOLD"
    engine = MeasurementEngine()
    result = engine.process(image, settings)
    check(result.calibration.paused and not result.calibration.valid, "missing marker pauses measurement")
    check(all(item.width_mm is None for item in result.objects), "no millimetres without scale")


def test_export_and_video() -> None:
    image = np.full((480, 640, 3), 235, np.uint8)
    _rect(image, (40, 180), (160, 60))
    _rect(image, (260, 140), (240, 120))
    settings = Settings()
    settings.calibration_mode = "reference"
    settings.reference_width_mm = 40
    settings.detection_method = "THRESHOLD"
    settings.smoothing = "OFF"
    settings.qc_enabled = True
    settings.part_name = "Bracket_A"
    settings.nominal_width_mm = 60
    settings.nominal_height_mm = 30
    settings.width_upper_mm = 2
    settings.width_lower_mm = 2
    settings.height_upper_mm = 2
    settings.height_lower_mm = 2
    engine = MeasurementEngine()
    result = engine.process(image, settings)
    check(any(item.result in ("PASS", "FAIL") for item in result.objects), "pass/fail assigned")
    saved = save_measurement(result, settings, "Bracket_A")
    check(saved["annotated"].exists() and saved["json"].exists() and saved["raw"].exists(), "measurement files")
    row = HistoryRow(
        timestamp="17:40:12",
        part="Bracket_A",
        object_id=1,
        width_mm=60.0,
        height_mm=30.0,
        angle_deg=1.2,
        area_mm2=1800,
        result="PASS",
        pixels_per_mm=4,
        calibration_mode="reference",
    )
    with tempfile.TemporaryDirectory() as folder:
        csv_path = export_history(Path(folder) / "measurement_history_20260930.csv", [row])
        text = csv_path.read_text(encoding="utf-8")
        check("Bracket_A" in text and "width_mm" in text, "csv export")
        clip = Path(folder) / "clip.mp4"
        writer, codec = open_writer(clip, 30, (320, 240))
        frame = np.zeros((240, 320, 3), np.uint8)
        frame[:] = (30, 90, 200)
        for index in range(30):
            cv2.putText(frame, str(index), (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 2)
            writer.write(frame)
        writer.release()
        info = probe_video(clip)
        check(info["readable"] and info["frames"] >= 30 and abs(info["duration_s"] - 1.0) < 0.2, f"writer {codec} {info}")


def test_camera_math() -> None:
    calibrator = CameraCalibrator()
    matrix = np.array([[800.0, 0, 320.0], [0, 800.0, 240.0], [0, 0, 1.0]], dtype=np.float64)
    dist = np.zeros(5)
    pattern = (6, 4)
    objp = np.zeros((pattern[0] * pattern[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:pattern[0], 0:pattern[1]].T.reshape(-1, 2) * 20.0
    for yaw in (-12, -4, 6, 14):
        rvec = np.array([[math.radians(yaw)], [math.radians(yaw / 3)], [0.0]], dtype=np.float64)
        tvec = np.array([[0.0], [0.0], [600.0]], dtype=np.float64)
        image_points, _ = cv2.projectPoints(objp, rvec, tvec, matrix, dist)
        calibrator.object_points.append(objp.copy())
        calibrator.image_points.append(image_points.reshape(-1, 2).astype(np.float32))
    calibrator.image_size = (640, 480)
    rms = calibrator.calibrate()
    check(rms < 1.0, f"camera calibration rms {rms:.4f}")
    skewed = np.array([[10, 10], [200, 30], [180, 120], [20, 140]], dtype=np.float32)
    warned, _message = quad_warning(skewed, square=True)
    check(warned, "perspective warning on a skewed marker")


def test_imports() -> None:
    import PySide6
    from PySide6 import QtWidgets

    check(bool(PySide6.__version__), "PySide6 import")
    check(hasattr(QtWidgets, "QApplication"), "Qt widgets")
    import cv2

    check(hasattr(cv2, "aruco"), f"OpenCV aruco {cv2.__version__}")


def main() -> None:
    test_imports()
    test_geometry()
    test_reference_scene()
    test_rotated_object()
    test_aruco()
    test_quality_and_smoothing()
    test_tracker()
    test_pause_without_reference()
    test_export_and_video()
    test_camera_math()
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
