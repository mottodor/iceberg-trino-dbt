"""Pure helper and fail-closed parser tests for the partition benchmark runner."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from datetime import timedelta
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_partitioning_file_pruning_acceptance as target  # noqa: E402


class RouteMappingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.candidates = [
            ("BENCH-R0004", 0),
            ("BENCH-R0005", 0),
            ("BENCH-R0009", 0),
            ("BENCH-R0013", 0),
            ("BENCH-R0001", 1),
            ("BENCH-R0006", 1),
            ("BENCH-R0014", 1),
            ("BENCH-R0018", 1),
            ("BENCH-R0002", 2),
            ("BENCH-R0008", 2),
            ("BENCH-R0012", 2),
            ("BENCH-R0003", 3),
            ("BENCH-R0007", 3),
            ("BENCH-R0011", 3),
        ]

    def test_selects_exact_bucket_distribution_and_representatives(self) -> None:
        mapping = target.select_route_mapping(reversed(self.candidates))
        summary = target.assert_route_mapping(mapping)

        self.assertEqual(summary["routes_by_bucket"], {"0": 3, "1": 3, "2": 2, "3": 2})
        self.assertEqual(summary["hot_routes"], ["BENCH-R0004", "BENCH-R0001"])
        self.assertEqual(summary["representative_hot_route"], "BENCH-R0004")
        self.assertEqual(summary["representative_cold_route"], "BENCH-R0002")

    def test_rejects_wrong_bucket_count_mutation(self) -> None:
        mapping = target.select_route_mapping(self.candidates)
        mutated = copy.deepcopy(mapping)
        mutated[6]["bucket_id"] = 3

        with self.assertRaisesRegex(target.AcceptanceError, "bucket 2"):
            target.assert_route_mapping(mutated)

    def test_rejects_wrong_hot_role_mutation(self) -> None:
        mapping = target.select_route_mapping(self.candidates)
        mutated = copy.deepcopy(mapping)
        mutated[1]["is_hot"] = True

        with self.assertRaisesRegex(target.AcceptanceError, "hot/cold role"):
            target.assert_route_mapping(mutated)

    def test_rejects_duplicate_or_invalid_candidates(self) -> None:
        with self.assertRaisesRegex(target.AcceptanceError, "duplicate benchmark route"):
            target.select_route_mapping([*self.candidates, self.candidates[0]])
        with self.assertRaisesRegex(target.AcceptanceError, "invalid benchmark route"):
            target.select_route_mapping([("route-1", 0)])

    def test_route_mapping_sql_and_csv_parser_preserve_bucket_contract(self) -> None:
        sql = target.route_mapping_sql()
        self.assertIn("lakehouse.system.bucket", sql)
        self.assertIn("PARTITION BY bucket_id ORDER BY route_id", sql)
        self.assertIn("bucket_id IN (0, 1) AND bucket_rank = 1", sql)

        mapping = target.select_route_mapping(self.candidates)
        rows = [["route_id", "bucket_id", "bucket_rank", "is_hot"]]
        rows.extend(
            [
                str(row["route_id"]),
                str(row["bucket_id"]),
                str(row["bucket_rank"]),
                str(row["is_hot"]).lower(),
            ]
            for row in mapping
        )
        self.assertEqual(target.parse_route_mapping_rows(rows), mapping)

        rows[-1][-1] = "yes"
        with self.assertRaisesRegex(target.AcceptanceError, "invalid route hot flag"):
            target.parse_route_mapping_rows(rows)


class DatasetContractTests(unittest.TestCase):
    def mapping(self) -> list[dict[str, Any]]:
        return target.select_route_mapping(
            [
                ("BENCH-R0004", 0),
                ("BENCH-R0005", 0),
                ("BENCH-R0009", 0),
                ("BENCH-R0001", 1),
                ("BENCH-R0006", 1),
                ("BENCH-R0014", 1),
                ("BENCH-R0002", 2),
                ("BENCH-R0008", 2),
                ("BENCH-R0003", 3),
                ("BENCH-R0007", 3),
            ]
        )

    def test_group_sizes_match_balanced_and_skewed_contract(self) -> None:
        for peak in (False, True):
            for hot in (False, True):
                self.assertEqual(target.group_size("balanced", peak=peak, hot=hot), 512)

        self.assertEqual(target.group_size("skewed", peak=True, hot=True), 8_192)
        self.assertEqual(target.group_size("skewed", peak=True, hot=False), 512)
        self.assertEqual(target.group_size("skewed", peak=False, hot=True), 512)
        self.assertEqual(target.group_size("skewed", peak=False, hot=False), 32)

    def test_group_size_rejects_unknown_dataset(self) -> None:
        with self.assertRaisesRegex(target.AcceptanceError, "unknown benchmark dataset"):
            target.group_size("other", peak=False, hot=False)

    def test_state_cycle_and_all_case_aggregates_are_exact(self) -> None:
        self.assertEqual(
            target.expected_aggregate(16),
            {
                "package_count": 16,
                "completed_count": 14,
                "on_time_count": 10,
                "total_delay_minutes": 300,
            },
        )
        self.assertEqual(
            target.expected_case_aggregate("balanced", "day_route"),
            {
                "package_count": 512,
                "completed_count": 448,
                "on_time_count": 320,
                "total_delay_minutes": 9_600,
            },
        )
        self.assertEqual(
            target.expected_case_aggregate("skewed", "hot_peak"),
            {
                "package_count": 8_192,
                "completed_count": 7_168,
                "on_time_count": 5_120,
                "total_delay_minutes": 153_600,
            },
        )
        for dataset, cases in target.CASE_ROW_COUNTS.items():
            for case, row_count in cases.items():
                target.assert_case_aggregate(
                    target.expected_aggregate(row_count), dataset, case
                )

    def test_aggregate_mutations_fail_closed(self) -> None:
        with self.assertRaisesRegex(target.AcceptanceError, "positive multiple of 16"):
            target.expected_aggregate(511)

        mutated = target.expected_case_aggregate("balanced", "day")
        mutated["completed_count"] -= 1
        with self.assertRaisesRegex(target.AcceptanceError, "unexpected aggregate"):
            target.assert_case_aggregate(mutated, "balanced", "day")

        with self.assertRaisesRegex(target.AcceptanceError, "invalid aggregate"):
            target.assert_case_aggregate(
                {"package_count": 512}, "balanced", "day_route"
            )

    def test_eligible_record_matrices_match_approved_values(self) -> None:
        self.assertEqual(
            target.expected_eligible_records("balanced", "day_route"),
            {"u": 256_000, "d": 5_120, "r": 51_200, "dr": 1_024},
        )
        self.assertEqual(
            target.expected_eligible_records("skewed", "hot_off_peak"),
            {"u": 256_000, "d": 1_280, "r": 115_200, "dr": 576},
        )
        self.assertEqual(
            target.expected_eligible_records("skewed", "cold_off_peak"),
            {"u": 256_000, "d": 1_280, "r": 12_800, "dr": 64},
        )
        for dataset, cases in target.ELIGIBLE_RECORDS.items():
            for case, expected in cases.items():
                target.assert_eligible_records(expected, dataset, case)

    def test_eligible_record_mutation_is_detected(self) -> None:
        mutated = target.expected_eligible_records("skewed", "hot_peak")
        mutated["dr"] = 8_192
        with self.assertRaisesRegex(target.AcceptanceError, "unexpected eligible records"):
            target.assert_eligible_records(mutated, "skewed", "hot_peak")

    def test_dataset_sql_builders_encode_exact_deterministic_contract(self) -> None:
        mapping = self.mapping()
        balanced = target.build_dataset_sql(
            "balanced", schema="unit_partition_benchmark", mapping=mapping
        )
        skewed = target.build_dataset_sql(
            "skewed", schema="unit_partition_benchmark", mapping=mapping
        )

        self.assertIn('"balanced_u" AS', balanced)
        self.assertIn("BIGINT '512' AS group_size", balanced)
        self.assertIn("stop => 511", balanced)
        self.assertIn("'BAL-D'", balanced)
        self.assertIn('"skewed_u" AS', skewed)
        self.assertIn("WHEN is_hot AND day_number < 10 THEN BIGINT '8192'", skewed)
        self.assertIn("WHEN is_hot OR day_number < 10 THEN BIGINT '512'", skewed)
        self.assertIn("ELSE BIGINT '32'", skewed)
        self.assertIn("stop => 8191", skewed)
        self.assertIn("WHERE position < group_size", skewed)
        for sql in (balanced, skewed):
            self.assertIn("position % 16 AS cycle_position", sql)
            self.assertIn("INTERVAL '48' HOUR", sql)
            self.assertNotIn("ORDER BY", sql)
            self.assertNotIn("sorted_by", sql.lower())

        with self.assertRaisesRegex(target.AcceptanceError, "invalid benchmark schema"):
            target.build_dataset_sql("balanced", schema="bad.schema", mapping=mapping)
        mutated = copy.deepcopy(mapping)
        mutated[0]["route_id"] = "BENCH-R0004'); DROP TABLE x; --"
        with self.assertRaisesRegex(target.AcceptanceError, "invalid route IDs"):
            target.build_dataset_sql(
                "balanced", schema="unit_partition_benchmark", mapping=mutated
            )

    def test_schema_group_and_dataset_assertions_fail_closed(self) -> None:
        schema_rows = [["Column", "Type", "Extra", "Comment"]]
        schema_rows.extend([[name, type_name, "", ""] for name, type_name in target.BENCHMARK_COLUMNS])
        target.assert_benchmark_schema(schema_rows)
        mutated_schema = copy.deepcopy(schema_rows)
        mutated_schema[-1][1] = "integer"
        with self.assertRaisesRegex(target.AcceptanceError, "unexpected benchmark schema"):
            target.assert_benchmark_schema(mutated_schema)

        mapping = self.mapping()
        hot_routes = set(target.assert_route_mapping(mapping)["hot_routes"])
        for dataset in target.DATASETS:
            rows = [[
                "pickup_day",
                "route_id",
                "package_count",
                "completed_count",
                "on_time_count",
                "total_delay_minutes",
            ]]
            for day_number in range(target.PICKUP_DAY_COUNT):
                pickup_day = target.PICKUP_START_DATE + timedelta(days=day_number)
                for mapping_row in mapping:
                    route_id = str(mapping_row["route_id"])
                    expected = target.expected_aggregate(
                        target.group_size(
                            dataset,
                            peak=day_number < target.PEAK_DAY_COUNT,
                            hot=route_id in hot_routes,
                        )
                    )
                    rows.append(
                        [pickup_day.isoformat(), route_id]
                        + [str(expected[key]) for key in expected]
                    )
            target.assert_group_contract_rows(rows, dataset=dataset, mapping=mapping)
            mutated_rows = copy.deepcopy(rows)
            mutated_rows[1][2] = str(int(mutated_rows[1][2]) - 1)
            with self.assertRaisesRegex(target.AcceptanceError, "unexpected .* group aggregate"):
                target.assert_group_contract_rows(
                    mutated_rows, dataset=dataset, mapping=mapping
                )

        contract = {
            "row_count": 256_000,
            "unique_packages": 256_000,
            "route_count": 10,
            "day_count": 50,
            "completed_count": 224_000,
            "on_time_count": 160_000,
            "total_delay_minutes": 4_800_000,
            "not_null_violations": 0,
            "route_version_violations": 0,
            "pickup_formula_violations": 0,
            "sla_violations": 0,
            "state_violations": 0,
        }
        target.assert_dataset_contract_row(contract, "balanced")
        contract["state_violations"] = 1
        with self.assertRaisesRegex(target.AcceptanceError, "unexpected balanced"):
            target.assert_dataset_contract_row(contract, "balanced")


class PlanParserTests(unittest.TestCase):
    schema = "unit_partition_benchmark"

    def distributed_document(self) -> dict[str, Any]:
        return {
            "0": {"name": "Output", "descriptor": {}, "children": []},
            "1": {
                "name": "Aggregate",
                "descriptor": {},
                "children": [
                    {
                        "name": "ScanFilterProject",
                        "descriptor": {
                            "table": (
                                "lakehouse:unit_partition_benchmark.balanced_dr$data@123 "
                                "constraint on [picked_up_at]"
                            ),
                            "filterPredicate": "(route_id = varchar 'BENCH-R0002')",
                        },
                        "children": [],
                    }
                ],
            },
        }

    def io_document(self) -> dict[str, Any]:
        return {
            "inputTableColumnInfos": [
                {
                    "table": {
                        "catalog": "lakehouse",
                        "schemaTable": {
                            "schema": self.schema,
                            "table": "balanced_dr",
                        },
                    },
                    "constraint": {
                        "columnConstraints": [
                            {"columnName": "picked_up_at", "domain": {}},
                            {"columnName": "route_id", "domain": {}},
                        ]
                    },
                    "estimate": {"outputRowCount": 1_024.0},
                }
            ]
        }

    def analyze_text(self) -> str:
        return "\n".join(
            [
                "Fragment 2 [SOURCE]",
                (
                    "ScanFilterProject[table = "
                    "lakehouse:unit_partition_benchmark.balanced_dr$data@123 "
                    "constraint on [picked_up_at], filterPredicate = "
                    "(route_id = varchar 'BENCH-R0002')]"
                ),
                (
                    "Input: 1,024 rows (43.97kB), Filtered: 50.00%, "
                    "Physical input: 8.03kB, Physical input time: 2.88us, Splits: 1"
                ),
            ]
        )

    def test_decimal_byte_units(self) -> None:
        self.assertEqual(target.parse_byte_size("1B"), 1)
        self.assertEqual(target.parse_byte_size("1kB"), 1_000)
        self.assertEqual(target.parse_byte_size("1.25MB"), 1_250_000)
        self.assertEqual(target.parse_byte_size("1GB"), 1_000_000_000)
        with self.assertRaisesRegex(target.AcceptanceError, "unparseable byte size"):
            target.parse_byte_size("1KiB")

    def test_distributed_plan_requires_one_owned_scan(self) -> None:
        document = self.distributed_document()
        summary = target.parse_distributed_plan(json.dumps(document), schema=self.schema)
        self.assertEqual(summary["scan_count"], 1)
        self.assertEqual(summary["scan_node"], "ScanFilterProject")
        self.assertEqual(summary["constraint_columns"], ["picked_up_at"])
        self.assertIn("route_id", summary["filter_predicate"])

        duplicate = copy.deepcopy(document)
        duplicate["2"] = copy.deepcopy(document["1"])
        with self.assertRaisesRegex(target.AcceptanceError, "got 2"):
            target.parse_distributed_plan(json.dumps(duplicate), schema=self.schema)

    def test_io_plan_requires_one_input_and_expected_constraints(self) -> None:
        document = self.io_document()
        summary = target.parse_io_plan(
            json.dumps(document),
            schema=self.schema,
            expected_constraints={"picked_up_at", "route_id"},
        )
        self.assertEqual(summary["input_table_count"], 1)
        self.assertEqual(summary["constraint_columns"], ["picked_up_at", "route_id"])
        self.assertEqual(summary["estimate"]["outputRowCount"], 1_024.0)

        missing = copy.deepcopy(document)
        missing["inputTableColumnInfos"][0]["constraint"]["columnConstraints"] = []
        with self.assertRaisesRegex(target.AcceptanceError, "missing expected IO constraints"):
            target.parse_io_plan(
                json.dumps(missing),
                schema=self.schema,
                expected_constraints={"route_id"},
            )

        duplicate = copy.deepcopy(document)
        duplicate["inputTableColumnInfos"].append(
            copy.deepcopy(duplicate["inputTableColumnInfos"][0])
        )
        with self.assertRaisesRegex(target.AcceptanceError, "got 2"):
            target.parse_io_plan(
                json.dumps(duplicate),
                schema=self.schema,
                expected_constraints={"route_id"},
            )

    def test_explain_analyze_requires_one_scan_and_physical_input(self) -> None:
        text = self.analyze_text()
        summary = target.parse_explain_analyze(text, schema=self.schema)
        self.assertEqual(summary["input_rows"], 1_024)
        self.assertEqual(summary["input_size"], "43.97kB")
        self.assertEqual(summary["filtered_pct"], 50.0)
        self.assertEqual(summary["physical_input_bytes"], 8_030)
        self.assertEqual(summary["splits"], 1)

        with self.assertRaisesRegex(target.AcceptanceError, "got 2"):
            target.parse_explain_analyze(text + "\n" + text, schema=self.schema)
        with self.assertRaisesRegex(target.AcceptanceError, "physical-input anchor missing"):
            target.parse_explain_analyze(
                text.replace("Physical input:", "Physical missing:", 1),
                schema=self.schema,
            )

    def test_explain_analyze_rejects_stats_from_foreign_scan(self) -> None:
        owned_without_stats = "\n".join(self.analyze_text().splitlines()[:2])
        foreign_with_stats = "\n".join(
            [
                "ScanProject[table = lakehouse:other_schema.other_table$data@456]",
                (
                    "Input: 1,024 rows (43.97kB), Filtered: 0.00%, "
                    "Physical input: 8.03kB, Physical input time: 2.88us, Splits: 1"
                ),
            ]
        )
        with self.assertRaisesRegex(target.AcceptanceError, "runtime scan, got 2"):
            target.parse_explain_analyze(
                owned_without_stats + "\n" + foreign_with_stats,
                schema=self.schema,
            )


class BoundsAndManifestTests(unittest.TestCase):
    def bounds_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "layout": layout,
                "selected_files": 1,
                "bounds_include_target": 1,
                "no_additional_file_exclusion": True,
            }
            for layout in target.LAYOUTS
        ]

    def manifest(self) -> dict[str, Any]:
        digest = "a" * 64
        return {
            "files": [
                {"path": path, "size": 1, "sha256": digest}
                for path in sorted(target.required_final_evidence_paths())
            ]
        }

    def cleanup(self) -> dict[str, Any]:
        return {
            "schema_absent": True,
            "final_prefix_empty": True,
            "preexisting_volumes_preserved": True,
            "final_compose_state": "stopped",
        }

    def test_bounds_decision_accepts_all_selected_files(self) -> None:
        target.assert_bounds_decisions(self.bounds_rows())

    def test_bounds_decision_rejects_extra_file_exclusion(self) -> None:
        rows = self.bounds_rows()
        rows[-1]["bounds_include_target"] = 0
        rows[-1]["no_additional_file_exclusion"] = False
        with self.assertRaisesRegex(target.AcceptanceError, "file bounds exclude"):
            target.assert_bounds_decisions(rows)

    def test_manifest_covers_all_52_query_layout_cases(self) -> None:
        required = target.required_final_evidence_paths()
        self.assertEqual(len(required), 427)
        target.assert_final_evidence_manifest(
            self.manifest(), cleanup=self.cleanup()
        )

    def test_manifest_rejects_missing_case_and_false_cleanup(self) -> None:
        manifest = self.manifest()
        missing_path = "workload/skewed/cold_off_peak/dr/explain_analyze.txt"
        manifest["files"] = [
            entry for entry in manifest["files"] if entry["path"] != missing_path
        ]
        with self.assertRaisesRegex(target.AcceptanceError, missing_path):
            target.assert_final_evidence_manifest(manifest, cleanup=self.cleanup())

        cleanup = self.cleanup()
        cleanup["final_prefix_empty"] = False
        with self.assertRaisesRegex(target.AcceptanceError, "cleanup is incomplete"):
            target.assert_final_evidence_manifest(self.manifest(), cleanup=cleanup)

    def test_manifest_rejects_duplicate_or_invalid_entries(self) -> None:
        manifest = self.manifest()
        manifest["files"].append(copy.deepcopy(manifest["files"][0]))
        with self.assertRaisesRegex(target.AcceptanceError, "duplicate evidence"):
            target.assert_final_evidence_manifest(manifest, cleanup=self.cleanup())

        manifest = self.manifest()
        manifest["files"][0]["sha256"] = "not-a-digest"
        with self.assertRaisesRegex(target.AcceptanceError, "invalid evidence"):
            target.assert_final_evidence_manifest(manifest, cleanup=self.cleanup())


if __name__ == "__main__":
    unittest.main()
