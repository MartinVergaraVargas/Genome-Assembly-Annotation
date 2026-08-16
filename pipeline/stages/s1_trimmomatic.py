"""Stage 1 — Trimmomatic paired-end trimming of raw DNA reads."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.envs import run_in_env
from pipeline.stages.base import Stage, Step

ADAPTERS = Path(
    "/opt/miniconda3/envs/trimmomatic/share/trimmomatic-0.40-0/adapters/TruSeq3-PE.fa"
)


class TrimStep(Step):
    stage_id = "s1_trimmomatic"
    step_id = "trim"

    def config_subset(self) -> dict[str, Any]:
        return {
            "r1": str(self.cfg.dna_reads.r1),
            "r2": str(self.cfg.dna_reads.r2),
            "adapters": str(ADAPTERS),
        }

    def _paths(self) -> dict[str, Path]:
        d = self.cfg.dir_trimmomatic
        s = self.cfg.strain
        return {
            "r1_paired": d / f"{s}_1_paired.fastq.gz",
            "r1_unpaired": d / f"{s}_1_unpaired.fastq.gz",
            "r2_paired": d / f"{s}_2_paired.fastq.gz",
            "r2_unpaired": d / f"{s}_2_unpaired.fastq.gz",
            "trimlog": d / f"{s}_trimlog.txt",
            "summary": d / f"{s}_summary.txt",
        }

    def outputs(self) -> list[Path]:
        p = self._paths()
        # r2_unpaired and trimlog are disposable byproducts (see execute()),
        # not part of the durable contract this step promises downstream.
        return [p["r1_paired"], p["r1_unpaired"], p["r2_paired"]]

    def execute(self) -> None:
        d = self.cfg.dir_trimmomatic
        d.mkdir(parents=True, exist_ok=True)
        p = self._paths()

        run_in_env(
            [
                "trimmomatic",
                "PE",
                "-threads",
                str(self.cfg.resources.threads),
                "-phred33",
                "-trimlog",
                str(p["trimlog"]),
                "-summary",
                str(p["summary"]),
                str(self.cfg.dna_reads.r1),
                str(self.cfg.dna_reads.r2),
                str(p["r1_paired"]),
                str(p["r1_unpaired"]),
                str(p["r2_paired"]),
                str(p["r2_unpaired"]),
                f"ILLUMINACLIP:{ADAPTERS}:2:30:10:2:true",
                "LEADING:3",
                "TRAILING:3",
                "SLIDINGWINDOW:4:15",
                "MINLEN:36",
            ],
            env_name=self.cfg.conda_envs.trimmomatic,
            log_file=self.cfg.log_dir / "s1_trimmomatic.log",
        )

        # Disposable immediately: trimlog is a huge line-per-read log already
        # captured in full in the step log; 2_unpaired is never consumed by
        # any later stage (only -1/-2 paired and -s 1_unpaired feed SPAdes).
        p["trimlog"].unlink(missing_ok=True)
        p["r2_unpaired"].unlink(missing_ok=True)


def build_stage(cfg, logger) -> Stage:
    return Stage(cfg, logger, steps=[TrimStep(cfg, logger)])
