"""Save the raw frame, the annotated frame, and a JSON measurement record."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import cv2

from app.paths import DIR_MEASUREMENTS, ensure_dirs


def save_measurement(result, settings, part_name: str) -> dict:
    ensure_dirs()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = _safe(part_name) if part_name else "measurement"
    stem = f"{prefix}_{stamp}"
    annotated = DIR_MEASUREMENTS / f"{stem}.png"
    raw = DIR_MEASUREMENTS / f"{stem}_raw.png"
    meta = DIR_MEASUREMENTS / f"{stem}.json"
    cv2.imwrite(str(annotated), result.display_bgr)
    cv2.imwrite(str(raw), result.raw_bgr)
    payload = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "part": part_name,
        "storage_unit": "mm",
        "display_unit": settings.units,
        "image_size": [int(result.display_bgr.shape[1]), int(result.display_bgr.shape[0])],
        "calibration": result.calibration.to_dict(),
        "stability": result.stability,
        "objects": [item.to_dict() for item in result.objects],
        "files": {
            "annotated": annotated.name,
            "raw": raw.name,
        },
    }
    meta.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"annotated": annotated, "raw": raw, "json": meta, "stem": stem}


def _safe(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    return cleaned.strip("._") or "measurement"
