"""Decide whether the recent samples of an object are steady enough to record."""

from __future__ import annotations

from collections import defaultdict, deque


class StabilityMonitor:
    def __init__(self) -> None:
        self._history: dict[int, deque] = defaultdict(lambda: deque(maxlen=12))

    def reset(self) -> None:
        self._history.clear()

    def prune(self, active_ids: set[int]) -> None:
        for object_id in list(self._history):
            if object_id not in active_ids:
                del self._history[object_id]

    def update(self, object_id: int, width_mm: float, height_mm: float) -> None:
        self._history[object_id].append((width_mm, height_mm))

    def is_stable(self, object_id: int, samples: int, threshold_mm: float) -> bool:
        history = self._history.get(object_id)
        if history is None or len(history) < max(2, samples):
            return False
        recent = list(history)[-samples:]
        widths = [item[0] for item in recent]
        heights = [item[1] for item in recent]
        return (max(widths) - min(widths) <= threshold_mm) and (
            max(heights) - min(heights) <= threshold_mm
        )
