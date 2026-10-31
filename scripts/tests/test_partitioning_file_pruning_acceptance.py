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


class LayoutContractTests(unittest.TestCase):
    schema = "unit_partition_benchmark"

    def test_layout_sql_builders_encode_exact_unsorted_partitioning(self) -> None:
        expected = {
            "d": "partitioning = ARRAY['day(picked_up_at)']",
            "r": "partitioning = ARRAY['bucket(route_id, 4)']",
            "dr": (
                "partitioning = ARRAY['day(picked_up_at)', "
                "'bucket(route_id, 4)']"
            ),
        }
        for layout, partitioning in expected.items():
            sql = target.build_layout_sql(
                "balanced", layout=layout, schema=self.schema
            )
            self.assertIn(f'"balanced_{layout}"', sql)
            self.assertIn('FROM "lakehouse"."unit_partition_benchmark"."balanced_u"', sql)
            self.assertIn(partitioning, sql)
            self.assertNotIn("ORDER BY", sql)
            self.assertNotIn("sorted_by", sql.lower())
            self.assertNotIn("optimize", sql.lower())
        with self.assertRaisesRegex(target.AcceptanceError, "U layout"):
            target.build_layout_sql("balanced", layout="u", schema=self.schema)
        with self.assertRaisesRegex(target.AcceptanceError, "unknown benchmark layout"):
            target.build_layout_sql("balanced", layout="x", schema=self.schema)

    def test_table_listing_and_show_create_fail_closed(self) -> None:
        listing = [["table_name"]] + [
            [f"{dataset}_{layout}"]
            for dataset in target.DATASETS
            for layout in target.LAYOUTS
        ]
        listing[1:] = sorted(listing[1:])
        target.assert_layout_table_listing(listing)
        with self.assertRaisesRegex(target.AcceptanceError, "unexpected benchmark table"):
            target.assert_layout_table_listing(listing[:-1])

        for layout, transforms in target.LAYOUT_PARTITIONING.items():
            partitioning = ""
            if transforms:
                values = ",".join(f"'{value}'" for value in transforms)
                partitioning = f", partitioning = ARRAY[{values}]"
            rows = [
                ["Create Table"],
                [
                    f"CREATE TABLE lakehouse.{self.schema}.balanced_{layout} ("
                    "package_id varchar) WITH (format = 'PARQUET'"
                    f"{partitioning})"
                ],
            ]
            summary = target.assert_show_create_layout(
                rows,
                schema=self.schema,
                dataset="balanced",
                layout=layout,
            )
            self.assertEqual(summary["partitioning"], list(transforms))

        mutated = [
            ["Create Table"],
            [
                f"CREATE TABLE lakehouse.{self.schema}.balanced_dr "
                "(package_id varchar) WITH (format = 'PARQUET', "
                "partitioning = ARRAY['day(picked_up_at)'])"
            ],
        ]
        with self.assertRaisesRegex(target.AcceptanceError, "unexpected balanced_dr"):
            target.assert_show_create_layout(
                mutated,
                schema=self.schema,
                dataset="balanced",
                layout="dr",
            )

    def test_layout_contract_reconciliation_and_topology_fail_closed(self) -> None:
        contract_header = [
            "layout",
            "row_count",
            "unique_packages",
            "route_count",
            "day_count",
            "completed_count",
            "on_time_count",
            "total_delay_minutes",
        ]
        contract = [contract_header] + [
            [layout, "256000", "256000", "10", "50", "224000", "160000", "4800000"]
            for layout in target.LAYOUTS
        ]
        target.assert_layout_contract_rows(contract, dataset="balanced")
        mutated_contract = copy.deepcopy(contract)
        mutated_contract[-1][1] = "255999"
        with self.assertRaisesRegex(target.AcceptanceError, "unexpected balanced/dr"):
            target.assert_layout_contract_rows(mutated_contract, dataset="balanced")

        reconciliation = [
            ["layout", "u_minus_layout", "layout_minus_u"],
            ["d", "0", "0"],
            ["r", "0", "0"],
            ["dr", "0", "0"],
        ]
        target.assert_reconciliation_rows(reconciliation, dataset="balanced")
        mutated_reconciliation = copy.deepcopy(reconciliation)
        mutated_reconciliation[-1][2] = "1"
        with self.assertRaisesRegex(target.AcceptanceError, "differs from U"):
            target.assert_reconciliation_rows(
                mutated_reconciliation, dataset="balanced"
            )

        topology = [[
            "layout",
            "tuple_count",
            "record_count",
            "min_files_per_tuple",
            "file_count",
            "min_records_per_tuple",
            "max_records_per_tuple",
        ]]
        topology.extend(
            [
                layout,
                str(target.LAYOUT_TUPLE_COUNTS[layout]),
                "256000",
                "1",
                str(target.LAYOUT_TUPLE_COUNTS[layout]),
                "1",
                "256000",
            ]
            for layout in target.LAYOUTS
        )
        target.assert_topology_rows(topology, dataset="skewed")
        mutated_topology = copy.deepcopy(topology)
        mutated_topology[-1][3] = "0"
        with self.assertRaisesRegex(target.AcceptanceError, "unexpected skewed/dr"):
            target.assert_topology_rows(mutated_topology, dataset="skewed")

    def test_file_inventory_and_representative_bounds_contract(self) -> None:
        rows = [[
            "content",
            "file_path",
            "record_count",
            "file_format",
            "file_size_in_bytes",
            "lower_bounds",
            "upper_bounds",
        ], [
            "0",
            (
                "s3://iceberg-trino-dbt/warehouse/unit_partition_benchmark/"
                "balanced_u-abc/data/file.parquet"
            ),
            "256000",
            "PARQUET",
            "1000",
            "{2=BENCH-R0001, 4=2025-03-01 00:00:00.000000 UTC}",
            "{2=BENCH-R0014, 4=2025-04-19 08:31:00.000000 UTC}",
        ]]
        summary = target.assert_file_inventory_rows(
            rows,
            schema=self.schema,
            dataset="balanced",
            layout="u",
        )
        self.assertEqual(summary["record_count"], 256_000)
        mutated = copy.deepcopy(rows)
        mutated[1][3] = "ORC"
        with self.assertRaisesRegex(target.AcceptanceError, "invalid balanced/u"):
            target.assert_file_inventory_rows(
                mutated,
                schema=self.schema,
                dataset="balanced",
                layout="u",
            )

        sql = target.representative_bounds_sql(
            self.schema,
            "balanced",
            route_id="BENCH-R0002",
            route_bucket=2,
        )
        self.assertIn("picked_up_at_day=2025-03-30", sql)
        self.assertIn("route_id_bucket=2", sql)
        self.assertIn('lower_bounds."4"', sql)
        self.assertIn('upper_bounds."2"', sql)
        self.assertNotIn("ORDER BY picked_up_at", sql)

    def test_residual_object_cleanup_scope_is_exact(self) -> None:
        prefix = "warehouse/unit_partition_benchmark/"
        inventory = {
            "Contents": [
                {"Key": f"{prefix}a.parquet"},
                {"Key": f"{prefix}metadata.json"},
            ]
        }
        remaining = {"Contents": [{"Key": f"{prefix}a.parquet"}]}
        self.assertEqual(
            target.validate_residual_object_keys(
                inventory, remaining, prefix=prefix
            ),
            [f"{prefix}a.parquet"],
        )
        outside = {"Contents": [{"Key": "warehouse/other/a.parquet"}]}
        with self.assertRaisesRegex(target.AcceptanceError, "ownership mismatch"):
            target.validate_residual_object_keys(inventory, outside, prefix=prefix)
        unknown = {"Contents": [{"Key": f"{prefix}unknown.parquet"}]}
        with self.assertRaisesRegex(target.AcceptanceError, "ownership mismatch"):
            target.validate_residual_object_keys(inventory, unknown, prefix=prefix)


