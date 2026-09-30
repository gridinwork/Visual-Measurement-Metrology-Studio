"""Write the measurement table to CSV."""

from __future__ import annotations

import csv
from pathlib import Path

from app.models import HistoryRow


COLUMNS = [
    "timestamp",
    "part",
    "object_id",
    "width_mm",
    "height_mm",
    "angle_deg",
    "area_mm2",
    "result",
    "pixels_per_mm",
    "calibration_mode",
]


def export_history(path: Path, rows: list[HistoryRow]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            payload = row.to_dict()
            writer.writerow({key: payload.get(key, "") for key in COLUMNS})
    return path
