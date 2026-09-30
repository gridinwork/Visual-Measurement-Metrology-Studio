"""Two-point scale: pixel distance divided by a real distance."""

from __future__ import annotations

from measurement.geometry import euclidean


def pixels_per_mm(point_a, point_b, real_distance_mm: float) -> float | None:
    if real_distance_mm is None or real_distance_mm <= 0:
        return None
    if point_a is None or point_b is None:
        return None
    distance_px = euclidean(point_a, point_b)
    if distance_px <= 1:
        return None
    return float(distance_px / real_distance_mm)


def scale_from_settings(settings, frame_wh: tuple[int, int]) -> float | None:
    points = settings.manual_points or []
    if len(points) < 2:
        return None
    stored = settings.manual_frame_wh or []
    if len(stored) == 2 and (int(stored[0]) != int(frame_wh[0]) or int(stored[1]) != int(frame_wh[1])):
        return None
    return pixels_per_mm(points[0], points[1], settings.manual_distance_mm)