class BalancedWorkloadTests(unittest.TestCase):
    schema = "unit_partition_benchmark"

    def metadata(self, layout: str, case: str) -> tuple[list[list[str]], list[list[str]]]:
        partitions = [["pickup_day", "route_bucket", "record_count", "file_count", "total_size"]]
        files = [["file_path", "record_count", "file_size_in_bytes", "bounds_include_target"]]
        # Independent fixture: one file for every partition tuple in the universe.
        days = [f"2025-03-{i:02d}" for i in range(1, 32)] + [f"2025-04-{i:02d}" for i in range(1, 20)]
        if layout not in {"d", "dr"}:
            days = [""]
        elif case in {"day", "day_route"}:
            days = ["2025-03-30"]
        buckets = ["0", "1", "2", "3"] if layout in {"r", "dr"} else [""]
        if layout in {"r", "dr"} and case in {"route", "day_route"}:
            buckets = ["2"]
        for day in days:
            for bucket in buckets:
                routes = {"": 10, "0": 3, "1": 3, "2": 2, "3": 2}[bucket]
                records = 512 * routes * (1 if day else 50)
                path = f"s3://bucket/warehouse/{self.schema}/balanced_{layout}-uuid/data/"
                if day:
                    path += f"picked_up_at_day={day}/"
                if bucket:
                    path += f"route_id_bucket={bucket}/"
                path += "file.parquet"
                partitions.append([day, bucket, str(records), "1", "1000"])
                files.append([path, str(records), "1000", "true"])
        return partitions, files

    def comparison(self) -> dict[str, Any]:
        logical = {
            "day": (5120, 4480, 3200, 96000),
            "route": (25600, 22400, 16000, 480000),
            "day_route": (512, 448, 320, 9600),
            "full_scan": (256000, 224000, 160000, 4800000),
        }
        eligible = {
            "day": (256000, 5120, 256000, 5120),
            "route": (256000, 256000, 51200, 51200),
            "day_route": (256000, 5120, 51200, 1024),
            "full_scan": (256000, 256000, 256000, 256000),
        }
        return {
            case: {
                layout: {
                    "result": dict(zip(("package_count", "completed_count", "on_time_count", "total_delay_minutes"), logical[case], strict=True)),
                    "candidates": {"record_count": records},
                    "io": {"estimate": {"outputRowCount": records}},
                    "runtime": {"input_rows": records, "physical_input_bytes": records, "splits": 1},
                }
                for layout, records in zip(("u", "d", "r", "dr"), eligible[case], strict=True)
            }
            for case in logical
        }

    def test_queries_use_approved_predicates_and_identical_projection(self) -> None:
        for case in ("day", "route", "day_route", "full_scan"):
            for layout in ("u", "d", "r", "dr"):
                sql = target.balanced_query_sql(self.schema, layout, case, "BENCH-R0002")
                self.assertIn(f'"balanced_{layout}"', sql)
                self.assertIn("count_if(delivered_at IS NOT NULL)", sql)
                self.assertNotIn("CAST(picked_up_at", sql)
                self.assertEqual("WHERE" in sql, case != "full_scan")
                self.assertEqual("picked_up_at >=" in sql, case in {"day", "day_route"})
                self.assertEqual("route_id =" in sql, case in {"route", "day_route"})
        with self.assertRaisesRegex(target.AcceptanceError, "unknown balanced"):
            target.balanced_query_sql(self.schema, "u", "other", "BENCH-R0002")
        with self.assertRaisesRegex(target.AcceptanceError, "invalid representative"):
            target.balanced_query_sql(self.schema, "u", "route", "bad'route")

    def test_all_sixteen_candidate_selections_and_metadata_sql(self) -> None:
        for case in ("day", "route", "day_route", "full_scan"):
            for layout in ("u", "d", "r", "dr"):
                partitions, files = self.metadata(layout, case)
                summary = target.assert_balanced_candidates(partitions, files, schema=self.schema, layout=layout, case=case)
                expected = self.comparison()[case][layout]["candidates"]["record_count"]
                self.assertEqual(summary["record_count"], expected)
                partition_sql, file_sql = target.balanced_candidate_sql(self.schema, layout, case, "BENCH-R0002", 2)
                self.assertEqual("partition.picked_up_at_day =" in partition_sql, layout in {"d", "dr"} and case in {"day", "day_route"})
                self.assertEqual("partition.route_id_bucket =" in partition_sql, layout in {"r", "dr"} and case in {"route", "day_route"})
                self.assertNotIn("bounds", file_sql.split("WHERE")[1])
                self.assertEqual(summary["file_count"], len(files) - 1)

    def test_candidate_mutations_fail_closed(self) -> None:
        for mutation in ("empty_partitions", "empty_files", "missing_tuple", "wrong_tuple", "duplicate_file", "wrong_records", "wrong_size", "null_bounds", "foreign_file"):
            partitions, files = self.metadata("dr", "day_route")
            if mutation == "empty_partitions":
                partitions = partitions[:1]
            elif mutation == "empty_files":
                files = files[:1]
            elif mutation == "missing_tuple":
                partitions[1][1] = ""
            elif mutation == "wrong_tuple":
                partitions[1][0] = "2025-03-29"
            elif mutation == "duplicate_file":
                files.append(files[1][:])
            elif mutation == "wrong_records":
                files[1][1] = "512"
            elif mutation == "wrong_size":
                files[1][2] = "999"
            elif mutation == "null_bounds":
                files[1][3] = ""
            else:
                files[1][0] = files[1][0].replace(self.schema, "foreign")
            with self.subTest(mutation=mutation), self.assertRaises(target.AcceptanceError):
                target.assert_balanced_candidates(partitions, files, schema=self.schema, layout="dr", case="day_route")

    def test_comparison_rejects_missing_results_stats_and_false_reductions(self) -> None:
        self.assertEqual(target.assert_balanced_comparison(self.comparison())["query_layout_count"], 16)
        for mutation in ("missing_case", "missing_layout", "wrong_aggregate", "null_aggregate", "wrong_eligible", "wrong_runtime", "zero_bytes", "zero_splits", "wrong_io", "no_reduction", "pruned_full_scan"):
            cases = self.comparison()
            value = cases["day_route"]["dr"]
            if mutation == "missing_case":
                cases.pop("full_scan")
            elif mutation == "missing_layout":
                cases["day"].pop("r")
            elif mutation == "wrong_aggregate":
                value["result"]["completed_count"] = 447
            elif mutation == "null_aggregate":
                value["result"]["on_time_count"] = ""
            elif mutation == "wrong_eligible":
                value["candidates"]["record_count"] = 512
            elif mutation == "wrong_runtime":
                value["runtime"]["input_rows"] = 512
            elif mutation == "zero_bytes":
                value["runtime"]["physical_input_bytes"] = 0
            elif mutation == "zero_splits":
                value["runtime"]["splits"] = 0
            elif mutation == "wrong_io":
                value["io"]["estimate"]["outputRowCount"] = 512
            elif mutation == "no_reduction":
                value["runtime"]["physical_input_bytes"] = 256000
            else:
                cases["full_scan"]["dr"]["runtime"]["input_rows"] = 1024
            with self.subTest(mutation=mutation), self.assertRaises(target.AcceptanceError):
                target.assert_balanced_comparison(cases)


