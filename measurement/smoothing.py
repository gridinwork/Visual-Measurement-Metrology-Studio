"""Smooth live dimensions without hiding a real size change."""

from __future__ import annotations

from collections import deque

from measurement.geometry import normalize_angle

_ALPHA = {"OFF": 1.0, "LOW": 0.65, "MEDIUM": 0.40, "HIGH": 0.22}
_WINDOW = {"OFF": 1, "LOW": 3, "MEDIUM": 5, "HIGH": 8}


def _ema_angle(previous: float, new_value: float, alpha: float) -> float:
    delta = normalize_angle(new_value) - normalize_angle(previous)
    while delta > 90.0:
        delta -= 180.0
    while delta < -90.0:
        delta += 180.0
    return normalize_angle(previous + alpha * delta)


def _circular_median(values: list[float]) -> float:
    if not values:
        return 0.0
    base = values[-1]
    shifted = []
    for value in values:
        delta = value - base
        while delta > 90.0:
            delta -= 180.0
        while delta < -90.0:
            delta += 180.0
        shifted.append(delta)
    shifted.sort()
    mid = shifted[len(shifted) // 2]
    return normalize_angle(base + mid)


class MeasurementSmoother:
    def __init__(self) -> None:
        self._state: dict[int, dict] = {}

    def reset(self) -> None:
        self._state.clear()

    def prune(self, active_ids: set[int]) -> None:
        for object_id in list(self._state):
            if object_id not in active_ids:
                del self._state[object_id]

    def apply(
        self,
        object_id: int,
        width_mm: float | None,
        height_mm: float | None,
        angle_deg: float | None,
        level: str,
    ) -> tuple[float | None, float | None, float | None]:
        if width_mm is None or height_mm is None or angle_deg is None or level == "OFF":
            self._state.pop(object_id, None)
            return width_mm, height_mm, angle_deg

        state = self._state.get(object_id)
        if state is not None:
            span = max(state["w"], 1.0)
            if abs(width_mm - state["w"]) / span > 0.25 or abs(height_mm - state["h"]) / max(state["h"], 1.0) > 0.25:
                state = None

        window = _WINDOW.get(level, 5)
        alpha = _ALPHA.get(level, 0.4)
        if state is None:
            state = {
                "w": width_mm,
                "h": height_mm,
                "a": angle_deg,
                "hist": deque(maxlen=window),
            }
            self._state[object_id] = state

        state["hist"].append((width_mm, height_mm, angle_deg))
        sample_w, sample_h, sample_a = width_mm, height_mm, angle_deg
        if level == "HIGH" and len(state["hist"]) >= 3:
            sample_w = float(np_median([item[0] for item in state["hist"]]))
            sample_h = float(np_median([item[1] for item in state["hist"]]))
            sample_a = _circular_median([item[2] for item in state["hist"]])

        state["w"] = state["w"] + alpha * (sample_w - state["w"])
        state["h"] = state["h"] + alpha * (sample_h - state["h"])
        state["a"] = _ema_angle(state["a"], sample_a, alpha)
        return state["w"], state["h"], state["a"]


def np_median(values: list[float]) -> float:
    ordered = sorted(values)
    count = len(ordered)
    mid = count // 2
    if count % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) * 0.5
