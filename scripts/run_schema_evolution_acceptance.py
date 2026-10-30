#!/usr/bin/env python3
"""Run the isolated schema-evolution acceptance workflow and save evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from run_acceptance import (
    AcceptanceError,
    AcceptanceRun,
    BUCKET,
    CATALOG,
    DEFAULT_EVIDENCE_ROOT,
    LAYERS,
    ROOT,
    RUN_ID_PATTERN,
    iso_now,
    normalize_sql,
    qualified,
)

EVOLUTION_TABLE = "schema_evolution_package_delivery"
SCHEMA_EVOLUTION_ACS = tuple(f"AC-{number:03d}" for number in range(13, 21))
S0_COLUMNS = [
    ("package_id", "varchar"),
    ("route_version_id", "varchar"),
    ("delivery_status", "varchar"),
    ("completed_visit_count", "integer"),
    ("delivery_duration_hours", "double"),
    ("is_on_time", "boolean"),
]
S0_EXPECTED_ROWS = [
    [
        "package_id",
        "route_version_id",
        "delivery_status",
        "completed_visit_count",
        "delivery_duration_hours",
        "is_on_time",
    ],
    ["P1", "R1-V1", "delivered", "1", "48.0", "true"],
    ["P2", "R1-V2", "delivered", "3", "48.0", "false"],
    ["P3", "R1-V2", "delivered", "2", "36.0", "true"],
    ["P4", "R1-V2", "arrived_at_hub", "0", "NULL", "NULL"],
]
S0_ICEBERG_TYPES = {
    "package_id": "string",
    "route_version_id": "string",
    "delivery_status": "string",
    "completed_visit_count": "int",
    "delivery_duration_hours": "double",
    "is_on_time": "boolean",
}
RENAMED_COLUMNS = [
    ("package_id", "varchar"),
    ("route_version_id", "varchar"),
    ("current_status", "varchar"),
    ("completed_visit_count", "integer"),
    ("delivery_duration_hours", "double"),
    ("is_on_time", "boolean"),
]
WIDENED_COLUMNS = [
    (name, "bigint" if name == "completed_visit_count" else data_type)
    for name, data_type in RENAMED_COLUMNS
]
EVOLVED_COLUMNS = [
    ("package_id", "varchar"),
    ("route_version_id", "varchar"),
    ("delivery_priority", "varchar"),
    ("current_status", "varchar"),
    ("completed_visit_count", "bigint"),
    ("delivery_duration_hours", "double"),
    ("is_on_time", "boolean"),
]
RENAMED_ICEBERG_TYPES = {
    "package_id": "string",
    "route_version_id": "string",
    "current_status": "string",
    "completed_visit_count": "int",
    "delivery_duration_hours": "double",
    "is_on_time": "boolean",
}
WIDENED_ICEBERG_TYPES = {
    **RENAMED_ICEBERG_TYPES,
    "completed_visit_count": "long",
}
EVOLVED_ICEBERG_TYPES = {
    "package_id": "string",
    "route_version_id": "string",
    "delivery_priority": "string",
    "current_status": "string",
    "completed_visit_count": "long",
    "delivery_duration_hours": "double",
    "is_on_time": "boolean",
}
EVOLVED_ROWS_HEADER = [
    "package_id",
    "route_version_id",
    "delivery_priority",
    "current_status",
    "completed_visit_count",
    "delivery_duration_hours",
    "is_on_time",
]
EVOLVED_S0_ROWS = [
    ["P1", "R1-V1", "NULL", "delivered", "1", "48.0", "true"],
    ["P2", "R1-V2", "NULL", "delivered", "3", "48.0", "false"],
    ["P3", "R1-V2", "NULL", "delivered", "2", "36.0", "true"],
    ["P4", "R1-V2", "NULL", "arrived_at_hub", "0", "NULL", "NULL"],
]
EVO_P5_ROW = [
    "EVO-P5",
    "R1-V2",
    "express",
    "delivered",
    "1",
    "24.0",
    "true",
]
BASELINE_TABLES = {
    "fixtures": (
        "hubs",
        "packages",
        "route_checkpoints",
        "route_plan_changes",
        "tracking_events",
    ),
    "bronze": (
        "bronze_hubs",
        "bronze_packages",
        "bronze_route_checkpoints",
        "bronze_route_plan_changes",
        "bronze_tracking_events",
    ),
    "silver": (
        "silver_package_current_state",
        "silver_package_route_binding",
        "silver_route_plan_checkpoint_segments",
        "silver_route_plan_versions",
        "silver_tracking_events",
        "silver_tracking_events_typed",
    ),
    "gold": (
        "gold_hub_visits",
        "gold_package_delivery_fact",
        "gold_route_version_efficiency",
        "gold_route_version_hub_dwell",
    ),
}
REQUIRED_FINAL_EVIDENCE_PATHS = {
    "commands.jsonl",
    "core/comparison.json",
    "evolution/s0/metadata.json",
    "evolution/ddl/01_rename/metadata.json",
    "evolution/ddl/02_widen/metadata.json",
    "evolution/ddl/03_add_priority/metadata.json",
    "evolution/historical/comparison.json",
    "evolution/narrowing/comparison.json",
    "runtime/catalog_tables.csv",
    "runtime/polaris_catalog.json",
    "runtime/object_paths.json",
    "runtime/object_paths.csv",
    "runtime/end_to_end.json",
    "cleanup/drop_schemas.log",
    "cleanup/remaining_schemas.csv",
    "cleanup/remaining_objects.json",
    "cleanup/environment.json",
    "secret_scan.json",
}


def core_contract_mismatches(
    before: dict[str, list[list[str]]],
    after: dict[str, list[list[str]]],
) -> list[str]:
    """Return the sorted contract captures that differ between two core runs."""
    return sorted(
        name
        for name in before.keys() | after.keys()
        if before.get(name) != after.get(name)
    )


def assert_end_to_end_catalog_rows(
    rows: list[list[str]],
    *,
    baseline_prefix: str,
    evolution_schema: str,
) -> None:
    """Require the exact core and evolution table registrations before cleanup."""
    expected = [
        ["table_schema", "table_name"],
        *sorted(
            [f"{baseline_prefix}_{layer}", table_name]
            for layer, table_names in BASELINE_TABLES.items()
            for table_name in table_names
        ),
        [evolution_schema, EVOLUTION_TABLE],
    ]
    expected[1:] = sorted(expected[1:])
    if rows != expected:
        raise AcceptanceError(
            f"unexpected end-to-end catalog tables: expected {len(expected) - 1}, "
            f"got {max(len(rows) - 1, 0)}"
        )


def assert_task_schemas_absent(rows: list[list[str]]) -> None:
    """Require the exact post-drop schema query to return no task schemas."""
    if rows != [["schema_name"]]:
        raise AcceptanceError(f"task schemas remain after cleanup: {rows[1:]}")


def assert_task_object_listing(
    objects: dict[str, Any],
    *,
    run_id: str,
) -> list[dict[str, Any]]:
    """Validate the task-owned Iceberg object listing captured before cleanup."""
    expected_prefix = f"warehouse/{run_id}_"
    if objects.get("Prefix") != expected_prefix:
        raise AcceptanceError(
            f"unexpected task object prefix: {objects.get('Prefix')}"
        )
    contents = objects.get("Contents")
    if not isinstance(contents, list) or not contents:
        raise AcceptanceError("no task object paths were found")

    validated = []
    for item in contents:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("Key"), str)
            or not item["Key"].startswith(expected_prefix)
            or not isinstance(item.get("Size"), int)
            or item["Size"] <= 0
        ):
            raise AcceptanceError(f"invalid task object listing row: {item}")
        validated.append(item)

    keys = [item["Key"] for item in validated]
    required_suffixes = (".parquet", ".metadata.json", ".avro")
    missing_suffixes = [
        suffix for suffix in required_suffixes if not any(key.endswith(suffix) for key in keys)
    ]
    if missing_suffixes:
        raise AcceptanceError(
            "task object paths lack required Iceberg files: "
            + ", ".join(missing_suffixes)
        )
    return sorted(validated, key=lambda item: item["Key"])


def assert_final_evidence_manifest(manifest: dict[str, Any]) -> None:
    """Require the final manifest to cover every AC-020 evidence boundary."""
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise AcceptanceError("evidence manifest is empty or invalid")

    paths: set[str] = set()
    for entry in entries:
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("path"), str)
            or not isinstance(entry.get("size"), int)
            or entry["size"] < 0
            or not isinstance(entry.get("sha256"), str)
            or len(entry["sha256"]) != 64
            or any(character not in "0123456789abcdef" for character in entry["sha256"])
        ):
            raise AcceptanceError(f"invalid evidence manifest entry: {entry}")
        path = entry["path"]
        if path in paths:
            raise AcceptanceError(f"duplicate evidence manifest path: {path}")
        paths.add(path)

    missing = sorted(REQUIRED_FINAL_EVIDENCE_PATHS - paths)
    if missing:
        raise AcceptanceError(
            "evidence manifest lacks required AC-020 paths: " + ", ".join(missing)
        )


def assert_s0_rows(rows: list[list[str]]) -> None:
    """Validate the four S0 rows without depending on DOUBLE text formatting."""
    if not rows or rows[0] != S0_EXPECTED_ROWS[0] or len(rows) != len(S0_EXPECTED_ROWS):
        raise AcceptanceError(f"unexpected S0 rows: {rows}")
    for actual, expected in zip(rows[1:], S0_EXPECTED_ROWS[1:], strict=True):
        if len(actual) != 6 or actual[:4] != expected[:4] or actual[5] != expected[5]:
            raise AcceptanceError(f"unexpected S0 row: {actual}")
        if expected[4] == "NULL":
            if actual[4] != "NULL":
                raise AcceptanceError(f"unexpected S0 duration: {actual}")
            continue
        try:
            actual_duration = float(actual[4])
            expected_duration = float(expected[4])
        except ValueError as error:
            raise AcceptanceError(f"invalid S0 duration: {actual}") from error
        if actual_duration != expected_duration:
            raise AcceptanceError(f"unexpected S0 duration: {actual}")


def parse_s0_snapshot(rows: list[list[str]]) -> int:
    """Validate the single initial data snapshot and return its generated ID."""
    expected_header = ["snapshot_id", "parent_id", "operation"]
    if not rows or rows[0] != expected_header or len(rows) != 2:
        raise AcceptanceError(f"expected one S0 snapshot row, got: {rows}")
    snapshot_id, parent_id, operation = rows[1]
    try:
        parsed_snapshot_id = int(snapshot_id)
    except ValueError as error:
        raise AcceptanceError(f"invalid S0 snapshot ID: {snapshot_id}") from error
    if parsed_snapshot_id <= 0 or parent_id or operation.lower() != "append":
        raise AcceptanceError(f"invalid S0 snapshot contract: {rows[1]}")
    return parsed_snapshot_id


def parse_current_metadata(metadata: dict[str, Any], snapshot_id: int) -> dict[str, Any]:
    """Return the current Iceberg schema identity after validating metadata shape."""
    current_schema_id = metadata.get("current-schema-id")
    current_snapshot_id = metadata.get("current-snapshot-id")
    last_column_id = metadata.get("last-column-id")
    schemas = metadata.get("schemas")
    if (
        not isinstance(current_schema_id, int)
        or not isinstance(last_column_id, int)
        or not isinstance(schemas, list)
    ):
        raise AcceptanceError("metadata JSON lacks current schema information")
    if current_snapshot_id != snapshot_id:
        raise AcceptanceError(
            f"metadata current snapshot {current_snapshot_id} != S0 {snapshot_id}"
        )

    current_schemas = [
        schema
        for schema in schemas
        if isinstance(schema, dict) and schema.get("schema-id") == current_schema_id
    ]
    if len(current_schemas) != 1:
        raise AcceptanceError(
            f"expected one current Iceberg schema {current_schema_id}, got {len(current_schemas)}"
        )
    fields = current_schemas[0].get("fields")
    if not isinstance(fields, list) or not fields:
        raise AcceptanceError(f"unexpected metadata fields: {fields}")

    field_ids: dict[str, int] = {}
    field_types: dict[str, str] = {}
    field_required: dict[str, bool] = {}
    used_field_ids: set[int] = set()
    for field in fields:
        if not isinstance(field, dict):
            raise AcceptanceError(f"invalid metadata field: {field}")
        name = field.get("name")
        field_id = field.get("id")
        field_type = field.get("type")
        required = field.get("required")
        if (
            not isinstance(name, str)
            or not isinstance(field_id, int)
            or not isinstance(field_type, str)
            or not isinstance(required, bool)
        ):
            raise AcceptanceError(f"invalid metadata field identity: {field}")
        if name in field_ids or field_id in used_field_ids or field_id <= 0:
            raise AcceptanceError(f"duplicate or invalid metadata field: {field}")
        field_ids[name] = field_id
        field_types[name] = field_type
        field_required[name] = required
        used_field_ids.add(field_id)

    if last_column_id < max(field_ids.values()):
        raise AcceptanceError(
            f"last-column-id {last_column_id} is below fields {field_ids}"
        )
    return {
        "current_schema_id": current_schema_id,
        "current_snapshot_id": current_snapshot_id,
        "last_column_id": last_column_id,
        "field_ids": field_ids,
        "field_types": field_types,
        "field_required": field_required,
    }


def parse_s0_metadata(metadata: dict[str, Any], snapshot_id: int) -> dict[str, Any]:
    """Validate the initial Iceberg metadata schema and return stable field evidence."""
    summary = parse_current_metadata(metadata, snapshot_id)
    field_ids = summary["field_ids"]
    field_types = summary["field_types"]
    expected_names = [name for name, _ in S0_COLUMNS]
    if list(field_ids) != expected_names or field_types != S0_ICEBERG_TYPES:
        raise AcceptanceError(
            f"unexpected S0 metadata schema: names={list(field_ids)}, types={field_types}"
        )
    if summary["last_column_id"] != max(field_ids.values()):
        raise AcceptanceError(
            f"last-column-id {summary['last_column_id']} does not match fields {field_ids}"
        )
    return summary


def parse_ddl_metadata(
    metadata: dict[str, Any],
    snapshot_id: int,
    *,
    expected_names: list[str],
    expected_types: dict[str, str],
    field_sources: dict[str, str | None],
    s0_summary: dict[str, Any],
    previous_schema_id: int,
) -> dict[str, Any]:
    """Validate one metadata-only DDL checkpoint against the S0 field identities."""
    summary = parse_current_metadata(metadata, snapshot_id)
    field_ids = summary["field_ids"]
    field_types = summary["field_types"]
    s0_field_ids = s0_summary["field_ids"]
    s0_last_column_id = s0_summary["last_column_id"]
    if list(field_ids) != expected_names or field_types != expected_types:
        raise AcceptanceError(
            f"unexpected evolved metadata schema: names={list(field_ids)}, types={field_types}"
        )
    if summary["current_schema_id"] in {
        s0_summary["current_schema_id"],
        previous_schema_id,
    }:
        raise AcceptanceError(
            f"schema ID did not advance at DDL checkpoint: {summary['current_schema_id']}"
        )

    new_fields = []
    for name in expected_names:
        source_name = field_sources[name]
        if source_name is None:
            if field_ids[name] in set(s0_field_ids.values()) or field_ids[name] <= s0_last_column_id:
                raise AcceptanceError(f"new field reused an S0 field ID: {name}={field_ids[name]}")
            if summary["field_required"][name]:
                raise AcceptanceError(f"new field is unexpectedly required: {name}")
            new_fields.append(name)
        elif field_ids[name] != s0_field_ids[source_name]:
            raise AcceptanceError(
                f"field ID changed for {name}: {field_ids[name]} != {s0_field_ids[source_name]}"
            )

    if new_fields:
        if new_fields != ["delivery_priority"] or summary["last_column_id"] != field_ids[new_fields[0]]:
            raise AcceptanceError(
                f"unexpected new-field identity: fields={new_fields}, summary={summary}"
            )
    elif summary["last_column_id"] != s0_last_column_id:
        raise AcceptanceError(
            f"DDL without add changed last-column-id: {summary['last_column_id']}"
        )
    return summary


def file_identity_mismatches(
    expected: list[dict[str, Any]],
    actual: list[dict[str, Any]],
) -> list[str]:
    """Return data-file paths whose size, record count, format, or digest changed."""
    expected_by_path = {item.get("file_path"): item for item in expected}
    actual_by_path = {item.get("file_path"): item for item in actual}
    return sorted(
        str(path)
        for path in expected_by_path.keys() | actual_by_path.keys()
        if expected_by_path.get(path) != actual_by_path.get(path)
    )


def assert_evolved_rows(rows: list[list[str]], *, include_evo_p5: bool) -> None:
    """Validate current-schema rows while accepting equivalent DOUBLE rendering."""
    expected_rows = [*EVOLVED_S0_ROWS]
    if include_evo_p5:
        expected_rows = [EVO_P5_ROW, *expected_rows]
    if not rows or rows[0] != EVOLVED_ROWS_HEADER or len(rows) != len(expected_rows) + 1:
        raise AcceptanceError(f"unexpected evolved rows: {rows}")
    for actual, expected in zip(rows[1:], expected_rows, strict=True):
        if len(actual) != 7 or actual[:5] != expected[:5] or actual[6] != expected[6]:
            raise AcceptanceError(f"unexpected evolved row: {actual}")
        if expected[5] == "NULL":
            if actual[5] != "NULL":
                raise AcceptanceError(f"unexpected evolved duration: {actual}")
            continue
        try:
            actual_duration = float(actual[5])
            expected_duration = float(expected[5])
        except ValueError as error:
            raise AcceptanceError(f"invalid evolved duration: {actual}") from error
        if actual_duration != expected_duration:
            raise AcceptanceError(f"unexpected evolved duration: {actual}")


def parse_s1_snapshots(rows: list[list[str]], s0_snapshot_id: int) -> int:
    """Validate the direct S0 to S1 append chain and return the generated S1 ID."""
    expected_header = ["snapshot_id", "parent_id", "operation"]
    if not rows or rows[0] != expected_header or len(rows) != 3:
        raise AcceptanceError(f"expected exactly S0 and S1 snapshots, got: {rows}")
    parsed_rows = []
    for snapshot_id, parent_id, operation in rows[1:]:
        try:
            parsed_snapshot_id = int(snapshot_id)
            parsed_parent_id = int(parent_id) if parent_id else None
        except ValueError as error:
            raise AcceptanceError(f"invalid snapshot chain row: {snapshot_id, parent_id}") from error
        if parsed_snapshot_id <= 0 or operation.lower() != "append":
            raise AcceptanceError(f"invalid snapshot chain row: {snapshot_id, parent_id, operation}")
        parsed_rows.append((parsed_snapshot_id, parsed_parent_id))
    roots = [snapshot_id for snapshot_id, parent_id in parsed_rows if parent_id is None]
    children = [
        snapshot_id
        for snapshot_id, parent_id in parsed_rows
        if parent_id == s0_snapshot_id
    ]
    if roots != [s0_snapshot_id] or len(children) != 1 or children[0] == s0_snapshot_id:
        raise AcceptanceError(f"invalid S0/S1 snapshot chain: {rows}")
    return children[0]


def compatibility_state_mismatches(
    expected: dict[str, Any],
    actual: dict[str, Any],
) -> list[str]:
    """Return compatibility-state components changed by an expected failure."""
    return sorted(
        name
        for name in expected.keys() | actual.keys()
        if expected.get(name) != actual.get(name)
    )


def normalize_historical_rows(rows: list[list[str]]) -> list[list[str]]:
    """Normalize Trino CSV's empty SQL NULL fields after typed capture."""
    normalized = [list(row) for row in rows]
    for row in normalized[1:]:
        if len(row) != 7:
            continue
        for index in (2, 5, 6):
            if row[index] == "":
                row[index] = "NULL"
    return normalized


