"""Builds the 7-stage list and runs/resumes it.

Replaces the old pipeline_maestro.sh pattern of manually commenting/
uncommenting stage blocks between runs with real stage selection
(--from-stage/--to-stage/--only) plus the Step-level resume machinery in
state.py — a stage/step is only ever skipped because it's verifiably done,
never because someone forgot to uncomment it.
"""

from __future__ import annotations

import logging
import signal
import time
import traceback
from dataclasses import dataclass

from pipeline import notify, state
from pipeline.cleanup import CleanupRule, run_cleanup_rules
from pipeline.config import PipelineConfig
from pipeline.diskmonitor import DiskMonitor
from pipeline.logging_setup import get_logger
from pipeline.stages import (
    s1_trimmomatic,
    s2_spades,
    s3_pilon,
    s4_filter,
    s5_funannotate_prep,
    s6_funannotate_train,
    s7_predict_annotate,
)
from pipeline.stages.base import Stage

STAGE_MODULES = [
    ("s1_trimmomatic", s1_trimmomatic),
    ("s2_spades", s2_spades),
    ("s3_pilon", s3_pilon),
    ("s4_filter", s4_filter),
    ("s5_funannotate_prep", s5_funannotate_prep),
    ("s6_funannotate_train", s6_funannotate_train),
    ("s7_predict_annotate", s7_predict_annotate),
]
STAGE_IDS = [sid for sid, _ in STAGE_MODULES]


class PipelineInterrupted(Exception):
    pass


class PipelineError(RuntimeError):
    pass


def _sigterm_handler(signum, frame):  # noqa: ANN001 - signal handler signature
    raise PipelineInterrupted(f"received signal {signum}")


def build_stages(cfg: PipelineConfig, logger: logging.Logger) -> dict[str, Stage]:
    return {stage_id: mod.build_stage(cfg, logger) for stage_id, mod in STAGE_MODULES}


def _final_annotate_step_id(cfg: PipelineConfig) -> str:
    return "annotate_pass2" if cfg.funannotate_busco_workaround else "annotate"


def build_cleanup_rules(cfg: PipelineConfig) -> list[CleanupRule]:
    """Cross-stage cleanup gated on a *later* stage's completion marker —
    the only case where deleting an earlier stage's file is safe, because
    by the time the whole pipeline (stage 7's final annotate step) is done,
    nothing will ever need to re-verify stage 1 in the same run again."""
    return [
        CleanupRule(
            description="stage 1 trimmed paired reads (no longer needed once annotation is done)",
            targets=[
                str(cfg.dir_trimmomatic / f"{cfg.strain}_1_paired.fastq.gz"),
                str(cfg.dir_trimmomatic / f"{cfg.strain}_2_paired.fastq.gz"),
            ],
            consumer_stage_id="s7_predict_annotate",
            consumer_step_id=_final_annotate_step_id(cfg),
        ),
    ]


def _resolve_stage_range(
    from_stage: str | None, to_stage: str | None, only: str | None
) -> list[str]:
    if only:
        if only not in STAGE_IDS:
            raise ValueError(f"unknown stage id: {only!r} (valid: {STAGE_IDS})")
        return [only]

    start = STAGE_IDS.index(from_stage) if from_stage else 0
    end = STAGE_IDS.index(to_stage) if to_stage else len(STAGE_IDS) - 1
    if from_stage and from_stage not in STAGE_IDS:
        raise ValueError(f"unknown stage id: {from_stage!r} (valid: {STAGE_IDS})")
    if to_stage and to_stage not in STAGE_IDS:
        raise ValueError(f"unknown stage id: {to_stage!r} (valid: {STAGE_IDS})")
    if start > end:
        raise ValueError(f"--from-stage {from_stage} comes after --to-stage {to_stage}")
    return STAGE_IDS[start : end + 1]


@dataclass
class RunResult:
    ran_stage_ids: list[str]
    interrupted: bool = False
    failed: bool = False


