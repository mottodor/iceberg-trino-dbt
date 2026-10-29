#!/usr/bin/env python3
"""Run the isolated core-slice acceptance workflow and save redacted evidence."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE_ROOT = ROOT / "artifacts" / "acceptance"
PROJECT_NAME = "iceberg-trino-dbt"
CATALOG = "lakehouse"
BUCKET = "iceberg-trino-dbt"
REQUIRED_ENV = (
    "RUSTFS_ACCESS_KEY",
    "RUSTFS_SECRET_KEY",
    "POLARIS_CLIENT_ID",
    "POLARIS_CLIENT_SECRET",
)
LAYERS = ("fixtures", "bronze", "silver", "gold")
RUN_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{2,31}$")

NEGATIVE_SCENARIOS = (
    (
        "conflicting_payload",
        "assert_no_conflicting_event_payloads",
    ),
    (
        "departure_without_arrival",
        "assert_no_departure_without_arrival",
    ),
    (
        "repeated_arrival",
        "assert_no_repeated_arrival_before_departure",
    ),
)


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    returncode: int
    duration_seconds: float
    stdout: str
    stderr: str


class AcceptanceError(RuntimeError):
    """An acceptance assertion or safe-operation precondition failed."""


class AcceptanceRun:
    def __init__(self, run_id: str, evidence_dir: Path) -> None:
        self.run_id = run_id
        self.evidence_dir = evidence_dir
        self.started_at = iso_now()
        self.commands: list[dict[str, Any]] = []
        self.stack_started = False
        self.query_ready = False
        self.prefixes_owned = False
        self.data_cleaned = False
        self.initial_volumes: list[str] = []
        self.final_volumes: list[str] = []
        self.ac_results: dict[str, str] = {
            ac: "NOT_RUN"
            for ac in (
                "AC-001",
                "AC-003",
                "AC-004",
                "AC-005",
                "AC-006",
                "AC-007",
                "AC-008",
                "AC-009",
                "AC-010",
                "AC-011",
                "AC-012",
            )
        }
        self.baseline_prefix = f"{run_id}_baseline"
        self.negative_prefixes = {
            scenario: f"{run_id}_neg_{index}"
            for index, (scenario, _) in enumerate(NEGATIVE_SCENARIOS, start=1)
        }

    def run(self) -> None:
        self.preflight()
        error: Exception | None = None
        try:
            self.start_stack()
            self.assert_stack_state()
            self.assert_query_ready()
            self.assert_prefixes_absent()
            self.prefixes_owned = True
            self.run_baseline()
            self.run_negative_scenarios()
            self.capture_catalog_and_object_evidence()
            self.assert_scope_contract()
            self.cleanup_task_data()
            self.data_cleaned = True
        except Exception as caught:  # cleanup must run for any failed assertion
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

    def preflight(self) -> None:
        missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
        if missing:
            raise AcceptanceError(
                "missing required local environment variables: " + ", ".join(missing)
            )

        if self.evidence_dir.exists():
            raise AcceptanceError(
                f"evidence directory already exists; choose a new run id: {self.evidence_dir}"
            )
        self.evidence_dir.mkdir(parents=True)

        if shutil.which("docker") is None:
            raise AcceptanceError("docker CLI is unavailable")

        existing = self.capture(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                f"label=com.docker.compose.project={PROJECT_NAME}",
                "--format",
                "{{.Names}}",
            ],
            "preflight/existing_containers.txt",
        )
        if existing.stdout.strip():
            raise AcceptanceError(
                "refusing to manage an already-running or stopped Compose project: "
                + existing.stdout.strip().replace("\n", ", ")
            )

        self.initial_volumes = self.project_volumes()
        self.run_command(
            ["docker", "compose", "--profile", "tools", "config", "--quiet"],
            "preflight/compose_config.log",
        )

        tracked = self.capture(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            "preflight/tracked_files.txt",
        ).stdout.splitlines()
        self.write_json(
            "preflight/scope.json",
            {
                "tracked_file_count": len(tracked),
                "excluded_scope_paths_present": sorted(
                    path
                    for path in tracked
                    if any(
                        token in path.lower()
                        for token in (
                            "airflow",
                            "kafka",
                            "debezium",
                            "spark",
                            "clickhouse",
                            "superset",
                        )
                    )
                ),
            },
        )

    def start_stack(self) -> None:
        self.stack_started = True
        self.run_command(
            [
                "docker",
                "compose",
                "up",
                "-d",
                "--wait",
                "--wait-timeout",
                "240",
                "rustfs",
                "polaris",
                "trino",
            ],
            "runtime/compose_up.log",
        )

    def stop_stack(self) -> None:
        self.run_command(
            ["docker", "compose", "down"],
            "cleanup/compose_down.log",
        )
        self.stack_started = False

    def assert_stack_state(self) -> None:
        result = self.capture(
            ["docker", "compose", "ps", "-a", "--format", "json"],
            "runtime/compose_ps.jsonl",
        )
        rows = [
            load_json_text(line, "docker compose ps")
            for line in result.stdout.splitlines()
            if line.strip()
        ]
        by_service = {row["Service"]: row for row in rows}
        for service in ("rustfs", "polaris", "trino"):
            row = by_service.get(service)
            if row is None or row.get("State") != "running" or row.get("Health") != "healthy":
                raise AcceptanceError(f"service is not healthy: {service}")
        for service in ("bucket-setup", "polaris-setup"):
            row = by_service.get(service)
            if row is None or row.get("ExitCode") != 0:
                raise AcceptanceError(f"setup service did not exit successfully: {service}")

    def assert_query_ready(self) -> None:
        command = [
            "docker",
            "compose",
            "exec",
            "-T",
            "trino",
            "trino",
            "--output-format",
            "CSV_HEADER",
            "--execute",
            "SELECT 1 AS ready",
        ]
        last_result: CommandResult | None = None
        for attempt in range(1, 16):
            result = execute(command)
            self.record_command(result)
            self.write_text(
                f"runtime/trino_ready_attempt_{attempt}.stdout.csv",
                result.stdout,
            )
            self.write_text(
                f"runtime/trino_ready_attempt_{attempt}.stderr.log",
                result.stderr,
            )
            last_result = result
            if result.returncode == 0:
                rows = list(csv.reader(result.stdout.splitlines()))
                if rows != [["ready"], ["1"]]:
                    raise AcceptanceError(
                        f"unexpected Trino readiness result: {rows}"
                    )
                self.write_text("runtime/trino_ready.csv", result.stdout)
                self.query_ready = True
                return
            time.sleep(2)
        raise AcceptanceError(
            "Trino did not accept SELECT 1 after 15 attempts; "
            f"last exit={last_result.returncode if last_result else 'unavailable'}"
        )

    def assert_prefixes_absent(self) -> None:
        schema_names = [
            f"{prefix}_{layer}"
            for prefix in [self.baseline_prefix, *self.negative_prefixes.values()]
            for layer in LAYERS
        ]
        quoted_names = ", ".join(f"'{name}'" for name in schema_names)
        rows = self.query_csv(
            "preflight/existing_schemas.csv",
            "SELECT schema_name FROM lakehouse.information_schema.schemata "
            f"WHERE schema_name IN ({quoted_names}) ORDER BY schema_name",
        )
        if len(rows) != 1:
            raise AcceptanceError(f"run-prefix schemas already exist: {rows[1:]}")

    def run_baseline(self) -> None:
        prefix = self.baseline_prefix
        self.load_fixtures(prefix, "baseline", "batch_1", "baseline/batch_1_load.log")
        self.dbt(
            prefix,
            ["run", "--select", "tag:bronze", "tag:silver", "tag:gold"],
            "baseline/stage_1",
            "baseline/stage_1/dbt_run.log",
        )
        self.assert_run_results(
            "baseline/stage_1/target/run_results.json",
            allowed_statuses={"success"},
            expected_count=15,
        )
        before = self.query_csv(
            "baseline/p3_before.csv",
            package_snapshot_sql(prefix, "P3"),
        )
        assert_package_snapshot(before, visits=0, dwell=0.0, route_ratio=1.0)

        self.load_fixtures(prefix, "baseline", "batch_2", "baseline/batch_2_load.log")
        self.dbt(
            prefix,
            ["build", "--select", "tag:bronze", "tag:silver", "tag:gold"],
            "baseline/final_build",
            "baseline/final_build/dbt_build.log",
        )
        results = self.assert_run_results(
            "baseline/final_build/target/run_results.json",
            allowed_statuses={"success", "pass"},
            expected_count=128,
        )
        for test_name in (
            "assert_no_conflicting_event_payloads",
            "assert_no_departure_without_arrival",
            "assert_no_repeated_arrival_before_departure",
        ):
            if not any(
                test_name in item["unique_id"] and item["status"] == "pass"
                for item in results
            ):
                raise AcceptanceError(f"baseline DQ test did not pass: {test_name}")

        after = self.query_csv(
            "baseline/p3_after.csv",
            package_snapshot_sql(prefix, "P3"),
        )
        assert_package_snapshot(after, visits=2, dwell=3.0, route_ratio=1.5)
        if before[1][1:4] != after[1][1:4]:
            raise AcceptanceError("P3 delivery state, duration, or on-time flag changed")

        p3_visits = self.query_csv(
            "baseline/p3_visits.csv",
            f"""
            SELECT hub_code, dwell_time_hours, is_open
            FROM {qualified(prefix, 'gold', 'gold_hub_visits')}
            WHERE package_id = 'P3'
            ORDER BY visit_seq
            """,
        )
        if p3_visits != [
            ["hub_code", "dwell_time_hours", "is_open"],
            ["B", "2.0", "false"],
            ["X", "1.0", "false"],
        ]:
            raise AcceptanceError(f"unexpected P3 visits: {p3_visits}")

        self.assert_route_binding(prefix)
        self.assert_layer_counts(prefix)
        self.assert_package_facts(prefix)
        self.assert_aggregates(prefix)

    def run_negative_scenarios(self) -> None:
        for scenario, test_name in NEGATIVE_SCENARIOS:
            prefix = self.negative_prefixes[scenario]
            base = f"negative/{scenario}"
            self.load_fixtures(prefix, "baseline", "all", f"{base}/baseline_load.log")
            self.load_fixtures(prefix, scenario, "all", f"{base}/scenario_load.log")
            self.dbt(
                prefix,
                ["run", "--select", "tag:bronze", "tag:silver"],
                f"{base}/models",
                f"{base}/models/dbt_run.log",
            )
            self.assert_run_results(
                f"{base}/models/target/run_results.json",
                allowed_statuses={"success"},
                expected_count=11,
            )
            result = self.dbt(
                prefix,
                [
                    "test",
                    "--select",
                    test_name,
                    "--indirect-selection",
                    "empty",
                ],
                f"{base}/expected_failure",
                f"{base}/expected_failure/dbt_test.log",
                allowed_returncodes={1},
            )
            if result.returncode != 1:
                raise AcceptanceError(
                    f"negative scenario unexpectedly returned {result.returncode}: {scenario}"
                )
            run_results = self.assert_run_results(
                f"{base}/expected_failure/target/run_results.json",
                allowed_statuses={"fail"},
                expected_count=1,
            )
            only = run_results[0]
            unique_id, failure_count = assert_expected_failure_result(
                scenario,
                test_name,
                only,
            )
            self.write_json(
                f"{base}/expected_failure/verification.json",
                {
                    "scenario": scenario,
                    "expected_test": test_name,
                    "dbt_exit_code": result.returncode,
                    "unique_id": unique_id,
                    "status": only.get("status"),
                    "failures": failure_count,
                },
            )

    def assert_route_binding(self, prefix: str) -> None:
        rows = self.query_csv(
            "baseline/route_binding.csv",
            f"""
            SELECT package_id, route_version_id, CAST(promised_delivery_at AS varchar)
            FROM {qualified(prefix, 'silver', 'silver_package_route_binding')}
            ORDER BY package_id
            """,
        )
        expected_versions = {
            "P1": "R1-V1",
            "P2": "R1-V2",
            "P3": "R1-V2",
            "P4": "R1-V2",
        }
        if len(rows) != 5 or {row[0]: row[1] for row in rows[1:]} != expected_versions:
            raise AcceptanceError(f"unexpected route binding: {rows}")

    def assert_layer_counts(self, prefix: str) -> None:
        rows = self.query_csv(
            "baseline/layer_counts.csv",
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
        )
        expected = [28, 28, 27, 4, 3, 1, 7, 6, 1, 2]
        if len(rows) != 2 or [
            parse_int(value, "layer count") for value in rows[1]
        ] != expected:
            raise AcceptanceError(f"unexpected layer counts: {rows}")

        duplicates = self.query_csv(
            "baseline/duplicate_reconciliation.csv",
            f"""
            SELECT
                (SELECT count(*) FROM {qualified(prefix, 'bronze', 'bronze_tracking_events')} WHERE event_id = 'P3-E02') AS bronze_rows,
                (SELECT count(DISTINCT event_payload_fingerprint) FROM {qualified(prefix, 'silver', 'silver_tracking_events_typed')} WHERE event_id = 'P3-E02') AS payload_variants,
                (SELECT count(*) FROM {qualified(prefix, 'silver', 'silver_tracking_events')} WHERE event_id = 'P3-E02') AS canonical_rows
            """,
        )
        if len(duplicates) != 2 or [
            parse_int(value, "P3 duplicate reconciliation")
            for value in duplicates[1]
        ] != [2, 1, 1]:
            raise AcceptanceError(f"unexpected duplicate reconciliation: {duplicates}")

    def assert_package_facts(self, prefix: str) -> None:
        rows = self.query_csv(
            "baseline/package_facts.csv",
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
        )
        if len(rows) != 5:
            raise AcceptanceError(f"unexpected package-fact row count: {rows}")
        facts = {row[0]: row[1:] for row in rows[1:]}
        if set(facts) != {"P1", "P2", "P3", "P4"}:
            raise AcceptanceError(f"unexpected package ids: {sorted(facts)}")
        assert_fact(facts["P1"], "delivered", 48.0, 0.0, "true", 1, 1, 0, 4.0, 1.0, 0.0)
        assert_fact(facts["P2"], "delivered", 48.0, 12.0, "false", 3, 3, 0, 16.0, 1.5, 50.0)
        assert_fact(facts["P3"], "delivered", 36.0, 0.0, "true", 2, 2, 0, 3.0, 1.5, 50.0)
        p4 = facts["P4"]
        if not (
            len(p4) == 10
            and p4[0] == "arrived_at_hub"
            and p4[1:4] == ["", "", ""]
            and [
                parse_int(p4[4], "P4 visit count"),
                parse_int(p4[5], "P4 completed visit count"),
                parse_int(p4[6], "P4 open visit count"),
            ]
            == [1, 0, 1]
            and close(parse_float(p4[7], "P4 dwell"), 0.0)
            and parse_float(p4[8], "P4 route ratio") > 0.0
            and p4[9] == ""
        ):
            raise AcceptanceError(f"unexpected P4 fact: {p4}")

        p4_visit = self.query_csv(
            "baseline/p4_open_visit.csv",
            f"""
            SELECT package_id, hub_code, departed_at, dwell_time_hours, is_open
            FROM {qualified(prefix, 'gold', 'gold_hub_visits')}
            WHERE package_id = 'P4'
            """,
        )
        if p4_visit != [
            ["package_id", "hub_code", "departed_at", "dwell_time_hours", "is_open"],
            ["P4", "D", "", "", "true"],
        ]:
            raise AcceptanceError(f"unexpected P4 open visit: {p4_visit}")

    def assert_aggregates(self, prefix: str) -> None:
        route_rows = self.query_csv(
            "baseline/route_version_efficiency.csv",
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
        )
        assert_route_aggregate_rows(route_rows)

        hub_rows = self.query_csv(
            "baseline/route_version_hub_dwell.csv",
            f"""
            SELECT route_version_id, hub_code, completed_dwell_hours
            FROM {qualified(prefix, 'gold', 'gold_route_version_hub_dwell')}
            ORDER BY route_version_id, hub_code
            """,
        )
        expected = {
            ("R1-V1", "B"): 4.0,
            ("R1-V2", "B"): 6.0,
            ("R1-V2", "D"): 2.0,
            ("R1-V2", "X"): 11.0,
        }
        actual = {
            (row[0], row[1]): parse_float(row[2], "hub dwell")
            for row in hub_rows[1:]
        }
        if actual != expected:
            raise AcceptanceError(f"unexpected hub aggregates: {hub_rows}")

    def capture_catalog_and_object_evidence(self) -> None:
        prefixes = [self.baseline_prefix, *self.negative_prefixes.values()]
        where = " OR ".join(f"table_schema LIKE '{prefix}_%'" for prefix in prefixes)
        rows = self.query_csv(
            "runtime/catalog_tables.csv",
            "SELECT table_schema, table_name FROM lakehouse.information_schema.tables "
            f"WHERE {where} ORDER BY table_schema, table_name",
        )
        if len(rows) - 1 != 68:
            raise AcceptanceError(f"unexpected task table count: {len(rows) - 1}")

        catalog = self.fetch_polaris_catalog()
        self.write_json("runtime/polaris_catalog.json", catalog)
        catalog_body = catalog.get("catalog", catalog)
        if catalog_body.get("name") != CATALOG:
            raise AcceptanceError("Polaris did not return the expected catalog")

        objects = self.list_objects(f"warehouse/{self.run_id}_")
        self.write_json("runtime/object_paths.json", objects)
        contents = objects.get("Contents") or []
        keys = [item["Key"] for item in contents]
        if not keys:
            raise AcceptanceError("no task object paths were found")
        if not any(key.endswith(".parquet") for key in keys):
            raise AcceptanceError("task object paths contain no Parquet data file")
        if not any(key.endswith(".metadata.json") for key in keys):
            raise AcceptanceError("task object paths contain no Iceberg metadata JSON")
        if not any(key.endswith(".avro") for key in keys):
            raise AcceptanceError("task object paths contain no Iceberg Avro manifest")
        self.write_csv(
            "runtime/object_paths.csv",
            [["key", "size"], *[[item["Key"], item["Size"]] for item in contents]],
        )

    def assert_scope_contract(self) -> None:
        scope = load_json_path(
            self.evidence_dir / "preflight/scope.json",
            "scope evidence",
        )
        if scope["excluded_scope_paths_present"]:
            raise AcceptanceError(
                "excluded technology path present: "
                + ", ".join(scope["excluded_scope_paths_present"])
            )
        self.ac_results["AC-001"] = "PASS"

    def cleanup_task_data(self) -> None:
        prefixes = [self.baseline_prefix, *self.negative_prefixes.values()]
        drop_logs = []
        for prefix in prefixes:
            for layer in reversed(LAYERS):
                schema = f"{prefix}_{layer}"
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
        remaining = self.list_objects(f"warehouse/{self.run_id}_")
        self.write_json("cleanup/remaining_objects.json", remaining)
        if remaining.get("Contents"):
            raise AcceptanceError("task object paths remain after schema cleanup")

    def assert_environment_restored(self) -> None:
        containers = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                f"label=com.docker.compose.project={PROJECT_NAME}",
                "--format",
                "{{.Names}}",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if containers.returncode != 0 or containers.stdout.strip():
            raise AcceptanceError("Compose project containers remain after acceptance")
        self.final_volumes = self.project_volumes()
        if not set(self.initial_volumes).issubset(self.final_volumes):
            raise AcceptanceError("a pre-existing project volume was removed")
        self.write_json(
            "cleanup/environment.json",
            {
                "initial_project_containers": [],
                "final_project_containers": [],
                "initial_project_volumes": self.initial_volumes,
                "final_project_volumes": self.final_volumes,
                "preexisting_volumes_preserved": True,
            },
        )

    def load_fixtures(
        self,
        prefix: str,
        scenario: str,
        batch: str,
        log_path: str,
    ) -> None:
        command = self.dbt_container_command(prefix, None)
        command.extend(
            [
                "--entrypoint",
                "python",
                "dbt",
                "scripts/load_fixtures.py",
                "--scenario",
                scenario,
                "--batch",
                batch,
            ]
        )
        self.run_command(command, log_path)

    def dbt(
        self,
        prefix: str,
        args: Sequence[str],
        artifact_base: str,
        log_path: str,
        *,
        allowed_returncodes: set[int] | None = None,
    ) -> CommandResult:
        target_path = f"/evidence/{artifact_base}/target"
        dbt_log_path = f"/evidence/{artifact_base}/logs"
        command = self.dbt_container_command(prefix, self.evidence_dir)
        command.extend(
            [
                "-e",
                f"DBT_TARGET_PATH={target_path}",
                "-e",
                f"DBT_LOG_PATH={dbt_log_path}",
                "-e",
                "DBT_SEND_ANONYMOUS_USAGE_STATS=false",
                "dbt",
                *args,
            ]
        )
        return self.run_command(
            command,
            log_path,
            allowed_returncodes=allowed_returncodes,
        )

    def dbt_container_command(
        self,
        prefix: str,
        evidence_mount: Path | None,
    ) -> list[str]:
        command = [
            "docker",
            "compose",
            "--profile",
            "tools",
            "run",
            "--rm",
            "--no-deps",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "-e",
            f"DBT_TRINO_SCHEMA={prefix}",
        ]
        if evidence_mount is not None:
            command.extend(["-v", f"{evidence_mount.resolve()}:/evidence"])
        return command

    def query_csv(self, relative_path: str, sql: str) -> list[list[str]]:
        result = self.capture(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "trino",
                "trino",
                "--output-format",
                "CSV_HEADER",
                "--execute",
                normalize_sql(sql),
            ],
            relative_path,
        )
        return list(csv.reader(result.stdout.splitlines()))

    def list_objects(self, prefix: str) -> dict[str, Any]:
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
                "list-objects-v2",
                "--bucket",
                BUCKET,
                "--prefix",
                prefix,
                "--output",
                "json",
            ],
            None,
        )
        return load_json_text(result.stdout, "RustFS object listing")

    def fetch_polaris_catalog(self) -> dict[str, Any]:
        port_result = self.capture(
            ["docker", "compose", "port", "polaris", "8181"],
            "runtime/polaris_port.txt",
        )
        port = port_result.stdout.strip().rsplit(":", 1)[-1]
        base_url = f"http://127.0.0.1:{port}"
        credentials = (
            f"{os.environ['POLARIS_CLIENT_ID']}:{os.environ['POLARIS_CLIENT_SECRET']}"
        )
        auth = base64.b64encode(credentials.encode()).decode()
        token_request = urllib.request.Request(
            f"{base_url}/api/catalog/v1/oauth/tokens",
            data=urllib.parse.urlencode(
                {
                    "grant_type": "client_credentials",
                    "scope": "PRINCIPAL_ROLE:ALL",
                }
            ).encode(),
            headers={
                "Authorization": f"Basic {auth}",
                "Polaris-Realm": "POLARIS",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(token_request, timeout=20) as response:
                token = json.load(response)["access_token"]
            catalog_request = urllib.request.Request(
                f"{base_url}/api/management/v1/catalogs/{CATALOG}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Polaris-Realm": "POLARIS",
                },
            )
            with opener.open(catalog_request, timeout=20) as response:
                return json.load(response)
        except (urllib.error.URLError, KeyError, json.JSONDecodeError) as error:
            raise AcceptanceError(f"Polaris catalog evidence request failed: {error}") from error

    def assert_run_results(
        self,
        relative_path: str,
        *,
        allowed_statuses: set[str],
        expected_count: int,
    ) -> list[dict[str, Any]]:
        path = self.evidence_dir / relative_path
        if not path.is_file():
            raise AcceptanceError(f"dbt run_results.json is missing: {relative_path}")
        document = load_json_path(path, f"dbt artifact {relative_path}")
        results = document.get("results") or []
        statuses = {item.get("status") for item in results}
        if len(results) != expected_count or not statuses.issubset(allowed_statuses):
            raise AcceptanceError(
                f"unexpected dbt results for {relative_path}: "
                f"count={len(results)} statuses={sorted(statuses)}"
            )
        return results

    def run_command(
        self,
        command: Sequence[str],
        log_path: str | None,
        *,
        allowed_returncodes: set[int] | None = None,
    ) -> CommandResult:
        result = execute(command)
        self.record_command(result)
        if log_path is not None:
            self.write_text(log_path, result.stdout + result.stderr)
        allowed = allowed_returncodes or {0}
        if result.returncode not in allowed:
            raise AcceptanceError(
                f"command exited {result.returncode}: {display_command(command)}"
            )
        return result

    def capture(self, command: Sequence[str], path: str | None) -> CommandResult:
        result = execute(command)
        self.record_command(result)
        if path is not None:
            self.write_text(path, result.stdout)
            if result.stderr:
                self.write_text(f"{path}.stderr.log", result.stderr)
        if result.returncode != 0:
            raise AcceptanceError(
                f"command exited {result.returncode}: {display_command(command)}"
            )
        return result

    def record_command(self, result: CommandResult) -> None:
        entry = {
            "command": display_command(result.command),
            "returncode": result.returncode,
            "duration_seconds": round(result.duration_seconds, 3),
        }
        self.commands.append(entry)
        path = self.evidence_dir / "commands.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")

    def project_volumes(self) -> list[str]:
        result = subprocess.run(
            [
                "docker",
                "volume",
                "ls",
                "--filter",
                f"label=com.docker.compose.project={PROJECT_NAME}",
                "--format",
                "{{.Name}}",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise AcceptanceError("could not list project volumes")
        return sorted(line for line in result.stdout.splitlines() if line)

    def finalize(self, error: Exception | None) -> Exception | None:
        if error is None:
            self.ac_results = {key: "PASS" for key in self.ac_results}

        try:
            self.assert_no_secrets_in_evidence()
        except Exception as scan_error:
            if error is None:
                error = scan_error

        if error is None:
            try:
                self.write_evidence_manifest()
                self.write_summary("PASS", None)
                return None
            except Exception as finalization_error:
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
                "negative_prefixes": self.negative_prefixes,
                "command_count": len(self.commands),
                "evidence": {
                    "dbt_run_results": "baseline/final_build/target/run_results.json",
                    "sql_results": "baseline/*.csv",
                    "negative_runs": "negative/*/expected_failure/target/run_results.json",
                    "catalog_tables": "runtime/catalog_tables.csv",
                    "polaris_catalog": "runtime/polaris_catalog.json",
                    "object_paths": "runtime/object_paths.csv",
                    "cleanup": "cleanup/environment.json",
                },
            },
        )

    def assert_no_secrets_in_evidence(self) -> None:
        findings: dict[str, list[str]] = {}
        for name in REQUIRED_ENV:
            value = os.environ[name].encode()
            matches = []
            for path in sorted(self.evidence_dir.rglob("*")):
                if path.is_file() and value in path.read_bytes():
                    matches.append(str(path.relative_to(self.evidence_dir)))
            if matches:
                findings[name] = matches
        self.write_json(
            "secret_scan.json",
            {
                "checked_environment_names": list(REQUIRED_ENV),
                "secret_values_written": bool(findings),
                "findings": findings,
            },
        )
        if findings:
            raise AcceptanceError(
                "local credential values were written to evidence: " + json.dumps(findings)
            )

    def write_evidence_manifest(self) -> None:
        entries = []
        for path in sorted(self.evidence_dir.rglob("*")):
            if not path.is_file() or path.name in {
                "acceptance_summary.json",
                "evidence_manifest.json",
            }:
                continue
            data = path.read_bytes()
            entries.append(
                {
                    "path": str(path.relative_to(self.evidence_dir)),
                    "size": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )
        self.write_json("evidence_manifest.json", {"files": entries})

    def write_text(self, relative_path: str, content: str) -> None:
        path = self.evidence_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def write_json(self, relative_path: str, value: Any) -> None:
        self.write_text(relative_path, json.dumps(value, indent=2, sort_keys=True) + "\n")

    def write_json_atomic(self, relative_path: str, value: Any) -> None:
        path = self.evidence_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        try:
            temporary.write_text(
                json.dumps(value, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    def write_csv(self, relative_path: str, rows: Iterable[Iterable[Any]]) -> None:
        path = self.evidence_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle).writerows(rows)


def load_json_text(value: str, source: str) -> dict[str, Any]:
    try:
        document = json.loads(value)
    except json.JSONDecodeError as error:
        raise AcceptanceError(f"invalid JSON from {source}: {error}") from error
    if not isinstance(document, dict):
        raise AcceptanceError(f"expected a JSON object from {source}")
    return document


def load_json_path(path: Path, source: str) -> dict[str, Any]:
    try:
        return load_json_text(path.read_text(encoding="utf-8"), source)
    except OSError as error:
        raise AcceptanceError(f"could not read {source}: {error}") from error


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the isolated baseline, staged late-event comparison, three expected "
            "DQ failures, catalog/object capture, cleanup, and secret scan."
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


def execute(command: Sequence[str]) -> CommandResult:
    started = time.monotonic()
    completed = subprocess.run(
        list(command),
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return CommandResult(
        command=list(command),
        returncode=completed.returncode,
        duration_seconds=time.monotonic() - started,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def display_command(command: Sequence[str]) -> str:
    return " ".join(command)


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def normalize_sql(sql: str) -> str:
    return " ".join(line.strip() for line in sql.strip().splitlines() if line.strip())


def qualified(prefix: str, layer: str, table: str) -> str:
    return f'"{CATALOG}"."{prefix}_{layer}"."{table}"'


def package_snapshot_sql(prefix: str, package_id: str) -> str:
    return f"""
        SELECT
            package_id,
            current_status,
            delivery_duration_hours,
            is_on_time,
            visit_count,
            completed_dwell_hours,
            actual_distance_meters / planned_distance_meters AS route_ratio
        FROM {qualified(prefix, 'gold', 'gold_package_delivery_fact')}
        WHERE package_id = '{package_id}'
    """


def assert_package_snapshot(
    rows: list[list[str]],
    *,
    visits: int,
    dwell: float,
    route_ratio: float,
) -> None:
    if len(rows) != 2:
        raise AcceptanceError(f"unexpected P3 snapshot row count: {rows}")
    row = rows[1]
    if not (
        len(row) == 7
        and row[0] == "P3"
        and row[1] == "delivered"
        and close(parse_float(row[2], "P3 duration"), 36.0)
        and row[3] == "true"
        and parse_int(row[4], "P3 visit count") == visits
        and close(parse_float(row[5], "P3 dwell"), dwell)
        and close(parse_float(row[6], "P3 route ratio"), route_ratio)
    ):
        raise AcceptanceError(f"unexpected P3 snapshot: {row}")


def assert_expected_failure_result(
    scenario: str,
    test_name: str,
    result: dict[str, Any],
) -> tuple[str, int]:
    unique_id = str(result.get("unique_id", ""))
    failure_count = parse_int(
        result.get("failures") or 0,
        f"{scenario} failure count",
    )
    expected_unique_id = f"test.iceberg_trino_dbt.{test_name}"
    if unique_id != expected_unique_id or failure_count != 1:
        raise AcceptanceError(
            f"negative scenario did not fail the intended test: {scenario}"
        )
    return unique_id, failure_count


def assert_route_aggregate_rows(rows: list[list[str]]) -> None:
    expected_header = [
        "route_version_id",
        "completed_package_count",
        "active_package_count",
        "on_time_rate_pct",
        "average_delay_hours",
        "average_final_route_deviation_pct",
    ]
    if len(rows) != 3 or rows[0] != expected_header:
        raise AcceptanceError(f"unexpected route aggregates: {rows}")
    actual = {row[0]: row[1:] for row in rows[1:]}
    if set(actual) != {"R1-V1", "R1-V2"}:
        raise AcceptanceError(f"unexpected route versions: {sorted(actual)}")
    expected = {
        "R1-V1": (1, 0, 100.0, 0.0, 0.0),
        "R1-V2": (2, 1, 50.0, 6.0, 50.0),
    }
    for route_version_id, values in actual.items():
        if len(values) != 5:
            raise AcceptanceError(f"unexpected route aggregate row: {values}")
        expected_values = expected[route_version_id]
        if not (
            parse_int(values[0], "completed package count") == expected_values[0]
            and parse_int(values[1], "active package count") == expected_values[1]
            and close(parse_float(values[2], "on-time rate"), expected_values[2], 0.01)
            and close(parse_float(values[3], "average delay"), expected_values[3], 0.000001)
            and close(
                parse_float(values[4], "average route deviation"),
                expected_values[4],
                0.01,
            )
        ):
            raise AcceptanceError(
                f"unexpected route aggregate for {route_version_id}: {values}"
            )


def assert_fact(
    row: list[str],
    status: str,
    duration: float,
    delay: float,
    on_time: str,
    visits: int,
    completed_visits: int,
    open_visits: int,
    dwell: float,
    ratio: float,
    deviation_pct: float,
) -> None:
    if not (
        len(row) == 10
        and row[0] == status
        and close(parse_float(row[1], "delivery duration"), duration)
        and close(parse_float(row[2], "delivery delay"), delay)
        and row[3] == on_time
        and [
            parse_int(row[4], "visit count"),
            parse_int(row[5], "completed visit count"),
            parse_int(row[6], "open visit count"),
        ]
        == [visits, completed_visits, open_visits]
        and close(parse_float(row[7], "completed dwell"), dwell)
        and close(parse_float(row[8], "route ratio"), ratio)
        and close(parse_float(row[9], "route deviation"), deviation_pct, 0.01)
    ):
        raise AcceptanceError(f"unexpected package fact: {row}")


def parse_int(value: Any, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise AcceptanceError(f"invalid integer for {field}: {value!r}") from error


def parse_float(value: Any, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise AcceptanceError(f"invalid number for {field}: {value!r}") from error


def close(actual: float, expected: float, tolerance: float = 0.000001) -> bool:
    return abs(actual - expected) <= tolerance


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
        AcceptanceRun(args.run_id, evidence_dir).run()
    except (AcceptanceError, OSError, json.JSONDecodeError) as error:
        print(f"acceptance_error: {error}", file=sys.stderr)
        print(f"evidence_dir={evidence_dir}", file=sys.stderr)
        return 1

    print(f"acceptance_ok run_id={args.run_id} evidence_dir={evidence_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
