"""Stage 6 — Funannotate train (RNA-seq-evidence-based gene model training).

Fixes the one concrete bug that prompted this rewrite: the old
`fun_train.py` hardcoded `--left`/`--right` to a single pooled reference
RNA-seq file regardless of which strain was being trained. Here
`rna_reads.left`/`.right` are required PipelineConfig fields (see
config.py) with no fallback — every run states explicitly what RNA-seq
evidence it's training against.

Also fixes the `os.chdir()` Trinity-output-location workaround: the old
script chdir'd the whole process into the funannotate output dir because
Trinity writes `trinity_out_dir/` into CWD. That's a process-global change,
unsafe once stages run inside one long-lived orchestrator alongside a
disk-monitor thread. `subprocess.run(cmd, cwd=...)` sets the child's
working directory only.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from pipeline.envs import run_in_env
from pipeline.stages.base import Stage, Step
from pipeline.stages.s5_funannotate_prep import CleanSortMaskStep


class TrainStep(Step):
    stage_id = "s6_funannotate_train"
    step_id = "train"

    def config_subset(self) -> dict[str, Any]:
        return {
            "mask_config": CleanSortMaskStep(self.cfg, self.logger).config_subset(),
            "rna_left": [str(p) for p in self.cfg.rna_reads.left],
            "rna_right": [str(p) for p in self.cfg.rna_reads.right],
            "species": self.cfg.species,
            "strain": self.cfg.strain,
        }

    def outputs(self) -> list[Path]:
        # funannotate predict (stage 7) consumes this file as its evidence
        # input — the definitive signal `train` actually finished, not just
        # that training/ exists (it's created and populated incrementally).
        return [self.cfg.dir_funannotate / "training" / "funannotate_train.stringtie.gtf"]

    def execute(self) -> None:
        cfg = self.cfg
        d = cfg.dir_funannotate
        d.mkdir(parents=True, exist_ok=True)
        masked_fasta = d / f"{cfg.strain}_masked.fasta"

        run_in_env(
            [
                "funannotate", "train",
                "-i", str(masked_fasta),
                "-o", str(d),
                "--left", *[str(p) for p in cfg.rna_reads.left],
                "--right", *[str(p) for p in cfg.rna_reads.right],
                "--species", cfg.species,
                "--strain", cfg.strain,
                "--cpus", str(cfg.resources.threads),
                "--memory", f"{cfg.resources.memory_gb}G",
                "--no_normalize_reads",
            ],
            env_name=cfg.conda_envs.funannotate,
            log_file=cfg.log_dir / "s6_funannotate_train.log",
            cwd=d,
        )

        # Disposable immediately: trinity_out_dir can land either at cwd (d,
        # matching the cwd= above) or, defensively, at the process's actual
        # cwd if some grandchild tool ignores it — clean up both spots.
        shutil.rmtree(d / "trinity_out_dir", ignore_errors=True)
        shutil.rmtree(Path.cwd() / "trinity_out_dir", ignore_errors=True)
        for bam in (d / "training").glob("*.bam"):
            bam.unlink(missing_ok=True)
        for bai in (d / "training").glob("*.bam.bai"):
            bai.unlink(missing_ok=True)
        # Trinity's own re-trimmed copy of the RNA-seq input — by far the
        # biggest chunk of training/ (tens of GB) and fully reproducible by
        # rerunning this step against the same rna_reads config.
        shutil.rmtree(d / "training" / "trimmomatic", ignore_errors=True)


def build_stage(cfg, logger) -> Stage:
    return Stage(cfg, logger, steps=[TrainStep(cfg, logger)])
