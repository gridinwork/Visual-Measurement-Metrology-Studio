"""ArUco marker scale. Marker side length in pixels / real marker size."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class MarkerHit:
    marker_id: int
    corners: np.ndarray
    side_px: float
    pixels_per_mm: float
    size_mm: float


class ArucoCalibrator:
    def __init__(self) -> None:
        self._cache_key = ""
        self._detector = None
        self._dictionary = None

    def detect(self, frame_bgr, dictionary_name: str, marker_size_mm: float) -> MarkerHit | None:
        if marker_size_mm <= 0:
            return None
        gray = frame_bgr if frame_bgr.ndim == 2 else cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        corners, ids = self._detect(gray, dictionary_name)
        if ids is None or len(ids) == 0 or corners is None:
            return None
        best = None
        for index, marker_id in enumerate(ids.reshape(-1)):
            pts = np.asarray(corners[index], dtype=np.float32).reshape(4, 2)
            sides = [float(np.linalg.norm(pts[i] - pts[(i + 1) % 4])) for i in range(4)]
            side_px = float(sum(sides) / len(sides))
            if side_px < 8:
                continue
            hit = MarkerHit(
                marker_id=int(marker_id),
                corners=pts,
                side_px=side_px,
                pixels_per_mm=side_px / float(marker_size_mm),
                size_mm=float(marker_size_mm),
            )
            if best is None or hit.side_px > best.side_px:
                best = hit
        return best

    def _detect(self, gray, dictionary_name: str):
        dictionary = dictionary_by_name(dictionary_name)
        key = dictionary_name
        if self._detector is None or self._cache_key != key:
            self._cache_key = key
            self._dictionary = dictionary
            if hasattr(cv2.aruco, "ArucoDetector"):
                self._detector = cv2.aruco.ArucoDetector(dictionary, cv2.aruco.DetectorParameters())
            else:
                self._detector = None
        if self._detector is not None:
            detected = self._detector.detectMarkers(gray)
        else:
            parameters = cv2.aruco.DetectorParameters_create()
            detected = cv2.aruco.detectMarkers(gray, self._dictionary, parameters=parameters)
        corners = detected[0] if len(detected) > 0 else ()
        ids = detected[1] if len(detected) > 1 else None
        return corners, ids


def dictionary_names() -> list[str]:
    names = []
    for name in dir(cv2.aruco):
        if not name.startswith("DICT_"):
            continue
        value = getattr(cv2.aruco, name)
        if isinstance(value, int):
            names.append(name)
    preferred = [
        "DICT_4X4_50",
        "DICT_4X4_100",
        "DICT_4X4_250",
        "DICT_4X4_1000",
        "DICT_5X5_50",
        "DICT_5X5_100",
        "DICT_5X5_250",
        "DICT_5X5_1000",
        "DICT_6X6_50",
        "DICT_6X6_100",
        "DICT_6X6_250",
        "DICT_6X6_1000",
        "DICT_7X7_50",
        "DICT_7X7_100",
        "DICT_7X7_250",
        "DICT_7X7_1000",
        "DICT_ARUCO_ORIGINAL",
    ]
    ordered = [name for name in preferred if name in names]
    ordered.extend(sorted(name for name in names if name not in ordered))
    return ordered


def dictionary_by_name(name: str):
    if not hasattr(cv2.aruco, name):
        name = "DICT_4X4_50"
    return cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, name))
