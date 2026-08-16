"""Stage 5 — Funannotate clean -> sort -> mask.

Modeled as a single Step (not three) even though it's three funannotate
subcommands: each is fast (seconds-minutes, not hours), so checkpointing at
sub-operation granularity buys nothing, and keeping clean.fasta/sorted.fasta
as separately-tracked Step outputs would recreate the same
deleted-output-breaks-upstream-resumability bug fixed in stage 4 — masking
would have to delete them to avoid duplicating that mistake at every layer.
Instead they're plain untracked byproducts, safely removed at the end.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from pipeline.envs import run_in_env
from pipeline.stages.base import Stage, Step
from pipeline.stages.s4_filter import FilterStep


class CleanSortMaskStep(Step):
    stage_id = "s5_funannotate_prep"
    step_id = "clean_sort_mask"

    def config_subset(self) -> dict[str, Any]:
        return {
            "filter_config": FilterStep(self.cfg, self.logger).config_subset(),
            "clean_minlen": 500,
            "clean_pident": 95,
            "clean_cov": 95,
        }

    def outputs(self) -> list[Path]:
        return [self.cfg.dir_funannotate / f"{self.cfg.strain}_masked.fasta"]

    def execute(self) -> None:
        cfg = self.cfg
        d = cfg.dir_funannotate
        d.mkdir(parents=True, exist_ok=True)
        log_file = cfg.log_dir / "s5_funannotate_prep.log"

        input_fasta = cfg.dir_pulido / f"{cfg.strain}_filtered_3000.fasta"
        clean_fasta = d / f"{cfg.strain}_clean.fasta"
        sorted_fasta = d / f"{cfg.strain}_sorted.fasta"
        masked_fasta = self.outputs()[0]

        run_in_env(
            [
                "funannotate", "clean",
                "-i", str(input_fasta),
                "-o", str(clean_fasta),
                "--minlen", "500",
                "--pident", "95",
                "--cov", "95",
            ],
            env_name=cfg.conda_envs.funannotate,
            log_file=log_file,
        )
        run_in_env(
            [
                "funannotate", "sort",
                "-i", str(clean_fasta),
                "-o", str(sorted_fasta),
                "-b", "scaffold",
                "--minlen", "0",
            ],
            env_name=cfg.conda_envs.funannotate,
            log_file=log_file,
        )
        run_in_env(
            [
                "funannotate", "mask",
                "-i", str(sorted_fasta),
                "-o", str(masked_fasta),
                "--cpus", str(cfg.resources.threads),
            ],
            env_name=cfg.conda_envs.funannotate,
            log_file=log_file,
        )

        clean_fasta.unlink(missing_ok=True)
        sorted_fasta.unlink(missing_ok=True)
        # RepeatMasker scratch dirs, named "<input>.<random suffix>/"
        for scratch in d.glob(f"{sorted_fasta.name}.*"):
            if scratch.is_dir():
                shutil.rmtree(scratch, ignore_errors=True)


def build_stage(cfg, logger) -> Stage:
    return Stage(cfg, logger, steps=[CleanSortMaskStep(cfg, logger)])
