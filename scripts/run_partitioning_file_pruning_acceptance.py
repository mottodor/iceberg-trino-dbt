#!/usr/bin/env python3
"""Run the isolated partitioning and file-pruning acceptance workflow."""

from __future__ import annotations

import argparse
import codecs
import csv
import json
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from run_acceptance import (
    AcceptanceError,
    AcceptanceRun,
    CATALOG,
    DEFAULT_EVIDENCE_ROOT,
    ROOT,
    RUN_ID_PATTERN,
    iso_now,
    parse_float,
    parse_int,
)

DATASETS = ("balanced", "skewed")
LAYOUTS = ("u", "d", "r", "dr")
PARTITIONING_FILE_PRUNING_ACS = tuple(
    f"AC-{number:03d}" for number in range(21, 28)
)
ROUTE_BUCKET_COUNTS = {0: 3, 1: 3, 2: 2, 3: 2}
DATASET_CASES = {
    "balanced": ("day", "route", "day_route", "full_scan"),
    "skewed": (
        "peak_day",
        "off_peak_day",
        "hot_route",
        "cold_route",
        "hot_peak",
        "hot_off_peak",
        "cold_peak",
        "cold_off_peak",
        "full_scan",
    ),
}
CASE_ROW_COUNTS = {
    "balanced": {
        "day": 5_120,
        "route": 25_600,
        "day_route": 512,
        "full_scan": 256_000,
    },
    "skewed": {
        "peak_day": 20_480,
        "off_peak_day": 1_280,
        "hot_route": 102_400,
        "cold_route": 6_400,
        "hot_peak": 8_192,
        "hot_off_peak": 512,
        "cold_peak": 512,
        "cold_off_peak": 32,
        "full_scan": 256_000,
    },
}
ELIGIBLE_RECORDS = {
    "balanced": {
        "day": {"u": 256_000, "d": 5_120, "r": 256_000, "dr": 5_120},
        "route": {"u": 256_000, "d": 256_000, "r": 51_200, "dr": 51_200},
        "day_route": {"u": 256_000, "d": 5_120, "r": 51_200, "dr": 1_024},
        "full_scan": {layout: 256_000 for layout in LAYOUTS},
    },
    "skewed": {
        "peak_day": {"u": 256_000, "d": 20_480, "r": 256_000, "dr": 20_480},
        "off_peak_day": {"u": 256_000, "d": 1_280, "r": 256_000, "dr": 1_280},
        "hot_route": {"u": 256_000, "d": 256_000, "r": 115_200, "dr": 115_200},
        "cold_route": {"u": 256_000, "d": 256_000, "r": 12_800, "dr": 12_800},
        "hot_peak": {"u": 256_000, "d": 20_480, "r": 115_200, "dr": 9_216},
        "hot_off_peak": {"u": 256_000, "d": 1_280, "r": 115_200, "dr": 576},
        "cold_peak": {"u": 256_000, "d": 20_480, "r": 12_800, "dr": 1_024},
        "cold_off_peak": {"u": 256_000, "d": 1_280, "r": 12_800, "dr": 64},
        "full_scan": {layout: 256_000 for layout in LAYOUTS},
    },
}
SCAN_NAMES = {"ScanProject", "ScanFilterProject"}
SCAN_PATTERN = re.compile(r"Scan(?:Filter)?Project\[table = (?P<table>[^\]]+)\]")
RUNTIME_STATS_PATTERN = re.compile(
    r"Input: (?P<input_rows>[\d,]+) rows \((?P<input_size>[^)]+)\), "
    r"Filtered: (?P<filtered>[\d.]+)%, Physical input: "
    r"(?P<physical>[\d.]+\s*(?:B|kB|MB|GB)), "
    r"Physical input time: (?P<physical_time>[^,]+), Splits: (?P<splits>\d+)"
)
SIZE_PATTERN = re.compile(r"^(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>B|kB|MB|GB)$")
UNIT_FACTORS = {"B": 1, "kB": 1_000, "MB": 1_000_000, "GB": 1_000_000_000}
CASE_EVIDENCE_FILES = {
    "query.sql",
    "result.csv",
    "partitions.csv",
    "files.csv",
    "explain.json",
    "explain_io.json",
    "explain_analyze.txt",
    "summary.json",
}
REQUIRED_FINAL_EVIDENCE_PATHS = {
    "commands.jsonl",
    "generation/route_mapping.csv",
    "generation/group_counts.csv",
    "layouts/summary.json",
    "runtime/catalog_tables.csv",
    "runtime/polaris_catalog.json",
    "runtime/object_paths.json",
    "cleanup/remaining_schemas.csv",
    "cleanup/remaining_objects.json",
    "cleanup/environment.json",
    "secret_scan.json",
}


