"""Independent maintenance oracle and mutation regressions."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_maintenance_acceptance as target
from run_acceptance import AcceptanceError


class WorkloadTests(unittest.TestCase):
    def test_independent_workload_values_and_full_grain(self):
        rows = target.expected_rows(2048)
        target.assert_rows(rows, 2048)
        self.assertEqual(rows[0], [1, "R1", 3])
        self.assertEqual(rows[-1], [2048, "R0", 6144])
        self.assertEqual(sum(row[2] for row in rows), 3 * 2048 * 2049 // 2)

    def test_missing_duplicate_null_wrong_type_and_amount_rejected(self):
        valid = target.expected_rows(4)
        variants = [[], valid[:-1], [valid[0], valid[0], *valid[2:]]]
        for col, value in [(0, True), (0, "1"), (1, None), (1, "R9"), (2, 4), (2, 3.0)]:
            rows = copy.deepcopy(valid)
            rows[0][col] = value
            variants.append(rows)
        for rows in variants:
            with self.subTest(rows=rows), self.assertRaises(AcceptanceError):
                target.assert_rows(rows, 4)

    def test_distribution_cannot_be_empty_or_hide_nonpositive_files(self):
        actual = target.distribution({"a": {"content": 0, "size": 100}, "b": {"content": 0, "size": 200}})
        self.assertEqual(actual["median"], 150)
        self.assertEqual(actual["count"], 2)
        for files in ({}, {"a": {"content": 0, "size": 0}}, {"a": {"content": 1, "size": 100}}):
            with self.assertRaises(AcceptanceError):
                target.distribution(files)


class CompactionTests(unittest.TestCase):
    def states(self):
        files = {f"root/data/f{i}": {"content": 0, "size": 100} for i in range(16)}
        before = {"metadata": {"table-uuid": "same", "current-snapshot-id": 16, "snapshots": [{"snapshot-id": i} for i in range(1,17)]}, "rows": target.expected_rows(2048), "files": files, "sha256": {key: key for key in files}}
        after = copy.deepcopy(before)
        after["files"] = {f"root/data/new{i}": {"content": 0, "size": 400} for i in range(4)}
        after["sha256"].update({key: key for key in after["files"]})
        after["metadata"]["snapshots"].append({"snapshot-id": 17, "parent-snapshot-id": 16})
        after["metadata"]["current-snapshot-id"] = 17
        return before, after

    def test_compaction_keeps_rows_history_and_reduces_files(self):
        before, after = self.states()
        result = target.assert_compaction(before, after)
        self.assertEqual((result["before"]["count"], result["after"]["count"]), (16, 4))

    def test_no_reduction_changed_rows_or_deleted_history_are_rejected(self):
        before, after = self.states()
        variants = [{**after, "files": before["files"]}, {**after, "rows": after["rows"][:-1]}, {**after, "sha256": {}}]
        changed = copy.deepcopy(after)
        changed["metadata"]["snapshots"] = [{"snapshot-id": 17}]
        variants.append(changed)
        for value in variants:
            with self.subTest(value=value.keys()), self.assertRaises(AcceptanceError):
                target.assert_compaction(before, value)


class ExpirationTests(unittest.TestCase):
    def states(self):
        before = {"metadata": {"table-uuid": "same", "current-snapshot-id": 18, "snapshots": [{"snapshot-id": 16}, {"snapshot-id": 17}, {"snapshot-id": 18}]}, "rows": target.expected_rows(2176), "files": {"retained": {}}, "sha256": {"retained": "hash", "obsolete": "old"}, "objects": {"retained": {}, "obsolete": {}}}
        after = copy.deepcopy(before)
        after["metadata"]["snapshots"] = [{"snapshot-id": 17}, {"snapshot-id": 18}]
        del after["objects"]["obsolete"]
        del after["sha256"]["obsolete"]
        return before, after

    def test_two_retained_snapshots_and_obsolete_file_removal(self):
        before, after = self.states()
        target.assert_expiration(before, after, {17,18}, {"obsolete"})

    def test_wrong_retention_data_loss_or_no_reclamation_rejected(self):
        before, after = self.states()
        variants = [{**after, "sha256": {}}, {**after, "rows": after["rows"][:-1]}, {**after, "objects": before["objects"]}]
        changed = copy.deepcopy(after)
        changed["metadata"]["snapshots"] = [{"snapshot-id": 18}]
        variants.append(changed)
        for value in variants:
            with self.subTest(value=value.keys()), self.assertRaises(AcceptanceError):
                target.assert_expiration(before, value, {17,18}, {"obsolete"})

    def test_retention_negative_requires_semantic_error(self):
        from run_acceptance import CommandResult
        target.assert_retention_error(CommandResult([],1,0,"","Retention specified is shorter than minimum retention"))
        for code, message in [(0,"retention shorter minimum"),(1,"connection refused"),(1,"syntax error retention shorter minimum"),(1,"access denied retention shorter minimum")]:
            with self.assertRaises(AcceptanceError):
                target.assert_retention_error(CommandResult([],code,0,"",message))


class OrphanTests(unittest.TestCase):
    def states(self):
        before = {"metadata": {"table-uuid": "same"}, "metadata_location": "pointer", "rows": target.expected_rows(3), "objects": {"old": {}, "outside": {}, "retained": {}}, "sha256": {"old": "o", "outside": "x", "retained": "r"}}
        after = copy.deepcopy(before)
        del after["objects"]["old"]
        del after["sha256"]["old"]
        after["objects"]["young"] = {}
        after["sha256"]["young"] = "y"
        return before, after

    def test_only_aged_orphan_is_removed(self):
        before, after = self.states()
        target.assert_orphan(before, after, "old", "young", "outside")

    def test_missing_marker_or_retained_mutation_rejected(self):
        before, after = self.states()
        variants = []
        for key in ("young", "outside"):
            changed = copy.deepcopy(after)
            del changed["objects"][key]
            variants.append(changed)
        changed = copy.deepcopy(after)
        changed["sha256"]["retained"] = "changed"
        variants.append(changed)
        variants.append({**after, "rows": []})
        variants.append({**after, "metadata_location": "changed"})
        for value in variants:
            with self.subTest(value=value.keys()), self.assertRaises(AcceptanceError):
                target.assert_orphan(before, value, "old", "young", "outside")
