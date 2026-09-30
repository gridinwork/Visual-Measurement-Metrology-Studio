"""Status strip, crosshair and debug timings drawn on the viewport."""

from __future__ import annotations

import cv2
import numpy as np

from measurement.units import format_length
from visualization.labels import draw_label


def draw_crosshair(image, center, color, size: int = 10) -> None:
    x, y = int(round(center[0])), int(round(center[1]))
    cv2.line(image, (x - size, y), (x + size, y), color, 1, cv2.LINE_AA)
    cv2.line(image, (x, y - size), (x, y + size), color, 1, cv2.LINE_AA)
    cv2.circle(image, (x, y), 3, color, 1, cv2.LINE_AA)


def draw_hud(image, lines_left: list[str], lines_right: list[str], scale: float, warning: bool) -> None:
    if not lines_left and not lines_right:
        return
    height, width = image.shape[:2]
    bar_h = int(max(28, 34 * scale))
    overlay = image.copy()
    color = (28, 36, 48) if not warning else (28, 42, 70)
    cv2.rectangle(overlay, (0, 0), (width, bar_h), color, -1)
    cv2.addWeighted(overlay, 0.72, image, 0.28, 0, image)
    y = int(bar_h * 0.72)
    if lines_left:
        draw_label(
            image,
            "   ".join(lines_left),
            (10, y),
            (232, 236, 242),
            scale=max(0.45, scale * 0.85),
            thickness=1,
            bg=(20, 24, 30),
        )
    if lines_right:
        draw_label(
            image,
            "  ".join(lines_right),
            (width - 12, y),
            (180, 220, 255),
            scale=max(0.45, scale * 0.85),
            thickness=1,
            align="right",
            bg=(20, 24, 30),
        )


def draw_debug(image, lines: list[str], scale: float) -> None:
    y = image.shape[0] - 12
    for text in reversed(lines):
        draw_label(image, text, (10, y), (210, 220, 230), scale=max(0.4, scale * 0.7), thickness=1, bg=(12, 14, 18))
        y -= int(22 * max(0.8, scale))


def draw_paused_banner(image, lines: list[str], scale: float) -> None:
    height, width = image.shape[:2]
    y = height // 2
    for index, text in enumerate(lines):
        draw_label(
            image,
            text,
            (width // 2, y + index * int(36 * scale)),
            (40, 180, 255),
            scale=max(0.7, scale * 1.15),
            thickness=2,
            align="center",
            bg=(16, 18, 22),
        )


def calibration_hud_lines(calibration, settings) -> tuple[list[str], bool]:
    left = []
    warning = False
    if settings.show_calibration or settings.presentation:
        if calibration.detail:
            left.append(calibration.detail)
        if calibration.marker_size_mm:
            left.append(format_length(calibration.marker_size_mm, "mm"))
        elif calibration.reference_width_mm and calibration.mode == "reference":
            left.append("REF " + format_length(calibration.reference_width_mm, "mm"))
        left.append(calibration.message)
        if calibration.pixels_per_mm:
            left.append(f"{calibration.pixels_per_mm:.2f} px/mm")
    if calibration.perspective_warning:
        left.append("PERSPECTIVE WARNING")
        warning = True
    if calibration.paused:
        left.append("MEASUREMENT PAUSED")
        warning = True
    return left, warning
