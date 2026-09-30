"""File logging. Frame-by-frame messages are intentionally not written."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from app.paths import LOG_PATH, ensure_dirs


def setup_logging() -> logging.Logger:
    ensure_dirs()
    logger = logging.getLogger("vms")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = RotatingFileHandler(
        LOG_PATH, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger("vms")
