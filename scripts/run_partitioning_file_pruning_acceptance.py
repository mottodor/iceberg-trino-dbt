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
from datetime import date, timedelta
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
    normalize_sql,
    parse_float,
    parse_int,
)

DATASETS = ("balanced", "skewed")
LAYOUTS = ("u", "d", "r", "dr")
LAYOUT_PARTITIONING = {
    "u": (),
    "d": ("day(picked_up_at)",),
    "r": ("bucket(route_id, 4)",),
    "dr": ("day(picked_up_at)", "bucket(route_id, 4)"),
}
LAYOUT_TUPLE_COUNTS = {"u": 1, "d": 50, "r": 4, "dr": 200}
REPRESENTATIVE_BOUNDS_DAY = date(2025, 3, 30)
PARTITIONING_FILE_PRUNING_ACS = tuple(
    f"AC-{number:03d}" for number in range(21, 28)
)
ROUTE_BUCKET_COUNTS = {0: 3, 1: 3, 2: 2, 3: 2}
ROUTE_CANDIDATE_LIMIT = 128
PICKUP_START_DATE = date(2025, 3, 1)
PICKUP_DAY_COUNT = 50
PEAK_DAY_COUNT = 10
BENCHMARK_COLUMNS = (
    ("package_id", "varchar"),
    ("route_id", "varchar"),
    ("route_version_id", "varchar"),
    ("picked_up_at", "timestamp(6) with time zone"),
    ("promised_delivery_at", "timestamp(6) with time zone"),
    ("delivered_at", "timestamp(6) with time zone"),
    ("is_on_time", "boolean"),
    ("delay_minutes", "bigint"),
)
DATASET_PREFIXES = {"balanced": "BAL", "skewed": "SKW"}
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
    "generation/balanced_group_counts.csv",
    "generation/skewed_group_counts.csv",
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
    invalid_route_ids = [
        route_id
        for route_id in route_ids
        if not re.fullmatch(r"BENCH-R\d{4}", route_id)
    ]
    if invalid_route_ids:
        raise AcceptanceError(
            f"route mapping contains invalid route IDs: {invalid_route_ids}"
        )
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


def route_mapping_sql() -> str:
    """Return the pinned Iceberg bucket-aware route-selection query."""
    return f"""
        WITH candidates AS (
            SELECT
                format('BENCH-R%04d', sequential_number) AS route_id,
                {CATALOG}.system.bucket(
                    format('BENCH-R%04d', sequential_number),
                    4
                ) AS bucket_id
            FROM TABLE(sequence(start => 1, stop => {ROUTE_CANDIDATE_LIMIT}))
        ), ranked AS (
            SELECT
                route_id,
                bucket_id,
                row_number() OVER (
                    PARTITION BY bucket_id ORDER BY route_id
                ) AS bucket_rank
            FROM candidates
        )
        SELECT
            route_id,
            bucket_id,
            bucket_rank,
            bucket_id IN (0, 1) AND bucket_rank = 1 AS is_hot
        FROM ranked
        WHERE (bucket_id IN (0, 1) AND bucket_rank <= 3)
           OR (bucket_id IN (2, 3) AND bucket_rank <= 2)
        ORDER BY bucket_id, bucket_rank
    """


def parse_route_mapping_rows(rows: Sequence[Sequence[str]]) -> list[dict[str, Any]]:
    """Parse route-mapping CSV evidence and revalidate the exact contract."""
    expected_header = ["route_id", "bucket_id", "bucket_rank", "is_hot"]
    if not rows or list(rows[0]) != expected_header:
        raise AcceptanceError(f"invalid route mapping header: {rows[:1]}")
    mapping: list[dict[str, Any]] = []
    for row in rows[1:]:
        if len(row) != len(expected_header):
            raise AcceptanceError(f"invalid route mapping row: {row}")
        hot_value = row[3].lower()
        if hot_value not in {"true", "false"}:
            raise AcceptanceError(f"invalid route hot flag: {row[3]}")
        mapping.append(
            {
                "route_id": row[0],
                "bucket_id": parse_int(row[1], "route bucket ID"),
                "bucket_rank": parse_int(row[2], "route bucket rank"),
                "is_hot": hot_value == "true",
            }
        )
    assert_route_mapping(mapping)
    return mapping


