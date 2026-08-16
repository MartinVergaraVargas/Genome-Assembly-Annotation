"""Background disk-usage monitor for a set of directories.

Reimplementation of the original `bash -c` du-sampling subshell in
pipeline_maestro.sh, as a daemon thread instead: same max/last-size
tracking, but no shell string interpolation of directory paths (the
original built a `bash -c "..."` string from a directory list, which is a
minor injection risk if a strain name or path ever contains shell
metacharacters).
"""

from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path


def _human(num_bytes: int) -> str:
    for unit, threshold in (("GB", 1024**3), ("MB", 1024**2), ("KB", 1024)):
        if num_bytes >= threshold:
            return f"{num_bytes / threshold:.2f} {unit}"
    return f"{num_bytes} B"


def _dir_size_bytes(path: Path) -> int:
    if not path.is_dir():
        return 0
    try:
        result = subprocess.run(
            ["du", "-sb", str(path)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        return int(result.stdout.split()[0])
    except (subprocess.TimeoutExpired, ValueError, IndexError):
        return 0


@dataclass
class DiskMonitor:
    label: str
    directories: list[Path]
    interval_seconds: int = 60
    max_bytes: int = field(default=0, init=False)
    last_bytes: int = field(default=0, init=False)
    last_sample_at: str = field(default="", init=False)

    _thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _stop_event: threading.Event = field(default_factory=threading.Event, init=False, repr=False)

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name=f"diskmon-{self.label}")
        self._thread.start()

    def stop(self) -> dict:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval_seconds + 5)
        return {
            "label": self.label,
            "max_bytes": self.max_bytes,
            "max_human": _human(self.max_bytes),
            "last_bytes": self.last_bytes,
            "last_human": _human(self.last_bytes),
            "last_sample_at": self.last_sample_at,
        }

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            total = sum(_dir_size_bytes(d) for d in self.directories)
            self.last_bytes = total
            self.max_bytes = max(self.max_bytes, total)
            self.last_sample_at = time.strftime("%Y-%m-%d %H:%M:%S")
            self._stop_event.wait(self.interval_seconds)
