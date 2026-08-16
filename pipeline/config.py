"""Config schema and YAML loading for the Trichoderma pipeline.

Everything a run needs is explicit here — no hardcoded strain-specific paths
anywhere else in the codebase. In particular `rna_reads` is required with no
fallback default: the old `fun_train.py` silently trained every strain
against the same pooled reference RNA-seq file regardless of which strain
was passed in, which is exactly the kind of bug this schema makes structurally
impossible to repeat.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, field_validator, model_validator


class ReadPair(BaseModel):
    r1: Path
    r2: Path

    @model_validator(mode="after")
    def _check_exist(self) -> "ReadPair":
        for p in (self.r1, self.r2):
            if not p.is_file():
                raise ValueError(f"read file does not exist: {p}")
        return self


class RNAReads(BaseModel):
    left: list[Path]
    right: list[Path]

    @model_validator(mode="after")
    def _check_paired(self) -> "RNAReads":
        if len(self.left) != len(self.right):
            raise ValueError(
                f"rna_reads.left has {len(self.left)} entries but "
                f"rna_reads.right has {len(self.right)} — must match 1:1"
            )
        if not self.left:
            raise ValueError("rna_reads.left/right must have at least one pair")
        for p in (*self.left, *self.right):
            if not p.is_file():
                raise ValueError(f"RNA-seq read file does not exist: {p}")
        return self


class CondaEnvsConfig(BaseModel):
    trimmomatic: str = "trimmomatic"
    spades: str = "spades"
    pilon: str = "pilon"  # this env must also have bwa/samtools on PATH
    seqkit: str = "seqkit"
    funannotate: str = "funannotate"
    busco: str = "busco"


class ResourceConfig(BaseModel):
    threads: int = 16
    memory_gb: int = 26


class NotificationConfig(BaseModel):
    enabled: bool = True
    email: str = "your-email@example.com"


class PipelineConfig(BaseModel):
    strain: str
    species: str = "Trichoderma sp."
    base_dir: Path = Path("/srv/TFM/PL-iteracion.05")

    dna_reads: ReadPair
    rna_reads: RNAReads

    busco_lineage: Path

    conda_envs: CondaEnvsConfig = CondaEnvsConfig()
    resources: ResourceConfig = ResourceConfig()
    notifications: NotificationConfig = NotificationConfig()

    funannotate_busco_workaround: bool = True
    pilon_max_rounds: int = 2
    contig_min_len: int = 3000
    busco_seed_species: str = "fusarium_graminearum"

    interproscan_sh: Path = Path(
        "/srv/biodata/interproscan_db/interproscan-5.77-108.0/interproscan.sh"
    )

    @field_validator("strain")
    @classmethod
    def _strain_is_safe(cls, v: str) -> str:
        # Strain names get interpolated into shell commands and file paths
        # downstream (conda run argv, du-monitor paths). Keep them boring.
        if not v or not all(c.isalnum() or c in "-_" for c in v):
            raise ValueError(
                f"strain must be alphanumeric plus '-'/'_' only, got: {v!r}"
            )
        return v

    @model_validator(mode="after")
    def _check_busco_lineage(self) -> "PipelineConfig":
        if not self.busco_lineage.is_dir():
            raise ValueError(f"busco_lineage directory not found: {self.busco_lineage}")
        return self

    # ── Derived paths, matching the existing numbered directory convention ──
    @property
    def dir_trimmomatic(self) -> Path:
        return self.base_dir / "01.Trimmomatic" / self.strain

    @property
    def dir_spades(self) -> Path:
        return self.base_dir / "02.SPAdes_Assembly" / self.strain

    @property
    def dir_pulido(self) -> Path:
        return self.base_dir / "03.Pulido_y_filtrado" / self.strain

    @property
    def dir_funannotate(self) -> Path:
        return self.base_dir / "04.Funannotate" / self.strain

    @property
    def state_dir(self) -> Path:
        return self.dir_funannotate / ".pipeline_state"

    @property
    def log_dir(self) -> Path:
        return self.base_dir / "logs" / self.strain


def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(
    yaml_path: Path | None = None, overrides: dict[str, Any] | None = None
) -> PipelineConfig:
    """Load a PipelineConfig from a YAML file, a dict of CLI overrides, or both.

    CLI overrides win over the YAML file, so `--strain foo` on top of a
    shared template config works as expected.
    """
    data: dict[str, Any] = {}
    if yaml_path is not None:
        with open(yaml_path, "r", encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh)
            if loaded:
                data = loaded
    if overrides:
        data = _deep_merge(data, overrides)
    return PipelineConfig.model_validate(data)
