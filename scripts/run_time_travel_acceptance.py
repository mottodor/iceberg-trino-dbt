#!/usr/bin/env python3
"""TT environment checkpoint (TT-ENV-001), not the complete TT acceptance.

Only --check-environment is implemented. It performs no fixture/model/table
writes. A healthy default stack is borrowed, never stopped. Otherwise only a
fresh, run-specific Compose project may be started; partial/stopped foreign
projects are refused. Named volumes are never removed.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from run_acceptance import (
    BUCKET,
    CATALOG,
    DEFAULT_EVIDENCE_ROOT,
    LAYERS,
    PROJECT_NAME,
    REQUIRED_ENV,
    ROOT,
    RUN_ID_PATTERN,
    AcceptanceError,
    AcceptanceRun,
    CommandResult,
    load_project_env,
)

RUNTIME_SERVICES = ("rustfs", "polaris", "trino")
SETUP_SERVICES = ("bucket-setup", "polaris-setup")
SERVICES = (*RUNTIME_SERVICES, *SETUP_SERVICES)
COMPOSE_FILE = ROOT / "compose.yaml"
# Never request Config.Env or a full inspect/config dump: they contain secrets.
INSPECT_FORMAT = (
    '{"id":{{json .Id}},"service":{{json (index .Config.Labels "com.docker.compose.service")}},'
    '"project":{{json (index .Config.Labels "com.docker.compose.project")}},'
    '"hash":{{json (index .Config.Labels "com.docker.compose.config-hash")}},'
    '"files":{{json (index .Config.Labels "com.docker.compose.project.config_files")}},'
    '"directory":{{json (index .Config.Labels "com.docker.compose.project.working_dir")}},'
    '"oneoff":{{json (index .Config.Labels "com.docker.compose.oneoff")}},'
    '"state":{{json .State.Status}},"exit_code":{{.State.ExitCode}},'
    '"health":{{with index .State "Health"}}{{json .Status}}{{else}}null{{end}}}'
)


@dataclass(frozen=True)
class TaskAllowlist:
    run_id: str

    def __post_init__(self) -> None:
        if not RUN_ID_PATTERN.fullmatch(self.run_id):
            raise AcceptanceError("invalid run id; use 3–32 lowercase identifier characters")

    @property
    def schemas(self) -> tuple[str, ...]:
        return (
            *(f"{self.run_id}_source_{layer}" for layer in LAYERS),
            f"{self.run_id}_time_travel",
        )

    @property
    def object_prefixes(self) -> tuple[str, ...]:
        return tuple(f"warehouse/{schema}/" for schema in self.schemas)

    def require_schema(self, schema: str) -> None:
        if schema not in self.schemas:
            raise AcceptanceError("schema is outside the exact task allowlist")

    def require_location(self, schema: str, location: str) -> None:
        self.require_schema(schema)
        if location != f"s3://{BUCKET}/warehouse/{schema}/":
            raise AcceptanceError("schema location is outside the exact task allowlist")

    def require_object(self, key: str) -> None:
        if (
            not any(key.startswith(prefix) for prefix in self.object_prefixes)
            or any(part in {"", ".", ".."} for part in key.split("/"))
            or "\\" in key
            or "%" in key
        ):
            raise AcceptanceError("object key is outside the exact task allowlist")


def validate_containers(
    rows: list[dict[str, Any]], project: str, hashes: dict[str, str], *, ready: bool
) -> None:
    """Validate identity even for partial own startup; ready requires all five."""
    seen: set[str] = set()
    ids: set[str] = set()
    for row in rows:
        service = row.get("service")
        container_id = row.get("id")
        if (
            service not in SERVICES
            or service in seen
            or not container_id
            or container_id in ids
            or row.get("project") != project
            or row.get("hash") != hashes.get(service)
            or row.get("files") != str(COMPOSE_FILE)
            or row.get("directory") != str(ROOT)
            or str(row.get("oneoff")).lower() != "false"
        ):
            raise AcceptanceError("unknown/duplicate/mismatched Compose container; refusing management")
        seen.add(service)
        ids.add(container_id)
        if ready:
            if service in RUNTIME_SERVICES:
                if row.get("state") != "running" or row.get("health") != "healthy":
                    raise AcceptanceError("partial/stopped/unhealthy stack; refusing management")
            elif row.get("state") != "exited" or row.get("exit_code") != 0:
                raise AcceptanceError("setup job is not successfully completed")
    if ready and seen != set(SERVICES):
        raise AcceptanceError("partial stack; refusing management")


class TimeTravelAcceptanceRun(AcceptanceRun):
    """Reuse read/evidence helpers, not the core runner's lifecycle or finalizer."""

    def __init__(self, run_id: str, evidence_dir: Path) -> None:
        self.allowlist = TaskAllowlist(run_id)
        super().__init__(run_id, evidence_dir)
        self.ac_results = {f"AC-{number:03}": "NOT_RUN" for number in range(28, 34)}
        self.project = PROJECT_NAME
        self.own_project = f"{PROJECT_NAME}-tt-{run_id}"
        self.initial_state = "unavailable"
        self.initial_containers: list[dict[str, Any]] = []
        self.hashes: dict[str, str] = {}
        self.owns_stack = False
        self.ownership_captured = False
        self.owned_container_ids: set[str] = set()
        self.owned_networks: dict[str, str] = {}
        self.allowlist_verified = False
        self.evidence_reserved = False
        self.run_attempted = False

    def compose(self, *args: str) -> list[str]:
        return [
            "docker", "compose", "--project-directory", str(ROOT),
            "-f", str(COMPOSE_FILE), "-p", self.project, *args,
        ]

    def capture(self, command: Sequence[str], path: str | None, *, allowed_returncodes: set[int] | None = None) -> CommandResult:
        # Pin inherited read helpers too; COMPOSE_* must not redirect the project.
        if list(command[:2]) == ["docker", "compose"]:
            args = list(command[2:])
            if "run" in args:
                pos = args.index("run") + 1
                args[pos:pos] = ["--pull", "never"]
            command = self.compose(*args)
        env = {key: value for key, value in os.environ.items() if not key.startswith("COMPOSE_")}
        started = time.monotonic()
        result = subprocess.run(
            command, cwd=ROOT, env=env, text=True, capture_output=True, timeout=300,
        )
        secrets = [os.environ[name] for name in REQUIRED_ENV if os.environ.get(name)]

        def redact(value: str) -> str:
            for secret in sorted(secrets, key=len, reverse=True):
                value = value.replace(secret, "[REDACTED]")
            return value

        captured = CommandResult(
            list(command), result.returncode, time.monotonic() - started,
            redact(result.stdout), redact(result.stderr),
        )
        self.record_command(captured)
        if path is not None:
            self.write_text(path, captured.stdout)
            if captured.stderr:
                self.write_text(f"{path}.stderr.log", captured.stderr)
        if captured.returncode not in (allowed_returncodes or {0}):
            self.write_text(f"diagnostics/command_{len(self.commands):04}.stderr.log", captured.stderr)
            raise AcceptanceError(f"command failed (exit {captured.returncode}); see command journal")
        return captured

    def run_command(self, command: Sequence[str], log_path: str | None, *, allowed_returncodes: set[int] | None = None) -> CommandResult:
        # Inherited fixture/dbt helpers must use the same pinned project/redaction.
        return self.capture(command, log_path, allowed_returncodes=allowed_returncodes)

    def inventory(self, project: str) -> list[dict[str, Any]]:
        result = self.capture([
            "docker", "ps", "-aq", "--filter", f"label=com.docker.compose.project={project}",
        ], None)
        ids = result.stdout.split()
        if not ids:
            return []
        result = self.capture(["docker", "inspect", "--format", INSPECT_FORMAT, *ids], None)
        try:
            rows = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        except json.JSONDecodeError as error:
            raise AcceptanceError("malformed container inventory JSON") from error
        if len(rows) != len(ids) or any(not isinstance(row, dict) for row in rows):
            raise AcceptanceError("incomplete or malformed container inventory")
        return rows

    def query_csv(self, relative_path: str, sql: str) -> list[list[str]]:
        # Compose health only checks HTTP availability, not SQL readiness.
        self.write_text(f"{relative_path}.sql", sql.strip() + "\n")
        for attempt in range(15):
            try:
                return super().query_csv(relative_path, sql)
            except AcceptanceError:
                diagnostic = self.evidence_dir / f"{relative_path}.stderr.log"
                if attempt == 14 or not diagnostic.is_file() or "Trino server is still initializing" not in diagnostic.read_text():
                    raise
                time.sleep(2)
        raise AcceptanceError("SQL readiness retry budget exhausted")

    def volumes(self) -> set[str]:
        return set(self.capture(["docker", "volume", "ls", "--format", "{{.Name}}"], None).stdout.split())

    def networks(self, project: str) -> dict[str, str]:
        result = self.capture([
            "docker", "network", "ls", "--filter", f"label=com.docker.compose.project={project}",
            "--no-trunc", "--format", "{{.ID}} {{.Name}}",
        ], None)
        pairs = [line.split() for line in result.stdout.splitlines() if line.strip()]
        if any(len(pair) != 2 for pair in pairs) or len({pair[0] for pair in pairs}) != len(pairs):
            raise AcceptanceError("malformed network identity inventory")
        return dict(pairs)

    def preflight(self) -> None:
        load_project_env()
        missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
        if missing:
            raise AcceptanceError("missing local environment variables: " + ", ".join(missing))
        # Only the canonical, fresh evidence path is permitted (no external symlinks).
        expected = DEFAULT_EVIDENCE_ROOT / self.run_id
        if self.evidence_dir != expected or expected.resolve() != expected:
            raise AcceptanceError("evidence path must be the canonical in-repository run directory")
        self.evidence_dir.mkdir(parents=True, exist_ok=False)
        self.evidence_reserved = True
        self.capture(["docker", "compose", "config", "--quiet"], None)
        hashes = self.capture(["docker", "compose", "config", "--hash", "*"], None)
        self.hashes = dict(line.split() for line in hashes.stdout.splitlines() if line.strip())
        if not set(SERVICES) <= self.hashes.keys():
            raise AcceptanceError("incomplete Compose service hashes")
        self.initial_volumes = sorted(self.volumes())
        self.initial_containers = self.inventory(PROJECT_NAME)
        if self.initial_containers:
            validate_containers(self.initial_containers, PROJECT_NAME, self.hashes, ready=True)
            self.initial_state = "initial_running"
        else:
            self.initial_state = "initial_stopped"
            self.project = self.own_project
            if self.inventory(self.project) or self.networks(self.project) or any(
                name.startswith(f"{self.project}_") for name in self.initial_volumes
            ):
                raise AcceptanceError("run-specific Compose resources already exist; choose a fresh run id")
        self.write_json("preflight/environment.json", {
            "initial_state": self.initial_state, "project": self.project,
            "containers": self.initial_containers, "preserved_volumes": self.initial_volumes,
        })

    def start_stack(self) -> None:
        if self.initial_state == "initial_running":
            if self.inventory(PROJECT_NAME) != self.initial_containers:
                raise AcceptanceError("borrowed stack changed after preflight")
            return
        if self.initial_state != "initial_stopped" or self.inventory(self.project):
            raise AcceptanceError("stack state changed before startup")
        # Mark before up: even a failed startup may have created containers.
        self.owns_stack = True
        try:
            self.capture([
                "docker", "compose", "up", "-d", "--wait", "--wait-timeout", "240",
                "--no-recreate", "--no-build", "--pull", "never", *RUNTIME_SERVICES,
            ], "runtime/compose_up.log")
        finally:
            # Capture even a partial failed startup. Never rediscover ownership
            # at cleanup: labels/config hashes do not establish instance identity.
            rows = self.inventory(self.project)
            validate_containers(rows, self.project, self.hashes, ready=False)
            networks = self.networks(self.project)
            if set(networks.values()) - {f"{self.project}_lakehouse"}:
                raise AcceptanceError("unknown network after startup; refusing ownership")
            self.owned_container_ids = {row["id"] for row in rows}
            self.owned_networks = networks
            self.ownership_captured = True
            self.write_json("runtime/owned_resources.json", {
                "container_ids": sorted(self.owned_container_ids), "networks": networks,
            })
        validate_containers(rows, self.project, self.hashes, ready=True)
        if set(networks.values()) != {f"{self.project}_lakehouse"}:
            raise AcceptanceError("missing owned network after startup")

    def assert_allowlist_absent(self) -> None:
        catalog = self.fetch_polaris_catalog()
        if catalog.get("properties", {}).get("default-base-location") != f"s3://{BUCKET}/warehouse":
            raise AcceptanceError("unverified catalog base location")
        storage = catalog.get("storageConfigInfo")
        expected_storage = {
            "storageType": "S3", "endpoint": "http://rustfs:9000",
            "endpointInternal": "http://rustfs:9000", "pathStyleAccess": True,
            "region": "us-west-2", "allowedLocations": [f"s3://{BUCKET}/warehouse"],
        }
        if (
            catalog.get("name") != CATALOG
            or catalog.get("type") != "INTERNAL"
            or not isinstance(storage, dict)
            or any(storage.get(key) != value for key, value in expected_storage.items())
            or storage.get("pathStyleAccess") is not True
        ):
            raise AcceptanceError("unverified catalog storage identity/configuration")
        names = ", ".join(f"'{schema}'" for schema in self.allowlist.schemas)
        rows = self.query_csv(
            "preflight/task_schemas.csv",
            f"SELECT schema_name FROM {CATALOG}.information_schema.schemata "
            f"WHERE schema_name IN ({names}) ORDER BY schema_name",
        )
        if rows != [["schema_name"]]:
            raise AcceptanceError("task schema collision or malformed schema listing")
        for prefix in self.allowlist.object_prefixes:
            listing = self.list_objects(prefix)
            if (
                listing.get("Prefix") != prefix
                or listing.get("IsTruncated", False) is not False
                or "NextContinuationToken" in listing
                or listing.get("Contents", []) != []
                or listing.get("KeyCount", 0) != 0
            ):
                raise AcceptanceError("task object collision or incomplete object listing")
        self.write_json("preflight/task_allowlist.json", {
            "catalog": CATALOG, "bucket": BUCKET,
            "storage_identity": expected_storage,
            "schemas": list(self.allowlist.schemas),
            "object_prefixes": list(self.allowlist.object_prefixes),
            "schema_locations": {
                schema: f"s3://{BUCKET}/warehouse/{schema}/" for schema in self.allowlist.schemas
            },
            "verified_absent": True,
        })
        self.allowlist_verified = True

    def stop_stack(self) -> None:
        if not self.owns_stack:
            return  # borrowed containers must never receive stop/down/rm
        if not self.ownership_captured:
            raise AcceptanceError("startup ownership was not captured; refusing cleanup")
        rows = self.inventory(self.project)
        validate_containers(rows, self.project, self.hashes, ready=False)
        networks = self.networks(self.project)
        if {row["id"] for row in rows} != self.owned_container_ids or networks != self.owned_networks:
            raise AcceptanceError("owned resource identity changed; refusing cleanup")
        ids = sorted(self.owned_container_ids)
        if ids:
            self.capture(["docker", "stop", "--time", "30", *ids], "cleanup/stop.log")
            self.capture(["docker", "rm", *ids], "cleanup/remove.log")
        for network_id in sorted(self.owned_networks):
            self.capture(["docker", "network", "rm", network_id], "cleanup/network.log")
        if self.inventory(self.project) or self.networks(self.project):
            raise AcceptanceError("owned Compose resources remain after cleanup")
        self.owns_stack = False

    def assert_environment_restored(self) -> None:
        if self.inventory(PROJECT_NAME) != self.initial_containers:
            raise AcceptanceError("default project containers changed")
        self.final_volumes = sorted(self.volumes())
        if not set(self.initial_volumes) <= set(self.final_volumes):
            raise AcceptanceError("pre-existing volume disappeared")
        if self.owns_stack:
            raise AcceptanceError("own startup was not restored")

    def run(self) -> None:
        """Environment-only checkpoint: never call core run()/finalize()."""
        if self.run_attempted or self.evidence_reserved:
            raise AcceptanceError("run instances are single-use; choose a fresh run id")
        self.run_attempted = True
        errors: list[str] = []
        try:
            self.preflight()
            self.start_stack()
            self.assert_allowlist_absent()
        except Exception as error:
            errors.append(str(error))
        finally:
            if self.owns_stack:
                try:
                    self.stop_stack()
                except Exception as error:
                    errors.append(f"lifecycle cleanup failed: {error}")
            if self.initial_state != "unavailable":
                try:
                    self.assert_environment_restored()
                except Exception as error:
                    errors.append(f"environment restoration failed: {error}")
        if self.evidence_reserved:
            self.write_json_atomic("environment_checkpoint.json", {
                "scope": "TT-ENV-001 environment only; no data writes or full-slice acceptance",
                "outcome": "FAIL" if errors else "ENVIRONMENT_READY",
                "ac_results": self.ac_results,
                "initial_state": self.initial_state, "project": self.project,
                "allowlist_verified": self.allowlist_verified,
                "preserved_volumes": self.final_volumes, "errors": errors,
            })
        if errors:
            raise AcceptanceError("; ".join(errors))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AcceptanceError(message)