class SkewedWorkloadTests(unittest.TestCase):
    schema = "unit_partition_benchmark"
    hot_route = "BENCH-R0004"
    cold_route = "BENCH-R0002"

    def metadata(self, layout: str, case: str) -> tuple[list[list[str]], list[list[str]]]:
        partitions = [["pickup_day", "route_bucket", "record_count", "file_count", "total_size"]]
        files = [["file_path", "record_count", "file_size_in_bytes", "bounds_include_target"]]
        days = [f"2025-03-{i:02d}" for i in range(1, 32)] + [
            f"2025-04-{i:02d}" for i in range(1, 20)
        ]
        if layout not in {"d", "dr"}:
            days = [""]
        elif case in {"peak_day", "hot_peak", "cold_peak"}:
            days = ["2025-03-05"]
        elif case in {"off_peak_day", "hot_off_peak", "cold_off_peak"}:
            days = ["2025-03-30"]
        buckets = ["0", "1", "2", "3"] if layout in {"r", "dr"} else [""]
        if layout in {"r", "dr"} and case in {"hot_route", "hot_peak", "hot_off_peak"}:
            buckets = ["0"]
        elif layout in {"r", "dr"} and case in {"cold_route", "cold_peak", "cold_off_peak"}:
            buckets = ["2"]
        for day in days:
            for bucket in buckets:
                if not day and not bucket:
                    records = 256000
                elif not bucket:
                    records = 20480 if day <= "2025-03-10" else 1280
                elif not day:
                    records = 115200 if bucket in {"0", "1"} else 12800
                elif bucket in {"0", "1"}:
                    records = 9216 if day <= "2025-03-10" else 576
                else:
                    records = 1024 if day <= "2025-03-10" else 64
                path = f"s3://iceberg-trino-dbt/warehouse/{self.schema}/skewed_{layout}-uuid/"
                if day:
                    path += f"picked_up_at_day={day}/"
                if bucket:
                    path += f"route_id_bucket={bucket}/"
                path += f"file-{day or 'all'}-{bucket or 'all'}.parquet"
                partitions.append([day, bucket, str(records), "1", str(records * 2)])
                files.append([path, str(records), str(records * 2), "true"])
        return partitions, files

    def comparison(self) -> dict[str, Any]:
        logical = {
            "peak_day": (20480, 17920, 12800, 384000),
            "off_peak_day": (1280, 1120, 800, 24000),
            "hot_route": (102400, 89600, 64000, 1920000),
            "cold_route": (6400, 5600, 4000, 120000),
            "hot_peak": (8192, 7168, 5120, 153600),
            "hot_off_peak": (512, 448, 320, 9600),
            "cold_peak": (512, 448, 320, 9600),
            "cold_off_peak": (32, 28, 20, 600),
            "full_scan": (256000, 224000, 160000, 4800000),
        }
        eligible = {
            "peak_day": (256000, 20480, 256000, 20480),
            "off_peak_day": (256000, 1280, 256000, 1280),
            "hot_route": (256000, 256000, 115200, 115200),
            "cold_route": (256000, 256000, 12800, 12800),
            "hot_peak": (256000, 20480, 115200, 9216),
            "hot_off_peak": (256000, 1280, 115200, 576),
            "cold_peak": (256000, 20480, 12800, 1024),
            "cold_off_peak": (256000, 1280, 12800, 64),
            "full_scan": (256000, 256000, 256000, 256000),
        }
        return {
            case: {
                layout: {
                    "result": dict(
                        zip(
                            (
                                "package_count",
                                "completed_count",
                                "on_time_count",
                                "total_delay_minutes",
                            ),
                            map(str, logical[case]),
                            strict=True,
                        )
                    ),
                    "candidates": {"record_count": records},
                    "io": {"estimate": {"outputRowCount": records}},
                    "runtime": {
                        "input_rows": records,
                        "physical_input_bytes": records,
                        "splits": 1,
                    },
                }
                for layout, records in zip(
                    ("u", "d", "r", "dr"), eligible[case], strict=True
                )
            }
            for case in logical
        }

    def test_queries_use_exact_peak_off_peak_and_route_predicates(self) -> None:
        date_cases = {
            "peak_day",
            "off_peak_day",
            "hot_peak",
            "hot_off_peak",
            "cold_peak",
            "cold_off_peak",
        }
        route_cases = {
            "hot_route",
            "cold_route",
            "hot_peak",
            "hot_off_peak",
            "cold_peak",
            "cold_off_peak",
        }
        for case in target.DATASET_CASES["skewed"]:
            for layout in target.LAYOUTS:
                sql = target.skewed_query_sql(
                    self.schema, layout, case, self.hot_route, self.cold_route
                )
                self.assertIn(f'"skewed_{layout}"', sql)
                self.assertNotIn("CAST(picked_up_at", sql)
                self.assertEqual("picked_up_at >=" in sql, case in date_cases)
                self.assertEqual("route_id =" in sql, case in route_cases)
                self.assertEqual("2025-03-05" in sql, case in {"peak_day", "hot_peak", "cold_peak"})
                self.assertEqual("2025-03-30" in sql, case in {"off_peak_day", "hot_off_peak", "cold_off_peak"})
        with self.assertRaisesRegex(target.AcceptanceError, "unknown skewed"):
            target.skewed_query_sql(
                self.schema, "u", "other", self.hot_route, self.cold_route
            )
        with self.assertRaisesRegex(target.AcceptanceError, "invalid representative"):
            target.skewed_query_sql(
                self.schema, "u", "hot_route", "bad'route", self.cold_route
            )

    def test_all_thirty_six_candidate_selections_and_metadata_sql(self) -> None:
        comparison = self.comparison()
        for case in target.DATASET_CASES["skewed"]:
            for layout in target.LAYOUTS:
                partitions, files = self.metadata(layout, case)
                summary = target.assert_skewed_candidates(
                    partitions,
                    files,
                    schema=self.schema,
                    layout=layout,
                    case=case,
                )
                self.assertEqual(
                    summary["record_count"],
                    comparison[case][layout]["candidates"]["record_count"],
                )
                partition_sql, file_sql = target.skewed_candidate_sql(
                    self.schema,
                    layout,
                    case,
                    self.hot_route,
                    0,
                    self.cold_route,
                    2,
                )
                date_filtered = case in {
                    "peak_day",
                    "off_peak_day",
                    "hot_peak",
                    "hot_off_peak",
                    "cold_peak",
                    "cold_off_peak",
                }
                route_filtered = case in {
                    "hot_route",
                    "cold_route",
                    "hot_peak",
                    "hot_off_peak",
                    "cold_peak",
                    "cold_off_peak",
                }
                self.assertEqual(
                    "partition.picked_up_at_day =" in partition_sql,
                    layout in {"d", "dr"} and date_filtered,
                )
                self.assertEqual(
                    "partition.route_id_bucket =" in partition_sql,
                    layout in {"r", "dr"} and route_filtered,
                )
                self.assertNotIn("bounds", file_sql.split("WHERE")[1])
                self.assertEqual(summary["file_count"], len(files) - 1)
        with self.assertRaisesRegex(target.AcceptanceError, "hot bucket 0"):
            target.skewed_candidate_sql(
                self.schema,
                "r",
                "hot_route",
                self.hot_route,
                1,
                self.cold_route,
                2,
            )

    def test_candidate_mutations_fail_closed(self) -> None:
        partitions, files = self.metadata("dr", "hot_peak")
        mutations = {
            "wrong_partition_records": lambda p, f: p[1].__setitem__(2, "8192"),
            "missing_partition": lambda p, f: p.pop(),
            "duplicate_file": lambda p, f: f.append(f[1][:]),
            "wrong_file_records": lambda p, f: f[1].__setitem__(1, "8192"),
            "bounds_exclude": lambda p, f: f[1].__setitem__(3, "false"),
            "foreign_file": lambda p, f: f[1].__setitem__(
                0, f[1][0].replace(self.schema, "foreign")
            ),
        }
        for name, mutate in mutations.items():
            changed_partitions = copy.deepcopy(partitions)
            changed_files = copy.deepcopy(files)
            mutate(changed_partitions, changed_files)
            with self.subTest(name=name), self.assertRaises(target.AcceptanceError):
                target.assert_skewed_candidates(
                    changed_partitions,
                    changed_files,
                    schema=self.schema,
                    layout="dr",
                    case="hot_peak",
                )

    def test_comparison_rejects_missing_evidence_and_false_skew_claims(self) -> None:
        self.assertEqual(
            target.assert_skewed_comparison(self.comparison())["query_layout_count"],
            36,
        )
        mutations = {
            "missing_case": lambda cases: cases.pop("full_scan"),
            "missing_layout": lambda cases: cases["peak_day"].pop("r"),
            "wrong_aggregate": lambda cases: cases["hot_peak"]["dr"]["result"].__setitem__("package_count", 8191),
            "wrong_eligible": lambda cases: cases["cold_off_peak"]["dr"]["candidates"].__setitem__("record_count", 32),
            "wrong_runtime": lambda cases: cases["hot_peak"]["dr"]["runtime"].__setitem__("input_rows", 8192),
            "wrong_io": lambda cases: cases["hot_peak"]["dr"]["io"]["estimate"].__setitem__("outputRowCount", 8192),
            "no_reduction": lambda cases: cases["hot_peak"]["dr"]["runtime"].__setitem__("physical_input_bytes", 256000),
            "hidden_co_bucket": lambda cases: cases["hot_route"]["r"]["candidates"].__setitem__("record_count", 102400),
            "no_dr_subset": lambda cases: cases["cold_off_peak"]["dr"]["candidates"].__setitem__("record_count", 1280),
            "no_density_contrast": lambda cases: cases["peak_day"]["d"]["runtime"].__setitem__("physical_input_bytes", 1280),
            "pruned_full_scan": lambda cases: cases["full_scan"]["dr"]["runtime"].__setitem__("input_rows", 200),
        }
        for name, mutate in mutations.items():
            cases = self.comparison()
            mutate(cases)
            with self.subTest(name=name), self.assertRaises(target.AcceptanceError):
                target.assert_skewed_comparison(cases)


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

    def test_plan_parsers_reject_extra_foreign_scan_or_input(self) -> None:
        distributed = self.distributed_document()
        distributed["2"] = copy.deepcopy(distributed["1"])
        distributed["2"]["children"][0]["descriptor"]["table"] = "lakehouse:foreign.other$data@123"
        with self.assertRaisesRegex(target.AcceptanceError, "got 2"):
            target.parse_distributed_plan(json.dumps(distributed), schema=self.schema)
        io = self.io_document()
        foreign = copy.deepcopy(io["inputTableColumnInfos"][0])
        foreign["table"]["schemaTable"]["schema"] = "foreign"
        io["inputTableColumnInfos"].append(foreign)
        with self.assertRaisesRegex(target.AcceptanceError, "got 2"):
            target.parse_io_plan(json.dumps(io), schema=self.schema, expected_constraints=set())

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
        self.assertEqual(len(required), 428)
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
