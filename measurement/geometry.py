"""Geometry used by the reference project, kept stable for rotated parts.

The original opencv-object-dimension-estimator script (PyImageSearch method):

- order four box corners as top-left, top-right, bottom-right, bottom-left
- take the midpoint of each side
- measure Euclidean distance between opposite midpoints

Those two distances are the side lengths of the rotated rectangle.
Width in the original script is the left-right span (dB) and height is the
top-bottom span (dA). The leftmost object supplies

    pixels_per_metric = reference_width_px / known_width

Corner order uses the angle around the center. The original sum/diff
ordering matches this for an upright rectangle and mis-labels corners once
the part is rotated, which swaps or stretches the reported size. Angular
order keeps the same midpoint math and stays consistent while the part turns.
"""

from __future__ import annotations

import math

import numpy as np


def midpoint(pt_a, pt_b) -> tuple[float, float]:
    return (
        (float(pt_a[0]) + float(pt_b[0])) * 0.5,
        (float(pt_a[1]) + float(pt_b[1])) * 0.5,
    )


def euclidean(pt_a, pt_b) -> float:
    return float(np.linalg.norm(np.asarray(pt_a, dtype=np.float64) - np.asarray(pt_b, dtype=np.float64)))


def order_points(pts) -> np.ndarray:
    """Return corners as TL, TR, BR, BL in image coordinates."""
    points = np.asarray(pts, dtype=np.float32).reshape(4, 2)
    center = points.mean(axis=0)
    angles = np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0])
    ordered = points[np.argsort(angles)]
    sums = ordered.sum(axis=1)
    ordered = np.roll(ordered, -int(np.argmin(sums)), axis=0)
    # argsort(atan2) is angular order. Rolling to the upper-left corner can
    # leave the next point as BL instead of TR. Flip so index 1 is TR.
    if ordered[1][0] + ordered[1][1] > ordered[-1][0] + ordered[-1][1]:
        ordered = np.vstack([ordered[0], ordered[3], ordered[2], ordered[1]])
    return ordered.astype(np.float32)


def normalize_angle(angle_deg: float) -> float:
    """Fold an undirected edge angle into (-90, 90]."""
    angle = float(angle_deg)
    while angle <= -90.0:
        angle += 180.0
    while angle > 90.0:
        angle -= 180.0
    return angle


def angle_difference(first_deg: float, second_deg: float) -> float:
    """Smallest difference between two undirected edge angles, in degrees."""
    delta = abs(normalize_angle(first_deg) - normalize_angle(second_deg)) % 180.0
    if delta > 90.0:
        delta = 180.0 - delta
    return delta


def edge_angle(pt_a, pt_b) -> float:
    return math.degrees(math.atan2(float(pt_b[1]) - float(pt_a[1]), float(pt_b[0]) - float(pt_a[0])))


def measure_ordered_box(ordered) -> dict:
    """Midpoint measurement from the reference project.

    dB / edge_top_px is the TL-TR side (original width for an upright object).
    dA / edge_side_px is the TL-BL side (original height for an upright object).
    """
    tl, tr, br, bl = [np.asarray(p, dtype=np.float64) for p in ordered]
    top_mid = midpoint(tl, tr)
    bottom_mid = midpoint(bl, br)
    left_mid = midpoint(tl, bl)
    right_mid = midpoint(tr, br)
    edge_side_px = euclidean(top_mid, bottom_mid)
    edge_top_px = euclidean(left_mid, right_mid)
    return {
        "ordered": np.vstack([tl, tr, br, bl]).astype(np.float32),
        "edge_top_px": edge_top_px,
        "edge_side_px": edge_side_px,
        "angle_top_deg": edge_angle(tl, tr),
        "angle_side_deg": edge_angle(tl, bl),
        "center": midpoint(tl, br),
        "top_edge": (tuple(tl), tuple(tr)),
        "side_edge": (tuple(tl), tuple(bl)),
        "midpoints": {
            "top": top_mid,
            "bottom": bottom_mid,
            "left": left_mid,
            "right": right_mid,
        },
    }


