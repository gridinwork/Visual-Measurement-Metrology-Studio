"""Warnings when the working plane is too tilted to trust a single scale."""

from __future__ import annotations

import math

import cv2
import numpy as np

from measurement.geometry import corner_angles, side_lengths


def quad_warning(ordered, square: bool = False) -> tuple[bool, str]:
    if ordered is None:
        return False, ""
    lengths = side_lengths(ordered)
    angles = corner_angles(ordered)
    if not lengths or max(lengths) <= 1:
        return False, ""
    messages = []
    angle_error = max(abs(angle - 90.0) for angle in angles)
    if angle_error > 14.0:
        messages.append(f"corner error {angle_error:.0f}°")
    opposite_top = abs(lengths[0] - lengths[2]) / max(lengths[0], lengths[2], 1.0)
    opposite_side = abs(lengths[1] - lengths[3]) / max(lengths[1], lengths[3], 1.0)
    if opposite_top > 0.15 or opposite_side > 0.15:
        messages.append("opposite sides differ")
    if square:
        ratio = (max(lengths) - min(lengths)) / max(lengths)
        if ratio > 0.15:
            messages.append("marker is not square in the image")
    if not messages:
        return False, ""
    return True, "PERSPECTIVE WARNING: " + ", ".join(messages)


def marker_tilt_degrees(corners, marker_size_mm: float, camera_matrix, dist_coeffs) -> float | None:
    """Tilt of a marker from the camera axis when a camera matrix is available."""
    if camera_matrix is None or corners is None:
        return None
    image_points = np.asarray(corners, dtype=np.float32).reshape(4, 2)
    size = float(marker_size_mm)
    object_points = np.array(
        [[0.0, 0.0, 0.0], [size, 0.0, 0.0], [size, size, 0.0], [0.0, size, 0.0]],
        dtype=np.float32,
    )
    dist = None if dist_coeffs is None else np.asarray(dist_coeffs, dtype=np.float64)
    flag = getattr(cv2, "SOLVEPNP_IPPE_SQUARE", cv2.SOLVEPNP_ITERATIVE)
    ok, rvec, _tvec = cv2.solvePnP(
        object_points,
        image_points,
        np.asarray(camera_matrix, dtype=np.float64),
        dist,
        flags=flag,
    )
    if not ok:
        return None
    rotation, _jacobian = cv2.Rodrigues(rvec)
    normal = rotation @ np.array([0.0, 0.0, 1.0])
    cosine = abs(float(normal[2])) / (float(np.linalg.norm(normal)) + 1e-9)
    return math.degrees(math.acos(float(np.clip(cosine, 0.0, 1.0))))
