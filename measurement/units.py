"""Convert millimetres to the unit selected in the interface."""

from __future__ import annotations

MM_PER_INCH = 25.4


def length_to_unit(value_mm: float | None, unit: str) -> float | None:
    if value_mm is None:
        return None
    if unit == "cm":
        return value_mm / 10.0
    if unit == "inch":
        return value_mm / MM_PER_INCH
    return value_mm


def length_from_unit(value: float, unit: str) -> float:
    if unit == "cm":
        return value * 10.0
    if unit == "inch":
        return value * MM_PER_INCH
    return value


def area_to_unit(value_mm2: float | None, unit: str) -> float | None:
    if value_mm2 is None:
        return None
    if unit == "cm":
        return value_mm2 / 100.0
    if unit == "inch":
        return value_mm2 / (MM_PER_INCH ** 2)
    return value_mm2


def unit_suffix(unit: str) -> str:
    return {"mm": "mm", "cm": "cm", "inch": "in"}.get(unit, "mm")


def area_suffix(unit: str) -> str:
    return {"mm": "mm²", "cm": "cm²", "inch": "in²"}.get(unit, "mm²")


def format_length(value_mm: float | None, unit: str) -> str:
    value = length_to_unit(value_mm, unit)
    if value is None:
        return "—"
    return f"{value:.2f} {unit_suffix(unit)}"


def format_area(value_mm2: float | None, unit: str) -> str:
    value = area_to_unit(value_mm2, unit)
    if value is None:
        return "—"
    if unit == "mm" and abs(value) >= 100:
        return f"{value:.0f} {area_suffix(unit)}"
    return f"{value:.2f} {area_suffix(unit)}"


def format_angle(angle_deg: float | None) -> str:
    if angle_deg is None:
        return "—"
    return f"{angle_deg:.1f}°"
