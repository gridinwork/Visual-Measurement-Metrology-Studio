"""Scale from a known reference object.

The reference width in pixels is the side closer to horizontal. On an upright
part that is the same left-right span (dB) used by opencv-object-dimension-estimator.
"""

from __future__ import annotations

from measurement.geometry import horizontal_reference_px


def pixels_per_mm(measured: dict, known_width_mm: float) -> float | None:
    if known_width_mm is None or known_width_mm <= 0:
        return None
    width_px = horizontal_reference_px(measured)
    if width_px <= 1:
        return None
    return float(width_px / known_width_mm)
