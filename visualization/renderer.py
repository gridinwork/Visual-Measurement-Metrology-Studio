"""Draw contours, rotated boxes, dimensions and the calibration status on a frame."""

from __future__ import annotations

import cv2
import numpy as np

from app.theme import BGR
from measurement.units import format_angle, format_length
from visualization.dimensions import draw_dimension
from visualization.labels import draw_label
from visualization.overlays import calibration_hud_lines, draw_crosshair, draw_debug, draw_hud, draw_paused_banner


class Renderer:
    def render(
        self,
        frame_bgr,
        objects,
        reference,
        marker,
        calibration,
        settings,
        timings_ms: dict,
        processing_fps: float,
        stability: str,
        method_used: str,
        warnings: list[str],
        camera_fps: float,
    ):
        image = frame_bgr.copy()
        height, width = image.shape[:2]
        scale = max(0.55, min(1.35, width / 1280.0))
        thickness = max(1, int(round(width / 700)))
        selected = settings.selected_object_id

        if marker is not None and (settings.show_boxes or settings.show_calibration or settings.presentation):
            pts = np.int32(marker.corners).reshape(-1, 1, 2)
            cv2.polylines(image, [pts], True, BGR["reference"], thickness + 1, cv2.LINE_AA)
            for corner in marker.corners:
                cv2.circle(image, (int(corner[0]), int(corner[1])), 4, BGR["reference"], -1, cv2.LINE_AA)
            draw_label(
                image,
                f"REFERENCE: ARUCO {marker.size_mm:.2f} mm",
                (marker.corners[:, 0].min(), marker.corners[:, 1].min() - 8),
                BGR["reference"],
                scale=scale * 0.7,
                thickness=max(1, thickness),
            )
            draw_label(
                image,
                f"ARUCO #{marker.marker_id}",
                (marker.corners[:, 0].min(), marker.corners[:, 1].max() + 22 * scale),
                BGR["text"],
                scale=scale * 0.65,
            )

        if reference is not None:
            self._draw_object(image, reference, settings, scale, thickness, selected, reference_style=True)

        for obj in objects:
            self._draw_object(image, obj, settings, scale, thickness, selected, reference_style=False)

        if settings.roi_enabled and settings.roi and len(settings.roi) == 4:
            x, y, roi_w, roi_h = settings.roi
            p1 = (int(x * width), int(y * height))
            p2 = (int((x + roi_w) * width), int((y + roi_h) * height))
            cv2.rectangle(image, p1, p2, BGR["roi"], 1, cv2.LINE_AA)
            draw_label(image, "ROI", (p1[0] + 4, p1[1] + 16), BGR["roi"], scale=scale * 0.55)

        if len(settings.manual_points) >= 1 and settings.calibration_mode == "manual":
            for point in settings.manual_points[:2]:
                cv2.circle(image, (int(point[0]), int(point[1])), 5, BGR["manual"], -1, cv2.LINE_AA)
            if len(settings.manual_points) >= 2:
                a, b = settings.manual_points[:2]
                cv2.line(image, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), BGR["manual"], thickness, cv2.LINE_AA)

        left, warning = calibration_hud_lines(calibration, settings)
        right = []
        if settings.show_fps or settings.presentation:
            right.append(f"FPS {processing_fps:.0f}")
        if settings.show_calibration or settings.presentation:
            if stability in ("STABLE", "UNSTABLE"):
                right.append(stability)
        if settings.show_calibration or settings.show_fps or settings.presentation:
            draw_hud(image, left, right, scale, warning)

        if calibration.paused and (settings.show_calibration or settings.presentation):
            draw_paused_banner(image, ["MEASUREMENT PAUSED", calibration.message], scale)

        if settings.debug and not settings.presentation:
            lines = [
                f"frame {timings_ms.get('frame_id', 0)}  method {method_used}",
                f"cam {camera_fps:.1f} fps   proc {processing_fps:.1f} fps",
                f"capture {timings_ms.get('capture_ms', 0):.1f} ms  undistort {timings_ms.get('undistort_ms', 0):.1f} ms",
                f"threshold {timings_ms.get('threshold_ms', 0):.1f} ms  contour {timings_ms.get('contour_ms', 0):.1f} ms",
                f"measure {timings_ms.get('measure_ms', 0):.1f} ms  render {timings_ms.get('render_ms', 0):.1f} ms",
                f"contours {timings_ms.get('contour_count', 0)}  accepted {timings_ms.get('accepted', 0)}",
                f"px/mm {calibration.pixels_per_mm or 0:.3f}",
            ]
            for obj in objects[:3]:
                raw_w = "—" if obj.raw_width_mm is None else f"{obj.raw_width_mm:.2f}"
                smooth_w = "—" if obj.width_mm is None else f"{obj.width_mm:.2f}"
                lines.append(f"#{obj.id} raw {raw_w}  smooth {smooth_w}")
            if warnings:
                lines.append(" | ".join(warnings[:3]))
            draw_debug(image, lines, scale)
        return image

    def _draw_object(self, image, obj, settings, scale, thickness, selected, reference_style: bool) -> None:
        color = self._color(obj, reference_style)
        box = np.int32(np.asarray(obj.box, dtype=np.float32)).reshape(-1, 1, 2)
        if settings.show_contours and obj.contour is not None and not reference_style:
            cv2.drawContours(image, [obj.contour], -1, color, 1, cv2.LINE_AA)
        if settings.show_boxes or settings.presentation:
            cv2.polylines(image, [box], True, color, thickness + (2 if obj.id == selected else 0), cv2.LINE_AA)
            for point in np.asarray(obj.box, dtype=np.float32):
                cv2.circle(image, (int(point[0]), int(point[1])), 4, BGR["corner"], -1, cv2.LINE_AA)
        if settings.show_center:
            draw_crosshair(image, obj.center_px, BGR["center"], size=int(8 * scale))
        label_y = min(point[1] for point in obj.box) - 6
        label_x = sum(point[0] for point in obj.box) / 4
        if obj.partial:
            draw_label(image, "PARTIAL OBJECT", obj.center_px, BGR["warn"], scale=scale * 0.7, thickness=2, align="center")
            return
        if reference_style:
            draw_label(image, "REFERENCE", (obj.center_px[0], obj.center_px[1] - 16), BGR["reference"], scale=scale * 0.65, align="center")
            return
        if (settings.show_id or settings.presentation) and not reference_style:
            draw_label(image, f"OBJECT #{obj.id}", (label_x, label_y), color, scale=scale * 0.62, align="center")
        if obj.width_mm is None:
            return
        center = obj.center_px
        if (settings.show_dimensions or settings.presentation) and obj.width_edge and obj.height_edge:
            draw_dimension(
                image,
                obj.width_edge[0],
                obj.width_edge[1],
                format_length(obj.width_mm, settings.units),
                color,
                center,
                scale,
                thickness,
            )
            draw_dimension(
                image,
                obj.height_edge[0],
                obj.height_edge[1],
                format_length(obj.height_mm, settings.units),
                color,
                center,
                scale,
                thickness,
            )
        if (settings.show_angle or settings.presentation) and obj.angle_deg is not None:
            draw_label(
                image,
                "ANGLE " + format_angle(obj.angle_deg),
                (center[0], max(point[1] for point in obj.box) + 18 * scale),
                BGR["text"],
                scale=scale * 0.58,
                align="center",
            )
        if obj.result in ("PASS", "FAIL"):
            badge_color = BGR["pass"] if obj.result == "PASS" else BGR["fail"]
            draw_label(
                image,
                obj.result,
                (center[0], center[1] + 18 * scale),
                badge_color,
                scale=scale * 0.7,
                thickness=2,
                align="center",
            )

    @staticmethod
    def _color(obj, reference_style: bool):
        if reference_style:
            return BGR["reference"]
        if obj.partial:
            return BGR["warn"]
        if obj.result == "PASS":
            return BGR["pass"]
        if obj.result == "FAIL":
            return BGR["fail"]
        return BGR["object"]
