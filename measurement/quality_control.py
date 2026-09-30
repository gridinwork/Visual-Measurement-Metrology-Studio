"""Compare a measurement with nominal size and asymmetric tolerances."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ToleranceResult:
    width_pass: bool
    height_pass: bool
    overall: str
    width_delta_mm: float
    height_delta_mm: float


def evaluate(
    width_mm: float,
    height_mm: float,
    nominal_width_mm: float,
    nominal_height_mm: float,
    width_upper_mm: float,
    width_lower_mm: float,
    height_upper_mm: float,
    height_lower_mm: float,
) -> ToleranceResult:
    width_low = nominal_width_mm - abs(width_lower_mm)
    width_high = nominal_width_mm + abs(width_upper_mm)
    height_low = nominal_height_mm - abs(height_lower_mm)
    height_high = nominal_height_mm + abs(height_upper_mm)
    width_pass = width_low <= width_mm <= width_high
    height_pass = height_low <= height_mm <= height_high
    overall = "PASS" if width_pass and height_pass else "FAIL"
    return ToleranceResult(
        width_pass=width_pass,
        height_pass=height_pass,
        overall=overall,
        width_delta_mm=width_mm - nominal_width_mm,
        height_delta_mm=height_mm - nominal_height_mm,
    )