def object_inventory(listing: dict[str, Any], prefix: str) -> dict[str, dict[str, Any]]:
    require(listing.get("Prefix") == prefix, "wrong object listing prefix")
    require(listing.get("IsTruncated", False) is False and "NextContinuationToken" not in listing, "incomplete object inventory")
    contents = listing.get("Contents", [])
    require(isinstance(contents, list), "malformed object inventory")
    result = {}
    for item in contents:
        require(isinstance(item, dict), "malformed object entry")
        key = item.get("Key")
        require(isinstance(key, str) and key.startswith(prefix) and key not in result, "wrong/duplicate object key")
        require(type(item.get("Size")) is int and item["Size"] >= 0 and isinstance(item.get("ETag"), str), "invalid object size/identity")
        result[key] = {"size": item["Size"], "etag": item["ETag"]}
    return result


def verify_manifest(root: Path, required: set[str]) -> None:
    manifest = json.loads((root / "evidence_manifest.json").read_text())
    entries = manifest.get("files", [])
    paths = [entry["path"] for entry in entries]
    require(len(paths) == len(set(paths)) and required <= set(paths), "incomplete/duplicate evidence manifest")
    actual = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and p.name not in {"acceptance_summary.json", "evidence_manifest.json"}}
    require(set(paths) == actual, "manifest does not cover all evidence")
    for entry in entries:
        path = root / entry["path"]
        require(path.resolve().is_relative_to(root.resolve()) and path.is_file() and not path.is_symlink(), "unsafe manifest path")
        data = path.read_bytes()
        require(entry["size"] == len(data) and entry["sha256"] == hashlib.sha256(data).hexdigest(), "evidence checksum mismatch")


