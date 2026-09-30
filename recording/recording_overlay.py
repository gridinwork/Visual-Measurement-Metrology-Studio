"""REC badge burned into the demo file, not into the desktop screenshot."""

from __future__ import annotations

import math

import cv2

from visualization.labels import draw_label


def draw_rec_badge(frame, remaining_s: float) -> None:
    seconds = max(0, int(math.ceil(remaining_s - 1e-6)))
    text = f"REC  00:{seconds:02d}"
    height = frame.shape[0]
    origin_y = height - 28
    cv2.circle(frame, (24, origin_y - 6), 8, (50, 50, 230), -1, cv2.LINE_AA)
    draw_label(frame, text, (40, origin_y), (80, 80, 255), scale=0.7, thickness=2, bg=(16, 16, 20))
