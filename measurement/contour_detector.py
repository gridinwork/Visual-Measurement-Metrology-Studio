"""Contour detection. AUTO keeps the original Canny preset when it is stable."""

from __future__ import annotations

import time
from dataclasses import dataclass

import cv2
import numpy as np

from measurement.geometry import measure_ordered_box, order_points, quad_from_contour


@dataclass
class ContourCandidate:
    contour: np.ndarray
    area: float
    perimeter: float
    center: tuple[float, float]
    rect: tuple
    box: np.ndarray
    measured: dict
    partial: bool
    quad: np.ndarray | None


class ContourDetector:
    def __init__(self) -> None:
        self._cached_method = ""
        self._ttl = 0

    def detect(self, frame_bgr: np.ndarray, settings) -> tuple[list[ContourCandidate], dict]:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        requested = settings.detection_method
        if requested != "AUTO":
            key = {"CANNY": "CANNY", "THRESHOLD": "THRESHOLD_INV", "ADAPTIVE": "ADAPTIVE"}.get(
                requested, "CANNY"
            )
            candidates, timings = self._collect(gray, settings, key)
            timings["method"] = key
            return candidates, timings

        if self._cached_method and self._ttl > 0:
            candidates, timings = self._collect(gray, settings, self._cached_method)
            self._ttl -= 1
            if candidates:
                timings["method"] = self._cached_method
                return candidates, timings
            self._ttl = 0

        best: tuple | None = None
        for key in ("CANNY", "THRESHOLD_INV", "THRESHOLD", "ADAPTIVE"):
            candidates, timings = self._collect(gray, settings, key)
            score = _score(candidates, gray.size)
            if best is None or score > best[0]:
                best = (score, key, candidates, timings)
        assert best is not None
        self._cached_method = best[1]
        self._ttl = 10
        best[3]["method"] = best[1]
        return best[2], best[3]

    def _collect(self, gray: np.ndarray, settings, method: str) -> tuple[list[ContourCandidate], dict]:
        started = time.perf_counter()
        blurred = cv2.GaussianBlur(gray, (_odd(settings.blur), _odd(settings.blur)), 0)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (_odd(settings.morph_kernel), _odd(settings.morph_kernel)))
        mask = _binary_mask(blurred, settings, method, kernel)
        threshold_ms = (time.perf_counter() - started) * 1000.0

        height, width = gray.shape[:2]
        roi = _roi_pixels(settings, width, height)
        if roi is not None:
            x, y, roi_w, roi_h = roi
            region = np.zeros_like(mask)
            region[y : y + roi_h, x : x + roi_w] = 255
            mask = cv2.bitwise_and(mask, region)

        contour_started = time.perf_counter()
        contours = _find_contours(mask)
        max_area = float(settings.max_area) if settings.max_area and settings.max_area > 0 else 0.90 * width * height
        min_area = float(settings.min_area)
        candidates: list[ContourCandidate] = []
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < min_area or area > max_area or len(contour) < 4:
                continue
            try:
                rect = cv2.minAreaRect(contour)
                box = order_points(cv2.boxPoints(rect))
            except cv2.error:
                continue
            measured = measure_ordered_box(box)
            if measured["edge_top_px"] < 2 or measured["edge_side_px"] < 2:
                continue
            center = measured["center"]
            touches_image = _touches_bounds(contour, 0, 0, width, height, 2)
            touches_roi = False
            if roi is not None:
                touches_roi = _touches_bounds(contour, roi[0], roi[1], roi[2], roi[3], 2)
            partial = bool(settings.ignore_border and (touches_image or touches_roi))
            moments = cv2.moments(contour)
            if moments["m00"] > 1:
                center = (float(moments["m10"] / moments["m00"]), float(moments["m01"] / moments["m00"]))
            candidates.append(
                ContourCandidate(
                    contour=contour,
                    area=area,
                    perimeter=float(cv2.arcLength(contour, True)),
                    center=center,
                    rect=rect,
                    box=box,
                    measured=measured,
                    partial=partial,
                    quad=quad_from_contour(contour),
                )
            )
        candidates.sort(key=lambda item: item.center[0])
        contour_ms = (time.perf_counter() - contour_started) * 1000.0
        return candidates, {
            "threshold_ms": threshold_ms,
            "contour_ms": contour_ms,
            "contour_count": len(contours),
        }


def _odd(value: int) -> int:
    value = max(1, int(value))
    if value % 2 == 0:
        return value + 1
    return value


def _binary_mask(blurred: np.ndarray, settings, method: str, kernel: np.ndarray) -> np.ndarray:
    if method == "CANNY":
        low = int(min(settings.canny_low, settings.canny_high - 1))
        high = int(max(settings.canny_high, low + 1))
        low = max(0, min(254, low))
        high = max(low + 1, min(255, high))
        mask = cv2.Canny(blurred, low, high)
        mask = cv2.dilate(mask, kernel, iterations=1)
        mask = cv2.erode(mask, kernel, iterations=1)
        return mask
    if method == "ADAPTIVE":
        mask = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 5
        )
    elif method == "THRESHOLD":
        level = int(settings.threshold) if settings.threshold and settings.threshold > 0 else 0
        if level <= 0:
            _, mask = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        else:
            _, mask = cv2.threshold(blurred, level, 255, cv2.THRESH_BINARY)
    else:
        level = int(settings.threshold) if settings.threshold and settings.threshold > 0 else 0
        if level <= 0:
            _, mask = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        else:
            _, mask = cv2.threshold(blurred, level, 255, cv2.THRESH_BINARY_INV)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    return mask


def _find_contours(mask: np.ndarray):
    found = cv2.findContours(mask.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if len(found) == 2:
        contours, _hierarchy = found
    else:
        _image, contours, _hierarchy = found
    return contours


def _roi_pixels(settings, width: int, height: int):
    if not settings.roi_enabled or not settings.roi or len(settings.roi) != 4:
        return None
    x, y, roi_w, roi_h = [float(value) for value in settings.roi]
    px = max(0, min(width - 1, int(round(x * width))))
    py = max(0, min(height - 1, int(round(y * height))))
    pw = max(1, int(round(roi_w * width)))
    ph = max(1, int(round(roi_h * height)))
    if px + pw > width:
        pw = width - px
    if py + ph > height:
        ph = height - py
    if pw < 8 or ph < 8:
        return None
    return px, py, pw, ph


def _touches_bounds(contour, x: int, y: int, width: int, height: int, margin: int) -> bool:
    points = contour.reshape(-1, 2)
    right = x + width - 1
    bottom = y + height - 1
    return bool(
        np.any(points[:, 0] <= x + margin)
        or np.any(points[:, 0] >= right - margin)
        or np.any(points[:, 1] <= y + margin)
        or np.any(points[:, 1] >= bottom - margin)
    )


def _score(candidates: list[ContourCandidate], frame_area: int) -> int:
    useful = [item for item in candidates if not item.partial]
    if not useful:
        return 0
    coverage = sum(item.area for item in useful) / float(max(frame_area, 1))
    if coverage > 0.75:
        return 1
    count = len(useful)
    if count > 25:
        return 3
    return 20 + min(count, 6) * 8
