#!/usr/bin/env python3
"""Validate and idempotently load deterministic logistics fixtures into Trino."""

from __future__ import annotations

import argparse
import csv
import importlib
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "hubs": (
        "fixture_row_id",
        "batch_id",
        "hub_code",
        "hub_name",
        "longitude",
        "latitude",
    ),
    "packages": (
        "fixture_row_id",
        "batch_id",
        "package_id",
        "shipment_id",
        "route_id",
    ),
    "route_plan_changes": (
        "fixture_row_id",
        "batch_id",
        "route_id",
        "route_version_id",
        "effective_at",
        "planned_duration_hours",
        "sla_duration_hours",
    ),
    "route_checkpoints": (
        "fixture_row_id",
        "batch_id",
        "route_version_id",
        "checkpoint_seq",
        "hub_code",
    ),
    "tracking_events": (
        "fixture_row_id",
        "batch_id",
        "event_id",
        "package_id",
        "event_type",
        "event_at",
        "received_at",
        "hub_code",
        "longitude",
        "latitude",
    ),
}

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
NEGATIVE_SCENARIOS = (
    "conflicting_payload",
    "departure_without_arrival",
    "repeated_arrival",
)


@dataclass(frozen=True)
class FixtureFile:
    scenario: str
    batch: str
    table: str
    relative_path: str


FIXTURE_FILES: tuple[FixtureFile, ...] = (
    FixtureFile("baseline", "batch_1", "hubs", "baseline/batch_1/hubs.csv"),
    FixtureFile("baseline", "batch_1", "packages", "baseline/batch_1/packages.csv"),
    FixtureFile(
        "baseline",
        "batch_1",
        "route_plan_changes",
        "baseline/batch_1/route_plan_changes.csv",
    ),
    FixtureFile(
        "baseline",
        "batch_1",
        "route_checkpoints",
        "baseline/batch_1/route_checkpoints.csv",
    ),
    FixtureFile(
        "baseline",
        "batch_1",
        "tracking_events",
        "baseline/batch_1/tracking_events.csv",
    ),
    FixtureFile(
        "baseline",
        "batch_2",
        "tracking_events",
        "baseline/batch_2/tracking_events.csv",
    ),
    FixtureFile(
        "conflicting_payload",
        "negative",
        "tracking_events",
        "negative/conflicting_payload/tracking_events.csv",
    ),
    FixtureFile(
        "departure_without_arrival",
        "negative",
        "tracking_events",
        "negative/departure_without_arrival/tracking_events.csv",
    ),
    FixtureFile(
        "repeated_arrival",
        "negative",
        "tracking_events",
        "negative/repeated_arrival/tracking_events.csv",
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the complete fixture package and load one baseline batch or "
            "one isolated negative-scenario delta into <run_prefix>_fixtures."
        )
    )
    parser.add_argument(
        "--scenario",
        choices=("baseline", *NEGATIVE_SCENARIOS),
        default="baseline",
    )
    parser.add_argument(
        "--batch",
        choices=("batch_1", "batch_2", "all"),
        default="all",
        help="Baseline batch selection; negative scenarios only accept the default 'all'.",
    )
    parser.add_argument(
        "--fixtures-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "fixtures",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate every fixture file and semantic contract without connecting to Trino.",
    )
    return parser.parse_args()


def read_fixture_file(root: Path, fixture_file: FixtureFile) -> list[dict[str, str]]:
    path = root / fixture_file.relative_path
    if not path.is_file():
        raise ValueError(f"missing fixture file: {path}")

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        expected_columns = TABLE_COLUMNS[fixture_file.table]
        if tuple(reader.fieldnames or ()) != expected_columns:
            raise ValueError(
                f"{path}: expected columns {expected_columns}, got {reader.fieldnames}"
            )
        rows = list(reader)

    if not rows:
        raise ValueError(f"{path}: fixture file must contain at least one data row")

    for line_number, row in enumerate(rows, start=2):
        empty_columns = [column for column in expected_columns if not row[column].strip()]
        if empty_columns:
            raise ValueError(
                f"{path}:{line_number}: empty values in {', '.join(empty_columns)}"
            )
    return rows