def assert_historical_projection_types(rows: list[list[str]]) -> None:
    """Require the shared seven-column projection to preserve contract types."""
    expected = [
        [
            "package_id_type",
            "route_version_id_type",
            "delivery_priority_type",
            "current_status_type",
            "completed_visit_count_type",
            "delivery_duration_hours_type",
            "is_on_time_type",
        ],
        ["varchar", "varchar", "varchar", "varchar", "bigint", "double", "boolean"],
    ]
    if rows != expected:
        raise AcceptanceError(f"unexpected historical projection types: {rows}")


def assert_historical_null_semantics(
    rows: list[list[str]],
    *,
    include_evo_p5: bool,
) -> None:
    """Require true SQL NULL semantics for historical nullable fields."""
    expected = [
        [
            "package_id",
            "delivery_priority_is_null",
            "delivery_duration_hours_is_null",
            "is_on_time_is_null",
        ]
    ]
    if include_evo_p5:
        expected.append(["EVO-P5", "false", "false", "false"])
    expected.extend(
        [
            ["P1", "true", "false", "false"],
            ["P2", "true", "false", "false"],
            ["P3", "true", "false", "false"],
            ["P4", "true", "true", "true"],
        ]
    )
    if rows != expected:
        raise AcceptanceError(f"unexpected historical NULL semantics: {rows}")