def build_dataset_sql(
    dataset: str,
    *,
    schema: str,
    mapping: Sequence[Mapping[str, Any]],
) -> str:
    """Build one deterministic unpartitioned benchmark dataset CTAS."""
    if dataset not in DATASET_PREFIXES:
        raise AcceptanceError(f"unknown benchmark dataset: {dataset}")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", schema):
        raise AcceptanceError(f"invalid benchmark schema: {schema}")
    assert_route_mapping(mapping)
    routes = sorted(
        mapping,
        key=lambda row: (
            parse_int(row["bucket_id"], "route bucket ID"),
            parse_int(row["bucket_rank"], "route bucket rank"),
        ),
    )
    route_values = ",\n                ".join(
        f"('{row['route_id']}', {'TRUE' if bool(row['is_hot']) else 'FALSE'})"
        for row in routes
    )
    if dataset == "balanced":
        group_expression = "BIGINT '512'"
        maximum_position = 511
    else:
        group_expression = """
            CASE
                WHEN is_hot AND day_number < 10 THEN BIGINT '8192'
                WHEN is_hot OR day_number < 10 THEN BIGINT '512'
                ELSE BIGINT '32'
            END
        """.strip()
        maximum_position = 8_191
    prefix = DATASET_PREFIXES[dataset]
    return f"""
        CREATE TABLE \"{CATALOG}\".\"{schema}\".\"{dataset}_u\" AS
        WITH routes(route_id, is_hot) AS (
            VALUES {route_values}
        ), groups AS (
            SELECT
                day_number,
                route_id,
                is_hot,
                {group_expression} AS group_size
            FROM TABLE(sequence(start => 0, stop => 49)) AS days(day_number)
            CROSS JOIN routes
        ), generated AS (
            SELECT
                concat(
                    '{prefix}-D',
                    lpad(cast(day_number + 1 AS varchar), 2, '0'),
                    '-', route_id, '-P',
                    lpad(cast(position AS varchar), 4, '0')
                ) AS package_id,
                route_id,
                concat(route_id, '-V1') AS route_version_id,
                TIMESTAMP '2025-03-01 00:00:00 UTC'
                    + day_number * INTERVAL '1' DAY
                    + (position % 1440) * INTERVAL '1' MINUTE AS picked_up_at,
                position % 16 AS cycle_position
            FROM groups
            CROSS JOIN TABLE(
                sequence(start => 0, stop => {maximum_position})
            ) AS positions(position)
            WHERE position < group_size
        ), promised AS (
            SELECT
                *,
                picked_up_at + INTERVAL '48' HOUR AS promised_delivery_at
            FROM generated
        ), stated AS (
            SELECT
                *,
                CASE
                    WHEN cycle_position <= 1 THEN CAST(NULL AS BIGINT)
                    WHEN cycle_position <= 11 THEN BIGINT '0'
                    ELSE (cycle_position - 11) * BIGINT '30'
                END AS delay_minutes
            FROM promised
        )
        SELECT
            package_id,
            route_id,
            route_version_id,
            picked_up_at,
            promised_delivery_at,
            CASE
                WHEN delay_minutes IS NULL
                    THEN CAST(NULL AS TIMESTAMP(6) WITH TIME ZONE)
                ELSE promised_delivery_at
                    + delay_minutes * INTERVAL '1' MINUTE
            END AS delivered_at,
            CASE
                WHEN delay_minutes IS NULL THEN CAST(NULL AS BOOLEAN)
                ELSE delay_minutes = 0
            END AS is_on_time,
            delay_minutes
        FROM stated
    """


def qualified_benchmark_table(schema: str, dataset: str, layout: str) -> str:
    """Return one validated quoted benchmark table identity."""
    if not re.fullmatch(r"[a-z][a-z0-9_]*", schema):
        raise AcceptanceError(f"invalid benchmark schema: {schema}")
    if dataset not in DATASETS:
        raise AcceptanceError(f"unknown benchmark dataset: {dataset}")
    if layout not in LAYOUTS:
        raise AcceptanceError(f"unknown benchmark layout: {layout}")
    return f'"{CATALOG}"."{schema}"."{dataset}_{layout}"'


def build_layout_sql(dataset: str, *, layout: str, schema: str) -> str:
    """Build one unsorted physical layout from the validated U control."""
    if layout == "u":
        raise AcceptanceError("the U layout is created by the dataset generator")
    target = qualified_benchmark_table(schema, dataset, layout)
    source = qualified_benchmark_table(schema, dataset, "u")
    transforms = LAYOUT_PARTITIONING[layout]
    partitioning = ", ".join(f"'{value}'" for value in transforms)
    columns = ",\n            ".join(name for name, _ in BENCHMARK_COLUMNS)
    return f"""
        CREATE TABLE {target}
        WITH (
            format = 'PARQUET',
            partitioning = ARRAY[{partitioning}]
        ) AS
        SELECT
            {columns}
        FROM {source}
    """


def parse_csv_dict_rows(
    rows: Sequence[Sequence[str]],
    *,
    expected_header: Sequence[str],
    label: str,
) -> list[dict[str, str]]:
    """Parse strict CSV evidence rows into dictionaries."""
    header = list(expected_header)
    if not rows or list(rows[0]) != header:
        raise AcceptanceError(f"invalid {label} header: {rows[:1]}")
    parsed: list[dict[str, str]] = []
    for row in rows[1:]:
        if len(row) != len(header):
            raise AcceptanceError(f"invalid {label} row: {row}")
        parsed.append(dict(zip(header, row, strict=True)))
    return parsed


