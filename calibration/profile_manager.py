"""Save and load fixed pixel-per-millimetre profiles."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from app.paths import DIR_PROFILES, ensure_dirs


def _safe(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    return cleaned.strip("._") or "profile"


class ProfileManager:
    def __init__(self) -> None:
        ensure_dirs()

    def list_profiles(self) -> list[str]:
        ensure_dirs()
        names = []
        for path in sorted(DIR_PROFILES.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                names.append(str(data.get("name") or path.stem))
            except (OSError, json.JSONDecodeError):
                names.append(path.stem)
        return names

    def path_for(self, name: str) -> Path:
        return DIR_PROFILES / f"{_safe(name)}.json"

    def save(
        self,
        name: str,
        pixels_per_mm: float,
        resolution: tuple[int, int],
        camera_index: int,
        method: str,
        reference_width_mm: float | None = None,
        marker_size_mm: float | None = None,
    ) -> Path:
        ensure_dirs()
        payload = {
            "name": name.strip() or "Office Camera 01",
            "pixels_per_mm": float(pixels_per_mm),
            "resolution": [int(resolution[0]), int(resolution[1])],
            "camera_index": int(camera_index),
            "method": method,
            "reference_width_mm": reference_width_mm,
            "marker_size_mm": marker_size_mm,
            "created": datetime.now().isoformat(timespec="seconds"),
        }
        path = self.path_for(payload["name"])
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def load(self, name: str) -> dict | None:
        path = self.path_for(name)
        if not path.exists():
            for candidate in DIR_PROFILES.glob("*.json"):
                try:
                    data = json.loads(candidate.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if data.get("name") == name:
                    return data
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def delete(self, name: str) -> None:
        path = self.path_for(name)
        if path.exists():
            path.unlink()