def select_route_mapping(
    candidates: Iterable[tuple[str, int]],
) -> list[dict[str, Any]]:
    """Select the first 3/3/2/2 routes per bucket and assign hot-route roles."""
    by_bucket = {bucket: [] for bucket in ROUTE_BUCKET_COUNTS}
    seen_routes: set[str] = set()
    for route_id, bucket_id in candidates:
        if not re.fullmatch(r"BENCH-R\d{4}", route_id):
            raise AcceptanceError(f"invalid benchmark route ID: {route_id}")
        if route_id in seen_routes:
            raise AcceptanceError(f"duplicate benchmark route ID: {route_id}")
        if bucket_id not in by_bucket:
            raise AcceptanceError(f"invalid route bucket: {bucket_id}")
        seen_routes.add(route_id)
        by_bucket[bucket_id].append(route_id)

    mapping: list[dict[str, Any]] = []
    for bucket_id, required_count in ROUTE_BUCKET_COUNTS.items():
        routes = sorted(by_bucket[bucket_id])
        if len(routes) < required_count:
            raise AcceptanceError(
                f"bucket {bucket_id} has {len(routes)} routes, needs {required_count}"
            )
        for bucket_rank, route_id in enumerate(routes[:required_count], start=1):
            mapping.append(
                {
                    "route_id": route_id,
                    "bucket_id": bucket_id,
                    "bucket_rank": bucket_rank,
                    "is_hot": bucket_id in {0, 1} and bucket_rank == 1,
                }
            )
    assert_route_mapping(mapping)
    return mapping


