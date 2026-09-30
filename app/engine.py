"""Turn one camera frame into measured objects and an annotated image."""

from __future__ import annotations

import time
from collections import deque

import cv2
import numpy as np

from app.models import CalibrationInfo, FrameResult, MeasuredObject
from calibration.aruco_calibration import ArucoCalibrator
from calibration.camera_calibration import CameraCalibrator
from calibration.manual_calibration import scale_from_settings
from calibration.perspective import marker_tilt_degrees, quad_warning
from calibration.profile_manager import ProfileManager
from calibration.reference_calibration import pixels_per_mm as reference_ppm
from measurement.contour_detector import ContourDetector
from measurement.geometry import assign_width_height
from measurement.object_tracker import ObjectTracker
from measurement.quality_control import evaluate
from measurement.smoothing import MeasurementSmoother
from measurement.stability import StabilityMonitor
from visualization.renderer import Renderer


class MeasurementEngine:
    def __init__(self) -> None:
        self.detector = ContourDetector()
        self.tracker = ObjectTracker()
        self.smoother = MeasurementSmoother()
        self.stability = StabilityMonitor()
        self.aruco = ArucoCalibrator()
        self.cameras = CameraCalibrator()
        self.profiles = ProfileManager()
        self.renderer = Renderer()
        self._frame_id = 0
        self._proc_times: deque[float] = deque(maxlen=30)
        self._cam_key: tuple | None = None
        self._force_camera_load = False
        self._prev_render_ms = 0.0

    def reset(self) -> None:
        self.tracker.reset()
        self.smoother.reset()
        self.stability.reset()
        self.detector._cached_method = ""
        self.detector._ttl = 0

    def process(self, frame_bgr: np.ndarray, settings, camera_fps: float = 0.0, capture_ms: float = 0.0) -> FrameResult:
        started = time.perf_counter()
        self._frame_id += 1
        raw = frame_bgr
        warnings: list[str] = []
        timings = {"capture_ms": float(capture_ms), "frame_id": self._frame_id}

        undistort_started = time.perf_counter()
        height, width = frame_bgr.shape[:2]
        self._ensure_camera(settings, width, height)
        working = frame_bgr
        if settings.lens_correction:
            undistorted = self.cameras.undistort(frame_bgr)
            if undistorted is None:
                warnings.append("Lens calibration does not match this resolution")
            else:
                working = undistorted
                height, width = working.shape[:2]
        timings["undistort_ms"] = (time.perf_counter() - undistort_started) * 1000.0

        detect_started = time.perf_counter()
        candidates, detect_timings = self.detector.detect(working, settings)
        timings["threshold_ms"] = detect_timings.get("threshold_ms", 0.0)
        timings["contour_ms"] = detect_timings.get("contour_ms", 0.0)
        timings["detection_ms"] = (time.perf_counter() - detect_started) * 1000.0
        method_used = detect_timings.get("method", settings.detection_method)
        contour_count = int(detect_timings.get("contour_count", 0))

        marker = None
        if settings.calibration_mode == "aruco":
            marker = self.aruco.detect(working, settings.aruco_dictionary, settings.marker_size_mm)
            if marker is not None:
                candidates = [item for item in candidates if not _inside_polygon(item.center, marker.corners)]

        measure_started = time.perf_counter()
        calibration, reference, ppm = self._calibrate(working, candidates, marker, settings, warnings)
        if reference is not None:
            candidates = [item for item in candidates if item is not reference]

        objects = self._measure_objects(candidates, ppm, settings, width, height)
        timings["measure_ms"] = (time.perf_counter() - measure_started) * 1000.0
        timings["accepted"] = len(objects)
        timings["render_ms"] = self._prev_render_ms

        real_objects = [item for item in objects if item.width_mm is not None and not item.partial]
        if not real_objects:
            stability = "—"
        elif all(item.stable for item in real_objects):
            stability = "STABLE"
        else:
            stability = "UNSTABLE"

        now = time.perf_counter()
        self._proc_times.append(now)
        processing_fps = _rate(self._proc_times)

        reference_draw = None
        if reference is not None and ppm:
            reference_draw = _reference_object(reference, settings.reference_width_mm, ppm)

        render_started = time.perf_counter()
        display = self.renderer.render(
            working,
            objects,
            reference_draw,
            marker,
            calibration,
            settings,
            timings,
            processing_fps,
            stability,
            method_used,
            warnings,
            camera_fps,
        )
        self._prev_render_ms = (time.perf_counter() - render_started) * 1000.0
        timings["total_ms"] = (time.perf_counter() - started) * 1000.0

        marker_label = ""
        if marker is not None:
            marker_label = f"ARUCO #{marker.marker_id}  {marker.size_mm:.2f} mm"

        return FrameResult(
            raw_bgr=raw,
            display_bgr=display,
            objects=objects,
            calibration=calibration,
            timings_ms=timings,
            camera_fps=camera_fps,
            processing_fps=processing_fps,
            stability=stability,
            warnings=warnings,
            frame_id=self._frame_id,
            contour_count=contour_count,
            accepted_count=len(objects),
            method_used=method_used,
            reference=reference_draw,
            marker_label=marker_label,
        )

    def request_camera_reload(self) -> None:
        self._force_camera_load = True

    def _ensure_camera(self, settings, width: int, height: int) -> None:
        key = (int(settings.camera_index), int(width), int(height))
        if self._force_camera_load:
            self._cam_key = None
            self._force_camera_load = False
        if key == self._cam_key:
            return
        self._cam_key = key
        self.cameras.load_for(key[0], key[1], key[2])

    def _calibrate(self, frame, candidates, marker, settings, warnings):
        mode = settings.calibration_mode
        calibration = CalibrationInfo(mode=mode, message="REFERENCE NOT FOUND", paused=True)
        reference = None
        ppm = None
        height, width = frame.shape[:2]

        if mode == "reference":
            usable = [item for item in candidates if not item.partial]
            if usable:
                reference = usable[0]
                ppm = reference_ppm(reference.measured, settings.reference_width_mm)
                calibration.reference_width_mm = settings.reference_width_mm
                calibration.detail = "REFERENCE"
                warned, message = quad_warning(reference.quad, square=False)
                calibration.perspective_warning = warned
                calibration.perspective_message = message
        elif mode == "aruco":
            if marker is not None:
                ppm = marker.pixels_per_mm
                calibration.aruco_id = marker.marker_id
                calibration.marker_size_mm = marker.size_mm
                calibration.detail = f"ARUCO #{marker.marker_id}"
                warned, message = quad_warning(marker.corners, square=True)
                tilt = marker_tilt_degrees(
                    marker.corners,
                    marker.size_mm,
                    self.cameras.matrix,
                    self.cameras.dist,
                )
                if tilt is not None and tilt > 20.0:
                    warned = True
                    extra = f"tilt {tilt:.0f}°"
                    message = f"{message}; {extra}" if message else f"PERSPECTIVE WARNING: {extra}"
                calibration.perspective_warning = warned
                calibration.perspective_message = message
        elif mode == "manual":
            ppm = scale_from_settings(settings, (width, height))
            calibration.detail = "MANUAL"
            if len(settings.manual_points) < 2:
                calibration.message = "PICK TWO POINTS"
        elif mode == "fixed":
            ppm = settings.fixed_pixels_per_mm if settings.fixed_pixels_per_mm and settings.fixed_pixels_per_mm > 0 else None
            if ppm is None and settings.fixed_profile:
                profile = self.profiles.load(settings.fixed_profile)
                if profile and profile.get("pixels_per_mm"):
                    ppm = float(profile["pixels_per_mm"])
            calibration.detail = settings.fixed_profile or "FIXED"
            calibration.paused = ppm is None

        if ppm is not None and ppm > 0:
            calibration.valid = True
            calibration.paused = False
            calibration.pixels_per_mm = float(ppm)
            calibration.message = "CALIBRATED"
        else:
            calibration.valid = False
            calibration.paused = True
            calibration.pixels_per_mm = None
            if mode != "manual" or calibration.message == "REFERENCE NOT FOUND":
                calibration.message = "REFERENCE NOT FOUND"
            warnings.append("MEASUREMENT PAUSED")
            warnings.append(calibration.message)
            ppm = None

        if calibration.perspective_warning:
            warnings.append("PERSPECTIVE WARNING")
        return calibration, reference, ppm

    def _measure_objects(self, candidates, ppm, settings, width: int, height: int) -> list[MeasuredObject]:
        detections = []
        for candidate in candidates:
            detections.append({"center": candidate.center, "rect": candidate.rect, "candidate": candidate})
        now = time.perf_counter()
        matches = self.tracker.update(detections, now, settings.track_timeout_s)
        nominal = None
        if settings.qc_enabled and settings.nominal_width_mm > 0 and settings.nominal_height_mm > 0:
            nominal = (settings.nominal_width_mm, settings.nominal_height_mm)

        origin_x, origin_y = 0.0, 0.0
        if settings.roi_enabled and settings.roi and len(settings.roi) == 4:
            origin_x = float(settings.roi[0]) * width
            origin_y = float(settings.roi[1]) * height

        objects: list[MeasuredObject] = []
        active_ids: set[int] = set()
        for match in matches:
            candidate = detections[match.candidate_index]["candidate"]
            active_ids.add(match.track_id)
            previous = None
            if match.previous_width_mm is not None and match.previous_height_mm is not None:
                previous = (match.previous_width_mm, match.previous_height_mm)
            measured = candidate.measured
            assigned = assign_width_height(
                measured["edge_top_px"],
                measured["edge_side_px"],
                measured["angle_top_deg"],
                measured["angle_side_deg"],
                ppm,
                previous=previous,
                nominal=nominal,
            )
            raw_w = assigned["width_mm"]
            raw_h = assigned["height_mm"]
            angle = assigned["angle_deg"]
            if candidate.partial or ppm is None:
                smooth_w, smooth_h, smooth_a = None, None, angle
            else:
                smooth_w, smooth_h, smooth_a = self.smoother.apply(
                    match.track_id, raw_w, raw_h, angle, settings.smoothing
                )
            self.tracker.remember(match.track_id, smooth_w, smooth_h, smooth_a)

            width_pass = None
            height_pass = None
            stable = False
            if candidate.partial:
                result = "PARTIAL"
            elif smooth_w is None or smooth_h is None:
                result = "PAUSED"
            else:
                stable = self.stability.is_stable(
                    match.track_id,
                    settings.stability_samples,
                    settings.stability_threshold_mm,
                )
                self.stability.update(match.track_id, smooth_w, smooth_h)
                stable = self.stability.is_stable(
                    match.track_id,
                    settings.stability_samples,
                    settings.stability_threshold_mm,
                )
                if settings.qc_enabled:
                    quality = evaluate(
                        smooth_w,
                        smooth_h,
                        settings.nominal_width_mm,
                        settings.nominal_height_mm,
                        settings.width_upper_mm,
                        settings.width_lower_mm,
                        settings.height_upper_mm,
                        settings.height_lower_mm,
                    )
                    result = quality.overall
                    width_pass = quality.width_pass
                    height_pass = quality.height_pass
                else:
                    result = "—"

            area_mm2 = candidate.area / (ppm ** 2) if ppm and not candidate.partial else None
            perimeter_mm = candidate.perimeter / ppm if ppm and not candidate.partial else None
            center_mm = None
            if ppm and not candidate.partial:
                center_mm = (
                    (candidate.center[0] - origin_x) / ppm,
                    (candidate.center[1] - origin_y) / ppm,
                )
            width_edge = measured["top_edge"] if assigned["width_is_top"] else measured["side_edge"]
            height_edge = measured["side_edge"] if assigned["width_is_top"] else measured["top_edge"]
            objects.append(
                MeasuredObject(
                    id=match.track_id,
                    width_mm=None if candidate.partial else smooth_w,
                    height_mm=None if candidate.partial else smooth_h,
                    raw_width_mm=None if candidate.partial else raw_w,
                    raw_height_mm=None if candidate.partial else raw_h,
                    width_px=assigned["width_px"],
                    height_px=assigned["height_px"],
                    angle_deg=smooth_a,
                    area_px=candidate.area,
                    area_mm2=area_mm2,
                    perimeter_px=candidate.perimeter,
                    perimeter_mm=perimeter_mm,
                    center_px=candidate.center,
                    center_mm=center_mm,
                    box=np.asarray(measured["ordered"], dtype=np.float32).tolist(),
                    width_edge=[list(width_edge[0]), list(width_edge[1])],
                    height_edge=[list(height_edge[0]), list(height_edge[1])],
                    partial=candidate.partial,
                    result=result,
                    width_pass=width_pass,
                    height_pass=height_pass,
                    stable=stable,
                    contour=candidate.contour,
                )
            )

        self.smoother.prune(active_ids)
        self.stability.prune(active_ids)
        objects.sort(key=lambda item: item.id)
        return objects


