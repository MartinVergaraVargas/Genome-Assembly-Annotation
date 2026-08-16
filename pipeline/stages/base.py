"""Abstract Stage/Step contract shared by every pipeline stage.

A Stage is one of the 7 pipeline phases; a Step is an internally-ordered
unit inside it. Splitting this way matters for stages 3, 6, 7: they are not
one subprocess call, they are multi-operation sequences, and checkpointing
only at the stage boundary would force a full stage re-run (hours of
InterProScan, a whole Pilon polishing loop) after a crash on the last
sub-operation. Each Step gets its own resumable checkpoint instead.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pipeline import state
from pipeline.config import PipelineConfig


class Step(ABC):
    stage_id: str
    step_id: str

    def __init__(self, cfg: PipelineConfig, logger: logging.Logger):
        self.cfg = cfg
        self.logger = logger

    @abstractmethod
    def config_subset(self) -> dict[str, Any]:
        """The subset of config that affects this step's output — used for
        the invalidation hash. Keep it to inputs/tool-params; leave out
        things like thread count so bumping resources doesn't spuriously
        invalidate expensive completed work."""

    @abstractmethod
    def outputs(self) -> list[Path]:
        """Declared output path(s) this step must produce."""

    @abstractmethod
    def execute(self) -> None:
        """Do the actual work. Raise on failure; do not swallow errors here
        (tolerated-failure steps handle that explicitly in their own
        execute(), see s7's AnnotateFirstPassStep)."""

    def config_hash(self) -> str:
        return state.config_hash(self.config_subset())

    def is_done(self) -> bool:
        return state.is_step_done(
            self.cfg.state_dir, self.stage_id, self.step_id, self.config_hash(), self.outputs()
        )

    def mark_done(self, extra: dict[str, Any] | None = None) -> None:
        state.write_marker(
            self.cfg.state_dir, self.stage_id, self.step_id, self.config_hash(), self.outputs(), extra
        )

    def run(self, force: bool = False) -> None:
        label = f"{self.stage_id}.{self.step_id}"
        if not force and self.is_done():
            self.logger.info("SKIP %s (already done)", label)
            return

        if force:
            state.invalidate_step(self.cfg.state_dir, self.stage_id, self.step_id)

        self.logger.info("RUN %s", label)
        self.execute()

        missing = [str(p) for p in self.outputs() if not p.exists()]
        if missing:
            raise RuntimeError(
                f"{label} finished but did not produce expected output(s): {missing}"
            )

        self.mark_done()
        self.logger.info("DONE %s", label)


class Stage:
    stage_id: str
    name: str

    def __init__(self, cfg: PipelineConfig, logger: logging.Logger, steps: list[Step]):
        self.cfg = cfg
        self.logger = logger
        self.steps = steps

    def is_done(self) -> bool:
        return bool(self.steps) and all(step.is_done() for step in self.steps)

    def run(self, force: bool = False) -> None:
        for step in self.steps:
            step.run(force=force)