def assert_route_mapping(mapping: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Validate exact bucket counts, ranks, hot routes, and representatives."""
    if len(mapping) != 10:
        raise AcceptanceError(f"route mapping has {len(mapping)} rows, expected 10")
    route_ids = [str(row.get("route_id")) for row in mapping]
    if len(set(route_ids)) != len(route_ids):
        raise AcceptanceError("route mapping contains duplicate route IDs")

    by_bucket: dict[int, list[Mapping[str, Any]]] = {
        bucket: [] for bucket in ROUTE_BUCKET_COUNTS
    }
    for row in mapping:
        bucket_id = row.get("bucket_id")
        if bucket_id not in by_bucket:
            raise AcceptanceError(f"route mapping contains invalid bucket: {bucket_id}")
        by_bucket[bucket_id].append(row)

    for bucket_id, required_count in ROUTE_BUCKET_COUNTS.items():
        rows = sorted(
            by_bucket[bucket_id],
            key=lambda row: parse_int(row.get("bucket_rank", 0), "route bucket rank"),
        )
        if len(rows) != required_count:
            raise AcceptanceError(
                f"bucket {bucket_id} has {len(rows)} selected routes, expected {required_count}"
            )
        ranks = [
            parse_int(row.get("bucket_rank", 0), "route bucket rank")
            for row in rows
        ]
        if ranks != list(range(1, required_count + 1)):
            raise AcceptanceError(f"bucket {bucket_id} has invalid ranks: {ranks}")
        for row in rows:
            rank = parse_int(row["bucket_rank"], "route bucket rank")
            expected_hot = bucket_id in {0, 1} and rank == 1
            if bool(row.get("is_hot")) != expected_hot:
                raise AcceptanceError(
                    f"route {row.get('route_id')} has an invalid hot/cold role"
                )

    hot_routes = sorted(
        (row for row in mapping if bool(row.get("is_hot"))),
        key=lambda row: parse_int(row["bucket_id"], "route bucket ID"),
    )
    if [
        parse_int(row["bucket_id"], "route bucket ID") for row in hot_routes
    ] != [0, 1]:
        raise AcceptanceError("hot routes must be the first routes in buckets 0 and 1")
    bucket_two = sorted(
        by_bucket[2],
        key=lambda row: parse_int(row["bucket_rank"], "route bucket rank"),
    )
    return {
        "hot_routes": [str(row["route_id"]) for row in hot_routes],
        "representative_hot_route": str(hot_routes[0]["route_id"]),
        "representative_cold_route": str(bucket_two[0]["route_id"]),
        "routes_by_bucket": {
            str(bucket): len(rows) for bucket, rows in by_bucket.items()
        },
    }


def group_size(dataset: str, *, peak: bool, hot: bool) -> int:
    """Return the exact row count for one day/route group."""
    if dataset == "balanced":
        return 512
    if dataset != "skewed":
        raise AcceptanceError(f"unknown benchmark dataset: {dataset}")
    if hot and peak:
        return 8_192
    if hot or peak:
        return 512
    return 32


def expected_aggregate(row_count: int) -> dict[str, int]:
    """Return exact aggregate values for a whole number of 16-row state cycles."""
    if row_count <= 0 or row_count % 16:
        raise AcceptanceError(
            f"row count must be a positive multiple of 16: {row_count}"
        )
    cycles = row_count // 16
    return {
        "package_count": row_count,
        "completed_count": cycles * 14,
        "on_time_count": cycles * 10,
        "total_delay_minutes": cycles * 300,
    }


def expected_case_aggregate(dataset: str, case: str) -> dict[str, int]:
    """Return the approved logical result for one benchmark case."""
    try:
        row_count = CASE_ROW_COUNTS[dataset][case]
    except KeyError as error:
        raise AcceptanceError(f"unknown benchmark case: {dataset}/{case}") from error
    return expected_aggregate(row_count)


def assert_case_aggregate(
    actual: Mapping[str, Any], dataset: str, case: str
) -> None:
    """Require an exact four-metric aggregate for the selected case."""
    expected = expected_case_aggregate(dataset, case)
    try:
        normalized = {
            key: parse_int(actual[key], f"{dataset}/{case} {key}") for key in expected
        }
    except (KeyError, TypeError, ValueError) as error:
        raise AcceptanceError(
            f"invalid aggregate for {dataset}/{case}: {actual}"
        ) from error
    if normalized != expected or set(actual) != set(expected):
        raise AcceptanceError(
            f"unexpected aggregate for {dataset}/{case}: {normalized} != {expected}"
        )


def expected_eligible_records(dataset: str, case: str) -> dict[str, int]:
    """Return exact eligible partition records for U/D/R/DR."""
    try:
        return dict(ELIGIBLE_RECORDS[dataset][case])
    except KeyError as error:
        raise AcceptanceError(f"unknown eligible-record case: {dataset}/{case}") from error


def assert_eligible_records(
    actual: Mapping[str, Any], dataset: str, case: str
) -> None:
    """Require the exact eligible-record matrix row for a benchmark case."""
    expected = expected_eligible_records(dataset, case)
    try:
        normalized = {
            layout: parse_int(
                actual[layout], f"{dataset}/{case}/{layout} eligible records"
            )
            for layout in LAYOUTS
        }
    except (KeyError, TypeError, ValueError) as error:
        raise AcceptanceError(
            f"invalid eligible records for {dataset}/{case}: {actual}"
        ) from error
    if normalized != expected or set(actual) != set(LAYOUTS):
        raise AcceptanceError(
            f"unexpected eligible records for {dataset}/{case}: "
            f"{normalized} != {expected}"
        )


def parse_byte_size(value: str) -> int:
    """Parse Trino's decimal B/kB/MB/GB sizes into rounded bytes."""
    match = SIZE_PATTERN.fullmatch(value.strip())
    if not match:
        raise AcceptanceError(f"unparseable byte size: {value!r}")
    try:
        bytes_value = Decimal(match.group("value")) * UNIT_FACTORS[match.group("unit")]
    except InvalidOperation as error:
        raise AcceptanceError(f"unparseable byte size: {value!r}") from error
    return bytes_value.quantize(Decimal("1"), rounding=ROUND_HALF_UP).__int__()


def decode_cli_json(raw: str) -> dict[str, Any]:
    """Decode JSON emitted as one escaped TSV field by the Trino CLI."""
    try:
        document = json.loads(codecs.decode(raw.strip(), "unicode_escape"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise AcceptanceError(f"invalid Trino JSON evidence: {error}") from error
    if not isinstance(document, dict):
        raise AcceptanceError("Trino JSON evidence root is not an object")
    return document


def flatten_plan(node: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    """Yield one distributed-plan node and all nested child nodes."""
    yield node
    children = node.get("children", [])
    if not isinstance(children, list):
        raise AcceptanceError("distributed plan children are not a list")
    for child in children:
        if not isinstance(child, dict):
            raise AcceptanceError("distributed plan child is not an object")
        yield from flatten_plan(child)


def parse_distributed_plan(raw: str, *, schema: str) -> dict[str, Any]:
    """Require exactly one task-schema Iceberg scan in distributed JSON."""
    document = decode_cli_json(raw)
    roots = [root for root in document.values() if isinstance(root, dict)]
    nodes = [node for root in roots for node in flatten_plan(root)]
    scans = [
        node
        for node in nodes
        if node.get("name") in SCAN_NAMES
        and str(node.get("descriptor", {}).get("table", "")).startswith(
            f"lakehouse:{schema}."
        )
    ]
    if len(scans) != 1:
        raise AcceptanceError(f"expected one Iceberg scan, got {len(scans)}")
    scan = scans[0]
    descriptor = scan.get("descriptor", {})
    table_anchor = str(descriptor.get("table", ""))
    constraint_match = re.search(r" constraint on \[([^\]]*)\]", table_anchor)
    constraint_columns = []
    if constraint_match and constraint_match.group(1).strip():
        constraint_columns = [
            value.strip() for value in constraint_match.group(1).split(",")
        ]
    return {
        "scan_count": 1,
        "scan_node": str(scan["name"]),
        "table_anchor": table_anchor,
        "constraint_columns": constraint_columns,
        "filter_predicate": descriptor.get("filterPredicate"),
    }


def parse_io_plan(
    raw: str,
    *,
    schema: str,
    expected_constraints: set[str],
) -> dict[str, Any]:
    """Require one task input and the expected query-column constraints in IO JSON."""
    document = decode_cli_json(raw)
    input_infos = document.get("inputTableColumnInfos", [])
    if not isinstance(input_infos, list):
        raise AcceptanceError("IO inputTableColumnInfos is not a list")
    owned = [
        item
        for item in input_infos
        if isinstance(item, dict)
        and item.get("table", {}).get("catalog") == CATALOG
        and item.get("table", {}).get("schemaTable", {}).get("schema") == schema
    ]
    if len(owned) != 1:
        raise AcceptanceError(f"expected one IO input table, got {len(owned)}")
    item = owned[0]
    constraints = item.get("constraint", {}).get("columnConstraints", [])
    if not isinstance(constraints, list):
        raise AcceptanceError("IO columnConstraints is not a list")
    columns = {
        str(constraint.get("columnName"))
        for constraint in constraints
        if isinstance(constraint, dict)
    }
    missing = expected_constraints - columns
    if missing:
        raise AcceptanceError(
            f"missing expected IO constraints: {sorted(missing)}"
        )
    estimate = item.get("estimate", {})
    output_rows = estimate.get("outputRowCount")
    if not isinstance(output_rows, (int, float)) or output_rows < 0:
        raise AcceptanceError(f"invalid IO output row estimate: {output_rows}")
    return {
        "input_table_count": 1,
        "table": item["table"],
        "constraint_columns": sorted(columns),
        "column_constraints": constraints,
        "estimate": estimate,
    }


def parse_explain_analyze(text: str, *, schema: str) -> dict[str, Any]:
    """Require one total task scan and parse its bound physical-input stats line."""
    scans = list(SCAN_PATTERN.finditer(text))
    owned = [
        match
        for match in scans
        if f"lakehouse:{schema}." in match.group("table")
    ]
    if len(owned) != 1:
        raise AcceptanceError(
            f"expected one runtime Iceberg scan, got {len(owned)}"
        )
    if len(scans) != 1:
        raise AcceptanceError(f"expected one runtime scan, got {len(scans)}")
    scan = owned[0]
    stats = RUNTIME_STATS_PATTERN.search(text[scan.end() :])
    if not stats:
        raise AcceptanceError("physical-input anchor missing after scan")
    values = stats.groupdict()
    return {
        "scan_count": 1,
        "scan_anchor": scan.group(0),
        "input_rows": parse_int(
            values["input_rows"].replace(",", ""), "runtime input rows"
        ),
        "input_size": values["input_size"],
        "filtered_pct": parse_float(values["filtered"], "runtime filtered percent"),
        "physical_input": values["physical"],
        "physical_input_bytes": parse_byte_size(values["physical"]),
        "physical_input_time": values["physical_time"],
        "splits": parse_int(values["splits"], "runtime splits"),
    }


def assert_bounds_decisions(rows: Sequence[Mapping[str, Any]]) -> None:
    """Require every layout's selected files to retain the representative target."""
    by_layout: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        layout = str(row.get("layout", ""))
        if layout not in LAYOUTS or layout in by_layout:
            raise AcceptanceError(f"invalid or duplicate bounds layout: {layout}")
        by_layout[layout] = row
    if set(by_layout) != set(LAYOUTS):
        raise AcceptanceError(
            f"bounds evidence layouts mismatch: {sorted(by_layout)}"
        )
    for layout in LAYOUTS:
        row = by_layout[layout]
        try:
            selected = parse_int(row["selected_files"], f"{layout} selected files")
            included = parse_int(
                row["bounds_include_target"], f"{layout} bounds-included files"
            )
        except (KeyError, TypeError, ValueError) as error:
            raise AcceptanceError(f"invalid bounds evidence for {layout}: {row}") from error
        no_exclusion = row.get("no_additional_file_exclusion")
        if isinstance(no_exclusion, str):
            no_exclusion = no_exclusion.lower() == "true"
        if selected <= 0 or included != selected or no_exclusion is not True:
            raise AcceptanceError(
                f"file bounds exclude representative files for {layout}: {row}"
            )


def required_final_evidence_paths() -> set[str]:
    """Return the exact 52-case evidence paths plus slice-level final evidence."""
    required = set(REQUIRED_FINAL_EVIDENCE_PATHS)
    for dataset, cases in DATASET_CASES.items():
        for case in cases:
            for layout in LAYOUTS:
                required.update(
                    f"workload/{dataset}/{case}/{layout}/{name}"
                    for name in CASE_EVIDENCE_FILES
                )
    return required


def assert_final_evidence_manifest(
    manifest: Mapping[str, Any],
    *,
    cleanup: Mapping[str, Any],
) -> None:
    """Fail closed on missing/invalid evidence or an unproven cleanup result."""
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise AcceptanceError("evidence manifest is empty or invalid")
    paths: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise AcceptanceError(f"invalid evidence manifest entry: {entry}")
        path = entry.get("path")
        size = entry.get("size")
        digest = entry.get("sha256")
        if (
            not isinstance(path, str)
            or not isinstance(size, int)
            or size < 0
            or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
        ):
            raise AcceptanceError(f"invalid evidence manifest entry: {entry}")
        if path in paths:
            raise AcceptanceError(f"duplicate evidence manifest path: {path}")
        paths.add(path)
    missing = sorted(required_final_evidence_paths() - paths)
    if missing:
        raise AcceptanceError(
            "evidence manifest lacks required partition benchmark paths: "
            + ", ".join(missing)
        )
    expected_cleanup = {
        "schema_absent": True,
        "final_prefix_empty": True,
        "preexisting_volumes_preserved": True,
        "final_compose_state": "stopped",
    }
    mismatches = {
        key: cleanup.get(key)
        for key, expected in expected_cleanup.items()
        if cleanup.get(key) != expected
    }
    if mismatches:
        raise AcceptanceError(f"partition benchmark cleanup is incomplete: {mismatches}")


class PartitioningFilePruningAcceptanceRun(AcceptanceRun):
    """Lifecycle and safety boundary for the partition benchmark slice."""

    def __init__(self, run_id: str, evidence_dir: Path) -> None:
        super().__init__(run_id, evidence_dir)
        self.ac_results = {
            ac: "NOT_RUN" for ac in PARTITIONING_FILE_PRUNING_ACS
        }
        self.negative_prefixes = {}
        self.benchmark_schema = f"{run_id}_partition_benchmark"
        self.benchmark_tables = tuple(
            f"{dataset}_{layout}"
            for dataset in DATASETS
            for layout in LAYOUTS
        )

    def run(self) -> None:
        self.preflight()
        error: Exception | None = None
        try:
            self.start_stack()
            self.assert_stack_state()
            self.assert_query_ready()
            self.assert_prefixes_absent()
            self.prefixes_owned = True
            self.run_partitioning_file_pruning_workflow()
            self.cleanup_task_data()
            self.data_cleaned = True
        except Exception as caught:  # cleanup must run after ownership is established
            error = caught
        finally:
            if (
                self.stack_started
                and self.query_ready
                and self.prefixes_owned
                and not self.data_cleaned
            ):
                try:
                    self.cleanup_task_data()
                    self.data_cleaned = True
                except Exception as cleanup_error:
                    if error is None:
                        error = cleanup_error
                    else:
                        self.write_text(
                            "cleanup/secondary_error.txt",
                            f"{type(cleanup_error).__name__}: {cleanup_error}\n",
                        )
            if self.stack_started:
                try:
                    self.stop_stack()
                except Exception as stop_error:
                    if error is None:
                        error = stop_error
                    else:
                        self.write_text(
                            "cleanup/stop_error.txt",
                            f"{type(stop_error).__name__}: {stop_error}\n",
                        )

        try:
            self.assert_environment_restored()
        except Exception as restore_error:
            if error is None:
                error = restore_error

        error = self.finalize(error)
        if error is not None:
            raise error

    def assert_prefixes_absent(self) -> None:
        rows = self.query_csv(
            "preflight/existing_schemas.csv",
            "SELECT schema_name FROM lakehouse.information_schema.schemata "
            f"WHERE schema_name = '{self.benchmark_schema}' ORDER BY schema_name",
        )
        if rows != [["schema_name"]]:
            raise AcceptanceError(
                f"benchmark schema already exists: {self.benchmark_schema}"
            )

    def run_partitioning_file_pruning_workflow(self) -> None:
        raise AcceptanceError(
            "partitioning/file-pruning behavior is not implemented yet; "
            "continue with PF-ENV-002 and PF-IMP-001"
        )

    def cleanup_task_data(self) -> None:
        result = self.capture(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "trino",
                "trino",
                "--execute",
                f'DROP SCHEMA IF EXISTS "{CATALOG}".'
                f'"{self.benchmark_schema}" CASCADE',
            ],
            None,
        )
        self.write_text(
            "cleanup/drop_schema.log",
            f"{self.benchmark_schema}: {result.stdout}{result.stderr}",
        )

        remaining_schemas = self.query_csv(
            "cleanup/remaining_schemas.csv",
            "SELECT schema_name FROM lakehouse.information_schema.schemata "
            f"WHERE schema_name = '{self.benchmark_schema}' ORDER BY schema_name",
        )
        if remaining_schemas != [["schema_name"]]:
            raise AcceptanceError(
                f"benchmark schema remains after cleanup: {remaining_schemas[1:]}"
            )

        remaining_objects = self.list_objects(
            f"warehouse/{self.benchmark_schema}/"
        )
        self.write_json("cleanup/remaining_objects.json", remaining_objects)
        if remaining_objects.get("Contents"):
            raise AcceptanceError(
                "task object paths remain after benchmark schema cleanup"
            )

    def write_summary(self, outcome: str, error: str | None) -> None:
        self.write_json_atomic(
            "acceptance_summary.json",
            {
                "run_id": self.run_id,
                "outcome": outcome,
                "started_at": self.started_at,
                "finished_at": iso_now(),
                "ac_results": self.ac_results,
                "error": error,
                "benchmark_schema": self.benchmark_schema,
                "benchmark_tables": list(self.benchmark_tables),
                "command_count": len(self.commands),
                "evidence": {
                    "commands": "commands.jsonl",
                    "generation": "generation/",
                    "layouts": "layouts/",
                    "workload": "workload/",
                    "runtime": "runtime/",
                    "cleanup": "cleanup/environment.json",
                    "secret_scan": "secret_scan.json",
                    "manifest": "evidence_manifest.json",
                },
            },
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the isolated Iceberg partitioning/file-pruning benchmark, "
            "capture evidence, and clean up only its task-owned schema and objects."
        )
    )
    parser.add_argument(
        "--run-id",
        required=True,
        help="Lowercase isolated identifier: 3-32 characters, [a-z][a-z0-9_]*.",
    )
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=DEFAULT_EVIDENCE_ROOT,
        help="Parent directory for generated evidence (default: artifacts/acceptance).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not RUN_ID_PATTERN.fullmatch(args.run_id):
        print(
            "acceptance_error: --run-id must match [a-z][a-z0-9_]{2,31}",
            file=sys.stderr,
        )
        return 2

    evidence_root = args.evidence_root
    if not evidence_root.is_absolute():
        evidence_root = ROOT / evidence_root
    evidence_dir = evidence_root.resolve() / args.run_id

    try:
        PartitioningFilePruningAcceptanceRun(args.run_id, evidence_dir).run()
    except (AcceptanceError, OSError, json.JSONDecodeError, csv.Error) as error:
        print(f"acceptance_error: {error}", file=sys.stderr)
        print(f"evidence_dir={evidence_dir}", file=sys.stderr)
        return 1

    print(
        "acceptance_ok "
        f"run_id={args.run_id} evidence_dir={evidence_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