def assign_width_height(
    edge_top_px: float,
    edge_side_px: float,
    angle_top_deg: float,
    angle_side_deg: float,
    pixels_per_mm: float | None,
    previous: tuple[float, float] | None = None,
    nominal: tuple[float, float] | None = None,
) -> dict:
    """Choose which physical side is width so a rotation does not swap them.

    Preference order:
    1. previous tracked size, so a slow rotation keeps the same labels
    2. nominal width/height, when quality control is configured
    3. the longer side is width
    """
    if pixels_per_mm and pixels_per_mm > 0:
        top_mm = edge_top_px / pixels_per_mm
        side_mm = edge_side_px / pixels_per_mm
    else:
        top_mm = None
        side_mm = None

    options = (
        {
            "width_px": edge_top_px,
            "height_px": edge_side_px,
            "width_mm": top_mm,
            "height_mm": side_mm,
            "angle_deg": normalize_angle(angle_top_deg),
            "width_is_top": True,
        },
        {
            "width_px": edge_side_px,
            "height_px": edge_top_px,
            "width_mm": side_mm,
            "height_mm": top_mm,
            "angle_deg": normalize_angle(angle_side_deg),
            "width_is_top": False,
        },
    )

    if previous and previous[0] is not None and top_mm is not None:
        def _prev_cost(option: dict) -> float:
            return abs(option["width_mm"] - previous[0]) + abs(option["height_mm"] - previous[1])

        return min(options, key=_prev_cost)

    if nominal and nominal[0] > 0 and nominal[1] > 0 and top_mm is not None:
        def _nom_cost(option: dict) -> float:
            return abs(option["width_mm"] - nominal[0]) + abs(option["height_mm"] - nominal[1])

        return min(options, key=_nom_cost)

    if edge_top_px >= edge_side_px:
        return options[0]
    return options[1]


def horizontal_reference_px(measured: dict) -> float:
    """Pixel length of the reference side that lies closer to horizontal.

    For an upright reference this is dB, the same span the original script
    divides by the known width.
    """
    if abs(normalize_angle(measured["angle_top_deg"])) <= abs(normalize_angle(measured["angle_side_deg"])):
        return float(measured["edge_top_px"])
    return float(measured["edge_side_px"])


def quad_from_contour(contour) -> np.ndarray | None:
    """Four corners of a contour when it is close to a quadrilateral."""
    if contour is None or len(contour) < 4:
        return None
    perimeter = cv2_arc_length(contour)
    if perimeter <= 0:
        return None
    approx = cv2_approx(contour, 0.02 * perimeter)
    if approx is None or len(approx) != 4:
        return None
    return order_points(approx.reshape(4, 2))


def cv2_arc_length(contour) -> float:
    import cv2

    return float(cv2.arcLength(contour, True))


def cv2_approx(contour, epsilon):
    import cv2

    return cv2.approxPolyDP(contour, epsilon, True)


def corner_angles(ordered) -> list[float]:
    pts = np.asarray(ordered, dtype=np.float64).reshape(4, 2)
    angles = []
    for index in range(4):
        prev_pt = pts[(index - 1) % 4]
        current = pts[index]
        next_pt = pts[(index + 1) % 4]
        first = prev_pt - current
        second = next_pt - current
        denom = float(np.linalg.norm(first) * np.linalg.norm(second))
        if denom <= 1e-6:
            angles.append(0.0)
            continue
        cosine = float(np.clip(np.dot(first, second) / denom, -1.0, 1.0))
        angles.append(math.degrees(math.acos(cosine)))
    return angles


def side_lengths(ordered) -> list[float]:
    pts = np.asarray(ordered, dtype=np.float64).reshape(4, 2)
    return [euclidean(pts[i], pts[(i + 1) % 4]) for i in range(4)]