def assert_historical_compatibility(
    s0_rows: list[list[str]],
    s1_rows: list[list[str]],
    current_rows: list[list[str]],
) -> None:
    """Validate exact current-schema projections for S0, S1, and current."""
    assert_evolved_rows(s0_rows, include_evo_p5=False)
    assert_evolved_rows(s1_rows, include_evo_p5=True)
    assert_evolved_rows(current_rows, include_evo_p5=True)
    if s1_rows != current_rows:
        raise AcceptanceError("historical S1 rows do not match the current table")


def assert_narrowing_failure(returncode: int, output: str) -> None:
    """Require the expected BIGINT-to-INTEGER type-change rejection."""
    normalized = output.lower()
    sql_type_pair = "bigint" in normalized and "integer" in normalized
    iceberg_type_pair = "long -> int" in normalized or "long to int" in normalized
    type_change_failure = (
        "cannot change column type" in normalized
        or "unsupported type change" in normalized
    )
    if (
        returncode == 0
        or "completed_visit_count" not in normalized
        or not type_change_failure
        or not (sql_type_pair or iceberg_type_pair)
    ):
        raise AcceptanceError(
            "narrowing DDL did not fail for completed_visit_count BIGINT to INTEGER"
        )


def assert_old_name_insert_failure(returncode: int, output: str) -> None:
    """Require the expected missing-target-column failure for the legacy name."""
    normalized = output.lower()
    if (
        returncode == 0
        or "insert column name does not exist in target table" not in normalized
        or "delivery_status" not in normalized
    ):
        raise AcceptanceError(
            "old-name INSERT did not fail with the missing delivery_status column"
        )


