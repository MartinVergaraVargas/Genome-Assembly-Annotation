"""Stage 2 — SPAdes de novo assembly (--careful)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from pipeline.envs import run_in_env
from pipeline.stages.base import Stage, Step
from pipeline.stages.s1_trimmomatic import TrimStep


class SpadesStep(Step):
    stage_id = "s2_spades"
    step_id = "assemble"

    def config_subset(self) -> dict[str, Any]:
        return {
            "trim_config": TrimStep(self.cfg, self.logger).config_subset(),
            "careful": True,
            "cov_cutoff": "auto",
        }

    def outputs(self) -> list[Path]:
        return [self.cfg.dir_spades / "scaffolds.fasta"]

    def execute(self) -> None:
        out_dir = self.cfg.dir_spades
        out_dir.mkdir(parents=True, exist_ok=True)
        trim_paths = TrimStep(self.cfg, self.logger)._paths()

        run_in_env(
            [
                "spades.py",
                "--careful",
                "--cov-cutoff",
                "auto",
                "-t",
                str(self.cfg.resources.threads),
                "-m",
                str(self.cfg.resources.memory_gb),
                "-1",
                str(trim_paths["r1_paired"]),
                "-2",
                str(trim_paths["r2_paired"]),
                "-s",
                str(trim_paths["r1_unpaired"]),
                "-o",
                str(out_dir),
            ],
            env_name=self.cfg.conda_envs.spades,
            log_file=self.cfg.log_dir / "s2_spades.log",
        )

        # Disposable immediately: Pilon (stage 3) only ever reads
        # scaffolds.fasta, never the k-mer graphs / correction scratch.
        for name in ("tmp", "misc", "corrected"):
            shutil.rmtree(out_dir / name, ignore_errors=True)
        for kdir in out_dir.glob("K*"):
            if kdir.is_dir():
                shutil.rmtree(kdir, ignore_errors=True)


def build_stage(cfg, logger) -> Stage:
    return Stage(cfg, logger, steps=[SpadesStep(cfg, logger)])