def load_fixture_package(
    root: Path,
) -> dict[FixtureFile, list[dict[str, str]]]:
    package: dict[FixtureFile, list[dict[str, str]]] = {}
    fixture_ids: dict[str, str] = {}

    for fixture_file in FIXTURE_FILES:
        rows = read_fixture_file(root, fixture_file)
        package[fixture_file] = rows
        for row in rows:
            fixture_id = row["fixture_row_id"]
            previous_path = fixture_ids.get(fixture_id)
            if previous_path is not None:
                raise ValueError(
                    f"duplicate fixture_row_id {fixture_id!r} in "
                    f"{previous_path} and {fixture_file.relative_path}"
                )
            fixture_ids[fixture_id] = fixture_file.relative_path

    validate_semantic_contract(package)
    return package


def rows_for(
    package: dict[FixtureFile, list[dict[str, str]]],
    *,
    scenario: str,
    table: str | None = None,
    batch: str | None = None,
) -> list[dict[str, str]]:
    return [
        row
        for fixture_file, rows in package.items()
        if fixture_file.scenario == scenario
        and (table is None or fixture_file.table == table)
        and (batch is None or fixture_file.batch == batch)
        for row in rows
    ]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(f"fixture contract violation: {message}")


def parse_integer(value: str, field_name: str) -> int:
    try:
        return int(value)
    except ValueError as error:
        raise ValueError(f"{field_name} must be an integer, got {value!r}") from error