def snapshot_chain(metadata: dict[str, Any], count: int) -> list[int]:
    snapshots = metadata.get("snapshots", [])
    require(len(snapshots) == count, "unexpected data snapshot count")
    history = metadata.get("snapshot-log", [])
    require(len(history) == count, "unexpected linear snapshot history")
    ids = [entry["snapshot-id"] for entry in history]
    require(len(set(ids)) == count and set(ids) == {s["snapshot-id"] for s in snapshots}, "invalid snapshot IDs/history")
    by_id = {entry["snapshot-id"]: entry for entry in snapshots}
    for index, sid in enumerate(ids):
        require(type(sid) is int and 0 < sid < 2**63, "invalid snapshot ID")
        require(by_id[sid].get("parent-snapshot-id") == (ids[index - 1] if index else None), "snapshot parent mismatch")
        require(by_id[sid]["timestamp-ms"] == history[index]["timestamp-ms"], "commit/history timestamp mismatch")
        if index:
            require(history[index]["timestamp-ms"] - history[index - 1]["timestamp-ms"] >= 2, "timestamp boundaries cannot distinguish commits")
    require(metadata.get("current-snapshot-id") == ids[-1], "current snapshot does not end linear history")
    return ids


def assert_rollback(before: dict[str, Any], after: dict[str, Any], ids: list[int]) -> None:
    first, restored, bad = ids
    old, new = before["metadata"], after["metadata"]
    require(new.get("current-snapshot-id") == restored and old.get("current-snapshot-id") == bad, "rollback current mismatch")
    for key in ("table-uuid", "current-schema-id", "schemas", "snapshots", "partition-specs", "default-spec-id"):
        require(old.get(key) == new.get(key), f"rollback changed {key}")
    history = new.get("snapshot-log", [])
    require([entry["snapshot-id"] for entry in history] == [first, restored, bad, restored], "rollback history mismatch")
    require(history[:3] == old["snapshot-log"] and history[-1]["timestamp-ms"] > history[-2]["timestamp-ms"], "rollback rewrote history")
    old_data = {key: (before["objects"][key]["size"], digest) for key, digest in before["sha256"].items() if "/data/" in key}
    new_data = {key: (after["objects"][key]["size"], digest) for key, digest in after["sha256"].items() if "/data/" in key}
    require(bool(old_data) and old_data == new_data, "rollback changed historical data/delete files")
    require(before["metadata_location"] != after["metadata_location"], "rollback did not update catalog pointer")


