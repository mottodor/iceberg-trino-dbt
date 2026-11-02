"""Single-schema adapter for the remaining isolated lakehouse exercises.

Reuse the completed TT lifecycle and storage helpers without changing them.
Each concrete exercise supplies behavioral assertions and a saved-evidence replay.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from run_acceptance import BUCKET, CATALOG, PROJECT_NAME, ROOT, AcceptanceError
from run_time_travel_acceptance import (
    TaskAllowlist, TimeTravelWorkflow, require, verify_manifest,
)


def canonical_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    # Polaris reserializes statistics from an internal map. Live 16-commit
    # evidence contains identical entries in a different order. History,
    # snapshots and schema field order remain significant and are preserved.
    result = dict(metadata)
    for name in ("statistics", "partition-statistics"):
        if name in result:
            require(isinstance(result[name], list), "malformed statistics metadata")
            result[name] = sorted(result[name], key=lambda entry: json.dumps(entry, sort_keys=True))
    return result


@dataclass(frozen=True)
class ExerciseAllowlist(TaskAllowlist):
    exercise: str

    def __post_init__(self) -> None:
        super().__post_init__()
        require(self.exercise in {"maintenance", "incremental"}, "unknown exercise")

    @property
    def schemas(self) -> tuple[str, ...]:
        return (f"{self.run_id}_{self.exercise}",)


class LearningExercise(TimeTravelWorkflow):
    exercise = "maintenance"
    table_name = "maintenance_events"
    ac_numbers = tuple(range(34, 41))

    def __init__(self, run_id: str, evidence_dir: Path) -> None:
        super().__init__(run_id, evidence_dir)
        self.allowlist = ExerciseAllowlist(run_id, self.exercise)
        self.own_project = f"{PROJECT_NAME}-{self.exercise}-{run_id}"
        self.ac_results = {f"AC-{number:03}": "NOT_RUN" for number in self.ac_numbers}
        self.current_ac: str | None = None

    @property
    def schema(self) -> str:
        return self.allowlist.schemas[0]

    @property
    def table(self) -> str:
        return self.relation(self.table_name)

    def relation(self, name: str) -> str:
        require(name.replace("_", "").isalnum(), "invalid table identifier")
        return f'"{CATALOG}"."{self.schema}"."{name}"'

    def metadata(self, schema: str | None = None, table: str | None = None) -> dict[str, Any]:
        return super().metadata(schema or self.schema, table or self.table_name)

    def implementation(self) -> dict[str, str]:
        names = ["scripts/learning_exercise.py", f"scripts/run_{self.exercise}_acceptance.py",
                 "scripts/tests/test_learning_exercise.py", f"scripts/tests/test_{self.exercise}_acceptance.py"]
        if self.exercise == "incremental":
            names += [str(p.relative_to(ROOT)) for p in sorted((ROOT / "dbt/exercises/incremental").rglob("*"))
                      if p.is_file() and not {"target", "logs"}.intersection(p.parts)]
        return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}

    def rows(self, name: str, query: str) -> list[list[Any]]:
        raw = self.query_csv(f"{name}.csv", query)
        require(raw and raw[0] == ["row_json"], "invalid typed result header")
        result = [json.loads(row[0]) for row in raw[1:]]
        self.write_json(f"{name}.json", result)
        return result

    def snapshot(self, name: str, row_query: str) -> dict[str, Any]:
        base = f"states/{name}"
        loaded = self.metadata()
        self.write_json(f"{base}/catalog_metadata.json", loaded)
        metadata = loaded.get("metadata")
        require(isinstance(metadata, dict), "catalog metadata is missing")
        metadata = canonical_metadata(metadata)
        key = loaded.get("metadata-location", "").removeprefix(f"s3://{BUCKET}/")
        self.allowlist.require_object(key)
        objects = self.objects(self.schema)
        require(key in objects, "catalog pointer missing in storage")
        raw = self.capture(["docker", "compose", "run", "--rm", "--no-deps", "--entrypoint", "aws", "bucket-setup", "s3", "cp", f"s3://{BUCKET}/{key}", "-"], f"{base}/metadata.json").stdout
        require(canonical_metadata(json.loads(raw)) == metadata, "catalog/storage metadata mismatch")
        columns = self.query_csv(f"{base}/columns.csv", f"DESCRIBE {self.table}")
        snapshots = self.query_csv(f"{base}/snapshots.csv", f'SELECT * FROM "{CATALOG}"."{self.schema}"."{self.table_name}$snapshots" ORDER BY committed_at')
        history = self.query_csv(f"{base}/history.csv", f'SELECT * FROM "{CATALOG}"."{self.schema}"."{self.table_name}$history" ORDER BY made_current_at')
        files = self.query_csv(f"{base}/files.csv", f'SELECT content, file_path, file_size_in_bytes, record_count FROM "{CATALOG}"."{self.schema}"."{self.table_name}$files" ORDER BY file_path')
        hashes = self.checksums(self.schema, objects, label=base)
        current_files = {}
        require(files[0] == ["content", "file_path", "file_size_in_bytes", "record_count"], "invalid file metadata header")
        for content, location, size, records in files[1:]:
            file_key = location.removeprefix(f"s3://{BUCKET}/")
            self.allowlist.require_object(file_key)
            require(file_key in objects and int(size) == objects[file_key]["size"] and int(size) > 0, "file/storage size mismatch")
            require(file_key not in current_files, "duplicate file metadata")
            current_files[file_key] = {"content": int(content), "size": int(size), "records": int(records), "sha256": hashes[file_key]}
        state = {"metadata_location": loaded["metadata-location"], "metadata": metadata,
                 "columns": columns, "snapshots": snapshots, "history": history,
                 "rows": self.rows(f"{base}/rows", row_query), "files": current_files,
                 "objects": objects, "sha256": hashes}
        self.write_json(f"{base}/bundle.json", state)
        return state

    def verify_behavior(self, root: Path) -> None:
        raise AcceptanceError("concrete exercise must implement evidence replay")

    def cleanup_task_data(self) -> None:
        super().cleanup_task_data()
        self.write_json("cleanup/data.json", {"schemas_absent": True,
            "empty_object_prefixes": list(self.allowlist.object_prefixes)})

    def run(self, workflow, *, required: set[str], complete: bool = True) -> None:
        require(not self.run_attempted, "run instances are single-use")
        self.run_attempted = True
        final_ac = f"AC-{self.ac_numbers[-1]:03}"
        self.ac_results[final_ac] = "NOT_RUN"
        errors = []
        boundary = protected = implementation = None
        restored = False
        try:
            self.preflight()
            implementation = self.implementation()
            self.write_json("preflight/implementation.json", implementation)
            self.start_stack()
            self.assert_allowlist_absent()
            protected = self.immutable()
            self.write_json("preflight/immutable.json", protected)
            boundary = self.boundary("before")
            workflow()
        except Exception as error:
            if self.current_ac:
                self.ac_results[self.current_ac] = "FAIL"
            errors.append(f"{type(error).__name__}: {error}")
        finally:
            if self.allowlist_verified:
                try:
                    self.cleanup_task_data()
                    require(boundary is not None and self.boundary("after") == boundary, "foreign runtime state changed")
                    require(protected is not None and self.immutable() == protected, "protected implementation changed")
                    self.write_json("runtime/isolation.json", {"unchanged": True})
                    self.ac_results[f"AC-{self.ac_numbers[0]:03}"] = "PASS"
                except Exception as error:
                    errors.append(f"cleanup/isolation: {error}")
            if self.owns_stack:
                try:
                    self.stop_stack()
                except Exception as error:
                    errors.append(f"lifecycle: {error}")
            if self.initial_state != "unavailable":
                try:
                    self.assert_environment_restored()
                    restored = True
                    self.write_json("cleanup/environment.json", {"restored": True, "initial_state": self.initial_state, "preserved_volumes": self.final_volumes})
                except Exception as error:
                    errors.append(f"environment: {error}")
        if not self.evidence_reserved:
            raise AcceptanceError("; ".join(errors))
        try:
            self.assert_no_secrets_in_evidence()
            require(not errors, "; ".join(errors))
            require(restored and self.data_cleaned, "cleanup/restoration incomplete")
            if complete:
                require(implementation == self.implementation(), "exercise code changed during acceptance")
                require(all(value == "PASS" for key, value in self.ac_results.items() if key != final_ac), "mandatory criterion missing")
                self.verify_behavior(self.evidence_dir)
            common = {"commands.jsonl", "preflight/implementation.json", "preflight/immutable.json", "preflight/task_allowlist.json", "cleanup/data.json", "cleanup/environment.json", "runtime/isolation.json", "secret_scan.json"}
            self.write_evidence_manifest()
            verify_manifest(self.evidence_dir, common | required)
            if complete:
                self.ac_results[final_ac] = "PASS"
        except Exception as error:
            if str(error) not in errors:
                errors.append(str(error))
        self.write_json_atomic("acceptance_summary.json", {"run_id": self.run_id, "exercise": self.exercise,
            "outcome": "FAIL" if errors else ("PASS" if complete else "CHECKPOINT"),
            "ac_results": self.ac_results, "error": "; ".join(errors) or None,
            "started_at": self.started_at, "finished_at": datetime.now(timezone.utc).isoformat(),
            "command_count": len(self.commands)})
        if errors:
            raise AcceptanceError("; ".join(errors))
