#!/usr/bin/env python3
"""Run the isolated schema-evolution acceptance workflow and save evidence."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from run_acceptance import (
    AcceptanceError,
    AcceptanceRun,
    CATALOG,
    DEFAULT_EVIDENCE_ROOT,
    LAYERS,
    ROOT,
    RUN_ID_PATTERN,
    iso_now,
    qualified,
)

EVOLUTION_TABLE = "schema_evolution_package_delivery"
SCHEMA_EVOLUTION_ACS = tuple(f"AC-{number:03d}" for number in range(13, 21))


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


class SchemaEvolutionAcceptanceRun(AcceptanceRun):
    """Lifecycle and safety boundary for the schema-evolution slice."""

    def __init__(self, run_id: str, evidence_dir: Path) -> None:
        super().__init__(run_id, evidence_dir)
        self.ac_results = {ac: "NOT_RUN" for ac in SCHEMA_EVOLUTION_ACS}
        self.negative_prefixes = {}
        self.evolution_schema = f"{run_id}_evolution"

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
            ac for ac in SCHEMA_EVOLUTION_ACS if self.ac_results[ac] != "PASS"
        ]
        if pending:
            self.write_json(
                "evolution/pending.json",
                {
                    "completed": [
                        ac
                        for ac in SCHEMA_EVOLUTION_ACS
                        if self.ac_results[ac] == "PASS"
                    ],
                    "pending": pending,
                    "next_task": "SE-IMP-002",
                },
            )
            raise AcceptanceError(
                "schema-evolution exercise is incomplete after core regression; "
                "continue with SE-IMP-002"
            )

    def run_schema_evolution_steps(self) -> None:
        """Extension point for the evolution operations added by SE-IMP-002–005."""

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

        remaining = self.list_objects(f"warehouse/{self.run_id}_")
        self.write_json("cleanup/remaining_objects.json", remaining)
        if remaining.get("Contents"):
            raise AcceptanceError("task object paths remain after schema cleanup")

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