def _reference_object(candidate, known_width_mm: float, ppm: float) -> MeasuredObject:
    measured = candidate.measured
    return MeasuredObject(
        id=0,
        width_mm=known_width_mm,
        height_mm=None,
        raw_width_mm=known_width_mm,
        raw_height_mm=None,
        width_px=measured["edge_top_px"],
        height_px=measured["edge_side_px"],
        angle_deg=measured["angle_top_deg"],
        area_px=candidate.area,
        area_mm2=candidate.area / (ppm ** 2),
        perimeter_px=candidate.perimeter,
        perimeter_mm=candidate.perimeter / ppm,
        center_px=candidate.center,
        center_mm=None,
        box=np.asarray(measured["ordered"], dtype=np.float32).tolist(),
        width_edge=[],
        height_edge=[],
        partial=False,
        result="REFERENCE",
        width_pass=None,
        height_pass=None,
        stable=False,
        is_reference=True,
        contour=candidate.contour,
    )


def _inside_polygon(point, corners) -> bool:
    contour = np.asarray(corners, dtype=np.float32).reshape(-1, 1, 2)
    return cv2.pointPolygonTest(contour, (float(point[0]), float(point[1])), False) >= 0


def _rate(times: deque[float]) -> float:
    if len(times) < 2:
        return 0.0
    span = times[-1] - times[0]
    if span <= 0:
        return 0.0
    return (len(times) - 1) / span
