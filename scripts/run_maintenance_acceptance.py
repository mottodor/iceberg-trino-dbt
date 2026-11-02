#!/usr/bin/env python3
"""Isolated maintenance exercise; see docs/spec.md section 13."""
from __future__ import annotations

import argparse
import json
import statistics
import time
from typing import Any
from datetime import datetime, timezone
from pathlib import Path

from learning_exercise import LearningExercise
from run_acceptance import BUCKET, CATALOG, DEFAULT_EVIDENCE_ROOT, AcceptanceError
from run_time_travel_acceptance import require, assert_negative_result


def expected_rows(count: int) -> list[list[Any]]:
    return [[i, f"R{i % 4}", 3 * i] for i in range(1, count + 1)]


def assert_rows(rows: list[list[Any]], count: int) -> None:
    require(len(rows) == count, "maintenance row count mismatch")
    for row, wanted in zip(rows, expected_rows(count)):
        require(isinstance(row, list) and len(row) == 3, "invalid maintenance row shape")
        require(type(row[0]) is int and type(row[1]) is str and type(row[2]) is int, "maintenance typed grain mismatch")
        require(row == wanted, "maintenance independent oracle mismatch")


def distribution(files: dict[str, Any]) -> dict[str, Any]:
    sizes = sorted(file["size"] for file in files.values() if file["content"] == 0)
    require(bool(sizes) and all(type(size) is int and size > 0 for size in sizes), "empty/invalid current data inventory")
    return {"count": len(sizes), "min": min(sizes), "median": statistics.median(sizes), "max": max(sizes), "total_bytes": sum(sizes)}


def same_table(before: dict[str, Any], after: dict[str, Any]) -> None:
    for key in ("table-uuid", "schemas", "current-schema-id", "format-version", "partition-specs", "default-spec-id"):
        require(before["metadata"].get(key) == after["metadata"].get(key), f"maintenance changed {key}")


