"""In-memory history mirrored to config/history.json."""

from __future__ import annotations

import json

from app.models import HistoryRow
from app.paths import HISTORY_PATH, ensure_dirs


class HistoryStore:
    def __init__(self) -> None:
        ensure_dirs()
        self.rows: list[HistoryRow] = []
        self.load()

    def load(self) -> None:
        if not HISTORY_PATH.exists():
            self.rows = []
            return
        try:
            data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.rows = []
            return
        self.rows = []
        for item in data:
            try:
                self.rows.append(HistoryRow.from_dict(item))
            except TypeError:
                continue

    def save(self) -> None:
        ensure_dirs()
        payload = [row.to_dict() for row in self.rows]
        HISTORY_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def add(self, row: HistoryRow) -> None:
        self.rows.append(row)
        self.save()

    def extend(self, rows: list[HistoryRow]) -> None:
        if not rows:
            return
        self.rows.extend(rows)
        self.save()

    def clear(self) -> None:
        self.rows.clear()
        self.save()
