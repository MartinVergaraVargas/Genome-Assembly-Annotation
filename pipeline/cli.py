#!/usr/bin/env python3
"""CLI entry point for the Trichoderma pipeline.

    python -m pipeline.cli run --config configs/example_strain.yaml
    python -m pipeline.cli run --config x.yaml --from-stage s6_funannotate_train
    python -m pipeline.cli run --config x.yaml --only s4_filter
    python -m pipeline.cli run --config x.yaml --force-from s5_funannotate_prep
    python -m pipeline.cli run --config x.yaml --validate-only
    python -m pipeline.cli run --config x.yaml --dry-run
    python -m pipeline.cli adopt --strain H5258
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from pipeline.adopt import adopt_strain
from pipeline.config import PipelineConfig, load_config
from pipeline.orchestrator import STAGE_IDS, run_pipeline


def _build_run_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser("run", help="run (or resume) the pipeline for one strain")
    p.add_argument("--config", type=Path, required=True, help="path to a strain YAML config")
    p.add_argument("--strain", help="override strain name from the config")
    p.add_argument("--from-stage", choices=STAGE_IDS, help="first stage to run")
    p.add_argument("--to-stage", choices=STAGE_IDS, help="last stage to run")
    p.add_argument("--only", choices=STAGE_IDS, help="run exactly one stage")
    p.add_argument("--force", action="store_true", help="force re-run of the selected stage(s)")
    p.add_argument(
        "--force-from",
        choices=STAGE_IDS,
        help="force re-run of this stage and every later stage in the requested range",
    )
    p.add_argument("--dry-run", action="store_true", help="print what would run without executing")
    p.add_argument("--validate-only", action="store_true", help="validate config and exit")


def _build_adopt_parser(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "adopt", help="backfill state markers for a strain already mid-pipeline under the old scripts"
    )
    p.add_argument(
        "--config",
        type=Path,
        required=True,
        help="config describing the run as it actually happened (e.g. the RNA-seq actually used for training)",
    )
    p.add_argument("--strain", help="override strain name from the config")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _build_run_parser(subparsers)
    _build_adopt_parser(subparsers)

    args = parser.parse_args(argv)

    overrides = {}
    if args.strain:
        overrides["strain"] = args.strain

    try:
        cfg: PipelineConfig = load_config(args.config, overrides=overrides)
    except (ValidationError, ValueError, FileNotFoundError) as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    if args.command == "adopt":
        adopted = adopt_strain(cfg)
        print(f"Adopted: {adopted}" if adopted else "Nothing adopted.")
        return 0

    # args.command == "run"
    if args.validate_only:
        print(f"Config OK for strain={cfg.strain}")
        print(f"  dna_reads: {cfg.dna_reads.r1}, {cfg.dna_reads.r2}")
        print(f"  rna_reads: {len(cfg.rna_reads.left)} pair(s)")
        print(f"  busco_lineage: {cfg.busco_lineage}")
        return 0

    result = run_pipeline(
        cfg,
        from_stage=args.from_stage,
        to_stage=args.to_stage,
        only=args.only,
        force=args.force,
        force_from=args.force_from,
        dry_run=args.dry_run,
    )

    if result.interrupted:
        return 130
    if result.failed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
