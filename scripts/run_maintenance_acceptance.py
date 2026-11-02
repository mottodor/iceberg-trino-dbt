#!/usr/bin/env python3
"""Isolated maintenance exercise; see docs/spec.md section 13."""
from __future__ import annotations

import argparse
import re
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


def assert_expiration(before: dict[str, Any], after: dict[str, Any], retained: set[int], obsolete: set[str]) -> None:
    same_table(before, after)
    assert_rows(after["rows"], 2176)
    require(before["rows"] == after["rows"] and before["metadata"]["current-snapshot-id"] == after["metadata"]["current-snapshot-id"], "expiration changed current data/pointer")
    snapshots = after["metadata"]["snapshots"]
    require(len(snapshots) == 2 and {row["snapshot-id"] for row in snapshots} == retained, "expiration retained wrong snapshots")
    for key in before["files"]:
        require(after["sha256"].get(key) == before["sha256"][key], "expiration removed/changed retained data")
    require(bool(obsolete) and bool(obsolete - set(after["objects"])), "expiration removed no obsolete data files")


def assert_retention_error(result) -> None:
    message = (result.stdout + result.stderr).lower()
    require(result.returncode != 0 and "retention" in message and "minimum" in message and ("shorter" in message or "less" in message), "unrelated error cannot prove retention guard")
    require(not any(token in message for token in ("connection refused", "syntax error", "mismatched input", "access denied")), "unrelated retention failure")