def assert_layout_table_listing(rows: Sequence[Sequence[str]]) -> None:
    """Require exactly the approved eight benchmark table names."""
    parsed = parse_csv_dict_rows(
        rows,
        expected_header=["table_name"],
        label="benchmark table listing",
    )
    actual = [row["table_name"] for row in parsed]
    expected = sorted(
        f"{dataset}_{layout}" for dataset in DATASETS for layout in LAYOUTS
    )
    if actual != expected:
        raise AcceptanceError(f"unexpected benchmark table listing: {actual}")


def assert_show_create_layout(
    rows: Sequence[Sequence[str]],
    *,
    schema: str,
    dataset: str,
    layout: str,
) -> dict[str, Any]:
    """Require the exact table identity and partition transforms without sorting."""
    if len(rows) != 2 or list(rows[0]) != ["Create Table"] or len(rows[1]) != 1:
        raise AcceptanceError(f"invalid SHOW CREATE evidence: {rows}")
    ddl = rows[1][0]
    normalized = re.sub(r"\s+", " ", ddl).strip().lower()
    expected_table = f"create table {CATALOG}.{schema}.{dataset}_{layout} ("
    if not normalized.startswith(expected_table):
        raise AcceptanceError(f"unexpected SHOW CREATE table identity: {ddl}")
    if "format = 'parquet'" not in normalized:
        raise AcceptanceError(f"non-Parquet benchmark table: {dataset}_{layout}")
    if "sorted_by" in normalized or "order by" in normalized:
        raise AcceptanceError(f"sorted benchmark layout is forbidden: {dataset}_{layout}")
    partition_match = re.search(r"partitioning\s*=\s*array\[([^\]]*)\]", normalized)
    actual_partitioning = (
        tuple(re.findall(r"'([^']+)'", partition_match.group(1)))
        if partition_match
        else ()
    )
    expected_partitioning = LAYOUT_PARTITIONING[layout]
    if actual_partitioning != expected_partitioning:
        raise AcceptanceError(
            f"unexpected {dataset}_{layout} partitioning: "
            f"{actual_partitioning} != {expected_partitioning}"
        )
    return {
        "table": f"{dataset}_{layout}",
        "partitioning": list(actual_partitioning),
    }


def layout_contract_sql(schema: str, dataset: str) -> str:
    """Return one four-layout exact aggregate contract query."""
    branches = []
    for layout in LAYOUTS:
        table = qualified_benchmark_table(schema, dataset, layout)
        branches.append(
            f"""
            SELECT
                '{layout}' AS layout,
                count(*) AS row_count,
                count(DISTINCT package_id) AS unique_packages,
                count(DISTINCT route_id) AS route_count,
                count(DISTINCT CAST(picked_up_at AS date)) AS day_count,
                count_if(delivered_at IS NOT NULL) AS completed_count,
                count_if(is_on_time) AS on_time_count,
                coalesce(sum(delay_minutes), BIGINT '0') AS total_delay_minutes
            FROM {table}
            """
        )
    return " UNION ALL ".join(branches) + " ORDER BY layout"


def assert_layout_contract_rows(
    rows: Sequence[Sequence[str]], *, dataset: str
) -> dict[str, dict[str, int]]:
    """Require exact row and aggregate contracts for all four layouts."""
    header = [
        "layout",
        "row_count",
        "unique_packages",
        "route_count",
        "day_count",
        "completed_count",
        "on_time_count",
        "total_delay_minutes",
    ]
    parsed = parse_csv_dict_rows(
        rows,
        expected_header=header,
        label=f"{dataset} layout contract",
    )
    by_layout: dict[str, dict[str, int]] = {}
    expected = {
        "row_count": 256_000,
        "unique_packages": 256_000,
        "route_count": 10,
        "day_count": 50,
        "completed_count": 224_000,
        "on_time_count": 160_000,
        "total_delay_minutes": 4_800_000,
    }
    for row in parsed:
        layout = row.pop("layout")
        if layout not in LAYOUTS or layout in by_layout:
            raise AcceptanceError(f"invalid or duplicate {dataset} layout: {layout}")
        actual = {
            key: parse_int(value, f"{dataset}/{layout} {key}")
            for key, value in row.items()
        }
        if actual != expected:
            raise AcceptanceError(
                f"unexpected {dataset}/{layout} contract: {actual} != {expected}"
            )
        by_layout[layout] = actual
    if set(by_layout) != set(LAYOUTS):
        raise AcceptanceError(
            f"{dataset} layout contract coverage mismatch: {sorted(by_layout)}"
        )
    return by_layout


def reconciliation_sql(schema: str, dataset: str) -> str:
    """Return bidirectional full-row reconciliation against the U control."""
    control = qualified_benchmark_table(schema, dataset, "u")
    branches = []
    for layout in LAYOUTS[1:]:
        table = qualified_benchmark_table(schema, dataset, layout)
        branches.append(
            f"""
            SELECT
                '{layout}' AS layout,
                (SELECT count(*) FROM (TABLE {control} EXCEPT TABLE {table}))
                    AS u_minus_layout,
                (SELECT count(*) FROM (TABLE {table} EXCEPT TABLE {control}))
                    AS layout_minus_u
            """
        )
    return " UNION ALL ".join(branches) + " ORDER BY layout"


