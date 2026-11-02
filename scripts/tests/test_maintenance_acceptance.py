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
