"""Declarative post-stage cleanup: delete known-disposable intermediates.

Replaces the hand-placed `rm -f`/`rm -rf` lines scattered through the old
pipeline_maestro.sh. Each rule names the stage/step whose completion marker
must exist before its targets get deleted — cleanup must never fire before
the *consumer* stage is verified done (an ordering hazard the old master
script also got right by hand, but only because someone remembered to put
`stop_monitor` and the cleanup block after the consumer stage ran, not
because anything enforced it).
"""

from __future__ import annotations

import glob
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from pipeline import state

logger = logging.getLogger("pipeline.cleanup")


@dataclass
class CleanupRule:
    description: str
    targets: list[str]  # exact paths or glob patterns, as strings
    consumer_stage_id: str
    consumer_step_id: str


def run_cleanup_rules(rules: list[CleanupRule], state_dir: Path) -> None:
    for rule in rules:
        marker = state.read_marker(state_dir, rule.consumer_stage_id, rule.consumer_step_id)
        if marker is None:
            logger.info(
                "skipping cleanup %r — consumer %s.%s not yet completed",
                rule.description,
                rule.consumer_stage_id,
                rule.consumer_step_id,
            )
            continue
        _apply(rule)


def _apply(rule: CleanupRule) -> None:
    for pattern in rule.targets:
        for match in glob.glob(pattern):
            path = Path(match)
            try:
                if path.is_dir() and not path.is_symlink():
                    shutil.rmtree(path)
                elif path.exists() or path.is_symlink():
                    path.unlink()
                logger.info("cleanup %r removed: %s", rule.description, path)
            except OSError as exc:
                logger.warning("cleanup %r failed on %s: %s", rule.description, path, exc)