def assert_reconciliation_rows(
    rows: Sequence[Sequence[str]], *, dataset: str
) -> dict[str, dict[str, int]]:
    """Require zero bidirectional row differences for D/R/DR."""
    header = ["layout", "u_minus_layout", "layout_minus_u"]
    parsed = parse_csv_dict_rows(
        rows,
        expected_header=header,
        label=f"{dataset} reconciliation",
    )
    by_layout: dict[str, dict[str, int]] = {}
    for row in parsed:
        layout = row["layout"]
        if layout not in LAYOUTS[1:] or layout in by_layout:
            raise AcceptanceError(
                f"invalid or duplicate {dataset} reconciliation layout: {layout}"
            )
        counts = {
            key: parse_int(row[key], f"{dataset}/{layout} {key}")
            for key in header[1:]
        }
        if any(counts.values()):
            raise AcceptanceError(
                f"{dataset}/{layout} differs from U control: {counts}"
            )
        by_layout[layout] = counts
    if set(by_layout) != set(LAYOUTS[1:]):
        raise AcceptanceError(
            f"{dataset} reconciliation coverage mismatch: {sorted(by_layout)}"
        )
    return by_layout


def topology_sql(schema: str, dataset: str) -> str:
    """Return aggregate partition/file topology for all four layouts."""
    branches = []
    for layout in LAYOUTS:
        table = qualified_benchmark_table(schema, dataset, layout)
        metadata = table[:-1] + '$partitions"'
        branches.append(
            f"""
            SELECT
                '{layout}' AS layout,
                count(*) AS tuple_count,
                coalesce(sum(record_count), BIGINT '0') AS record_count,
                coalesce(min(file_count), BIGINT '0') AS min_files_per_tuple,
                coalesce(sum(file_count), BIGINT '0') AS file_count,
                coalesce(min(record_count), BIGINT '0') AS min_records_per_tuple,
                coalesce(max(record_count), BIGINT '0') AS max_records_per_tuple
            FROM {metadata}
            """
        )
    return " UNION ALL ".join(branches) + " ORDER BY layout"


def assert_topology_rows(
    rows: Sequence[Sequence[str]], *, dataset: str
) -> dict[str, dict[str, int]]:
    """Require 1/50/4/200 non-empty tuples and complete records."""
    header = [
        "layout",
        "tuple_count",
        "record_count",
        "min_files_per_tuple",
        "file_count",
        "min_records_per_tuple",
        "max_records_per_tuple",
    ]
    parsed = parse_csv_dict_rows(
        rows,
        expected_header=header,
        label=f"{dataset} topology",
    )
    by_layout: dict[str, dict[str, int]] = {}
    for row in parsed:
        layout = row.pop("layout")
        if layout not in LAYOUTS or layout in by_layout:
            raise AcceptanceError(f"invalid or duplicate {dataset} topology: {layout}")
        actual = {
            key: parse_int(value, f"{dataset}/{layout} {key}")
            for key, value in row.items()
        }
        if (
            actual["tuple_count"] != LAYOUT_TUPLE_COUNTS[layout]
            or actual["record_count"] != 256_000
            or actual["min_files_per_tuple"] < 1
            or actual["file_count"] < actual["tuple_count"]
            or actual["min_records_per_tuple"] < 1
            or actual["max_records_per_tuple"] < actual["min_records_per_tuple"]
        ):
            raise AcceptanceError(
                f"unexpected {dataset}/{layout} topology: {actual}"
            )
        by_layout[layout] = actual
    if set(by_layout) != set(LAYOUTS):
        raise AcceptanceError(
            f"{dataset} topology coverage mismatch: {sorted(by_layout)}"
        )
    return by_layout


def assert_file_inventory_rows(
    rows: Sequence[Sequence[str]],
    *,
    schema: str,
    dataset: str,
    layout: str,
) -> dict[str, int]:
    """Require complete positive Parquet data-file metadata and typed bounds."""
    header = [
        "content",
        "file_path",
        "record_count",
        "file_format",
        "file_size_in_bytes",
        "lower_bounds",
        "upper_bounds",
    ]
    parsed = parse_csv_dict_rows(
        rows,
        expected_header=header,
        label=f"{dataset}/{layout} file inventory",
    )
    if not parsed:
        raise AcceptanceError(f"empty {dataset}/{layout} file inventory")
    path_anchor = f"/warehouse/{schema}/{dataset}_{layout}-"
    record_count = 0
    total_size = 0
    for row in parsed:
        if (
            row["content"] != "0"
            or row["file_format"] != "PARQUET"
            or path_anchor not in row["file_path"]
            or not row["lower_bounds"]
            or not row["upper_bounds"]
        ):
            raise AcceptanceError(
                f"invalid {dataset}/{layout} data-file evidence: {row}"
            )
        record_count += parse_int(
            row["record_count"], f"{dataset}/{layout} file records"
        )
        file_size = parse_int(
            row["file_size_in_bytes"], f"{dataset}/{layout} file size"
        )
        if file_size <= 0:
            raise AcceptanceError(f"non-positive {dataset}/{layout} file size")
        total_size += file_size
    if record_count != 256_000:
        raise AcceptanceError(
            f"unexpected {dataset}/{layout} file records: {record_count}"
        )
    return {
        "file_count": len(parsed),
        "record_count": record_count,
        "total_size_in_bytes": total_size,
    }


