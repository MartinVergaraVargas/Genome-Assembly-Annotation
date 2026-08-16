"""Per-stage file+console logger factory."""

from __future__ import annotations

import logging
from pathlib import Path

_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str, log_file: Path) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        # Already configured (e.g. re-fetched by the same name mid-run).
        return logger

    log_file.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(_FORMAT, datefmt=_DATEFMT)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger
