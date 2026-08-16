"""Stage 3 — Iterative Pilon polishing.

Modeled as a single Step whose execute() runs the round loop internally,
but each round's progress is checkpointed via stage-state (not just the
step-level marker) so a crash mid-loop resumes at last_completed_round+1
instead of restarting the whole polishing loop from round 1 — re-running a
finished round means re-mapping the full read set with bwa, which is not
cheap.
"""

from __future__ import annotations

import shlex
import shutil
from pathlib import Path
from typing import Any

from pipeline import state
from pipeline.envs import run_in_env
from pipeline.stages.base import Stage, Step
from pipeline.stages.s2_spades import SpadesStep


def _count_changes(changes_file: Path) -> int:
    if not changes_file.is_file():
        return 0
    with open(changes_file, "r", encoding="utf-8") as fh:
        return sum(1 for _ in fh)


def _strip_pilon_suffix(fasta: Path) -> None:
    text = fasta.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    out = []
    for line in lines:
        if line.startswith(">"):
            line = line.replace("_pilon", "")
        out.append(line)
    fasta.write_text("".join(out), encoding="utf-8")


class PilonStep(Step):
    stage_id = "s3_pilon"
    step_id = "polish"

    def config_subset(self) -> dict[str, Any]:
        return {
            "spades_config": SpadesStep(self.cfg, self.logger).config_subset(),
            "r1_paired": str(self.cfg.dir_trimmomatic / f"{self.cfg.strain}_1_paired.fastq.gz"),
            "r2_paired": str(self.cfg.dir_trimmomatic / f"{self.cfg.strain}_2_paired.fastq.gz"),
            "max_rounds": self.cfg.pilon_max_rounds,
        }

    def outputs(self) -> list[Path]:
        return [self.cfg.dir_pulido / f"{self.cfg.strain}_assembly_final.fasta"]

    def execute(self) -> None:
        cfg = self.cfg
        out_dir = cfg.dir_pulido
        out_dir.mkdir(parents=True, exist_ok=True)
        log_file = cfg.log_dir / "s3_pilon.log"

        scaffolds = cfg.dir_spades / "scaffolds.fasta"
        initial_copy = out_dir / f"{cfg.strain}_scaffolds_initial.fasta"
        r1 = cfg.dir_trimmomatic / f"{cfg.strain}_1_paired.fastq.gz"
        r2 = cfg.dir_trimmomatic / f"{cfg.strain}_2_paired.fastq.gz"

        stage_state = state.read_stage_state(cfg.state_dir, self.stage_id)
        last_round: int = stage_state.get("last_completed_round", 0)
        converged: bool = stage_state.get("converged", False)
        current_assembly = (
            Path(stage_state["current_assembly"]) if stage_state.get("current_assembly") else None
        )

        if last_round == 0:
            shutil.copy(scaffolds, initial_copy)
            current_assembly = initial_copy
        elif current_assembly is None or not current_assembly.exists():
            raise RuntimeError(
                f"{self.stage_id}: resume state points at a missing assembly "
                f"({stage_state.get('current_assembly')}); rerun with --force-from s3_pilon"
            )

        if not converged:
            for round_num in range(last_round + 1, cfg.pilon_max_rounds + 1):
                round_dir = out_dir / f"round_{round_num}"
                round_dir.mkdir(exist_ok=True)

                run_in_env(
                    ["bwa", "index", str(current_assembly)],
                    env_name=cfg.conda_envs.pilon,
                    log_file=log_file,
                )

                bam = round_dir / f"mapping_round{round_num}.bam"
                pipe_cmd = (
                    f"bwa mem -t {cfg.resources.threads} "
                    f"{shlex.quote(str(current_assembly))} {shlex.quote(str(r1))} {shlex.quote(str(r2))} "
                    f"| samtools sort -@ {cfg.resources.threads} -o {shlex.quote(str(bam))}"
                )
                run_in_env(
                    ["bash", "-c", pipe_cmd], env_name=cfg.conda_envs.pilon, log_file=log_file
                )
                run_in_env(
                    ["samtools", "index", str(bam)], env_name=cfg.conda_envs.pilon, log_file=log_file
                )

                pilon_prefix = f"{cfg.strain}_pilon_round{round_num}"
                run_in_env(
                    [
                        "pilon",
                        "--genome",
                        str(current_assembly),
                        "--frags",
                        str(bam),
                        "--output",
                        pilon_prefix,
                        "--outdir",
                        str(round_dir),
                        "--changes",
                        "--fix",
                        "all",
                        "--threads",
                        str(cfg.resources.threads),
                    ],
                    env_name=cfg.conda_envs.pilon,
                    log_file=log_file,
                )

                bam.unlink(missing_ok=True)
                Path(f"{bam}.bai").unlink(missing_ok=True)

                round_fasta = round_dir / f"{pilon_prefix}.fasta"
                _strip_pilon_suffix(round_fasta)

                changes = _count_changes(round_dir / f"{pilon_prefix}.changes")
                self.logger.info("Pilon round %d: %d changes", round_num, changes)

                current_assembly = round_fasta
                last_round = round_num
                converged = changes == 0

                state.write_stage_state(
                    cfg.state_dir,
                    self.stage_id,
                    {
                        "last_completed_round": last_round,
                        "current_assembly": str(current_assembly),
                        "converged": converged,
                    },
                )

                if converged:
                    self.logger.info("Pilon converged after round %d", round_num)
                    break

        final_assembly = out_dir / f"{cfg.strain}_assembly_final.fasta"
        shutil.copy(current_assembly, final_assembly)

        # Disposable now: the initial-copy duplicate (scaffolds.fasta already
        # lives in 02.SPAdes_Assembly/), its bwa index, and every round dir
        # except the last (its fasta was already folded into final_assembly).
        initial_copy.unlink(missing_ok=True)
        for idx_file in out_dir.glob(f"{initial_copy.name}.*"):
            idx_file.unlink(missing_ok=True)
        for round_dir in out_dir.glob("round_*"):
            if round_dir.name != f"round_{last_round}":
                shutil.rmtree(round_dir, ignore_errors=True)


def build_stage(cfg, logger) -> Stage:
    return Stage(cfg, logger, steps=[PilonStep(cfg, logger)])