class TimeTravelWorkflow(TimeTravelAcceptanceRun):
    """TT-only evidence/cleanup orchestration; never inherit blanket-PASS finalize."""

    @property
    def schema(self) -> str:
        return f"{self.run_id}_time_travel"

    @property
    def table(self) -> str:
        return f'"{CATALOG}"."{self.schema}"."time_travel_package_delivery"'

    @property
    def source_prefix(self) -> str:
        return f"{self.run_id}_source"

    def probe(self) -> None:
        started = time.monotonic()
        location = f"s3://{BUCKET}/warehouse/{self.schema}/"
        self.allowlist.require_location(self.schema, location)
        self.sql("probe/create_schema", f"CREATE SCHEMA {CATALOG}.{self.schema} WITH (location = '{location}')")
        self.sql("probe/h0", f"CREATE TABLE {self.table} WITH (format='PARQUET', format_version=2) AS SELECT 'P3' AS package_id, DOUBLE '36' AS delivery_duration_hours")
        self.sql("probe/h1", f"UPDATE {self.table} SET delivery_duration_hours=40 WHERE package_id='P3'")
        self.sql("probe/hbad", f"UPDATE {self.table} SET delivery_duration_hours=360 WHERE package_id='P3'")
        before = self.bundle("probe_before")
        ids = snapshot_chain(before["metadata"], 3)
        self.sql("probe/rollback", f"ALTER TABLE {self.table} EXECUTE rollback_to_snapshot({ids[1]})")
        after = self.bundle("probe_after")
        assert_rollback(before, after, ids)
        for label, sid, duration in zip(("h0", "h1", "hbad"), ids, (36, 40, 360)):
            rows = self.query_csv(f"probe/{label}.csv", f"SELECT package_id, delivery_duration_hours FROM {self.table} FOR VERSION AS OF {sid}")
            require(len(rows) == 2 and rows[1][0] == "P3" and float(rows[1][1]) == duration, "probe historical rows mismatch")
        require(len(after["rows"]) == 2 and float(after["rows"][1][1]) == 40, "probe restored rows mismatch")
        elapsed = time.monotonic() - started
        require(elapsed <= 120, "probe exceeded 120-second runtime budget")
        self.write_json("probe/comparison.json", {"snapshot_ids": ids, "rollback_verified": True, "duration_seconds": elapsed})

    def sql(self, name: str, sql: str) -> None:
        self.write_text(f"{name}.sql", sql.strip() + "\n")
        self.capture(["docker", "compose", "exec", "-T", "trino", "trino", "--execute", sql], f"{name}.log")

    def rest(self, path: str) -> dict[str, Any]:
        port = self.capture(["docker", "compose", "port", "polaris", "8181"], None).stdout.strip().rsplit(":", 1)[-1]
        base = f"http://127.0.0.1:{port}/api/catalog/v1"
        credentials = f"{os.environ['POLARIS_CLIENT_ID']}:{os.environ['POLARIS_CLIENT_SECRET']}"
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        auth = urllib.request.Request(base + "/oauth/tokens", data=urllib.parse.urlencode({"grant_type": "client_credentials", "scope": "PRINCIPAL_ROLE:ALL"}).encode(), headers={"Authorization": "Basic " + base64.b64encode(credentials.encode()).decode(), "Polaris-Realm": "POLARIS", "Content-Type": "application/x-www-form-urlencoded"})
        with opener.open(auth, timeout=20) as response:
            token = json.load(response)["access_token"]
        request = urllib.request.Request(base + "/" + path, headers={"Authorization": "Bearer " + token, "Polaris-Realm": "POLARIS"})
        with opener.open(request, timeout=20) as response:
            body = json.load(response)
        require(isinstance(body, dict), "invalid Polaris response")
        # Load-table responses may include credential configuration; retain metadata only.
        return {key: value for key, value in body.items() if key in {"metadata", "metadata-location", "identifiers"}}

    def metadata(self, schema: str | None = None, table: str = "time_travel_package_delivery") -> dict[str, Any]:
        schema = schema or self.schema
        return self.rest(f"{CATALOG}/namespaces/{urllib.parse.quote(schema, safe='')}/tables/{urllib.parse.quote(table, safe='')}")

    def immutable(self) -> dict[str, str]:
        files = self.capture(["git", "ls-files", "dbt", "docker", "infra", "compose.yaml"], None).stdout.splitlines()
        require(bool(files), "empty protected file set")
        return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files}

    def boundary(self, stage: str) -> dict[str, Any]:
        names = ", ".join(f"'{name}'" for name in self.allowlist.schemas)
        base = f"runtime/boundary_{stage}"
        schemas = self.query_csv(f"{base}/schemas.csv", f"SELECT schema_name FROM {CATALOG}.information_schema.schemata WHERE schema_name NOT IN ({names}) ORDER BY schema_name")
        tables = self.query_csv(f"{base}/tables.csv", f"SELECT table_schema, table_name, table_type FROM {CATALOG}.information_schema.tables WHERE table_schema NOT IN ({names}) ORDER BY table_schema, table_name")
        pointers = {}
        for schema, table, kind in tables[1:]:
            if schema not in {"information_schema", "system"} and kind == "BASE TABLE":
                pointers[f"{schema}.{table}"] = self.metadata(schema, table)["metadata-location"]
        objects = object_inventory(self.list_objects("warehouse/"), "warehouse/")
        objects = {key: val for key, val in objects.items() if not key.startswith(self.allowlist.object_prefixes)}
        state = {"schemas": schemas, "tables": tables, "pointers": pointers, "objects": objects}
        self.write_json(f"{base}/state.json", state)
        return state

    def objects(self, schema: str) -> dict[str, Any]:
        self.allowlist.require_schema(schema)
        prefix = f"warehouse/{schema}/"
        result = object_inventory(self.list_objects(prefix), prefix)
        for key in result:
            self.allowlist.require_object(key)
        return result

    def checksums(self, schema: str, objects: dict[str, Any]) -> dict[str, str]:
        self.allowlist.require_schema(schema)
        require(bool(objects), "no objects to checksum")
        prefix = f"warehouse/{schema}/"
        # Fixed script, URI passed as positional argument; no key is interpolated in shell code.
        result = self.capture(["docker", "compose", "run", "--rm", "--no-deps", "--entrypoint", "sh", "bucket-setup", "-c", 'set -eu; aws s3 cp --recursive "$1" /tmp/ttobjects/ >/dev/null; find /tmp/ttobjects -type f -exec sha256sum {} +', "sh", f"s3://{BUCKET}/{prefix}"], None)
        hashes = {}
        for line in result.stdout.splitlines():
            digest, path = line.split(maxsplit=1)
            require(re.fullmatch(r"[0-9a-f]{64}", digest) is not None and path.startswith("/tmp/ttobjects/"), "invalid content checksum")
            key = prefix + path.removeprefix("/tmp/ttobjects/")
            self.allowlist.require_object(key)
            require(key not in hashes, "duplicate checksum")
            hashes[key] = digest
        require(set(hashes) == set(objects) and self.objects(schema) == objects, "object/checksum inventory drift")
        return hashes

    def bundle(self, label: str) -> dict[str, Any]:
        base = f"states/{label}"
        loaded = self.metadata()
        metadata = loaded.get("metadata")
        require(isinstance(metadata, dict), "missing catalog metadata")
        key = loaded.get("metadata-location", "").removeprefix(f"s3://{BUCKET}/")
        self.allowlist.require_object(key)
        objects = self.objects(self.schema)
        require(key in objects, "catalog metadata pointer missing in storage")
        state = {
            "metadata_location": loaded["metadata-location"], "metadata": metadata,
            "columns": self.query_csv(f"{base}/columns.csv", f"DESCRIBE {self.table}"),
            "rows": self.query_csv(f"{base}/rows.csv", f"SELECT * FROM {self.table} ORDER BY package_id"),
            "snapshots": self.query_csv(f"{base}/snapshots.csv", f'SELECT * FROM "{CATALOG}"."{self.schema}"."time_travel_package_delivery$snapshots" ORDER BY committed_at'),
            "history": self.query_csv(f"{base}/history.csv", f'SELECT * FROM "{CATALOG}"."{self.schema}"."time_travel_package_delivery$history" ORDER BY made_current_at'),
            "files": self.query_csv(f"{base}/files.csv", f'SELECT * FROM "{CATALOG}"."{self.schema}"."time_travel_package_delivery$files" ORDER BY file_path'),
            "objects": objects, "sha256": self.checksums(self.schema, objects),
        }
        self.write_json(f"{base}/bundle.json", state)
        return state

    def cleanup_task_data(self) -> None:
        require(self.allowlist_verified, "cleanup requires verified ownership")
        for schema in reversed(self.allowlist.schemas):
            self.allowlist.require_schema(schema)
            existing = self.query_csv(f"cleanup/{schema}/exists.csv", f"SELECT schema_name FROM {CATALOG}.information_schema.schemata WHERE schema_name = '{schema}'")
            if len(existing) > 1:
                ddl = self.query_csv(f"cleanup/{schema}/location.csv", f'SHOW CREATE SCHEMA "{CATALOG}"."{schema}"')
                location = re.escape(f"s3://{BUCKET}/warehouse/{schema}")
                require(len(ddl) == 2 and re.search(r"location\s*=\s*'" + location + r"/?'", ddl[1][0]) is not None, "schema location ownership drift")
                self.sql(f"cleanup/{schema}/drop", f'DROP SCHEMA "{CATALOG}"."{schema}" CASCADE')
            remaining = self.objects(schema)
            keys = list(remaining)
            for start in range(0, len(keys), 500):
                batch = keys[start:start + 500]
                for key in batch:
                    self.allowlist.require_object(key)
                payload = json.dumps({"Objects": [{"Key": key} for key in batch], "Quiet": False})
                result = self.capture(["docker", "compose", "run", "--rm", "--no-deps", "--entrypoint", "aws", "bucket-setup", "s3api", "delete-objects", "--bucket", BUCKET, "--delete", payload, "--output", "json"], f"cleanup/{schema}/delete_{start}.json")
                response = json.loads(result.stdout)
                require(not response.get("Errors") and {x["Key"] for x in response.get("Deleted", [])} == set(batch), "object cleanup incomplete")
            require(not self.objects(schema), "task objects remain")
        names = ", ".join(f"'{name}'" for name in self.allowlist.schemas)
        rows = self.query_csv("cleanup/remaining_schemas.csv", f"SELECT schema_name FROM {CATALOG}.information_schema.schemata WHERE schema_name IN ({names}) ORDER BY schema_name")
        require(rows == [["schema_name"]], "task schemas remain")
        self.write_json("cleanup/data.json", {"schemas_absent": True, "all_five_prefixes_empty": True})
        self.data_cleaned = True

    def run_slice(self, workflow, *, complete: bool = False) -> None:
        require(not self.run_attempted, "run instances are single-use")
        self.run_attempted = True
        self.ac_results["AC-033"] = "NOT_RUN"
        errors = []
        before = None
        protected = None
        restored = False
        try:
            self.preflight()
            self.start_stack()
            self.assert_allowlist_absent()
            protected = self.immutable()
            self.write_json("preflight/immutable.json", protected)
            before = self.boundary("before")
            workflow()
        except Exception as error:
            errors.append(f"{type(error).__name__}: {error}")
        finally:
            if self.allowlist_verified:
                try:
                    self.cleanup_task_data()
                    after = self.boundary("after")
                    require(before is not None and before == after, "non-task runtime state changed")
                    require(protected is not None and protected == self.immutable(), "protected code changed")
                    self.write_json("runtime/isolation.json", {"unchanged": True})
                    self.ac_results["AC-028"] = "PASS"
                except Exception as error:
                    errors.append(f"cleanup/isolation: {error}")
            if self.owns_stack:
                try:
                    self.stop_stack()
                except Exception as error:
                    errors.append(f"lifecycle cleanup: {error}")
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
            require(not errors, "; ".join(errors))
            require(self.data_cleaned and restored, "cleanup/restoration gate failed")
            self.assert_no_secrets_in_evidence()
            required = {"preflight/task_allowlist.json", "cleanup/data.json", "cleanup/environment.json", "runtime/isolation.json", "commands.jsonl", "secret_scan.json"}
            if complete:
                require(all(self.ac_results[f"AC-{n:03}"] == "PASS" for n in range(28, 33)), "mandatory AC still pending")
                required |= {"history/comparison.json", "negative/comparison.json", "rollback/comparison.json", "source/comparison.json", "runtime/end_to_end.json"}
            self.write_evidence_manifest()
            verify_manifest(self.evidence_dir, required)
            if complete:
                self.ac_results["AC-033"] = "PASS"
        except Exception as error:
            if str(error) not in errors:
                errors.append(str(error))
        self.write_json_atomic("acceptance_summary.json", {"run_id": self.run_id, "outcome": "FAIL" if errors else ("PASS" if complete else "CHECKPOINT"), "ac_results": self.ac_results, "error": "; ".join(errors) or None, "command_count": len(self.commands), "started_at": self.started_at, "finished_at": datetime.now(timezone.utc).isoformat()})
        if errors:
            raise AcceptanceError("; ".join(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--check-environment", action="store_true",
        help="only verify lifecycle/allowlist, not TT-1 acceptance; may start a fresh project",
    )
    args = parser.parse_args()
    if not args.check_environment:
        parser.error("full TT acceptance is not implemented; only --check-environment is available")
    try:
        runner = TimeTravelAcceptanceRun(args.run_id, DEFAULT_EVIDENCE_ROOT / args.run_id)
        runner.run()
    except (AcceptanceError, OSError) as error:
        print(f"TT environment checkpoint failed: {error}", file=sys.stderr)
        return 1
    print("TT environment checkpoint ready; AC-028–AC-033 remain NOT_RUN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