def representative_bounds_sql(
    schema: str,
    dataset: str,
    *,
    route_id: str,
    route_bucket: int,
) -> str:
    """Return one bounds/no-extra-file-exclusion query for all layouts."""
    if not re.fullmatch(r"BENCH-R\d{4}", route_id):
        raise AcceptanceError(f"invalid representative route: {route_id}")
    if route_bucket not in ROUTE_BUCKET_COUNTS:
        raise AcceptanceError(f"invalid representative route bucket: {route_bucket}")
    day_start = REPRESENTATIVE_BOUNDS_DAY.isoformat()
    day_end = (REPRESENTATIVE_BOUNDS_DAY + timedelta(days=1)).isoformat()
    branches = []
    for layout in LAYOUTS:
        table = qualified_benchmark_table(schema, dataset, layout)
        metadata = table[:-1] + '$files"'
        filters = ["content = 0"]
        if layout in {"d", "dr"}:
            filters.append(f"file_path LIKE '%/picked_up_at_day={day_start}/%'")
        if layout in {"r", "dr"}:
            filters.append(f"file_path LIKE '%/route_id_bucket={route_bucket}/%'")
        where = " AND ".join(filters)
        includes_target = f"""
            lower_bounds."4" < TIMESTAMP '{day_end} 00:00:00 UTC'
            AND upper_bounds."4" >= TIMESTAMP '{day_start} 00:00:00 UTC'
            AND lower_bounds."2" <= '{route_id}'
            AND upper_bounds."2" >= '{route_id}'
        """
        branches.append(
            f"""
            SELECT
                '{layout}' AS layout,
                count(*) AS selected_files,
                count_if({includes_target}) AS bounds_include_target,
                count(*) > 0 AND count(*) = count_if({includes_target})
                    AS no_additional_file_exclusion
            FROM {metadata}
            WHERE {where}
            """
        )
    return " UNION ALL ".join(branches) + " ORDER BY layout"


def validate_residual_object_keys(
    inventory: Mapping[str, Any],
    remaining: Mapping[str, Any],
    *,
    prefix: str,
) -> list[str]:
    """Return exact owned residual keys or fail closed on cleanup scope."""
    inventory_contents = inventory.get("Contents") or []
    remaining_contents = remaining.get("Contents") or []
    if not isinstance(inventory_contents, list) or not isinstance(
        remaining_contents, list
    ):
        raise AcceptanceError("invalid object inventory shape")
    inventory_keys: set[str] = set()
    for item in inventory_contents:
        key = item.get("Key") if isinstance(item, dict) else None
        if not isinstance(key, str):
            raise AcceptanceError("invalid object inventory entry")
        inventory_keys.add(key)
    residual_keys: list[str] = []
    for item in remaining_contents:
        key = item.get("Key") if isinstance(item, dict) else None
        if not isinstance(key, str):
            raise AcceptanceError("invalid residual object listing")
        residual_keys.append(key)
    if len(set(residual_keys)) != len(residual_keys):
        raise AcceptanceError("duplicate residual object key")
    unsafe = [
        key
        for key in residual_keys
        if not key.startswith(prefix) or key not in inventory_keys
    ]
    if unsafe:
        raise AcceptanceError(f"residual object ownership mismatch: {unsafe[:3]}")
    return sorted(residual_keys)


def assert_benchmark_schema(rows: Sequence[Sequence[str]]) -> None:
    """Require the exact eight-column Trino schema for one benchmark table."""
    expected_header = ["Column", "Type", "Extra", "Comment"]
    if not rows or list(rows[0]) != expected_header:
        raise AcceptanceError(f"invalid benchmark schema header: {rows[:1]}")
    actual = [(row[0], row[1]) for row in rows[1:] if len(row) == 4]
    if actual != list(BENCHMARK_COLUMNS) or len(rows) != len(BENCHMARK_COLUMNS) + 1:
        raise AcceptanceError(f"unexpected benchmark schema: {actual}")


