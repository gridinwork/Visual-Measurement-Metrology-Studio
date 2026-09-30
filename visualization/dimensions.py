"""Dimension lines with end ticks, placed outside the rotated rectangle."""

from __future__ import annotations

import cv2
import numpy as np

from visualization.labels import draw_label


def draw_dimension(image, pt_a, pt_b, text: str, color, center, scale: float, thickness: int) -> None:
    start = np.asarray(pt_a, dtype=np.float64)
    end = np.asarray(pt_b, dtype=np.float64)
    vector = end - start
    length = float(np.linalg.norm(vector))
    if length < 8:
        return
    tangent = vector / length
    normal = np.array([-tangent[1], tangent[0]])
    midpoint = (start + end) * 0.5
    if np.dot(normal, midpoint - np.asarray(center, dtype=np.float64)) < 0:
        normal = -normal
    offset = max(22.0, 28.0 * scale)
    outer_a = start + normal * offset
    outer_b = end + normal * offset
    _line(image, start, outer_a, color, 1)
    _line(image, end, outer_b, color, 1)
    _line(image, outer_a, outer_b, color, thickness)
    _tick(image, outer_a, tangent, color, thickness)
    _tick(image, outer_b, -tangent, color, thickness)
    label_at = (outer_a + outer_b) * 0.5 + normal * (16 * scale)
    draw_label(image, text, label_at, color, scale=scale, thickness=max(1, thickness), align="center")


def _line(image, pt_a, pt_b, color, thickness: int) -> None:
    cv2.line(
        image,
        (int(round(pt_a[0])), int(round(pt_a[1]))),
        (int(round(pt_b[0])), int(round(pt_b[1]))),
        color,
        thickness,
        cv2.LINE_AA,
    )


def _tick(image, origin, direction, color, thickness: int) -> None:
    arm = 8.0
    left = np.array([-direction[1], direction[0]])
    a = origin + direction * arm + left * 4
    b = origin + direction * arm - left * 4
    _line(image, origin, a, color, thickness)
    _line(image, origin, b, color, thickness)
