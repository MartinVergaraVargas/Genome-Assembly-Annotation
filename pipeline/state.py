"""Per-Step completion markers: atomic JSON writes + config-hash invalidation.

A Step is "done" only if all three hold: a marker file exists, the marker's
recorded config-hash matches the current run's relevant config, and every
output path the marker recorded still exists and is non-empty. Any one of
those failing (manual deletion, a config edit, a killed process that never
reached the write) means "not done" — there is no way to end up trusting a
half-finished result.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def config_hash(relevant: dict[str, Any]) -> str:
    """Stable hash of the config fields that affect a given step's output.

    Only pass the subset of config that actually matters for that step
    (e.g. input paths + tool params, not thread count) so bumping unrelated
    resource settings doesn't spuriously invalidate expensive completed work.
    """
    canonical = json.dumps(relevant, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


@dataclass
class StepMarker:
    stage_id: str
    step_id: str
    completed_at: str
    config_hash: str
    outputs: list[str]

    def to_json(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "step_id": self.step_id,
            "completed_at": self.completed_at,
            "config_hash": self.config_hash,
            "outputs": self.outputs,
        }


def _marker_path(state_dir: Path, stage_id: str, step_id: str) -> Path:
    return state_dir / f"{stage_id}.{step_id}.json"


def write_marker(
    state_dir: Path,
    stage_id: str,
    step_id: str,
    cfg_hash: str,
    outputs: list[Path],
    extra: dict[str, Any] | None = None,
) -> None:
    """Atomically write a completion marker (temp file + os.replace)."""
    state_dir.mkdir(parents=True, exist_ok=True)
    marker = StepMarker(
        stage_id=stage_id,
        step_id=step_id,
        completed_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        config_hash=cfg_hash,
        outputs=[str(p) for p in outputs],
    )
    payload = marker.to_json()
    if extra:
        payload.update(extra)

    target = _marker_path(state_dir, stage_id, step_id)
    fd, tmp_path = tempfile.mkstemp(dir=state_dir, prefix=f".{stage_id}.{step_id}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        os.replace(tmp_path, target)
    except BaseException:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def read_marker(state_dir: Path, stage_id: str, step_id: str) -> dict[str, Any] | None:
    path = _marker_path(state_dir, stage_id, step_id)
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        # A corrupt/truncated marker (e.g. process killed mid torn-write on a
        # filesystem without atomic rename) must read as "not done", not crash.
        return None


def is_step_done(
    state_dir: Path,
    stage_id: str,
    step_id: str,
    cfg_hash: str,
    outputs: list[Path],
) -> bool:
    marker = read_marker(state_dir, stage_id, step_id)
    if marker is None:
        return False
    if marker.get("config_hash") != cfg_hash:
        return False
    for out in outputs:
        if not out.exists():
            return False
        if out.is_file() and out.stat().st_size == 0:
            return False
    return True


def invalidate_step(state_dir: Path, stage_id: str, step_id: str) -> None:
    path = _marker_path(state_dir, stage_id, step_id)
    path.unlink(missing_ok=True)


def invalidate_many(state_dir: Path, steps: list[tuple[str, str]]) -> None:
    for stage_id, step_id in steps:
        invalidate_step(state_dir, stage_id, step_id)


def read_stage_state(state_dir: Path, stage_id: str) -> dict[str, Any]:
    """Free-form per-stage scratch state (e.g. Pilon's last_completed_round,
    Stage 7's resolved proteins.fa path) — separate from step completion
    markers so it can be updated mid-stage without implying "done"."""
    path = state_dir / f"{stage_id}.state.json"
    if not path.is_file():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def write_stage_state(state_dir: Path, stage_id: str, data: dict[str, Any]) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / f"{stage_id}.state.json"
    fd, tmp_path = tempfile.mkstemp(dir=state_dir, prefix=f".{stage_id}.state.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp_path, path)
    except BaseException:
        Path(tmp_path).unlink(missing_ok=True)
        raise
