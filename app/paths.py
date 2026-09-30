"""Application paths and folder setup."""

from __future__ import annotations

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]

DIR_CONFIG = APP_ROOT / "config"
DIR_CALIBRATION = APP_ROOT / "calibration"
DIR_PROFILES = DIR_CALIBRATION / "profiles"
DIR_SCREENSHOTS = APP_ROOT / "screenshots"
DIR_MEASUREMENTS = APP_ROOT / "measurements"
DIR_DEMOS = APP_ROOT / "demo_videos"
DIR_EXPORTS = APP_ROOT / "exports"
DIR_LOGS = APP_ROOT / "logs"
DIR_BIN = APP_ROOT / "bin"

SETTINGS_PATH = DIR_CONFIG / "settings.json"
PARTS_PATH = DIR_CONFIG / "parts.json"
HISTORY_PATH = DIR_CONFIG / "history.json"
LOG_PATH = DIR_LOGS / "app.log"


def ensure_dirs() -> None:
    for path in (
        DIR_CONFIG,
        DIR_CALIBRATION,
        DIR_PROFILES,
        DIR_SCREENSHOTS,
        DIR_MEASUREMENTS,
        DIR_DEMOS,
        DIR_EXPORTS,
        DIR_LOGS,
        DIR_BIN,
    ):
        path.mkdir(parents=True, exist_ok=True)