def assert_compaction(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    same_table(before, after)
    assert_rows(before["rows"], 2048)
    require(after["rows"] == before["rows"], "compaction changed logical data")
    old, new = distribution(before["files"]), distribution(after["files"])
    require(old["count"] >= 16 and new["count"] * 2 <= old["count"], "compaction did not halve current files")
    snapshots = before["metadata"]["snapshots"]
    rewritten = after["metadata"]["snapshots"]
    require(len(rewritten) == len(snapshots) + 1, "compaction snapshot count mismatch")
    require({s["snapshot-id"] for s in snapshots} < {s["snapshot-id"] for s in rewritten}, "compaction lost historical snapshots")
    current = after["metadata"]["current-snapshot-id"]
    require(next(s for s in rewritten if s["snapshot-id"] == current).get("parent-snapshot-id") == before["metadata"]["current-snapshot-id"], "compaction parent mismatch")
    for key, digest in before["sha256"].items():
        if "/data/" in key:
            require(after["sha256"].get(key) == digest, "compaction destroyed historical data")
    return {"before": old, "after": new, "rows_unchanged": True, "history_preserved": True}


class MaintenanceRun(LearningExercise):
    def rows_query(self, relation: str | None = None) -> str:
        return f"SELECT json_format(CAST(ARRAY[CAST(event_id AS JSON), CAST(route_id AS JSON), CAST(amount_units AS JSON)] AS JSON)) AS row_json FROM {relation or self.table} ORDER BY event_id"

    def capture_state(self, name: str) -> dict[str, Any]:
        return self.snapshot(name, self.rows_query())

    def verify_control(self, state: dict[str, Any]) -> None:
        metadata = self.metadata(table="control")
        require(metadata == self.control_metadata, "control catalog pointer changed")
        prefix = self.control_metadata["metadata"]["location"].removeprefix(f"s3://{BUCKET}/").rstrip("/") + "/"
        signature = {key: digest for key, digest in state["sha256"].items() if key.startswith(prefix)}
        require(bool(signature), "missing control files")
        if hasattr(self, "control_hashes"):
            require(signature == self.control_hashes, "control content changed")
        else:
            self.control_hashes = signature
        rows = self.query_csv(f"control/{len(self.commands)}.csv", f"SELECT token FROM {self.relation('control')}")
        require(rows == [["token"], ["unchanged"]], "control rows changed")

    def stage_fixture(self) -> None:
        self.current_ac = "AC-035"
        self.create_schema(self.schema, "fixture/create_schema")
        self.sql("fixture/control", f"CREATE TABLE {self.relation('control')} AS SELECT 'unchanged' AS token")
        self.control_metadata = self.metadata(table="control")
        for batch in range(16):
            start, end = batch * 128 + 1, (batch + 1) * 128
            select = f"SELECT i AS event_id, CAST('R' || CAST(i % 4 AS VARCHAR) AS VARCHAR) AS route_id, BIGINT '3' * i AS amount_units FROM UNNEST(sequence(BIGINT '{start}', BIGINT '{end}')) t(i)"
            statement = (f"CREATE TABLE {self.table} WITH (format='PARQUET', format_version=2) AS " if batch == 0 else f"INSERT INTO {self.table} ") + select
            self.sql(f"fixture/batch_{batch:02}", statement)
        self.fragmented = self.capture_state("fragmented")
        assert_rows(self.fragmented["rows"], 2048)
        columns = [row[:2] for row in self.fragmented["columns"][1:]]
        require(columns == [["event_id", "bigint"], ["route_id", "varchar"], ["amount_units", "bigint"]], "maintenance schema mismatch")
        require(len(self.fragmented["metadata"]["snapshots"]) == 16, "expected exactly sixteen data commits")
        stats = distribution(self.fragmented["files"])
        require(stats["count"] >= 16 and stats["max"] < 1024**2, "small-files workload missing")
        self.verify_control(self.fragmented)
        self.capture_plan("fragmented")
        self.write_json("fixture/comparison.json", {"rows": 2048, "snapshots": 16, "distribution": stats, "oracle": "i, R(i%4), 3*i"})
        self.ac_results["AC-035"] = "PASS"

    def capture_plan(self, name: str) -> None:
        query = f"SELECT sum(event_id * amount_units) FROM {self.table} WHERE route_id='R1'"
        for kind, explain in (("distributed", "EXPLAIN (TYPE DISTRIBUTED)"), ("analyze", "EXPLAIN ANALYZE")):
            self.capture(["docker", "compose", "exec", "-T", "trino", "trino", "--execute", f"{explain} {query}"], f"plans/{name}_{kind}.txt")


    def stage_compaction(self) -> None:
        self.current_ac = "AC-036"
        before = self.capture_state("before_compaction")
        require(before == self.fragmented, "state changed before compaction")
        self.sql("compaction/optimize", f"ALTER TABLE {self.table} EXECUTE optimize(file_size_threshold => '1MB')")
        self.compacted = self.capture_state("compacted")
        proof = assert_compaction(before, self.compacted)
        historical = self.rows("compaction/historical", self.rows_query(f"{self.table} FOR VERSION AS OF {before['metadata']['current-snapshot-id']}"))
        require(historical == before["rows"], "old snapshot unreadable after compaction")
        self.verify_control(self.compacted)
        self.capture_plan("compacted")
        self.write_json("compaction/comparison.json", proof)
        self.ac_results["AC-036"] = "PASS"

    def workflow(self) -> None:
        raise AcceptanceError("maintenance behavioral stages are not implemented")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--check-environment", action="store_true")
    args = parser.parse_args()
    try:
        run = MaintenanceRun(args.run_id, DEFAULT_EVIDENCE_ROOT / args.run_id)
        run.run((lambda: None) if args.check_environment else run.workflow, required=set(), complete=not args.check_environment)
    except (AcceptanceError, OSError) as error:
        print(f"Maintenance failed: {error}")
        return 1
    print("Maintenance environment CHECKPOINT" if args.check_environment else "Maintenance PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