def assert_group_contract_rows(
    rows: Sequence[Sequence[str]],
    *,
    dataset: str,
    mapping: Sequence[Mapping[str, Any]],
) -> None:
    """Require every day/route group to match independent size/state expectations."""
    expected_header = [
        "pickup_day",
        "route_id",
        "package_count",
        "completed_count",
        "on_time_count",
        "total_delay_minutes",
    ]
    if not rows or list(rows[0]) != expected_header:
        raise AcceptanceError(f"invalid {dataset} group-count header: {rows[:1]}")
    mapping_summary = assert_route_mapping(mapping)
    hot_routes = set(mapping_summary["hot_routes"])
    route_ids = {str(row["route_id"]) for row in mapping}
    expected_keys = {
        (PICKUP_START_DATE + timedelta(days=day_number), route_id)
        for day_number in range(PICKUP_DAY_COUNT)
        for route_id in route_ids
    }
    actual_keys: set[tuple[date, str]] = set()
    for row in rows[1:]:
        if len(row) != len(expected_header):
            raise AcceptanceError(f"invalid {dataset} group-count row: {row}")
        pickup_day = date.fromisoformat(row[0])
        route_id = row[1]
        key = (pickup_day, route_id)
        if key in actual_keys:
            raise AcceptanceError(f"duplicate {dataset} group: {key}")
        actual_keys.add(key)
        expected = expected_aggregate(
            group_size(
                dataset,
                peak=pickup_day < PICKUP_START_DATE + timedelta(days=PEAK_DAY_COUNT),
                hot=route_id in hot_routes,
            )
        )
        actual = {
            name: parse_int(value, f"{dataset}/{pickup_day}/{route_id} {name}")
            for name, value in zip(expected, row[2:], strict=True)
        }
        if actual != expected:
            raise AcceptanceError(
                f"unexpected {dataset} group aggregate for {key}: "
                f"{actual} != {expected}"
            )
    if actual_keys != expected_keys:
        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)
        raise AcceptanceError(
            f"{dataset} group coverage mismatch; missing={missing[:3]}, extra={extra[:3]}"
        )


