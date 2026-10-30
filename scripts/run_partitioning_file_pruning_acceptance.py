#!/usr/bin/env python3
"""Run the isolated partitioning and file-pruning acceptance workflow."""

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
    ROOT,
    RUN_ID_PATTERN,
    iso_now,
)

DATASETS = ("balanced", "skewed")
LAYOUTS = ("u", "d", "r", "dr")
PARTITIONING_FILE_PRUNING_ACS = tuple(
    f"AC-{number:03d}" for number in range(21, 28)
)


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