def run_pipeline(
    cfg: PipelineConfig,
    from_stage: str | None = None,
    to_stage: str | None = None,
    only: str | None = None,
    force: bool = False,
    force_from: str | None = None,
    dry_run: bool = False,
) -> RunResult:
    requested = _resolve_stage_range(from_stage, to_stage, only)

    top_logger = get_logger(f"pipeline.{cfg.strain}", cfg.log_dir / "pipeline.log")
    stages = build_stages(cfg, top_logger)

    force_from_index = STAGE_IDS.index(force_from) if force_from else None

    if dry_run:
        top_logger.info("DRY RUN for strain=%s — stages requested: %s", cfg.strain, requested)
        for stage_id in requested:
            stage = stages[stage_id]
            for step in stage.steps:
                will_force = force or (force_from_index is not None and STAGE_IDS.index(stage_id) >= force_from_index)
                status = "WOULD RUN (forced)" if will_force else ("SKIP (done)" if step.is_done() else "WOULD RUN")
                top_logger.info("  %s.%s -> %s", stage_id, step.step_id, status)
        return RunResult(ran_stage_ids=[])

    old_sigterm = signal.signal(signal.SIGTERM, _sigterm_handler)
    monitor = DiskMonitor(
        label=cfg.strain,
        directories=[cfg.dir_trimmomatic, cfg.dir_spades, cfg.dir_pulido, cfg.dir_funannotate],
        interval_seconds=60,
    )
    monitor.start()

    notify.notify(
        f"[PIPELINE START] {cfg.strain}",
        f"Pipeline started for {cfg.strain} at {time.strftime('%Y-%m-%d %H:%M:%S')}.\n"
        f"Stages requested: {requested}",
        cfg.notifications,
    )

    ran: list[str] = []
    try:
        for stage_id in requested:
            stage = stages[stage_id]
            stage_force = force or (
                force_from_index is not None and STAGE_IDS.index(stage_id) >= force_from_index
            )
            top_logger.info("=== STAGE %s ===", stage_id)
            stage.run(force=stage_force)
            ran.append(stage_id)

            run_cleanup_rules(build_cleanup_rules(cfg), cfg.state_dir)

            notify.notify(
                f"[STAGE OK] {stage_id} — {cfg.strain}",
                f"{stage_id} completed for {cfg.strain} at {time.strftime('%Y-%m-%d %H:%M:%S')}.",
                cfg.notifications,
            )

    except PipelineInterrupted:
        top_logger.warning("pipeline interrupted (signal)")
        notify.notify(
            f"[PIPELINE INTERRUPTED] {cfg.strain}",
            f"Pipeline interrupted for {cfg.strain} during/after stages: {ran}. "
            "No stage marker was written for in-flight work — rerun the same command to resume.",
            cfg.notifications,
        )
        return RunResult(ran_stage_ids=ran, interrupted=True)

    except KeyboardInterrupt:
        top_logger.warning("pipeline interrupted (KeyboardInterrupt)")
        notify.notify(
            f"[PIPELINE INTERRUPTED] {cfg.strain}",
            f"Pipeline interrupted for {cfg.strain} during/after stages: {ran}.",
            cfg.notifications,
        )
        return RunResult(ran_stage_ids=ran, interrupted=True)

    except Exception as exc:  # noqa: BLE001 - top-level run boundary
        top_logger.error("pipeline failed: %s", exc)
        notify.notify(
            f"[PIPELINE FAILED] {cfg.strain}",
            f"Pipeline failed for {cfg.strain} after stages: {ran}.\n\n{traceback.format_exc()[-4000:]}",
            cfg.notifications,
        )
        raise PipelineError(str(exc)) from exc

    else:
        notify.notify(
            f"[PIPELINE COMPLETE] {cfg.strain}",
            f"Pipeline finished for {cfg.strain} at {time.strftime('%Y-%m-%d %H:%M:%S')}.\n"
            f"Results: {cfg.dir_funannotate}/annotate_results/",
            cfg.notifications,
        )
        return RunResult(ran_stage_ids=ran)

    finally:
        report = monitor.stop()
        top_logger.info("disk monitor report: %s", report)
        signal.signal(signal.SIGTERM, old_sigterm)
