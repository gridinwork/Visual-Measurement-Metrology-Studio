"""Load and save the application settings."""

from __future__ import annotations

import copy
import json
import threading

from app.models import Settings
from app.paths import SETTINGS_PATH, ensure_dirs


class SettingsStore:
    def __init__(self) -> None:
        ensure_dirs()
        self._lock = threading.Lock()
        self.settings = self._load()
        self._revision = 0

    def _load(self) -> Settings:
        if not SETTINGS_PATH.exists():
            return Settings()
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            return Settings.from_dict(data)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return Settings()

    def snapshot(self) -> Settings:
        with self._lock:
            cloned = copy.deepcopy(self.settings)
            cloned.revision = self._revision
            return cloned

    def update(self, **changes) -> Settings:
        with self._lock:
            for key, value in changes.items():
                if hasattr(self.settings, key):
                    setattr(self.settings, key, value)
            self.settings.sanitize()
            self._revision += 1
            cloned = copy.deepcopy(self.settings)
        self.save()
        return cloned

    def replace(self, settings: Settings) -> None:
        with self._lock:
            settings.sanitize()
            self.settings = settings
            self._revision += 1
        self.save()

    def save(self) -> None:
        with self._lock:
            data = self.settings.to_dict()
        ensure_dirs()
        SETTINGS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @property
    def revision(self) -> int:
        with self._lock:
            return self._revision
