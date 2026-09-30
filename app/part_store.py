"""Named part presets stored in config/parts.json."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from app.paths import PARTS_PATH, ensure_dirs


@dataclass
class PartPreset:
    name: str
    nominal_width_mm: float
    nominal_height_mm: float
    width_upper_mm: float
    width_lower_mm: float
    height_upper_mm: float
    height_lower_mm: float

    def to_dict(self) -> dict:
        return asdict(self)


class PartStore:
    def __init__(self) -> None:
        ensure_dirs()
        self.parts: list[PartPreset] = []
        self.load()

    def load(self) -> None:
        if not PARTS_PATH.exists():
            self.parts = [
                PartPreset("Bracket_A", 82.0, 46.5, 0.5, 0.5, 0.5, 0.5),
            ]
            self.save()
            return
        try:
            data = json.loads(PARTS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = []
        self.parts = []
        for item in data:
            try:
                self.parts.append(
                    PartPreset(
                        name=str(item["name"]),
                        nominal_width_mm=float(item["nominal_width_mm"]),
                        nominal_height_mm=float(item["nominal_height_mm"]),
                        width_upper_mm=float(item.get("width_upper_mm", 0.5)),
                        width_lower_mm=float(item.get("width_lower_mm", 0.5)),
                        height_upper_mm=float(item.get("height_upper_mm", 0.5)),
                        height_lower_mm=float(item.get("height_lower_mm", 0.5)),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        if not any(part.name == "Bracket_A" for part in self.parts):
            self.parts.insert(0, PartPreset("Bracket_A", 82.0, 46.5, 0.5, 0.5, 0.5, 0.5))
            self.save()

    def save(self) -> None:
        ensure_dirs()
        payload = [part.to_dict() for part in self.parts]
        PARTS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def names(self) -> list[str]:
        return [part.name for part in self.parts]

    def get(self, name: str) -> PartPreset | None:
        for part in self.parts:
            if part.name == name:
                return part
        return None

    def upsert(self, part: PartPreset) -> None:
        for index, existing in enumerate(self.parts):
            if existing.name == part.name:
                self.parts[index] = part
                self.save()
                return
        self.parts.append(part)
        self.save()

    def delete(self, name: str) -> None:
        self.parts = [part for part in self.parts if part.name != name]
        self.save()