def assert_dataset_contract_row(actual: Mapping[str, Any], dataset: str) -> None:
    """Require exact dataset cardinality, aggregate and formula assertions."""
    if dataset not in DATASET_PREFIXES:
        raise AcceptanceError(f"unknown benchmark dataset: {dataset}")
    expected = {
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
    try:
        normalized = {
            key: parse_int(actual[key], f"{dataset} {key}") for key in expected
        }
    except (KeyError, TypeError, ValueError) as error:
        raise AcceptanceError(
            f"invalid {dataset} dataset contract: {actual}"
        ) from error
    if normalized != expected or set(actual) != set(expected):
        raise AcceptanceError(
            f"unexpected {dataset} dataset contract: {normalized} != {expected}"
        )


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
        self.task_object_inventory: dict[str, Any] = {"Contents": []}

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
        self.execute_sql(
            "generation/create_schema.log",
            f'CREATE SCHEMA "{CATALOG}"."{self.benchmark_schema}"',
        )
        mapping_rows = self.query_csv(
            "generation/route_mapping.csv",
            route_mapping_sql(),
        )
        mapping = parse_route_mapping_rows(mapping_rows)
        self.write_json(
            "generation/route_mapping_summary.json",
            assert_route_mapping(mapping),
        )

        generation_summary: dict[str, Any] = {}
        for dataset in DATASETS:
            sql = build_dataset_sql(
                dataset,
                schema=self.benchmark_schema,
                mapping=mapping,
            )
            self.write_text(f"generation/create_{dataset}_u.sql", normalize_sql(sql))
            self.execute_sql(f"generation/create_{dataset}_u.log", sql)

            schema_rows = self.query_csv(
                f"generation/{dataset}_schema.csv",
                f'DESCRIBE "{CATALOG}"."{self.benchmark_schema}"."{dataset}_u"',
            )
            assert_benchmark_schema(schema_rows)

            group_rows = self.query_csv(
                f"generation/{dataset}_group_counts.csv",
                f"""
                SELECT
                    CAST(picked_up_at AS date) AS pickup_day,
                    route_id,
                    count(*) AS package_count,
                    count_if(delivered_at IS NOT NULL) AS completed_count,
                    count_if(is_on_time) AS on_time_count,
                    coalesce(sum(delay_minutes), BIGINT '0') AS total_delay_minutes
                FROM "{CATALOG}"."{self.benchmark_schema}"."{dataset}_u"
                GROUP BY 1, 2
                ORDER BY 1, 2
                """,
            )
            assert_group_contract_rows(
                group_rows,
                dataset=dataset,
                mapping=mapping,
            )

            contract_rows = self.query_csv(
                f"generation/{dataset}_contract.csv",
                self.dataset_contract_sql(dataset),
            )
            if len(contract_rows) != 2:
                raise AcceptanceError(
                    f"{dataset} contract returned {len(contract_rows) - 1} rows"
                )
            contract = dict(zip(contract_rows[0], contract_rows[1], strict=True))
            assert_dataset_contract_row(contract, dataset)
            generation_summary[dataset] = {
                key: parse_int(value, f"{dataset} {key}")
                for key, value in contract.items()
            }

        mapping_summary = assert_route_mapping(mapping)
        self.write_json(
            "generation/generation_summary.json",
            {
                "route_mapping": mapping_summary,
                "datasets": generation_summary,
            },
        )
        self.ac_results["AC-022"] = "PASS"

        for dataset in DATASETS:
            for layout in LAYOUTS[1:]:
                sql = build_layout_sql(
                    dataset,
                    layout=layout,
                    schema=self.benchmark_schema,
                )
                self.write_text(
                    f"layouts/{dataset}/{layout}/create.sql", normalize_sql(sql)
                )
                self.execute_sql(
                    f"layouts/{dataset}/{layout}/create.log",
                    sql,
                )

        table_rows = self.query_csv(
            "layouts/table_listing.csv",
            "SELECT table_name FROM lakehouse.information_schema.tables "
            f"WHERE table_schema = '{self.benchmark_schema}' ORDER BY table_name",
        )
        assert_layout_table_listing(table_rows)

        layout_summary: dict[str, Any] = {}
        representative_route = str(mapping_summary["representative_cold_route"])
        representative_bucket = next(
            parse_int(row["bucket_id"], "representative route bucket")
            for row in mapping
            if row["route_id"] == representative_route
        )
        for dataset in DATASETS:
            dataset_summary: dict[str, Any] = {"layouts": {}}
            for layout in LAYOUTS:
                table = qualified_benchmark_table(
                    self.benchmark_schema, dataset, layout
                )
                schema_rows = self.query_csv(
                    f"layouts/{dataset}/{layout}/schema.csv",
                    f"DESCRIBE {table}",
                )
                assert_benchmark_schema(schema_rows)
                show_create_rows = self.query_csv(
                    f"layouts/{dataset}/{layout}/show_create.csv",
                    f"SHOW CREATE TABLE {table}",
                )
                show_create = assert_show_create_layout(
                    show_create_rows,
                    schema=self.benchmark_schema,
                    dataset=dataset,
                    layout=layout,
                )
                metadata = table[:-1] + '$files"'
                file_rows = self.query_csv(
                    f"layouts/{dataset}/{layout}/files.csv",
                    "SELECT content, file_path, record_count, file_format, "
                    "file_size_in_bytes, lower_bounds, upper_bounds "
                    f"FROM {metadata} WHERE content = 0 ORDER BY file_path",
                )
                file_summary = assert_file_inventory_rows(
                    file_rows,
                    schema=self.benchmark_schema,
                    dataset=dataset,
                    layout=layout,
                )
                partitions = table[:-1] + '$partitions"'
                self.query_csv(
                    f"layouts/{dataset}/{layout}/partitions.csv",
                    f"SELECT * FROM {partitions}",
                )
                dataset_summary["layouts"][layout] = {
                    **show_create,
                    **file_summary,
                }

            contract_rows = self.query_csv(
                f"layouts/{dataset}/contract.csv",
                layout_contract_sql(self.benchmark_schema, dataset),
            )
            dataset_summary["contract"] = assert_layout_contract_rows(
                contract_rows, dataset=dataset
            )
            reconciliation_rows = self.query_csv(
                f"layouts/{dataset}/reconciliation.csv",
                reconciliation_sql(self.benchmark_schema, dataset),
            )
            dataset_summary["reconciliation"] = assert_reconciliation_rows(
                reconciliation_rows, dataset=dataset
            )
            topology_rows = self.query_csv(
                f"layouts/{dataset}/topology.csv",
                topology_sql(self.benchmark_schema, dataset),
            )
            dataset_summary["topology"] = assert_topology_rows(
                topology_rows, dataset=dataset
            )
            bounds_rows = self.query_csv(
                f"layouts/{dataset}/representative_bounds.csv",
                representative_bounds_sql(
                    self.benchmark_schema,
                    dataset,
                    route_id=representative_route,
                    route_bucket=representative_bucket,
                ),
            )
            bounds = parse_csv_dict_rows(
                bounds_rows,
                expected_header=[
                    "layout",
                    "selected_files",
                    "bounds_include_target",
                    "no_additional_file_exclusion",
                ],
                label=f"{dataset} representative bounds",
            )
            assert_bounds_decisions(bounds)
            dataset_summary["representative_bounds"] = bounds
            layout_summary[dataset] = dataset_summary

        self.write_json(
            "layouts/summary.json",
            {
                "representative_day": REPRESENTATIVE_BOUNDS_DAY.isoformat(),
                "representative_route": representative_route,
                "representative_route_bucket": representative_bucket,
                "datasets": layout_summary,
            },
        )
        self.ac_results["AC-023"] = "PASS"
        raise AcceptanceError(
            "partitioning/file-pruning workload checks are incomplete: "
            "continue with PF-IMP-003"
        )

    def execute_sql(self, relative_path: str, sql: str) -> None:
        self.capture(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "trino",
                "trino",
                "--execute",
                normalize_sql(sql),
            ],
            relative_path,
        )

    def dataset_contract_sql(self, dataset: str) -> str:
        if dataset not in DATASET_PREFIXES:
            raise AcceptanceError(f"unknown benchmark dataset: {dataset}")
        prefix = DATASET_PREFIXES[dataset]
        table = f'"{CATALOG}"."{self.benchmark_schema}"."{dataset}_u"'
        return f"""
            WITH decoded AS (
                SELECT
                    *,
                    CAST(
                        regexp_extract(package_id, '^{prefix}-D([0-9]{{2}})-', 1)
                        AS BIGINT
                    ) - 1 AS day_number,
                    CAST(
                        regexp_extract(package_id, '-P([0-9]+)$', 1)
                        AS BIGINT
                    ) AS position
                FROM {table}
            ), checked AS (
                SELECT
                    *,
                    position % 16 AS cycle_position
                FROM decoded
            )
            SELECT
                count(*) AS row_count,
                count(DISTINCT package_id) AS unique_packages,
                count(DISTINCT route_id) AS route_count,
                count(DISTINCT CAST(picked_up_at AS date)) AS day_count,
                count_if(delivered_at IS NOT NULL) AS completed_count,
                count_if(is_on_time) AS on_time_count,
                coalesce(sum(delay_minutes), BIGINT '0') AS total_delay_minutes,
                count_if(
                    package_id IS NULL
                    OR route_id IS NULL
                    OR route_version_id IS NULL
                    OR picked_up_at IS NULL
                    OR promised_delivery_at IS NULL
                ) AS not_null_violations,
                count_if(
                    route_version_id IS DISTINCT FROM concat(route_id, '-V1')
                ) AS route_version_violations,
                count_if(
                    picked_up_at IS DISTINCT FROM
                        TIMESTAMP '2025-03-01 00:00:00 UTC'
                        + day_number * INTERVAL '1' DAY
                        + (position % 1440) * INTERVAL '1' MINUTE
                ) AS pickup_formula_violations,
                count_if(
                    promised_delivery_at IS DISTINCT FROM
                        picked_up_at + INTERVAL '48' HOUR
                ) AS sla_violations,
                count_if(
                    CASE
                        WHEN cycle_position <= 1 THEN
                            delivered_at IS NOT NULL
                            OR is_on_time IS NOT NULL
                            OR delay_minutes IS NOT NULL
                        WHEN cycle_position <= 11 THEN
                            delivered_at IS DISTINCT FROM promised_delivery_at
                            OR is_on_time IS DISTINCT FROM TRUE
                            OR delay_minutes IS DISTINCT FROM BIGINT '0'
                        ELSE
                            delivered_at IS DISTINCT FROM
                                promised_delivery_at
                                + (cycle_position - 11) * BIGINT '30'
                                    * INTERVAL '1' MINUTE
                            OR is_on_time IS DISTINCT FROM FALSE
                            OR delay_minutes IS DISTINCT FROM
                                (cycle_position - 11) * BIGINT '30'
                    END
                ) AS state_violations
            FROM checked
        """

    def delete_owned_object_keys(self, keys: Sequence[str]) -> None:
        """Delete only exact task-owned residual keys in AWS API batches."""
        batch_size = 1000
        summaries = []
        for batch_number, start in enumerate(range(0, len(keys), batch_size), start=1):
            batch = list(keys[start : start + batch_size])
            payload = json.dumps(
                {"Objects": [{"Key": key} for key in batch], "Quiet": False},
                separators=(",", ":"),
            )
            result = self.capture(
                [
                    "docker",
                    "compose",
                    "run",
                    "--rm",
                    "--no-deps",
                    "--entrypoint",
                    "aws",
                    "bucket-setup",
                    "s3api",
                    "delete-objects",
                    "--bucket",
                    "iceberg-trino-dbt",
                    "--delete",
                    payload,
                    "--output",
                    "json",
                ],
                f"cleanup/delete_objects_{batch_number}.json",
            )
            try:
                response = json.loads(result.stdout or "{}")
            except json.JSONDecodeError as error:
                raise AcceptanceError(
                    "invalid RustFS delete-objects response"
                ) from error
            if not isinstance(response, dict):
                raise AcceptanceError("invalid RustFS delete-objects response")
            errors = response.get("Errors") or []
            if errors:
                raise AcceptanceError(
                    f"RustFS residual-object deletion errors: {errors[:3]}"
                )
            summaries.append(
                {
                    "batch": batch_number,
                    "requested": len(batch),
                    "deleted": len(response.get("Deleted") or []),
                }
            )
        self.write_json(
            "cleanup/delete_objects_summary.json",
            {"requested": len(keys), "batches": summaries},
        )

    def cleanup_task_data(self) -> None:
        prefix = f"warehouse/{self.benchmark_schema}/"
        self.task_object_inventory = self.list_objects(prefix)
        self.write_json(
            "cleanup/pre_drop_object_inventory.json", self.task_object_inventory
        )
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

        remaining_objects = self.list_objects(prefix)
        residual_keys = validate_residual_object_keys(
            self.task_object_inventory,
            remaining_objects,
            prefix=prefix,
        )
        if residual_keys:
            self.delete_owned_object_keys(residual_keys)
            remaining_objects = self.list_objects(prefix)
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
