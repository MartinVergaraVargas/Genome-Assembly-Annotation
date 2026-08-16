"""Stage 4 — seqkit contig length filtering (>= contig_min_len)."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from pipeline.envs import run_in_env
from pipeline.stages.base import Stage, Step
from pipeline.stages.s3_pilon import PilonStep


class FilterStep(Step):
    stage_id = "s4_filter"
    step_id = "filter"

    def config_subset(self) -> dict[str, Any]:
        return {
            "pilon_config": PilonStep(self.cfg, self.logger).config_subset(),
            "min_len": self.cfg.contig_min_len,
        }

    def outputs(self) -> list[Path]:
        return [self.cfg.dir_pulido / f"{self.cfg.strain}_filtered_3000.fasta"]

    def execute(self) -> None:
        cfg = self.cfg
        input_fasta = cfg.dir_pulido / f"{cfg.strain}_assembly_final.fasta"
        output_fasta = self.outputs()[0]

        pipe_cmd = (
            f"seqkit sort --by-length --reverse {shlex.quote(str(input_fasta))} "
            f"| seqkit seq --min-len {cfg.contig_min_len} -o {shlex.quote(str(output_fasta))}"
        )
        run_in_env(
            ["bash", "-c", pipe_cmd],
            env_name=cfg.conda_envs.seqkit,
            log_file=cfg.log_dir / "s4_filter.log",
        )

        # NOTE: the original bash pipeline deleted input_fasta here (it's
        # stage 3's declared output). Deliberately NOT replicated: doing so
        # would delete a file this tool's own resume logic depends on to
        # verify stage 3 completed, permanently breaking is_done() for stage
        # 3 on any later invocation and risking a wasted hours-long Pilon
        # re-run. At ~35MB, keeping it costs nothing next to the real space
        # hogs (K-mer graphs, BAMs, training scratch) that stages 2/3/6 do
        # aggressively clean.


def build_stage(cfg, logger) -> Stage:
    return Stage(cfg, logger, steps=[FilterStep(cfg, logger)])
