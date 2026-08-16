"""Stage 7 — Funannotate predict, InterProScan, BUSCO workaround, annotate.

The trickiest stage: predict's output filename embeds the resolved
taxonomic name (unknown ahead of time, so found via glob), and the
BUSCO/funannotate `annotate` integration has a known gap that the original
pipeline works around by deliberately tolerating a first `annotate` pass's
failure, running BUSCO manually, and feeding its table back in before a
second, real `annotate` pass. That workaround is gated behind
`funannotate_busco_workaround` (default True) so it's a config flip, not a
code change, if funannotate/BUSCO integration improves upstream.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from pipeline.envs import run_in_env, run_system
from pipeline.stages.base import Stage, Step
from pipeline.stages.s6_funannotate_train import TrainStep


def _find_one(pattern_dir: Path, pattern: str, what: str) -> Path:
    """Glob for exactly one match; funannotate names some outputs using the
    resolved taxonomic name, unknown in advance. Raising on 0 or >1 matches
    is deliberate — silently guessing among candidates (the old script's
    behavior for *.proteins.fa) is exactly the kind of latent bug this
    rewrite exists to remove."""
    matches = sorted(pattern_dir.glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(
            f"expected exactly one {what} matching {pattern_dir}/{pattern}, found {len(matches)}: {matches}"
        )
    return matches[0]


class PredictStep(Step):
    stage_id = "s7_predict_annotate"
    step_id = "predict"

    def config_subset(self) -> dict[str, Any]:
        return {
            "train_config": TrainStep(self.cfg, self.logger).config_subset(),
            "busco_lineage": str(self.cfg.busco_lineage),
            "busco_seed_species": self.cfg.busco_seed_species,
        }

    def outputs(self) -> list[Path]:
        return list((self.cfg.dir_funannotate / "predict_results").glob("*.proteins.fa"))

    def execute(self) -> None:
        cfg = self.cfg
        d = cfg.dir_funannotate
        masked_fasta = d / f"{cfg.strain}_masked.fasta"

        run_in_env(
            [
                "funannotate", "predict",
                "-i", str(masked_fasta),
                "-o", str(d),
                "-s", cfg.species,
                "--strain", cfg.strain,
                "--busco_db", str(cfg.busco_lineage),
                "--busco_seed_species", cfg.busco_seed_species,
                "--organism", "fungus",
                "--cpus", str(cfg.resources.threads),
            ],
            env_name=cfg.conda_envs.funannotate,
            log_file=cfg.log_dir / "s7_predict.log",
        )
        # Explicit postcondition beyond the generic exists-check: a glob
        # that matches nothing must fail loudly here, not silently produce
        # an empty outputs() list that the generic check would vacuously pass.
        _find_one(d / "predict_results", "*.proteins.fa", "predict proteins fasta")


class InterProScanStep(Step):
    stage_id = "s7_predict_annotate"
    step_id = "interproscan"

    def config_subset(self) -> dict[str, Any]:
        return {"predict_config": PredictStep(self.cfg, self.logger).config_subset()}

    def outputs(self) -> list[Path]:
        return [self.cfg.dir_funannotate / f"interproscan_{self.cfg.strain}.xml"]

    def execute(self) -> None:
        cfg = self.cfg
        d = cfg.dir_funannotate
        xml = self.outputs()[0]

        if xml.is_file() and xml.stat().st_size > 0:
            self.logger.info("InterProScan XML already present, skipping: %s", xml)
            return

        proteins_fa = _find_one(d / "predict_results", "*.proteins.fa", "predict proteins fasta")
        tmp_dir = d / "ipr_temp"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        run_system(
            [
                str(cfg.interproscan_sh),
                "-i", str(proteins_fa),
                "-f", "XML",
                "-o", str(xml),
                "-goterms",
                "-pa",
                "-cpu", str(cfg.resources.threads),
                "-T", str(tmp_dir),
            ],
            log_file=cfg.log_dir / "s7_interproscan.log",
        )
        shutil.rmtree(tmp_dir, ignore_errors=True)


class AnnotateFirstPassStep(Step):
    """Deliberately tolerates a nonzero exit — see module docstring."""

    stage_id = "s7_predict_annotate"
    step_id = "annotate_pass1"

    def config_subset(self) -> dict[str, Any]:
        return {"interproscan_config": InterProScanStep(self.cfg, self.logger).config_subset()}

    def outputs(self) -> list[Path]:
        return [self.cfg.dir_funannotate / "annotate_misc" / "genome.proteins.fasta"]

    def execute(self) -> None:
        cfg = self.cfg
        d = cfg.dir_funannotate
        proteins_out = self.outputs()[0]

        returncode = run_in_env(
            [
                "funannotate", "annotate",
                "-i", str(d),
                "--busco_db", str(cfg.busco_lineage),
                "--cpus", str(cfg.resources.threads),
            ],
            env_name=cfg.conda_envs.funannotate,
            log_file=cfg.log_dir / "s7_annotate_pass1.log",
            check=False,
        )
        if not proteins_out.is_file() or proteins_out.stat().st_size == 0:
            raise RuntimeError(
                f"annotate pass 1 exited {returncode} AND did not produce {proteins_out} "
                "— this is a genuine failure, not the tolerated BUSCO-integration gap"
            )
        if returncode != 0:
            self.logger.warning(
                "annotate pass 1 exited %d (expected — known BUSCO integration gap) — continuing",
                returncode,
            )


class BuscoWorkaroundStep(Step):
    stage_id = "s7_predict_annotate"
    step_id = "busco_workaround"

    def config_subset(self) -> dict[str, Any]:
        return {
            "annotate_pass1_config": AnnotateFirstPassStep(self.cfg, self.logger).config_subset(),
            "busco_lineage": str(self.cfg.busco_lineage),
        }

    def outputs(self) -> list[Path]:
        return [self.cfg.dir_funannotate / "annotate_misc" / "run_busco" / "full_table_busco.tsv"]

    def execute(self) -> None:
        cfg = self.cfg
        annotate_misc = cfg.dir_funannotate / "annotate_misc"
        proteins_fasta = annotate_misc / "genome.proteins.fasta"
        busco_out_name = "run_busco_test"
        lineage_run_dir = annotate_misc / busco_out_name / f"run_{cfg.busco_lineage.name}"
        busco_table = lineage_run_dir / "full_table.tsv"
        dest_file = self.outputs()[0]

        run_in_env(
            [
                "busco",
                "-i", str(proteins_fasta),
                "-o", busco_out_name,
                "--out_path", str(annotate_misc),
                "-l", str(cfg.busco_lineage),
                "-m", "proteins",
                "-c", str(cfg.resources.threads),
                "--offline",
                "--force",
            ],
            env_name=cfg.conda_envs.busco,
            log_file=cfg.log_dir / "s7_busco_workaround.log",
        )

        if not busco_table.is_file():
            raise RuntimeError(f"expected BUSCO table not found: {busco_table}")
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(busco_table, dest_file)
        shutil.rmtree(annotate_misc / busco_out_name, ignore_errors=True)


class AnnotateFinalPassStep(Step):
    stage_id = "s7_predict_annotate"
    step_id = "annotate_pass2"

    def config_subset(self) -> dict[str, Any]:
        return {"busco_workaround_config": BuscoWorkaroundStep(self.cfg, self.logger).config_subset()}

    def outputs(self) -> list[Path]:
        return list((self.cfg.dir_funannotate / "annotate_results").glob("*.gff3"))

    def execute(self) -> None:
        cfg = self.cfg
        d = cfg.dir_funannotate
        xml = d / f"interproscan_{cfg.strain}.xml"

        run_in_env(
            [
                "funannotate", "annotate",
                "-i", str(d),
                "--busco_db", str(cfg.busco_lineage),
                "--iprscan", str(xml),
                "--cpus", str(cfg.resources.threads),
            ],
            env_name=cfg.conda_envs.funannotate,
            log_file=cfg.log_dir / "s7_annotate_pass2.log",
        )
        _find_one(d / "annotate_results", "*.gff3", "final annotation GFF3")


class AnnotateSinglePassStep(Step):
    """Used instead of the 3-step tolerated-failure/BUSCO-workaround/final
    sequence when funannotate_busco_workaround=False — i.e. once upstream
    funannotate/BUSCO integration no longer needs the manual workaround."""

    stage_id = "s7_predict_annotate"
    step_id = "annotate"

    def config_subset(self) -> dict[str, Any]:
        return {"interproscan_config": InterProScanStep(self.cfg, self.logger).config_subset()}

    def outputs(self) -> list[Path]:
        return list((self.cfg.dir_funannotate / "annotate_results").glob("*.gff3"))

    def execute(self) -> None:
        cfg = self.cfg
        d = cfg.dir_funannotate
        xml = d / f"interproscan_{cfg.strain}.xml"

        run_in_env(
            [
                "funannotate", "annotate",
                "-i", str(d),
                "--busco_db", str(cfg.busco_lineage),
                "--iprscan", str(xml),
                "--cpus", str(cfg.resources.threads),
            ],
            env_name=cfg.conda_envs.funannotate,
            log_file=cfg.log_dir / "s7_annotate.log",
        )
        _find_one(d / "annotate_results", "*.gff3", "final annotation GFF3")


def build_stage(cfg, logger) -> Stage:
    steps: list[Step] = [PredictStep(cfg, logger), InterProScanStep(cfg, logger)]
    if cfg.funannotate_busco_workaround:
        steps += [
            AnnotateFirstPassStep(cfg, logger),
            BuscoWorkaroundStep(cfg, logger),
            AnnotateFinalPassStep(cfg, logger),
        ]
    else:
        steps.append(AnnotateSinglePassStep(cfg, logger))
    return Stage(cfg, logger, steps=steps)
