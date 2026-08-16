"""Backfill state markers for a strain that already progressed under the
old pre-rewrite scripts (H5258: stages 1-6 done, masked genome + training/
already on disk).

Re-running stage 6 (funannotate train — hours of Trinity/HISAT2) under the
new tool just to obtain a marker would be wasteful and pointless when the
training/ directory it already produced is exactly what a fresh run would
produce. This inspects the known legacy directory layout and, for whichever
stages already have valid-looking output, writes the same completion
marker `pipeline run` would have written — computed against the *given*
config, so that config must describe the run as it actually happened
(the RNA-seq reads actually used for training). Pass a different config
later and the stage correctly reads as stale and re-runs.

Stages 1-4 are not adopted: their intermediates were already deleted by the
old master script's own cleanup once stage 5 consumed them, matching that
script's documented (and, on inspection, actually followed) behavior. That
doesn't matter in practice — the point of adopting a strain is always to
resume at the first *not yet done* stage, i.e. `run --from-stage
s7_predict_annotate` for a strain like H5258.
"""

from __future__ import annotations

import logging

from pipeline import state
from pipeline.config import PipelineConfig
from pipeline.logging_setup import get_logger
from pipeline.stages.s5_funannotate_prep import CleanSortMaskStep
from pipeline.stages.s6_funannotate_train import TrainStep


def adopt_config(cfg: PipelineConfig, logger: logging.Logger) -> list[str]:
    adopted: list[str] = []

    mask_step = CleanSortMaskStep(cfg, logger)
    masked_fasta = mask_step.outputs()[0]
    if masked_fasta.is_file() and masked_fasta.stat().st_size > 0:
        state.write_marker(
            cfg.state_dir,
            mask_step.stage_id,
            mask_step.step_id,
            mask_step.config_hash(),
            mask_step.outputs(),
            extra={"adopted": True},
        )
        adopted.append(f"{mask_step.stage_id}.{mask_step.step_id}")
        logger.info("adopted %s.%s (found %s)", mask_step.stage_id, mask_step.step_id, masked_fasta)
    else:
        logger.warning(
            "stage 5 output not found (%s) — not adopted, a fresh `run` will redo it", masked_fasta
        )
        return adopted

    train_step = TrainStep(cfg, logger)
    train_output = train_step.outputs()[0]
    if train_output.is_file() and train_output.stat().st_size > 0:
        state.write_marker(
            cfg.state_dir,
            train_step.stage_id,
            train_step.step_id,
            train_step.config_hash(),
            train_step.outputs(),
            extra={"adopted": True},
        )
        adopted.append(f"{train_step.stage_id}.{train_step.step_id}")
        logger.info("adopted %s.%s (found %s)", train_step.stage_id, train_step.step_id, train_output)
    else:
        logger.warning(
            "stage 6 output not found (%s) — not adopted, run will resume from stage 6", train_output
        )

    return adopted


def adopt_strain(cfg: PipelineConfig) -> list[str]:
    logger = get_logger(f"pipeline.adopt.{cfg.strain}", cfg.log_dir / "adopt.log")
    adopted = adopt_config(cfg, logger)
    if adopted:
        logger.info(
            "adopted stages: %s — resume with: pipeline run --config <same config> --from-stage s7_predict_annotate",
            adopted,
        )
    else:
        logger.info("nothing adopted for %s — a fresh `pipeline run` will start from stage 1", cfg.strain)
    return adopted