class SchemaEvolutionAcceptanceRun(AcceptanceRun):
    """Lifecycle and safety boundary for the schema-evolution slice."""

    def __init__(self, run_id: str, evidence_dir: Path) -> None:
        super().__init__(run_id, evidence_dir)
        self.ac_results = {ac: "NOT_RUN" for ac in SCHEMA_EVOLUTION_ACS}
        self.negative_prefixes = {}
        self.evolution_schema = f"{run_id}_evolution"
        self.s0_snapshot_id: int | None = None
        self.s1_snapshot_id: int | None = None
        self.s0_file_identities: list[dict[str, Any]] = []
        self.s0_metadata_summary: dict[str, Any] = {}
        self.evolved_metadata_summary: dict[str, Any] = {}
        self.end_to_end_evidence_captured = False
        self.environment_restored = False

    def run(self) -> None:
        self.preflight()
        error: Exception | None = None
        try:
            self.start_stack()
            self.assert_stack_state()
            self.assert_query_ready()
            self.assert_prefixes_absent()
            self.prefixes_owned = True
            self.run_schema_evolution_workflow()
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
            self.environment_restored = True
        except Exception as restore_error:
            if error is None:
                error = restore_error

        error = self.finalize(error)
        if error is not None:
            raise error

    def assert_prefixes_absent(self) -> None:
        schema_names = [
            *(f"{self.baseline_prefix}_{layer}" for layer in LAYERS),
            self.evolution_schema,
        ]
        quoted_names = ", ".join(f"'{name}'" for name in schema_names)
        rows = self.query_csv(
            "preflight/existing_schemas.csv",
            "SELECT schema_name FROM lakehouse.information_schema.schemata "
            f"WHERE schema_name IN ({quoted_names}) ORDER BY schema_name",
        )
        if rows != [["schema_name"]]:
            raise AcceptanceError(f"run-prefix schemas already exist: {rows[1:]}")

    def run_schema_evolution_workflow(self) -> None:
        self.run_baseline()
        before = self.capture_core_contract("pre")

        self.run_schema_evolution_steps()

        self.dbt(
            self.baseline_prefix,
            ["build", "--select", "tag:bronze", "tag:silver", "tag:gold"],
            "core/post/build",
            "core/post/build/dbt_build.log",
        )
        self.assert_run_results(
            "core/post/build/target/run_results.json",
            allowed_statuses={"success", "pass"},
            expected_count=128,
        )
        after = self.capture_core_contract("post")

        mismatches = core_contract_mismatches(before, after)
        self.write_json(
            "core/comparison.json",
            {
                "before": "core/pre",
                "after": "core/post",
                "matched_contracts": sorted(before.keys() - set(mismatches)),
                "mismatches": mismatches,
            },
        )
        if mismatches:
            raise AcceptanceError(
                "core regression changed after schema evolution: "
                + ", ".join(mismatches)
            )

        self.ac_results["AC-013"] = "PASS"
        pending = [
            ac for ac in SCHEMA_EVOLUTION_ACS[:-1] if self.ac_results[ac] != "PASS"
        ]
        if pending:
            raise AcceptanceError(
                "schema-evolution behavior checks are incomplete: " + ", ".join(pending)
            )
        self.capture_end_to_end_evidence()

    def run_schema_evolution_steps(self) -> None:
        """Create S0, then prove the ordered schema changes are metadata-only."""
        evolution_table = self.evolution_table_name()
        source_table = qualified(
            self.baseline_prefix,
            "gold",
            "gold_package_delivery_fact",
        )
        self.execute_sql(
            "evolution/s0/create_schema.log",
            f'CREATE SCHEMA "{CATALOG}"."{self.evolution_schema}"',
        )
        self.execute_sql(
            "evolution/s0/create_table.log",
            f"""
            CREATE TABLE {evolution_table} AS
            SELECT
                CAST(package_id AS varchar) AS package_id,
                CAST(route_version_id AS varchar) AS route_version_id,
                CAST(current_status AS varchar) AS delivery_status,
                CAST(completed_visit_count AS integer) AS completed_visit_count,
                CAST(delivery_duration_hours AS double) AS delivery_duration_hours,
                CAST(is_on_time AS boolean) AS is_on_time
            FROM {source_table}
            """,
        )
        self.capture_s0_evidence()
        self.ac_results["AC-014"] = "PASS"
        self.run_metadata_only_ddl_checkpoints()
        self.ac_results["AC-015"] = "PASS"
        self.run_reader_writer_compatibility()
        self.run_historical_compatibility_and_narrowing()

    def evolution_table_name(self) -> str:
        return f'"{CATALOG}"."{self.evolution_schema}"."{EVOLUTION_TABLE}"'

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

    def capture_s0_evidence(self) -> None:
        evolution_table = self.evolution_table_name()
        self.query_csv("evolution/s0/describe.csv", f"DESCRIBE {evolution_table}")
        columns = self.query_csv(
            "evolution/s0/columns.csv",
            f"""
            SELECT column_name, data_type, ordinal_position
            FROM {CATALOG}.information_schema.columns
            WHERE table_schema = '{self.evolution_schema}'
              AND table_name = '{EVOLUTION_TABLE}'
            ORDER BY ordinal_position
            """,
        )
        expected_columns = [
            ["column_name", "data_type", "ordinal_position"],
            *[
                [name, data_type, str(position)]
                for position, (name, data_type) in enumerate(S0_COLUMNS, start=1)
            ],
        ]
        if columns != expected_columns:
            raise AcceptanceError(f"unexpected S0 columns: {columns}")

        rows = self.query_csv(
            "evolution/s0/rows.csv",
            f"""
            SELECT
                package_id,
                route_version_id,
                delivery_status,
                CAST(completed_visit_count AS varchar) AS completed_visit_count,
                COALESCE(CAST(delivery_duration_hours AS varchar), 'NULL') AS delivery_duration_hours,
                COALESCE(CAST(is_on_time AS varchar), 'NULL') AS is_on_time
            FROM {evolution_table}
            ORDER BY package_id
            """,
        )
        assert_s0_rows(rows)

        snapshots = self.query_csv(
            "evolution/s0/snapshots.csv",
            f"""
            SELECT
                CAST(snapshot_id AS varchar) AS snapshot_id,
                COALESCE(CAST(parent_id AS varchar), '') AS parent_id,
                operation
            FROM {self.evolution_metadata_table('snapshots')}
            ORDER BY committed_at, snapshot_id
            """,
        )
        self.s0_snapshot_id = parse_s0_snapshot(snapshots)

        file_rows = self.query_csv(
            "evolution/s0/files.csv",
            f"""
            SELECT
                file_path,
                file_format,
                CAST(record_count AS varchar) AS record_count,
                CAST(file_size_in_bytes AS varchar) AS file_size_in_bytes
            FROM {self.evolution_metadata_table('files')}
            ORDER BY file_path
            """,
        )
        self.query_csv(
            "evolution/s0/metadata_log_entries.csv",
            f"""
            SELECT
                CAST(timestamp AS varchar) AS committed_at,
                file,
                CAST(latest_snapshot_id AS varchar) AS latest_snapshot_id,
                CAST(latest_schema_id AS varchar) AS latest_schema_id,
                CAST(latest_sequence_number AS varchar) AS latest_sequence_number
            FROM {self.evolution_metadata_table('metadata_log_entries')}
            ORDER BY timestamp, file
            """,
        )

        objects = self.list_objects(f"warehouse/{self.evolution_schema}/")
        self.write_json("evolution/s0/objects.json", objects)
        object_rows = objects.get("Contents") or []
        if not isinstance(object_rows, list) or not object_rows:
            raise AcceptanceError("S0 object listing is empty")
        typed_object_rows: list[dict[str, Any]] = []
        objects_by_key: dict[str, dict[str, Any]] = {}
        for item in object_rows:
            if not isinstance(item, dict) or not isinstance(item.get("Key"), str):
                raise AcceptanceError(f"invalid S0 object listing row: {item}")
            typed_object_rows.append(item)
            objects_by_key[item["Key"]] = item
        self.write_csv(
            "evolution/s0/objects.csv",
            [
                ["key", "size", "etag"],
                *[
                    [item["Key"], item.get("Size"), item.get("ETag")]
                    for item in typed_object_rows
                ],
            ],
        )

        expected_file_header = [
            "file_path",
            "file_format",
            "record_count",
            "file_size_in_bytes",
        ]
        if not file_rows or file_rows[0] != expected_file_header or len(file_rows) < 2:
            raise AcceptanceError(f"S0 has no data files: {file_rows}")
        file_identities = []
        total_records = 0
        for file_path, file_format, record_count, file_size in file_rows[1:]:
            object_key = self.object_key(file_path)
            object_row = objects_by_key.get(object_key)
            if file_format.upper() != "PARQUET" or object_row is None:
                raise AcceptanceError(f"invalid S0 data file mapping: {file_path}")
            object_size_value = object_row.get("Size")
            try:
                parsed_record_count = int(record_count)
                parsed_file_size = int(file_size)
                if not isinstance(object_size_value, int):
                    raise TypeError("object size is not an integer")
                object_size = object_size_value
            except (TypeError, ValueError) as error:
                raise AcceptanceError(f"invalid S0 file metrics: {file_rows}") from error
            if parsed_record_count <= 0 or parsed_file_size <= 0:
                raise AcceptanceError(f"invalid S0 file metrics: {file_rows}")
            if object_size != parsed_file_size:
                raise AcceptanceError(
                    f"Trino/object size mismatch for {object_key}: "
                    f"{parsed_file_size} != {object_size}"
                )
            total_records += parsed_record_count
            file_identities.append(
                {
                    "file_path": file_path,
                    "object_key": object_key,
                    "file_format": file_format.upper(),
                    "record_count": parsed_record_count,
                    "size": parsed_file_size,
                    "sha256": self.object_sha256(object_key),
                }
            )
        if total_records != 4:
            raise AcceptanceError(f"S0 data files contain {total_records} rows, expected 4")
        self.s0_file_identities = file_identities
        self.write_json("evolution/s0/file_identities.json", file_identities)

        metadata_keys = sorted(
            key for key in objects_by_key if key.endswith(".metadata.json")
        )
        if len(metadata_keys) != 1:
            raise AcceptanceError(
                f"expected one initial metadata JSON, got: {metadata_keys}"
            )
        metadata_key = metadata_keys[0]
        metadata_text = self.read_object_text(metadata_key)
        self.write_text("evolution/s0/metadata.json", metadata_text)
        try:
            metadata = json.loads(metadata_text)
        except json.JSONDecodeError as error:
            raise AcceptanceError(f"invalid metadata JSON: {metadata_key}") from error
        if not isinstance(metadata, dict) or self.s0_snapshot_id is None:
            raise AcceptanceError(f"invalid metadata JSON root: {metadata_key}")
        metadata_summary = parse_s0_metadata(metadata, self.s0_snapshot_id)
        metadata_summary.update(
            {
                "object_key": metadata_key,
                "size": len(metadata_text.encode("utf-8")),
                "sha256": hashlib.sha256(metadata_text.encode("utf-8")).hexdigest(),
            }
        )
        self.s0_metadata_summary = metadata_summary
        self.write_json("evolution/s0/metadata_summary.json", metadata_summary)
        self.write_json(
            "evolution/s0/invariant_bundle.json",
            {
                "symbolic_snapshot": "S0",
                "snapshot_id": self.s0_snapshot_id,
                "columns": [
                    {"name": name, "type": data_type}
                    for name, data_type in S0_COLUMNS
                ],
                "row_count": 4,
                "file_identities": file_identities,
                "metadata": metadata_summary,
            },
        )

    def run_metadata_only_ddl_checkpoints(self) -> None:
        evolution_table = self.evolution_table_name()
        field_sources = {
            "package_id": "package_id",
            "route_version_id": "route_version_id",
            "current_status": "delivery_status",
            "completed_visit_count": "completed_visit_count",
            "delivery_duration_hours": "delivery_duration_hours",
            "is_on_time": "is_on_time",
        }
        checkpoints = [
            (
                "01_rename",
                f"ALTER TABLE {evolution_table} RENAME COLUMN delivery_status TO current_status",
                RENAMED_COLUMNS,
                RENAMED_ICEBERG_TYPES,
                field_sources,
            ),
            (
                "02_widen",
                f"ALTER TABLE {evolution_table} ALTER COLUMN completed_visit_count SET DATA TYPE BIGINT",
                WIDENED_COLUMNS,
                WIDENED_ICEBERG_TYPES,
                field_sources,
            ),
            (
                "03_add_priority",
                f"ALTER TABLE {evolution_table} ADD COLUMN delivery_priority VARCHAR AFTER route_version_id",
                EVOLVED_COLUMNS,
                EVOLVED_ICEBERG_TYPES,
                {
                    "package_id": "package_id",
                    "route_version_id": "route_version_id",
                    "delivery_priority": None,
                    "current_status": "delivery_status",
                    "completed_visit_count": "completed_visit_count",
                    "delivery_duration_hours": "delivery_duration_hours",
                    "is_on_time": "is_on_time",
                },
            ),
        ]
        previous_schema_id = self.s0_metadata_summary["current_schema_id"]
        previous_metadata_key = self.s0_metadata_summary["object_key"]
        summaries = []
        for checkpoint, sql, columns, iceberg_types, sources in checkpoints:
            root = f"evolution/ddl/{checkpoint}"
            self.execute_sql(f"{root}/alter.log", sql)
            summary = self.capture_metadata_only_checkpoint(
                root,
                columns=columns,
                iceberg_types=iceberg_types,
                field_sources=sources,
                previous_schema_id=previous_schema_id,
                previous_metadata_key=previous_metadata_key,
            )
            summaries.append(summary)
            previous_schema_id = summary["metadata"]["current_schema_id"]
            previous_metadata_key = summary["metadata"]["object_key"]
        self.evolved_metadata_summary = summaries[-1]["metadata"]
        self.write_json("evolution/ddl/checkpoints.json", summaries)

    def capture_metadata_only_checkpoint(
        self,
        root: str,
        *,
        columns: list[tuple[str, str]],
        iceberg_types: dict[str, str],
        field_sources: dict[str, str | None],
        previous_schema_id: int,
        previous_metadata_key: str,
    ) -> dict[str, Any]:
        if self.s0_snapshot_id is None:
            raise AcceptanceError("S0 snapshot is unavailable at DDL checkpoint")
        evolution_table = self.evolution_table_name()
        self.query_csv(f"{root}/describe.csv", f"DESCRIBE {evolution_table}")
        actual_columns = self.query_csv(
            f"{root}/columns.csv",
            f"""
            SELECT column_name, data_type, ordinal_position
            FROM {CATALOG}.information_schema.columns
            WHERE table_schema = '{self.evolution_schema}'
              AND table_name = '{EVOLUTION_TABLE}'
            ORDER BY ordinal_position
            """,
        )
        expected_columns = [
            ["column_name", "data_type", "ordinal_position"],
            *[
                [name, data_type, str(position)]
                for position, (name, data_type) in enumerate(columns, start=1)
            ],
        ]
        if actual_columns != expected_columns:
            raise AcceptanceError(f"unexpected DDL checkpoint columns: {actual_columns}")

        snapshots = self.query_csv(
            f"{root}/snapshots.csv",
            f"""
            SELECT
                CAST(snapshot_id AS varchar) AS snapshot_id,
                COALESCE(CAST(parent_id AS varchar), '') AS parent_id,
                operation
            FROM {self.evolution_metadata_table('snapshots')}
            ORDER BY committed_at, snapshot_id
            """,
        )
        checkpoint_snapshot_id = parse_s0_snapshot(snapshots)
        if checkpoint_snapshot_id != self.s0_snapshot_id:
            raise AcceptanceError(
                f"DDL changed current data snapshot: {checkpoint_snapshot_id} != {self.s0_snapshot_id}"
            )

        file_rows = self.query_csv(
            f"{root}/files.csv",
            f"""
            SELECT
                file_path,
                file_format,
                CAST(record_count AS varchar) AS record_count,
                CAST(file_size_in_bytes AS varchar) AS file_size_in_bytes
            FROM {self.evolution_metadata_table('files')}
            ORDER BY file_path
            """,
        )
        objects = self.list_objects(f"warehouse/{self.evolution_schema}/")
        self.write_json(f"{root}/objects.json", objects)
        object_rows = objects.get("Contents") or []
        if not isinstance(object_rows, list) or not object_rows:
            raise AcceptanceError(f"DDL checkpoint object listing is empty: {root}")
        objects_by_key = {
            item["Key"]: item
            for item in object_rows
            if isinstance(item, dict) and isinstance(item.get("Key"), str)
        }
        if len(objects_by_key) != len(object_rows):
            raise AcceptanceError(f"invalid DDL checkpoint object listing: {root}")
        self.write_csv(
            f"{root}/objects.csv",
            [
                ["key", "size", "etag"],
                *[
                    [item["Key"], item.get("Size"), item.get("ETag")]
                    for item in object_rows
                ],
            ],
        )

        expected_header = [
            "file_path",
            "file_format",
            "record_count",
            "file_size_in_bytes",
        ]
        if not file_rows or file_rows[0] != expected_header or len(file_rows) < 2:
            raise AcceptanceError(f"DDL checkpoint has no data files: {file_rows}")
        file_identities = []
        for file_path, file_format, record_count, file_size in file_rows[1:]:
            object_key = self.object_key(file_path)
            object_row = objects_by_key.get(object_key)
            try:
                parsed_record_count = int(record_count)
                parsed_file_size = int(file_size)
                object_size = object_row.get("Size") if object_row is not None else None
                if not isinstance(object_size, int):
                    raise TypeError("object size is not an integer")
            except (TypeError, ValueError) as error:
                raise AcceptanceError(f"invalid DDL file metrics: {file_rows}") from error
            if file_format.upper() != "PARQUET" or parsed_file_size != object_size:
                raise AcceptanceError(f"invalid DDL data file mapping: {file_path}")
            file_identities.append(
                {
                    "file_path": file_path,
                    "object_key": object_key,
                    "file_format": file_format.upper(),
                    "record_count": parsed_record_count,
                    "size": parsed_file_size,
                    "sha256": self.object_sha256(object_key),
                }
            )
        mismatches = file_identity_mismatches(self.s0_file_identities, file_identities)
        if mismatches:
            raise AcceptanceError(
                "DDL rewrote or changed S0 data files: " + ", ".join(mismatches)
            )
        parquet_keys = sorted(
            key for key in objects_by_key if key.lower().endswith(".parquet")
        )
        expected_parquet_keys = sorted(
            item["object_key"] for item in self.s0_file_identities
        )
        if parquet_keys != expected_parquet_keys:
            raise AcceptanceError(
                f"DDL changed Parquet object set: {parquet_keys} != {expected_parquet_keys}"
            )
        self.write_json(f"{root}/file_identities.json", file_identities)

        metadata_log = self.query_csv(
            f"{root}/metadata_log_entries.csv",
            f"""
            SELECT
                CAST(timestamp AS varchar) AS committed_at,
                file,
                CAST(latest_snapshot_id AS varchar) AS latest_snapshot_id,
                CAST(latest_schema_id AS varchar) AS latest_schema_id,
                CAST(latest_sequence_number AS varchar) AS latest_sequence_number
            FROM {self.evolution_metadata_table('metadata_log_entries')}
            ORDER BY timestamp, file
            """,
        )
        latest_metadata = self.query_csv(
            f"{root}/latest_metadata.csv",
            f"""
            SELECT
                file,
                CAST(latest_snapshot_id AS varchar) AS latest_snapshot_id,
                CAST(latest_schema_id AS varchar) AS latest_schema_id
            FROM {self.evolution_metadata_table('metadata_log_entries')}
            ORDER BY timestamp DESC
            LIMIT 1
            """,
        )
        if (
            not metadata_log
            or metadata_log[0]
            != [
                "committed_at",
                "file",
                "latest_snapshot_id",
                "latest_schema_id",
                "latest_sequence_number",
            ]
            or len(latest_metadata) != 2
            or latest_metadata[0]
            != ["file", "latest_snapshot_id", "latest_schema_id"]
        ):
            raise AcceptanceError(f"invalid DDL metadata log evidence: {root}")
        metadata_location, latest_snapshot_id, latest_schema_id = latest_metadata[1]
        try:
            parsed_latest_snapshot_id = int(latest_snapshot_id)
            parsed_latest_schema_id = int(latest_schema_id)
        except ValueError as error:
            raise AcceptanceError(
                f"invalid DDL metadata log IDs: {latest_metadata[1]}"
            ) from error
        if parsed_latest_snapshot_id != self.s0_snapshot_id:
            raise AcceptanceError(
                f"DDL metadata log changed snapshot: {latest_snapshot_id}"
            )
        metadata_key = self.object_key(metadata_location)
        if metadata_key == previous_metadata_key or metadata_key not in objects_by_key:
            raise AcceptanceError(
                f"DDL did not create a new current metadata object: {metadata_key}"
            )
        metadata_text = self.read_object_text(metadata_key)
        self.write_text(f"{root}/metadata.json", metadata_text)
        try:
            metadata = json.loads(metadata_text)
        except json.JSONDecodeError as error:
            raise AcceptanceError(f"invalid metadata JSON: {metadata_key}") from error
        if not isinstance(metadata, dict):
            raise AcceptanceError(f"invalid metadata JSON root: {metadata_key}")
        metadata_summary = parse_ddl_metadata(
            metadata,
            self.s0_snapshot_id,
            expected_names=[name for name, _ in columns],
            expected_types=iceberg_types,
            field_sources=field_sources,
            s0_summary=self.s0_metadata_summary,
            previous_schema_id=previous_schema_id,
        )
        if parsed_latest_schema_id != self.s0_metadata_summary["current_schema_id"]:
            raise AcceptanceError(
                f"S0 snapshot schema changed in metadata log: {latest_schema_id} != "
                f"{self.s0_metadata_summary['current_schema_id']}"
            )
        metadata_summary.update(
            {
                "object_key": metadata_key,
                "size": len(metadata_text.encode("utf-8")),
                "sha256": hashlib.sha256(metadata_text.encode("utf-8")).hexdigest(),
            }
        )
        self.write_json(f"{root}/metadata_summary.json", metadata_summary)
        summary = {
            "root": root,
            "snapshot_id": self.s0_snapshot_id,
            "columns": [
                {"name": name, "type": data_type}
                for name, data_type in columns
            ],
            "file_identities": file_identities,
            "metadata": metadata_summary,
            "snapshot_schema_id": parsed_latest_schema_id,
            "object_count": len(object_rows),
            "metadata_log_entry_count": len(metadata_log) - 1,
        }
        self.write_json(f"{root}/invariant_bundle.json", summary)
        return summary

    def run_reader_writer_compatibility(self) -> None:
        """Prove current-schema reads, old-name rejection, and the S1 append."""
        before_failure = self.capture_compatibility_state(
            "evolution/compatibility/current_schema_s0",
            include_evo_p5=False,
            snapshot_stage="s0",
        )
        self.ac_results["AC-016"] = "PASS"

        old_name_sql = f"""
            INSERT INTO {self.evolution_table_name()} (
                package_id,
                route_version_id,
                delivery_status,
                completed_visit_count,
                delivery_duration_hours,
                is_on_time
            ) VALUES ('EVO-P5', 'R1-V2', 'delivered', 1, 24, true)
        """
        failure_result = self.run_command(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "trino",
                "trino",
                "--execute",
                normalize_sql(old_name_sql),
            ],
            "evolution/writer/old_name_insert.log",
            allowed_returncodes=set(range(1, 256)),
        )
        failure_output = failure_result.stdout + failure_result.stderr
        assert_old_name_insert_failure(failure_result.returncode, failure_output)
        self.write_json(
            "evolution/writer/old_name_failure.json",
            {
                "returncode": failure_result.returncode,
                "diagnostic_matches_missing_column": True,
            },
        )

        after_failure = self.capture_compatibility_state(
            "evolution/writer/old_name_after",
            include_evo_p5=False,
            snapshot_stage="s0",
        )
        failure_mismatches = compatibility_state_mismatches(
            before_failure,
            after_failure,
        )
        self.write_json(
            "evolution/writer/old_name_comparison.json",
            {
                "before": "evolution/compatibility/current_schema_s0",
                "after": "evolution/writer/old_name_after",
                "mismatches": failure_mismatches,
            },
        )
        if failure_mismatches:
            raise AcceptanceError(
                "old-name INSERT changed table state: "
                + ", ".join(failure_mismatches)
            )

        self.execute_sql(
            "evolution/writer/insert_evo_p5.log",
            f"""
            INSERT INTO {self.evolution_table_name()} (
                package_id,
                route_version_id,
                delivery_priority,
                current_status,
                completed_visit_count,
                delivery_duration_hours,
                is_on_time
            ) VALUES ('EVO-P5', 'R1-V2', 'express', 'delivered', 1, 24, true)
            """,
        )
        s1_state = self.capture_compatibility_state(
            "evolution/s1",
            include_evo_p5=True,
            snapshot_stage="s1",
        )
        self.s1_snapshot_id = s1_state["current_snapshot_id"]
        self.write_json(
            "evolution/s1/snapshot_identity.json",
            {
                "S0": self.s0_snapshot_id,
                "S1": self.s1_snapshot_id,
                "parent_id": self.s0_snapshot_id,
            },
        )
        self.ac_results["AC-017"] = "PASS"

    def run_historical_compatibility_and_narrowing(self) -> None:
        """Prove S0/S1 reads and atomically reject narrowing after S1."""
        if self.s0_snapshot_id is None or self.s1_snapshot_id is None:
            raise AcceptanceError("S0/S1 snapshot identities are unavailable")

        table = self.evolution_table_name()
        s0_projection = f"""
            SELECT
                package_id,
                route_version_id,
                CAST(NULL AS varchar) AS delivery_priority,
                delivery_status AS current_status,
                CAST(completed_visit_count AS bigint) AS completed_visit_count,
                delivery_duration_hours,
                is_on_time
            FROM {table} FOR VERSION AS OF {self.s0_snapshot_id}
        """
        current_projection = """
            SELECT
                package_id,
                route_version_id,
                delivery_priority,
                current_status,
                completed_visit_count,
                delivery_duration_hours,
                is_on_time
            FROM {table} {version_clause}
        """
        projections = {
            "s0": s0_projection,
            "s1": current_projection.format(
                table=table,
                version_clause=f"FOR VERSION AS OF {self.s1_snapshot_id}",
            ),
            "current": current_projection.format(table=table, version_clause=""),
        }
        historical_rows: dict[str, list[list[str]]] = {}
        historical_types: dict[str, list[list[str]]] = {}
        historical_nulls: dict[str, list[list[str]]] = {}
        for name, projection in projections.items():
            historical_rows[name] = normalize_historical_rows(
                self.query_csv(
                    f"evolution/historical/{name}.csv",
                    f"{projection} ORDER BY package_id",
                )
            )
            historical_types[name] = self.query_csv(
                f"evolution/historical/{name}_types.csv",
                f"""
                SELECT
                    typeof(package_id) AS package_id_type,
                    typeof(route_version_id) AS route_version_id_type,
                    typeof(delivery_priority) AS delivery_priority_type,
                    typeof(current_status) AS current_status_type,
                    typeof(completed_visit_count) AS completed_visit_count_type,
                    typeof(delivery_duration_hours) AS delivery_duration_hours_type,
                    typeof(is_on_time) AS is_on_time_type
                FROM ({projection}) AS historical_projection
                LIMIT 1
                """,
            )
            historical_nulls[name] = self.query_csv(
                f"evolution/historical/{name}_nulls.csv",
                f"""
                SELECT
                    package_id,
                    delivery_priority IS NULL AS delivery_priority_is_null,
                    delivery_duration_hours IS NULL AS delivery_duration_hours_is_null,
                    is_on_time IS NULL AS is_on_time_is_null
                FROM ({projection}) AS historical_projection
                ORDER BY package_id
                """,
            )
            assert_historical_projection_types(historical_types[name])
            assert_historical_null_semantics(
                historical_nulls[name],
                include_evo_p5=name != "s0",
            )

        assert_historical_compatibility(
            historical_rows["s0"],
            historical_rows["s1"],
            historical_rows["current"],
        )
        self.write_json(
            "evolution/historical/normalized_rows.json",
            historical_rows,
        )
        self.write_json(
            "evolution/historical/projection_types.json",
            historical_types,
        )
        self.write_json(
            "evolution/historical/null_semantics.json",
            historical_nulls,
        )
        self.write_json(
            "evolution/historical/comparison.json",
            {
                "S0": self.s0_snapshot_id,
                "S1": self.s1_snapshot_id,
                "s0_row_count": len(historical_rows["s0"]) - 1,
                "s1_row_count": len(historical_rows["s1"]) - 1,
                "current_row_count": len(historical_rows["current"]) - 1,
                "s1_matches_current": True,
                "projection_types_match_contract": True,
                "null_semantics_match_contract": True,
            },
        )
        self.ac_results["AC-018"] = "PASS"

        before_failure = self.capture_compatibility_state(
            "evolution/narrowing/before",
            include_evo_p5=True,
            snapshot_stage="s1",
        )
        narrowing_sql = f"""
            ALTER TABLE {self.evolution_table_name()}
            ALTER COLUMN completed_visit_count SET DATA TYPE INTEGER
        """
        failure_result = self.run_command(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "trino",
                "trino",
                "--execute",
                normalize_sql(narrowing_sql),
            ],
            "evolution/narrowing/failure.log",
            allowed_returncodes=set(range(1, 256)),
        )
        failure_output = failure_result.stdout + failure_result.stderr
        assert_narrowing_failure(failure_result.returncode, failure_output)
        self.write_json(
            "evolution/narrowing/failure.json",
            {
                "returncode": failure_result.returncode,
                "diagnostic_matches_narrowing": True,
            },
        )

        after_failure = self.capture_compatibility_state(
            "evolution/narrowing/after",
            include_evo_p5=True,
            snapshot_stage="s1",
        )
        failure_mismatches = compatibility_state_mismatches(
            before_failure,
            after_failure,
        )
        self.write_json(
            "evolution/narrowing/comparison.json",
            {
                "before": "evolution/narrowing/before",
                "after": "evolution/narrowing/after",
                "mismatches": failure_mismatches,
            },
        )
        if failure_mismatches:
            raise AcceptanceError(
                "narrowing DDL changed table state: "
                + ", ".join(failure_mismatches)
            )
        self.ac_results["AC-019"] = "PASS"

    def capture_compatibility_state(
        self,
        root: str,
        *,
        include_evo_p5: bool,
        snapshot_stage: str,
    ) -> dict[str, Any]:
        """Capture and validate schema, rows, snapshots, files, and metadata."""
        if self.s0_snapshot_id is None or not self.evolved_metadata_summary:
            raise AcceptanceError("evolved S0 state is unavailable")
        if snapshot_stage not in {"s0", "s1"}:
            raise AcceptanceError(f"invalid compatibility snapshot stage: {snapshot_stage}")

        evolution_table = self.evolution_table_name()
        columns = self.query_csv(
            f"{root}/columns.csv",
            f"""
            SELECT column_name, data_type, ordinal_position
            FROM {CATALOG}.information_schema.columns
            WHERE table_schema = '{self.evolution_schema}'
              AND table_name = '{EVOLUTION_TABLE}'
            ORDER BY ordinal_position
            """,
        )
        expected_columns = [
            ["column_name", "data_type", "ordinal_position"],
            *[
                [name, data_type, str(position)]
                for position, (name, data_type) in enumerate(EVOLVED_COLUMNS, start=1)
            ],
        ]
        if columns != expected_columns:
            raise AcceptanceError(f"unexpected compatibility columns: {columns}")

        rows = self.query_csv(
            f"{root}/rows.csv",
            f"""
            SELECT
                package_id,
                route_version_id,
                COALESCE(delivery_priority, 'NULL') AS delivery_priority,
                current_status,
                CAST(completed_visit_count AS varchar) AS completed_visit_count,
                COALESCE(CAST(delivery_duration_hours AS varchar), 'NULL') AS delivery_duration_hours,
                COALESCE(CAST(is_on_time AS varchar), 'NULL') AS is_on_time
            FROM {evolution_table}
            ORDER BY package_id
            """,
        )
        assert_evolved_rows(rows, include_evo_p5=include_evo_p5)

        snapshots = self.query_csv(
            f"{root}/snapshots.csv",
            f"""
            SELECT
                CAST(snapshot_id AS varchar) AS snapshot_id,
                COALESCE(CAST(parent_id AS varchar), '') AS parent_id,
                operation
            FROM {self.evolution_metadata_table('snapshots')}
            ORDER BY committed_at, snapshot_id
            """,
        )
        if snapshot_stage == "s0":
            current_snapshot_id = parse_s0_snapshot(snapshots)
            if current_snapshot_id != self.s0_snapshot_id:
                raise AcceptanceError(
                    f"compatibility state changed S0: {current_snapshot_id} != {self.s0_snapshot_id}"
                )
        else:
            current_snapshot_id = parse_s1_snapshots(
                snapshots,
                self.s0_snapshot_id,
            )

        file_rows = self.query_csv(
            f"{root}/files.csv",
            f"""
            SELECT
                file_path,
                file_format,
                CAST(record_count AS varchar) AS record_count,
                CAST(file_size_in_bytes AS varchar) AS file_size_in_bytes
            FROM {self.evolution_metadata_table('files')}
            ORDER BY file_path
            """,
        )
        expected_file_header = [
            "file_path",
            "file_format",
            "record_count",
            "file_size_in_bytes",
        ]
        if not file_rows or file_rows[0] != expected_file_header or len(file_rows) < 2:
            raise AcceptanceError(f"compatibility state has no data files: {file_rows}")

        objects = self.list_objects(f"warehouse/{self.evolution_schema}/")
        self.write_json(f"{root}/objects.json", objects)
        object_rows = objects.get("Contents") or []
        if not isinstance(object_rows, list) or not object_rows:
            raise AcceptanceError(f"compatibility object listing is empty: {root}")
        objects_by_key: dict[str, dict[str, Any]] = {}
        object_identities = []
        for item in object_rows:
            if not isinstance(item, dict) or not isinstance(item.get("Key"), str):
                raise AcceptanceError(f"invalid compatibility object: {item}")
            key = item["Key"]
            if key in objects_by_key:
                raise AcceptanceError(f"duplicate compatibility object key: {key}")
            objects_by_key[key] = item
            object_identities.append(
                {
                    "key": key,
                    "size": item.get("Size"),
                    "etag": item.get("ETag"),
                }
            )
        object_identities.sort(key=lambda item: item["key"])

        file_identities = []
        for file_path, file_format, record_count, file_size in file_rows[1:]:
            object_key = self.object_key(file_path)
            object_row = objects_by_key.get(object_key)
            try:
                parsed_record_count = int(record_count)
                parsed_file_size = int(file_size)
                object_size = object_row.get("Size") if object_row is not None else None
                if not isinstance(object_size, int):
                    raise TypeError("object size is not an integer")
            except (TypeError, ValueError) as error:
                raise AcceptanceError(
                    f"invalid compatibility file metrics: {file_rows}"
                ) from error
            if (
                file_format.upper() != "PARQUET"
                or parsed_record_count <= 0
                or parsed_file_size <= 0
                or parsed_file_size != object_size
            ):
                raise AcceptanceError(f"invalid compatibility data file: {file_path}")
            file_identities.append(
                {
                    "file_path": file_path,
                    "object_key": object_key,
                    "file_format": file_format.upper(),
                    "record_count": parsed_record_count,
                    "size": parsed_file_size,
                    "sha256": self.object_sha256(object_key),
                }
            )

        actual_by_path = {
            item["file_path"]: item
            for item in file_identities
        }
        retained_s0_files = [
            actual_by_path[path]
            for path in (item["file_path"] for item in self.s0_file_identities)
            if path in actual_by_path
        ]
        s0_mismatches = file_identity_mismatches(
            self.s0_file_identities,
            retained_s0_files,
        )
        if s0_mismatches:
            raise AcceptanceError(
                "compatibility state changed S0 data files: "
                + ", ".join(s0_mismatches)
            )
        total_records = sum(item["record_count"] for item in file_identities)
        new_records = sum(
            item["record_count"]
            for item in file_identities
            if item["file_path"] not in {
                s0_file["file_path"] for s0_file in self.s0_file_identities
            }
        )
        expected_total_records = 5 if include_evo_p5 else 4
        expected_new_records = 1 if include_evo_p5 else 0
        if (
            total_records != expected_total_records
            or new_records != expected_new_records
        ):
            raise AcceptanceError(
                "unexpected compatibility file record counts: "
                f"total={total_records}, new={new_records}"
            )

        metadata_log = self.query_csv(
            f"{root}/metadata_log_entries.csv",
            f"""
            SELECT
                CAST(timestamp AS varchar) AS committed_at,
                file,
                CAST(latest_snapshot_id AS varchar) AS latest_snapshot_id,
                CAST(latest_schema_id AS varchar) AS latest_schema_id,
                CAST(latest_sequence_number AS varchar) AS latest_sequence_number
            FROM {self.evolution_metadata_table('metadata_log_entries')}
            ORDER BY timestamp, file
            """,
        )
        latest_metadata = self.query_csv(
            f"{root}/latest_metadata.csv",
            f"""
            SELECT
                file,
                CAST(latest_snapshot_id AS varchar) AS latest_snapshot_id
            FROM {self.evolution_metadata_table('metadata_log_entries')}
            ORDER BY timestamp DESC
            LIMIT 1
            """,
        )
        if (
            not metadata_log
            or len(latest_metadata) != 2
            or latest_metadata[0] != ["file", "latest_snapshot_id"]
        ):
            raise AcceptanceError(f"invalid compatibility metadata log: {root}")
        metadata_location, latest_snapshot_id = latest_metadata[1]
        try:
            parsed_latest_snapshot_id = int(latest_snapshot_id)
        except ValueError as error:
            raise AcceptanceError(
                f"invalid compatibility metadata snapshot: {latest_snapshot_id}"
            ) from error
        if parsed_latest_snapshot_id != current_snapshot_id:
            raise AcceptanceError(
                "compatibility metadata/current snapshot mismatch: "
                f"{parsed_latest_snapshot_id} != {current_snapshot_id}"
            )
        metadata_key = self.object_key(metadata_location)
        if metadata_key not in objects_by_key:
            raise AcceptanceError(
                f"current compatibility metadata object is absent: {metadata_key}"
            )
        metadata_text = self.read_object_text(metadata_key)
        self.write_text(f"{root}/metadata.json", metadata_text)
        try:
            metadata = json.loads(metadata_text)
        except json.JSONDecodeError as error:
            raise AcceptanceError(f"invalid compatibility metadata: {metadata_key}") from error
        if not isinstance(metadata, dict):
            raise AcceptanceError(f"invalid compatibility metadata root: {metadata_key}")
        metadata_summary = parse_current_metadata(metadata, current_snapshot_id)
        if (
            list(metadata_summary["field_ids"]) != [name for name, _ in EVOLVED_COLUMNS]
            or metadata_summary["field_types"] != EVOLVED_ICEBERG_TYPES
            or metadata_summary["field_ids"]
            != self.evolved_metadata_summary["field_ids"]
            or metadata_summary["current_schema_id"]
            != self.evolved_metadata_summary["current_schema_id"]
            or metadata_summary["last_column_id"]
            != self.evolved_metadata_summary["last_column_id"]
            or metadata_summary["field_required"]["delivery_priority"]
        ):
            raise AcceptanceError(
                f"unexpected compatibility metadata schema: {metadata_summary}"
            )
        comparable_metadata = {
            **metadata_summary,
            "object_key": metadata_key,
            "size": len(metadata_text.encode("utf-8")),
            "sha256": hashlib.sha256(metadata_text.encode("utf-8")).hexdigest(),
        }

        state = {
            "columns": columns,
            "rows": rows,
            "snapshots": snapshots,
            "file_identities": file_identities,
            "object_identities": object_identities,
            "metadata_log": metadata_log,
            "metadata": comparable_metadata,
            "current_snapshot_id": current_snapshot_id,
        }
        self.write_json(f"{root}/invariant_bundle.json", state)
        return state

    def evolution_metadata_table(self, suffix: str) -> str:
        return (
            f'"{CATALOG}"."{self.evolution_schema}".'
            f'"{EVOLUTION_TABLE}${suffix}"'
        )

    def object_key(self, location: str) -> str:
        for scheme in ("s3://", "s3a://", "s3n://"):
            prefix = f"{scheme}{BUCKET}/"
            if location.startswith(prefix):
                key = location[len(prefix):]
                expected_prefix = f"warehouse/{self.evolution_schema}/"
                if key.startswith(expected_prefix):
                    return key
        raise AcceptanceError(f"unexpected task object location: {location}")

    def object_sha256(self, object_key: str) -> str:
        result = self.capture(
            [
                "docker",
                "compose",
                "run",
                "--rm",
                "--no-deps",
                "--entrypoint",
                "sh",
                "bucket-setup",
                "-c",
                'set -eu; aws s3 cp "$1" /tmp/object >/dev/null; sha256sum /tmp/object',
                "sh",
                f"s3://{BUCKET}/{object_key}",
            ],
            None,
        )
        digest = result.stdout.split(maxsplit=1)[0] if result.stdout.strip() else ""
        if len(digest) != 64 or any(
            character not in "0123456789abcdef" for character in digest
        ):
            raise AcceptanceError(f"invalid SHA-256 for {object_key}: {result.stdout}")
        return digest

    def read_object_text(self, object_key: str) -> str:
        return self.capture(
            [
                "docker",
                "compose",
                "run",
                "--rm",
                "--no-deps",
                "--entrypoint",
                "aws",
                "bucket-setup",
                "s3",
                "cp",
                f"s3://{BUCKET}/{object_key}",
                "-",
            ],
            None,
        ).stdout

    def capture_core_contract(self, phase: str) -> dict[str, list[list[str]]]:
        if phase not in {"pre", "post"}:
            raise AcceptanceError(f"invalid core regression phase: {phase}")

        prefix = self.baseline_prefix
        schemas = [f"{prefix}_{layer}" for layer in LAYERS]
        quoted_schemas = ", ".join(f"'{schema}'" for schema in schemas)
        captures = {
            "columns": self.query_csv(
                f"core/{phase}/columns.csv",
                """
                SELECT
                    table_schema,
                    table_name,
                    ordinal_position,
                    column_name,
                    data_type,
                    is_nullable
                FROM lakehouse.information_schema.columns
                WHERE table_schema IN ("""
                + quoted_schemas
                + ") ORDER BY table_schema, table_name, ordinal_position",
            ),
            "route_binding": self.query_csv(
                f"core/{phase}/route_binding.csv",
                f"""
                SELECT
                    package_id,
                    route_version_id,
                    CAST(promised_delivery_at AS varchar) AS promised_delivery_at
                FROM {qualified(prefix, 'silver', 'silver_package_route_binding')}
                ORDER BY package_id
                """,
            ),
            "layer_counts": self.query_csv(
                f"core/{phase}/layer_counts.csv",
                f"""
                SELECT
                    (SELECT count(*) FROM {qualified(prefix, 'bronze', 'bronze_tracking_events')}) AS bronze_events,
                    (SELECT count(*) FROM {qualified(prefix, 'silver', 'silver_tracking_events_typed')}) AS typed_events,
                    (SELECT count(*) FROM {qualified(prefix, 'silver', 'silver_tracking_events')}) AS canonical_events,
                    (SELECT count(*) FROM {qualified(prefix, 'gold', 'gold_package_delivery_fact')}) AS package_facts,
                    (SELECT count_if(delivered_at IS NOT NULL) FROM {qualified(prefix, 'gold', 'gold_package_delivery_fact')}) AS completed_packages,
                    (SELECT count_if(delivered_at IS NULL) FROM {qualified(prefix, 'gold', 'gold_package_delivery_fact')}) AS active_packages,
                    (SELECT count(*) FROM {qualified(prefix, 'gold', 'gold_hub_visits')}) AS visits,
                    (SELECT count_if(NOT is_open) FROM {qualified(prefix, 'gold', 'gold_hub_visits')}) AS closed_visits,
                    (SELECT count_if(is_open) FROM {qualified(prefix, 'gold', 'gold_hub_visits')}) AS open_visits,
                    (SELECT count(*) FROM {qualified(prefix, 'gold', 'gold_package_delivery_fact')} WHERE shipment_id = 'S2') AS shipment_s2_packages
                """,
            ),
            "duplicate_reconciliation": self.query_csv(
                f"core/{phase}/duplicate_reconciliation.csv",
                f"""
                SELECT
                    (SELECT count(*) FROM {qualified(prefix, 'bronze', 'bronze_tracking_events')} WHERE event_id = 'P3-E02') AS bronze_rows,
                    (SELECT count(DISTINCT event_payload_fingerprint) FROM {qualified(prefix, 'silver', 'silver_tracking_events_typed')} WHERE event_id = 'P3-E02') AS payload_variants,
                    (SELECT count(*) FROM {qualified(prefix, 'silver', 'silver_tracking_events')} WHERE event_id = 'P3-E02') AS canonical_rows
                """,
            ),
            "package_facts": self.query_csv(
                f"core/{phase}/package_facts.csv",
                f"""
                SELECT
                    package_id,
                    current_status,
                    delivery_duration_hours,
                    delay_hours,
                    is_on_time,
                    visit_count,
                    completed_visit_count,
                    open_visit_count,
                    completed_dwell_hours,
                    actual_distance_meters / planned_distance_meters AS route_ratio,
                    final_route_deviation_pct
                FROM {qualified(prefix, 'gold', 'gold_package_delivery_fact')}
                ORDER BY package_id
                """,
            ),
            "hub_visits": self.query_csv(
                f"core/{phase}/hub_visits.csv",
                f"""
                SELECT
                    package_id,
                    visit_seq,
                    hub_code,
                    CAST(arrived_at AS varchar) AS arrived_at,
                    CAST(departed_at AS varchar) AS departed_at,
                    dwell_time_hours,
                    is_open
                FROM {qualified(prefix, 'gold', 'gold_hub_visits')}
                ORDER BY package_id, visit_seq
                """,
            ),
            "route_version_efficiency": self.query_csv(
                f"core/{phase}/route_version_efficiency.csv",
                f"""
                SELECT
                    route_version_id,
                    completed_package_count,
                    active_package_count,
                    on_time_rate_pct,
                    average_delay_hours,
                    average_final_route_deviation_pct
                FROM {qualified(prefix, 'gold', 'gold_route_version_efficiency')}
                ORDER BY route_version_id
                """,
            ),
            "route_version_hub_dwell": self.query_csv(
                f"core/{phase}/route_version_hub_dwell.csv",
                f"""
                SELECT route_version_id, hub_code, completed_dwell_hours
                FROM {qualified(prefix, 'gold', 'gold_route_version_hub_dwell')}
                ORDER BY route_version_id, hub_code
                """,
            ),
            "evo_p5_absence": self.query_csv(
                f"core/{phase}/evo_p5_absence.csv",
                f"""
                SELECT relation_name, row_count
                FROM (
                    SELECT 'fixtures.packages' AS relation_name, count(*) AS row_count
                    FROM {qualified(prefix, 'fixtures', 'packages')}
                    WHERE package_id = 'EVO-P5'
                    UNION ALL
                    SELECT 'fixtures.tracking_events', count(*)
                    FROM {qualified(prefix, 'fixtures', 'tracking_events')}
                    WHERE package_id = 'EVO-P5'
                    UNION ALL
                    SELECT 'bronze.bronze_packages', count(*)
                    FROM {qualified(prefix, 'bronze', 'bronze_packages')}
                    WHERE package_id = 'EVO-P5'
                    UNION ALL
                    SELECT 'bronze.bronze_tracking_events', count(*)
                    FROM {qualified(prefix, 'bronze', 'bronze_tracking_events')}
                    WHERE package_id = 'EVO-P5'
                    UNION ALL
                    SELECT 'silver.silver_tracking_events_typed', count(*)
                    FROM {qualified(prefix, 'silver', 'silver_tracking_events_typed')}
                    WHERE package_id = 'EVO-P5'
                    UNION ALL
                    SELECT 'silver.silver_tracking_events', count(*)
                    FROM {qualified(prefix, 'silver', 'silver_tracking_events')}
                    WHERE package_id = 'EVO-P5'
                    UNION ALL
                    SELECT 'silver.silver_package_current_state', count(*)
                    FROM {qualified(prefix, 'silver', 'silver_package_current_state')}
                    WHERE package_id = 'EVO-P5'
                    UNION ALL
                    SELECT 'silver.silver_package_route_binding', count(*)
                    FROM {qualified(prefix, 'silver', 'silver_package_route_binding')}
                    WHERE package_id = 'EVO-P5'
                    UNION ALL
                    SELECT 'gold.gold_hub_visits', count(*)
                    FROM {qualified(prefix, 'gold', 'gold_hub_visits')}
                    WHERE package_id = 'EVO-P5'
                    UNION ALL
                    SELECT 'gold.gold_package_delivery_fact', count(*)
                    FROM {qualified(prefix, 'gold', 'gold_package_delivery_fact')}
                    WHERE package_id = 'EVO-P5'
                )
                ORDER BY relation_name
                """,
            ),
        }

        absence_rows = captures["evo_p5_absence"]
        if len(absence_rows) != 11 or any(row[1] != "0" for row in absence_rows[1:]):
            raise AcceptanceError(f"EVO-P5 leaked into core relations: {absence_rows}")
        return captures

    def capture_end_to_end_evidence(self) -> None:
        """Capture final catalog and object evidence before task-owned cleanup."""
        schemas = [
            *(f"{self.baseline_prefix}_{layer}" for layer in LAYERS),
            self.evolution_schema,
        ]
        quoted_schemas = ", ".join(f"'{schema}'" for schema in schemas)
        rows = self.query_csv(
            "runtime/catalog_tables.csv",
            "SELECT table_schema, table_name "
            "FROM lakehouse.information_schema.tables "
            f"WHERE table_schema IN ({quoted_schemas}) "
            "ORDER BY table_schema, table_name",
        )
        assert_end_to_end_catalog_rows(
            rows,
            baseline_prefix=self.baseline_prefix,
            evolution_schema=self.evolution_schema,
        )

        catalog = self.fetch_polaris_catalog()
        self.write_json("runtime/polaris_catalog.json", catalog)
        catalog_body = catalog.get("catalog", catalog)
        if not isinstance(catalog_body, dict) or catalog_body.get("name") != CATALOG:
            raise AcceptanceError("Polaris did not return the expected catalog")

        objects = self.list_objects(f"warehouse/{self.run_id}_")
        self.write_json("runtime/object_paths.json", objects)
        contents = assert_task_object_listing(objects, run_id=self.run_id)
        self.write_csv(
            "runtime/object_paths.csv",
            [
                ["key", "size", "etag"],
                *[
                    [item["Key"], item["Size"], item.get("ETag")]
                    for item in contents
                ],
            ],
        )
        self.write_json(
            "runtime/end_to_end.json",
            {
                "catalog": CATALOG,
                "table_count": len(rows) - 1,
                "evolution_table": (
                    f"{CATALOG}.{self.evolution_schema}.{EVOLUTION_TABLE}"
                ),
                "object_count": len(contents),
                "required_object_types": [
                    "Parquet data",
                    "Iceberg metadata JSON",
                    "Iceberg Avro manifest",
                ],
            },
        )
        self.end_to_end_evidence_captured = True

    def cleanup_task_data(self) -> None:
        schemas = [
            self.evolution_schema,
            *(f"{self.baseline_prefix}_{layer}" for layer in reversed(LAYERS)),
        ]
        drop_logs = []
        for schema in schemas:
            result = self.capture(
                [
                    "docker",
                    "compose",
                    "exec",
                    "-T",
                    "trino",
                    "trino",
                    "--execute",
                    f'DROP SCHEMA IF EXISTS "{CATALOG}"."{schema}" CASCADE',
                ],
                None,
            )
            drop_logs.append(f"{schema}: {result.stdout}{result.stderr}")
        self.write_text("cleanup/drop_schemas.log", "".join(drop_logs))

        quoted_schemas = ", ".join(f"'{schema}'" for schema in schemas)
        remaining_schemas = self.query_csv(
            "cleanup/remaining_schemas.csv",
            "SELECT schema_name FROM lakehouse.information_schema.schemata "
            f"WHERE schema_name IN ({quoted_schemas}) ORDER BY schema_name",
        )
        assert_task_schemas_absent(remaining_schemas)

        remaining = self.list_objects(f"warehouse/{self.run_id}_")
        self.write_json("cleanup/remaining_objects.json", remaining)
        if remaining.get("Contents"):
            raise AcceptanceError("task object paths remain after schema cleanup")

    def finalize(self, error: Exception | None) -> Exception | None:
        """Set AC-020 PASS only after cleanup, restoration, scan, and manifest gates."""
        if error is None:
            pending = [
                ac for ac in SCHEMA_EVOLUTION_ACS[:-1] if self.ac_results[ac] != "PASS"
            ]
            if pending:
                error = AcceptanceError(
                    "cannot finalize AC-020 with pending behavior checks: "
                    + ", ".join(pending)
                )
            elif not self.end_to_end_evidence_captured:
                error = AcceptanceError("end-to-end catalog/object evidence was not captured")
            elif not self.data_cleaned:
                error = AcceptanceError("task-owned schemas and objects were not cleaned")
            elif not self.environment_restored:
                error = AcceptanceError("Compose environment was not restored")

        try:
            self.assert_no_secrets_in_evidence()
        except Exception as scan_error:
            if error is None:
                error = scan_error

        if error is None:
            try:
                self.write_evidence_manifest()
                manifest_path = self.evidence_dir / "evidence_manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if not isinstance(manifest, dict):
                    raise AcceptanceError("evidence manifest root is invalid")
                assert_final_evidence_manifest(manifest)
                self.ac_results["AC-020"] = "PASS"
                self.write_summary("PASS", None)
                return None
            except Exception as finalization_error:
                self.ac_results["AC-020"] = "NOT_RUN"
                error = finalization_error

        try:
            self.write_summary("FAIL", f"{type(error).__name__}: {error}")
        except Exception:
            pass
        try:
            self.write_evidence_manifest()
        except Exception:
            pass
        return error

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
                "baseline_prefix": self.baseline_prefix,
                "evolution_schema": self.evolution_schema,
                "evolution_table": EVOLUTION_TABLE,
                "command_count": len(self.commands),
                "evidence": {
                    "commands": "commands.jsonl",
                    "core": "core/",
                    "evolution": "evolution/",
                    "catalog_tables": "runtime/catalog_tables.csv",
                    "polaris_catalog": "runtime/polaris_catalog.json",
                    "object_paths": "runtime/object_paths.json",
                    "end_to_end": "runtime/end_to_end.json",
                    "remaining_schemas": "cleanup/remaining_schemas.csv",
                    "cleanup": "cleanup/environment.json",
                    "secret_scan": "secret_scan.json",
                    "manifest": "evidence_manifest.json",
                },
            },
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the isolated core regression and Iceberg schema-evolution exercise, "
            "capture evidence, and clean up only task-owned schemas and objects."
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
        SchemaEvolutionAcceptanceRun(args.run_id, evidence_dir).run()
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