def event_payload(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(
        row[column]
        for column in TABLE_COLUMNS["tracking_events"]
        if column not in {"fixture_row_id", "batch_id"}
    )


def validate_semantic_contract(
    package: dict[FixtureFile, list[dict[str, str]]],
) -> None:
    expected_counts = {
        "hubs": 5,
        "packages": 4,
        "route_plan_changes": 2,
        "route_checkpoints": 6,
        "tracking_events": 28,
    }
    for table, expected_count in expected_counts.items():
        actual_count = len(rows_for(package, scenario="baseline", table=table))
        require(
            actual_count == expected_count,
            f"baseline {table} count must be {expected_count}, got {actual_count}",
        )

    hubs = {
        row["hub_code"]: (row["longitude"], row["latitude"])
        for row in rows_for(package, scenario="baseline", table="hubs")
    }
    require(
        hubs
        == {
            "A": ("0.0", "0.0"),
            "X": ("0.5", "0.0"),
            "B": ("1.0", "0.0"),
            "D": ("1.5", "0.0"),
            "C": ("2.0", "0.0"),
        },
        "hub coordinates must match the approved equatorial fixture package",
    )

    packages = {
        row["package_id"]: (row["shipment_id"], row["route_id"])
        for row in rows_for(package, scenario="baseline", table="packages")
    }
    require(
        packages
        == {
            "P1": ("S1", "R1"),
            "P2": ("S2", "R1"),
            "P3": ("S2", "R1"),
            "P4": ("S3", "R1"),
        },
        "package/shipment/route mapping must match P1-P4",
    )

    route_versions = {
        row["route_version_id"]: (
            row["effective_at"],
            row["planned_duration_hours"],
            row["sla_duration_hours"],
        )
        for row in rows_for(
            package, scenario="baseline", table="route_plan_changes"
        )
    }
    require(
        route_versions
        == {
            "R1-V1": ("2025-01-01T00:00:00Z", "48", "48"),
            "R1-V2": ("2025-02-01T00:00:00Z", "36", "36"),
        },
        "route versions, effective times, planned durations, and SLAs must match",
    )

    checkpoints = sorted(
        (
            row["route_version_id"],
            parse_integer(row["checkpoint_seq"], "checkpoint_seq"),
            row["hub_code"],
        )
        for row in rows_for(
            package, scenario="baseline", table="route_checkpoints"
        )
    )
    require(
        checkpoints
        == [
            ("R1-V1", 1, "A"),
            ("R1-V1", 2, "B"),
            ("R1-V1", 3, "C"),
            ("R1-V2", 1, "A"),
            ("R1-V2", 2, "D"),
            ("R1-V2", 3, "C"),
        ],
        "route checkpoints must define A-B-C and A-D-C",
    )

    events = rows_for(package, scenario="baseline", table="tracking_events")
    batch_counts = {
        batch_id: sum(row["batch_id"] == batch_id for row in events)
        for batch_id in ("batch_1", "batch_2")
    }
    require(
        batch_counts == {"batch_1": 23, "batch_2": 5},
        f"tracking event batch counts must be 23/5, got {batch_counts}",
    )

    duplicate_rows = [row for row in events if row["event_id"] == "P3-E02"]
    require(len(duplicate_rows) == 2, "P3-E02 must have exactly two raw rows")
    require(
        len({event_payload(row) for row in duplicate_rows}) == 1,
        "the two P3-E02 rows must be exact business-payload duplicates",
    )
    require(
        {row["batch_id"] for row in duplicate_rows} == {"batch_1", "batch_2"},
        "the P3-E02 duplicate must span both baseline batches",
    )

    p3_late_rows = [
        row
        for row in events
        if row["batch_id"] == "batch_2" and row["event_id"] != "P3-E02"
    ]
    require(
        {row["event_id"] for row in p3_late_rows}
        == {"P3-E05", "P3-E06", "P3-E07", "P3-E08"},
        "batch_2 must contain the four late P3 B/X visit events plus the duplicate",
    )
    require(
        all(row["received_at"] > "2025-02-11T21:00:00Z" for row in p3_late_rows),
        "P3 visit events must be received after the delivered business event",
    )

    baseline_duplicate = duplicate_rows[0]
    conflict_rows = rows_for(
        package, scenario="conflicting_payload", table="tracking_events"
    )
    require(len(conflict_rows) == 1, "conflicting_payload must have one row")
    require(
        conflict_rows[0]["event_id"] == "P3-E02"
        and event_payload(conflict_rows[0]) != event_payload(baseline_duplicate),
        "conflicting_payload must reuse P3-E02 with a changed business payload",
    )

    departure_rows = rows_for(
        package, scenario="departure_without_arrival", table="tracking_events"
    )
    require(
        len(departure_rows) == 1
        and departure_rows[0]["package_id"] == "P4"
        and departure_rows[0]["event_type"] == "departed_at_hub"
        and departure_rows[0]["hub_code"] == "B",
        "departure_without_arrival must add a P4 departure from unopened hub B",
    )

    repeated_rows = rows_for(
        package, scenario="repeated_arrival", table="tracking_events"
    )
    require(
        len(repeated_rows) == 1
        and repeated_rows[0]["package_id"] == "P4"
        and repeated_rows[0]["event_type"] == "arrived_at_hub"
        and repeated_rows[0]["hub_code"] == "D",
        "repeated_arrival must add a second P4 arrival at still-open hub D",
    )


def selected_files(args: argparse.Namespace) -> list[FixtureFile]:
    if args.scenario != "baseline":
        if args.batch != "all":
            raise ValueError("--batch is only valid for the baseline scenario")
        return [item for item in FIXTURE_FILES if item.scenario == args.scenario]

    batches = {"batch_1", "batch_2"} if args.batch == "all" else {args.batch}
    return [
        item
        for item in FIXTURE_FILES
        if item.scenario == "baseline" and item.batch in batches
    ]


def quoted_identifier(identifier: str) -> str:
    if not IDENTIFIER.fullmatch(identifier):
        raise ValueError(f"unsafe SQL identifier: {identifier!r}")
    return f'"{identifier}"'


def sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def qualified_name(catalog: str, schema: str, table: str) -> str:
    return ".".join(quoted_identifier(item) for item in (catalog, schema, table))


def create_table(cursor: Any, catalog: str, schema: str, table: str) -> None:
    columns = TABLE_COLUMNS[table]
    definition = ",\n    ".join(
        f"{quoted_identifier(column)} varchar" for column in columns
    )
    cursor.execute(
        f"CREATE TABLE IF NOT EXISTS {qualified_name(catalog, schema, table)} (\n"
        f"    {definition}\n"
        ") WITH (format = 'PARQUET')"
    )


def existing_rows(
    cursor: Any,
    catalog: str,
    schema: str,
    table: str,
    rows: Sequence[dict[str, str]],
) -> dict[str, tuple[str, ...]]:
    columns = TABLE_COLUMNS[table]
    ids = ", ".join(sql_string(row["fixture_row_id"]) for row in rows)
    select_columns = ", ".join(quoted_identifier(column) for column in columns)
    cursor.execute(
        f"SELECT {select_columns} "
        f"FROM {qualified_name(catalog, schema, table)} "
        f"WHERE {quoted_identifier('fixture_row_id')} IN ({ids})"
    )
    return {str(row[0]): tuple(str(value) for value in row) for row in cursor.fetchall()}


def merge_rows(
    cursor: Any,
    catalog: str,
    schema: str,
    table: str,
    rows: Sequence[dict[str, str]],
) -> tuple[int, int]:
    columns = TABLE_COLUMNS[table]
    found = existing_rows(cursor, catalog, schema, table, rows)

    for row in rows:
        fixture_id = row["fixture_row_id"]
        expected = tuple(row[column] for column in columns)
        actual = found.get(fixture_id)
        if actual is not None and actual != expected:
            raise ValueError(
                f"existing immutable fixture row {fixture_id!r} differs from input"
            )

    values = ",\n        ".join(
        "(" + ", ".join(sql_string(row[column]) for column in columns) + ")"
        for row in rows
    )
    source_columns = ", ".join(quoted_identifier(column) for column in columns)
    insert_columns = source_columns
    insert_values = ", ".join(
        f"source.{quoted_identifier(column)}" for column in columns
    )
    cursor.execute(
        f"MERGE INTO {qualified_name(catalog, schema, table)} AS target\n"
        f"USING (VALUES\n        {values}\n"
        f") AS source ({source_columns})\n"
        f"ON target.{quoted_identifier('fixture_row_id')} = "
        f"source.{quoted_identifier('fixture_row_id')}\n"
        f"WHEN NOT MATCHED THEN INSERT ({insert_columns})\n"
        f"VALUES ({insert_values})"
    )
    existing_count = len(found)
    return len(rows) - existing_count, existing_count


def connect_from_environment() -> tuple[Any, str, str]:
    try:
        connect: Any = importlib.import_module("trino.dbapi").connect
    except (ImportError, AttributeError) as error:
        raise RuntimeError(
            "the Trino Python client is unavailable; run through the project dbt image"
        ) from error

    required = (
        "DBT_TRINO_HOST",
        "DBT_TRINO_PORT",
        "DBT_TRINO_USER",
        "DBT_TRINO_CATALOG",
        "DBT_TRINO_SCHEMA",
    )
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise ValueError(f"missing required environment variables: {', '.join(missing)}")

    host = os.environ["DBT_TRINO_HOST"]
    port = parse_integer(os.environ["DBT_TRINO_PORT"], "DBT_TRINO_PORT")
    user = os.environ["DBT_TRINO_USER"]
    catalog = os.environ["DBT_TRINO_CATALOG"]
    run_prefix = os.environ["DBT_TRINO_SCHEMA"].strip()
    fixture_schema = f"{run_prefix}_fixtures"

    quoted_identifier(catalog)
    quoted_identifier(fixture_schema)
    connection = connect(host=host, port=port, user=user, catalog=catalog)
    return connection, catalog, fixture_schema


def load_selected_files(
    package: dict[FixtureFile, list[dict[str, str]]],
    fixtures: Iterable[FixtureFile],
) -> None:
    connection, catalog, fixture_schema = connect_from_environment()
    cursor = connection.cursor()
    cursor.execute(
        f"CREATE SCHEMA IF NOT EXISTS "
        f"{quoted_identifier(catalog)}.{quoted_identifier(fixture_schema)}"
    )

    total_input = 0
    total_inserted = 0
    total_existing = 0
    for fixture_file in fixtures:
        rows = package[fixture_file]
        create_table(cursor, catalog, fixture_schema, fixture_file.table)
        inserted, existing = merge_rows(
            cursor, catalog, fixture_schema, fixture_file.table, rows
        )
        total_input += len(rows)
        total_inserted += inserted
        total_existing += existing
        print(
            "fixture_load "
            f"scenario={fixture_file.scenario} "
            f"batch={fixture_file.batch} "
            f"table={fixture_file.table} "
            f"input_rows={len(rows)} inserted_rows={inserted} "
            f"existing_rows={existing}"
        )

    print(
        "fixture_load_complete "
        f"schema={fixture_schema} input_rows={total_input} "
        f"inserted_rows={total_inserted} existing_rows={total_existing}"
    )


def main() -> int:
    args = parse_args()
    try:
        package = load_fixture_package(args.fixtures_root.resolve())
        print(
            f"fixture_validation_ok files={len(package)} "
            f"rows={sum(len(rows) for rows in package.values())}"
        )
        if args.validate_only:
            return 0
        load_selected_files(package, selected_files(args))
        return 0
    except (ValueError, RuntimeError) as error:
        print(f"fixture_loader_error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
