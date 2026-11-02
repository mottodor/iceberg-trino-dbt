"""Safety and finalization regressions for isolated learning exercises."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from learning_exercise import ExerciseAllowlist, LearningExercise, canonical_metadata
from run_acceptance import AcceptanceError


class SingleSchemaTests(unittest.TestCase):
    def test_statistics_order_is_ignored_but_contents_and_history_are_not(self):
        first = {"statistics": [{"snapshot-id": 3, "statistics-path": "a"}, {"snapshot-id": 1, "statistics-path": "b"}], "snapshot-log": [{"snapshot-id": 3}, {"snapshot-id": 1}]}
        reordered = {**first, "statistics": list(reversed(first["statistics"]))}
        self.assertEqual(canonical_metadata(first), canonical_metadata(reordered))
        altered = {**first, "statistics": [{"snapshot-id": 3, "statistics-path": "wrong"}, first["statistics"][1]]}
        self.assertNotEqual(canonical_metadata(first), canonical_metadata(altered))
        self.assertNotEqual(canonical_metadata(first), canonical_metadata({**first, "snapshot-log": list(reversed(first["snapshot-log"]))}))

    def test_exact_schema_location_and_prefix(self):
        for kind in ("maintenance", "incremental"):
            allow = ExerciseAllowlist("exercise_001", kind)
            self.assertEqual(allow.schemas, (f"exercise_001_{kind}",))
            allow.require_location(allow.schemas[0], f"s3://iceberg-trino-dbt/warehouse/{allow.schemas[0]}/")
            allow.require_object(f"warehouse/{allow.schemas[0]}/table/data/a.parquet")
            for key in (f"warehouse/{allow.schemas[0]}_sibling/a", f"warehouse/{allow.schemas[0]}/../other/a"):
                with self.assertRaises(AcceptanceError):
                    allow.require_object(key)

    def test_invalid_exercise_and_injected_id_rejected(self):
        for run_id, kind in (("x'; DROP SCHEMA x", "maintenance"), ("valid_run", "foreign")):
            with self.assertRaises(AcceptanceError):
                ExerciseAllowlist(run_id, kind)

    def test_no_concrete_replay_means_no_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            run = LearningExercise("exercise_001", Path(directory))
            with self.assertRaises(AcceptanceError):
                run.verify_behavior(Path(directory))

    def test_cleanup_failure_prevents_pass_and_preserves_pending_final_ac(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = LearningExercise("exercise_001", root)
            run.evidence_reserved = run.allowlist_verified = True
            run.initial_state = "initial_running"
            run.ac_results = {key: "PASS" for key in run.ac_results}
            with patch.object(run, "preflight"), patch.object(run, "implementation", return_value={}), patch.object(run, "start_stack"), patch.object(run, "assert_allowlist_absent"), patch.object(run, "immutable", return_value={"file": "hash"}), patch.object(run, "boundary", return_value={}), patch.object(run, "cleanup_task_data", side_effect=AcceptanceError("owned deletion failed")), patch.object(run, "assert_environment_restored"), patch.object(run, "assert_no_secrets_in_evidence"):
                with self.assertRaises(AcceptanceError):
                    run.run(lambda: None, required=set())
            summary = json.loads((root / "acceptance_summary.json").read_text())
            self.assertEqual(summary["outcome"], "FAIL")
            self.assertIn("owned deletion failed", summary["error"])
            self.assertEqual(summary["ac_results"]["AC-040"], "NOT_RUN")
