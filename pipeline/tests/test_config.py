"""Unit tests for config.py's schema validation — in particular that the
RNA-seq hardcoding bug this rewrite fixes can't silently reappear (rna_reads
is required, with paired-length and file-existence validation)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from pipeline.config import PipelineConfig, load_config


class ConfigTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

        self.r1 = self.tmp / "dna_1.fastq.gz"
        self.r2 = self.tmp / "dna_2.fastq.gz"
        self.r1.write_bytes(b"x")
        self.r2.write_bytes(b"x")

        self.rna_l1 = self.tmp / "rna_l1.fastq.gz"
        self.rna_r1 = self.tmp / "rna_r1.fastq.gz"
        self.rna_l1.write_bytes(b"x")
        self.rna_r1.write_bytes(b"x")

        self.lineage_dir = self.tmp / "lineage"
        self.lineage_dir.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def base_data(self) -> dict:
        return {
            "strain": "TEST01",
            "dna_reads": {"r1": str(self.r1), "r2": str(self.r2)},
            "rna_reads": {"left": [str(self.rna_l1)], "right": [str(self.rna_r1)]},
            "busco_lineage": str(self.lineage_dir),
        }


class TestPipelineConfig(ConfigTestBase):
    def test_valid_config_loads(self):
        cfg = PipelineConfig.model_validate(self.base_data())
        self.assertEqual(cfg.strain, "TEST01")
        self.assertEqual(len(cfg.rna_reads.left), 1)

    def test_rna_reads_required(self):
        data = self.base_data()
        del data["rna_reads"]
        with self.assertRaises(ValidationError):
            PipelineConfig.model_validate(data)

    def test_rna_reads_mismatched_lengths_rejected(self):
        data = self.base_data()
        data["rna_reads"] = {"left": [str(self.rna_l1), str(self.rna_l1)], "right": [str(self.rna_r1)]}
        with self.assertRaises(ValidationError):
            PipelineConfig.model_validate(data)

    def test_rna_reads_empty_rejected(self):
        data = self.base_data()
        data["rna_reads"] = {"left": [], "right": []}
        with self.assertRaises(ValidationError):
            PipelineConfig.model_validate(data)

    def test_missing_dna_read_file_rejected(self):
        data = self.base_data()
        data["dna_reads"]["r1"] = str(self.tmp / "does_not_exist.fastq.gz")
        with self.assertRaises(ValidationError):
            PipelineConfig.model_validate(data)

    def test_missing_rna_read_file_rejected(self):
        data = self.base_data()
        data["rna_reads"]["left"] = [str(self.tmp / "does_not_exist.fastq.gz")]
        with self.assertRaises(ValidationError):
            PipelineConfig.model_validate(data)

    def test_missing_busco_lineage_dir_rejected(self):
        data = self.base_data()
        data["busco_lineage"] = str(self.tmp / "no_such_lineage")
        with self.assertRaises(ValidationError):
            PipelineConfig.model_validate(data)

    def test_unsafe_strain_name_rejected(self):
        data = self.base_data()
        data["strain"] = "../../etc/passwd"
        with self.assertRaises(ValidationError):
            PipelineConfig.model_validate(data)

    def test_defaults_applied(self):
        cfg = PipelineConfig.model_validate(self.base_data())
        self.assertEqual(cfg.resources.threads, 16)
        self.assertEqual(cfg.notifications.email, "your-email@example.com")
        self.assertTrue(cfg.funannotate_busco_workaround)
        self.assertEqual(cfg.pilon_max_rounds, 2)

    def test_derived_paths(self):
        cfg = PipelineConfig.model_validate({**self.base_data(), "base_dir": str(self.tmp)})
        self.assertEqual(cfg.dir_trimmomatic, self.tmp / "01.Trimmomatic" / "TEST01")
        self.assertEqual(cfg.dir_funannotate, self.tmp / "04.Funannotate" / "TEST01")
        self.assertEqual(cfg.state_dir, cfg.dir_funannotate / ".pipeline_state")


class TestLoadConfig(ConfigTestBase):
    def test_load_from_yaml(self):
        import yaml

        yaml_path = self.tmp / "strain.yaml"
        yaml_path.write_text(yaml.dump(self.base_data()))
        cfg = load_config(yaml_path)
        self.assertEqual(cfg.strain, "TEST01")

    def test_cli_overrides_win_over_yaml(self):
        import yaml

        yaml_path = self.tmp / "strain.yaml"
        yaml_path.write_text(yaml.dump(self.base_data()))
        cfg = load_config(yaml_path, overrides={"strain": "OVERRIDDEN"})
        self.assertEqual(cfg.strain, "OVERRIDDEN")

    def test_nested_override_merges_not_replaces(self):
        import yaml

        yaml_path = self.tmp / "strain.yaml"
        yaml_path.write_text(yaml.dump(self.base_data()))
        cfg = load_config(yaml_path, overrides={"resources": {"threads": 4}})
        self.assertEqual(cfg.resources.threads, 4)
        self.assertEqual(cfg.resources.memory_gb, 26)  # untouched default preserved


if __name__ == "__main__":
    unittest.main()