def assert_orphan(before: dict[str, Any], after: dict[str, Any], old: str, young: str, outside: str) -> None:
    same_table(before, after)
    require(before["rows"] == after["rows"] and before["metadata"] == after["metadata"] and before["metadata_location"] == after["metadata_location"], "orphan cleanup changed table state")
    require(old in before["objects"] and old not in after["objects"], "aged orphan was not removed")
    require(young in after["objects"] and outside in after["objects"], "young or outside marker was deleted")
    for key, digest in before["sha256"].items():
        if key != old:
            require(after["sha256"].get(key) == digest, "orphan cleanup changed referenced/outside content")


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
        self.write_json("control/comparison.json", {"location": self.control_metadata["metadata"]["location"], "metadata_location": metadata["metadata-location"], "content_sha256": self.control_hashes, "unchanged": True})

    def stage_fixture(self) -> None:
        self.current_ac = "AC-035"
        self.create_schema(self.schema, "fixture/create_schema")
        self.sql("fixture/control", f"CREATE TABLE {self.relation('control')} AS SELECT 'unchanged' AS token")
        self.control_metadata = self.metadata(table="control")
        self.write_json("control/metadata.json", self.control_metadata)
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

    def retention_defaults(self, name: str) -> dict[str, str]:
        rows = self.query_csv(f"retention/{name}.csv", "SHOW SESSION LIKE 'lakehouse.%min_retention'")
        result = {row[0]: row[1] for row in rows[1:]}
        expected = {"lakehouse.expire_snapshots_min_retention", "lakehouse.remove_orphan_files_min_retention"}
        require(set(result) == expected and all(re.fullmatch(r"7(?:\.0+)?d", value) for value in result.values()), "global retention defaults are not seven days")
        return result

    def maintenance_command(self, operation: str, retention: str, *, relax: bool):
        require(operation in {"expire_snapshots", "remove_orphan_files"}, "unknown maintenance operation")
        self.allowlist.require_schema(self.schema)
        extra = ", retain_last => 2" if operation == "expire_snapshots" else ""
        statement = f"ALTER TABLE {self.table} EXECUTE {operation}(retention_threshold => '{retention}'{extra})"
        options = ["--session", f"{CATALOG}.{operation}_min_retention=0s"] if relax else []
        name = f"retention/{operation}_{'session' if relax else 'default'}"
        self.write_text(f"{name}.sql", statement + "\n")
        return self.capture(["docker", "compose", "exec", "-T", "trino", "trino", *options, "--execute", statement], f"{name}.log", allowed_returncodes={0} if relax else {0, 1, 2})

    def retention_negative(self, operation: str, retention: str) -> None:
        before = self.capture_state(f"{operation}_negative_before")
        result = self.maintenance_command(operation, retention, relax=False)
        assert_retention_error(result)
        require(self.capture_state(f"{operation}_negative_after") == before, "retention rejection changed state")
        self.write_json(f"retention/{operation}_negative.json", {"returncode": result.returncode, "semantic_error": True, "unchanged": True})

    def stage_expiration(self) -> None:
        self.current_ac = "AC-037"
        self.defaults = self.retention_defaults("before")
        self.sql("expiration/retention_anchor", f"UPDATE {self.table} SET amount_units=amount_units WHERE event_id=1")
        self.anchor = self.capture_state("retention_anchor")
        same_table(self.compacted, self.anchor)
        require(self.anchor["rows"] == self.compacted["rows"], "retention anchor changed compacted rows")
        require(len(self.anchor["metadata"]["snapshots"]) == len(self.compacted["metadata"]["snapshots"]) + 1, "identity update did not create retention anchor")
        anchor_id = self.anchor["metadata"]["current-snapshot-id"]
        require(next(s for s in self.anchor["metadata"]["snapshots"] if s["snapshot-id"] == anchor_id).get("parent-snapshot-id") == self.compacted["metadata"]["current-snapshot-id"], "retention anchor parent mismatch")
        self.sql("expiration/append", f"INSERT INTO {self.table} SELECT i, CAST('R' || CAST(i % 4 AS VARCHAR) AS VARCHAR), BIGINT '3' * i FROM UNNEST(sequence(BIGINT '2049', BIGINT '2176')) t(i)")
        self.retention_negative("expire_snapshots", "1s")
        before = self.capture_state("before_expiration")
        assert_rows(before["rows"], 2176)
        self.retained_ids = {self.anchor["metadata"]["current-snapshot-id"], before["metadata"]["current-snapshot-id"]}
        require(len(self.retained_ids) == 2, "append did not create a child snapshot")
        self.expired_id = self.fragmented["metadata"]["snapshots"][0]["snapshot-id"]
        time.sleep(1.2)
        self.maintenance_command("expire_snapshots", "1s", relax=True)
        after = self.capture_state("after_expiration")
        obsolete = set(self.fragmented["files"]) - set(before["files"])
        assert_expiration(before, after, self.retained_ids, obsolete)
        previous = self.anchor["metadata"]["current-snapshot-id"]
        assert_rows(self.rows("expiration/retained_historical", self.rows_query(f"{self.table} FOR VERSION AS OF {previous}")), 2048)
        result = self.capture(["docker", "compose", "exec", "-T", "trino", "trino", "--execute", f"SELECT * FROM {self.table} FOR VERSION AS OF {self.expired_id}"], "expiration/expired_read.log", allowed_returncodes={0, 1, 2})
        assert_negative_result(result, "snapshot_read", self.expired_id)
        require(self.capture_state("after_expired_read") == after, "expired read changed state")
        self.verify_control(after)
        require(self.retention_defaults("after_expiration") == self.defaults, "retention override leaked to another session")
        self.after_expiration = after
        self.write_json("expiration/comparison.json", {"retained_ids": sorted(self.retained_ids), "expired_id": self.expired_id, "expired_read_returncode": result.returncode, "obsolete_data_removed": sorted(obsolete - set(after["objects"])), "current_rows": 2176, "historical_rows": 2048})
        self.ac_results["AC-037"] = "PASS"

    def put_marker(self, key: str, name: str) -> None:
        self.allowlist.require_object(key)
        self.capture(["docker", "compose", "run", "--rm", "--no-deps", "--entrypoint", "sh", "bucket-setup", "-c", 'set -eu; printf "%s" "disposable orphan marker" >/tmp/marker; aws s3api put-object --bucket "$1" --key "$2" --body /tmp/marker --output json', "sh", BUCKET, key], f"orphan/{name}_put.json")

    def head_marker(self, key: str, name: str) -> dict[str, Any]:
        self.allowlist.require_object(key)
        result = self.capture(["docker", "compose", "run", "--rm", "--no-deps", "--entrypoint", "aws", "bucket-setup", "s3api", "head-object", "--bucket", BUCKET, "--key", key, "--output", "json"], f"orphan/{name}_head.json")
        return json.loads(result.stdout)

    def stage_orphan(self) -> None:
        self.current_ac = "AC-038"
        self.retention_negative("remove_orphan_files", "10s")
        prefix = self.after_expiration["metadata"]["location"].removeprefix(f"s3://{BUCKET}/").rstrip("/") + "/data/"
        old, young = prefix + "exercise-aged-orphan.parquet", prefix + "exercise-young-orphan.parquet"
        outside = f"warehouse/{self.schema}/outside-table/keep.txt"
        require(not any(key in self.after_expiration["objects"] for key in (old, young, outside)), "orphan marker collision")
        self.put_marker(old, "old")
        self.put_marker(outside, "outside")
        before = self.capture_state("before_orphan")
        head = self.head_marker(old, "old")
        modified = datetime.fromisoformat(head["LastModified"].replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - modified).total_seconds()
        if age <= 11:
            time.sleep(11 - age)
        self.put_marker(young, "young")
        young_head = self.head_marker(young, "young")
        started = datetime.now(timezone.utc)
        age = (started - modified).total_seconds()
        young_modified = datetime.fromisoformat(young_head["LastModified"].replace("Z", "+00:00"))
        young_age = (started - young_modified).total_seconds()
        require(age > 10 and 0 <= young_age < 10, "marker ages do not distinguish orphan retention")
        self.maintenance_command("remove_orphan_files", "10s", relax=True)
        after = self.capture_state("after_orphan")
        assert_orphan(before, after, old, young, outside)
        self.verify_control(after)
        require(self.retention_defaults("after_orphan") == self.defaults, "orphan session override leaked")
        self.write_json("orphan/comparison.json", {"old_key": old, "young_key": young, "outside_key": outside, "operation_started_at": started.isoformat(), "old_age_seconds": age, "young_age_seconds": young_age, "retention_seconds": 10, "old_removed_only": True})
        self.write_json("retention/comparison.json", {"ordinary_defaults": self.defaults, "unchanged": True, "session_only_overrides": True, "both_negative_guards": True})
        self.ac_results["AC-038"] = "PASS"
        self.ac_results["AC-039"] = "PASS"

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
