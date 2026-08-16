# Genome Assembly & Annotation Pipeline

*[Leer en español](README.es.md)*

A fungal genome assembly and functional annotation pipeline built for a Master's thesis (TFM) on *Trichoderma* spp. Takes paired-end Illumina DNA reads through trimming, de novo assembly, polishing, and RNA-seq-evidence-based gene annotation, producing a final GFF3 with functional annotations (Pfam, InterPro, CAZymes, MEROPS, GO terms, etc.).

**Status: v0.1.0 — functional, not polished.** This ran the actual strains (T16, T22, T36, H5258) used in the thesis. It's a personal research tool that's been cleaned up for publication, not a general-purpose production package — see [Known limitations](#known-limitations) below.

## What it does

Seven stages, each resumable independently:

| Stage | Tool(s) | Output |
|---|---|---|
| 1. Trim | Trimmomatic (PE) | Adapter/quality-trimmed reads |
| 2. Assemble | SPAdes (`--careful`) | Draft scaffolds |
| 3. Polish | Pilon (iterative, bwa-mapped) | Polished assembly |
| 4. Filter | seqkit | Contigs ≥ min length |
| 5. Prep | funannotate clean/sort/mask | Soft-masked genome |
| 6. Train | funannotate train (Trinity/PASA) | RNA-seq-based training models |
| 7. Predict + Annotate | funannotate predict, InterProScan, BUSCO, funannotate annotate | Final annotated GFF3 |

## Repository layout

- **`pipeline/`** — the orchestrator: a small Python package (config-driven, checkpointed, resumable) that runs the 7 stages above. This is the part worth reading if you want to understand the design.
- **`0X.Scripts/`** — the original per-stage bash/Python scripts the orchestrator replaced. Kept for reference; they're what actually produced the thesis results before the rewrite, and some auxiliary scripts (CAZyme family counting, annotation summaries, BUSCO plots) are still standalone and used as-is.
- **`pipeline_TFM.ipynb`** — exploratory notebook used during the thesis work.
- **`herramientas.txt`** — the conda environments used (see below).

Raw sequencing data, intermediate files, and full result sets (hundreds of GB) are **not** included in this repository — only code.

## Why the orchestrator exists

The original pipeline was a set of numbered bash/Python scripts run by hand, with a master script (`pipeline_maestro.sh`) where you'd comment/uncomment stage blocks between runs. That worked, but had no real resume logic (a stage that half-finished had to be manually diagnosed) and at least one concrete bug: the RNA-seq training script hardcoded the same pooled reference transcriptome for every strain regardless of which one was passed in.

`pipeline/` replaces that with:
- A Pydantic-validated config schema per strain (`pipeline/config.py`) — `rna_reads` is a required field with no fallback, specifically so that bug can't silently reappear.
- Per-step, not just per-stage, checkpointing (`pipeline/state.py`) — atomic JSON markers, invalidated by a hash of the config fields relevant to that step, so re-running after a crash resumes at the right sub-step instead of redoing hours of work.
- `conda run -n <env>` instead of PATH-prepending, so tool-specific activation hooks (e.g. funannotate's PASAHOME/AUGUSTUS_CONFIG_PATH) actually run.
- Process-group-aware interruption handling, so killing the pipeline also kills the grandchild subprocesses long-running tools like funannotate/InterProScan spawn.
- Declarative post-stage cleanup rules, gated on a *later* stage's completion, instead of hand-placed `rm` lines.

## Requirements

The orchestrator itself only needs:
```
python >= 3.10
pydantic >= 2
pyyaml
```
(`conda env create -f pipeline/environment.yml`)

The actual bioinformatics tools run in their own dedicated conda environments, invoked via `conda run`:

```
trimmomatic, spades, pilon (+ bwa/samtools), seqkit, funannotate, busco
```
plus a standalone InterProScan installation. See `herramientas.txt` for the exact environment list this was run against.

## Usage

```bash
# validate a strain config without running anything
python -m pipeline.cli run --config pipeline/configs/example_strain.yaml --validate-only

# run the full pipeline
python -m pipeline.cli run --config pipeline/configs/example_strain.yaml

# resume from a specific stage (e.g. after fixing something in stage 5)
python -m pipeline.cli run --config pipeline/configs/example_strain.yaml --from-stage s5_funannotate_prep

# re-run exactly one stage, forced
python -m pipeline.cli run --config pipeline/configs/example_strain.yaml --only s4_filter --force

# see what would run without executing anything
python -m pipeline.cli run --config pipeline/configs/example_strain.yaml --dry-run

# adopt a strain that already progressed under the old bash scripts
python -m pipeline.cli adopt --config pipeline/configs/example_strain.yaml
```

Copy `pipeline/configs/example_strain.yaml` per strain rather than editing it in place once you have more than one strain in flight.

Run the unit tests (no bioinformatics tools required — the resume/config machinery is tested with dummy steps):
```bash
python -m unittest discover pipeline/tests
```

## Known limitations

- Paths in `pipeline/config.py` (`base_dir`, `interproscan_sh`) and in the legacy `0X.Scripts/` default to this project's original machine layout (`/srv/TFM/...`, `/media/nesus/...`). You will need to adjust these for your own environment.
- `funannotate`'s BUSCO integration has a known gap that this pipeline works around by deliberately tolerating a first `annotate` pass's failure, running BUSCO manually, and feeding its table back in before a second pass (`funannotate_busco_workaround` config flag, on by default). Turn it off once upstream no longer needs it.
- The `0X.Scripts/` directory is the pre-rewrite version, kept for reference and for a few still-standalone report/plotting scripts — it's not being maintained in parallel with `pipeline/`.
- No CI, no packaging (`pip install`-able) yet.

## License

[MIT](LICENSE)
