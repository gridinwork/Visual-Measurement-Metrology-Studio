"""Small text labels drawn on the measurement image."""

from __future__ import annotations

import cv2
import numpy as np


def text_size(text: str, scale: float, thickness: int) -> tuple[int, int]:
    (width, height), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
    return width, height + baseline


def draw_label(
    image: np.ndarray,
    text: str,
    origin,
    fg: tuple[int, int, int],
    scale: float = 0.55,
    thickness: int = 1,
    bg: tuple[int, int, int] = (16, 18, 22),
    align: str = "left",
) -> None:
    if not text:
        return
    height, width = image.shape[:2]
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
    x = int(round(origin[0]))
    y = int(round(origin[1]))
    if align == "center":
        x -= tw // 2
    elif align == "right":
        x -= tw
    x = max(2, min(x, width - tw - 8))
    y = max(th + 6, min(y, height - baseline - 4))
    cv2.rectangle(image, (x - 3, y - th - 5), (x + tw + 5, y + baseline + 3), bg, -1)
    cv2.putText(image, text, (x, y), font, scale, fg, thickness, cv2.LINE_AA)
