"""Unit tests for the resume/invalidation machinery: state.py's markers,
stages/base.py's Step contract, and orchestrator.py's stage-range/force
resolution. No real bioinformatics tools are invoked — subprocess execution
is replaced by dummy Step subclasses that just touch files.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pipeline import state
from pipeline.orchestrator import _resolve_stage_range
from pipeline.stages.base import Stage, Step


class DummyStep(Step):
    stage_id = "dummy_stage"
    step_id = "dummy_step"

    def __init__(self, cfg_dict, logger, run_dir: Path):
        self._cfg_dict = cfg_dict
        self.run_dir = run_dir
        self.execute_count = 0
        # bypass PipelineConfig -- Step only needs .state_dir off self.cfg
        class _FakeCfg:
            state_dir = run_dir / "state"
        self.cfg = _FakeCfg()
        self.logger = logger

    def config_subset(self):
        return self._cfg_dict

    def outputs(self):
        return [self.run_dir / "out.txt"]

    def execute(self):
        self.execute_count += 1
        self.outputs()[0].write_text(f"run #{self.execute_count}")


class _NullLogger:
    def info(self, *a, **k):
        pass

    def warning(self, *a, **k):
        pass


class TestStateMarkers(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_not_done_without_marker(self):
        out = self.state_dir / "out.txt"
        out.write_text("x")
        h = state.config_hash({"a": 1})
        self.assertFalse(state.is_step_done(self.state_dir, "s", "step", h, [out]))

    def test_done_after_write_marker(self):
        out = self.state_dir / "out.txt"
        out.write_text("x")
        h = state.config_hash({"a": 1})
        state.write_marker(self.state_dir, "s", "step", h, [out])
        self.assertTrue(state.is_step_done(self.state_dir, "s", "step", h, [out]))

    def test_config_change_invalidates(self):
        out = self.state_dir / "out.txt"
        out.write_text("x")
        h1 = state.config_hash({"a": 1})
        h2 = state.config_hash({"a": 2})
        state.write_marker(self.state_dir, "s", "step", h1, [out])
        self.assertFalse(state.is_step_done(self.state_dir, "s", "step", h2, [out]))

    def test_deleted_output_invalidates(self):
        out = self.state_dir / "out.txt"
        out.write_text("x")
        h = state.config_hash({"a": 1})
        state.write_marker(self.state_dir, "s", "step", h, [out])
        out.unlink()
        self.assertFalse(state.is_step_done(self.state_dir, "s", "step", h, [out]))

    def test_empty_output_file_invalidates(self):
        out = self.state_dir / "out.txt"
        out.write_text("")  # zero bytes
        h = state.config_hash({"a": 1})
        state.write_marker(self.state_dir, "s", "step", h, [out])
        self.assertFalse(state.is_step_done(self.state_dir, "s", "step", h, [out]))

    def test_corrupt_marker_reads_as_not_done(self):
        self.state_dir.mkdir(exist_ok=True)
        marker_path = self.state_dir / "s.step.json"
        marker_path.write_text("{not valid json")
        out = self.state_dir / "out.txt"
        out.write_text("x")
        h = state.config_hash({"a": 1})
        self.assertFalse(state.is_step_done(self.state_dir, "s", "step", h, [out]))

    def test_invalidate_step_removes_marker(self):
        out = self.state_dir / "out.txt"
        out.write_text("x")
        h = state.config_hash({"a": 1})
        state.write_marker(self.state_dir, "s", "step", h, [out])
        state.invalidate_step(self.state_dir, "s", "step")
        self.assertIsNone(state.read_marker(self.state_dir, "s", "step"))

    def test_stage_state_roundtrip(self):
        state.write_stage_state(self.state_dir, "s3_pilon", {"last_completed_round": 2})
        data = state.read_stage_state(self.state_dir, "s3_pilon")
        self.assertEqual(data["last_completed_round"], 2)

    def test_stage_state_missing_returns_empty(self):
        self.assertEqual(state.read_stage_state(self.state_dir, "nope"), {})


class TestStepRunSemantics(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.run_dir = Path(self._tmp.name)
        self.logger = _NullLogger()

    def tearDown(self):
        self._tmp.cleanup()

    def test_run_executes_once_then_skips(self):
        step = DummyStep({"a": 1}, self.logger, self.run_dir)
        step.run()
        step.run()
        self.assertEqual(step.execute_count, 1, "second run() should skip, not re-execute")

    def test_force_reexecutes(self):
        step = DummyStep({"a": 1}, self.logger, self.run_dir)
        step.run()
        step.run(force=True)
        self.assertEqual(step.execute_count, 2)

    def test_missing_output_after_execute_raises(self):
        class BrokenStep(DummyStep):
            def execute(self):
                self.execute_count += 1
                # deliberately do not write the declared output

        step = BrokenStep({"a": 1}, self.logger, self.run_dir)
        with self.assertRaises(RuntimeError):
            step.run()

    def test_stage_is_done_requires_all_steps(self):
        class DummyStepA(DummyStep):
            step_id = "step_a"

        class DummyStepB(DummyStep):
            step_id = "step_b"

            def outputs(self):
                return [self.run_dir / "out_b.txt"]

        step1 = DummyStepA({"a": 1}, self.logger, self.run_dir)
        step2 = DummyStepB({"b": 2}, self.logger, self.run_dir)  # shares state_dir, distinct step_id
        stage = Stage(cfg=None, logger=self.logger, steps=[step1, step2])
        self.assertFalse(stage.is_done())
        stage.run()
        self.assertTrue(stage.is_done())


class TestStageRangeResolution(unittest.TestCase):
    def test_full_range_default(self):
        r = _resolve_stage_range(None, None, None)
        self.assertEqual(r[0], "s1_trimmomatic")
        self.assertEqual(r[-1], "s7_predict_annotate")
        self.assertEqual(len(r), 7)

    def test_from_stage_only(self):
        r = _resolve_stage_range("s5_funannotate_prep", None, None)
        self.assertEqual(r, ["s5_funannotate_prep", "s6_funannotate_train", "s7_predict_annotate"])

    def test_to_stage_only(self):
        r = _resolve_stage_range(None, "s3_pilon", None)
        self.assertEqual(r, ["s1_trimmomatic", "s2_spades", "s3_pilon"])

    def test_only_flag_overrides_range(self):
        r = _resolve_stage_range("s1_trimmomatic", "s7_predict_annotate", "s4_filter")
        self.assertEqual(r, ["s4_filter"])

    def test_unknown_stage_raises(self):
        with self.assertRaises(ValueError):
            _resolve_stage_range("not_a_stage", None, None)

    def test_from_after_to_raises(self):
        with self.assertRaises(ValueError):
            _resolve_stage_range("s6_funannotate_train", "s2_spades", None)


if __name__ == "__main__":
    unittest.main()
