"""TT-ENV-001 contract tests; Docker/HTTP are simulated, never started here."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_time_travel_acceptance as target  # noqa: E402


HASHES = {service: f"hash-{service}" for service in target.SERVICES}
CATALOG = {
    "name": target.CATALOG, "type": "INTERNAL",
    "properties": {"default-base-location": f"s3://{target.BUCKET}/warehouse"},
    "storageConfigInfo": {
        "storageType": "S3", "endpoint": "http://rustfs:9000",
        "endpointInternal": "http://rustfs:9000", "pathStyleAccess": True,
        "region": "us-west-2", "allowedLocations": [f"s3://{target.BUCKET}/warehouse"],
    },
}


def containers(project: str) -> list[dict]:
    return [
        {
            "id": f"{project}-{service}-id", "service": service, "project": project,
            "hash": HASHES[service], "files": str(target.COMPOSE_FILE),
            "directory": str(target.ROOT), "oneoff": "False",
            "state": "running" if service in target.RUNTIME_SERVICES else "exited",
            "exit_code": 0,
            "health": "healthy" if service in target.RUNTIME_SERVICES else None,
        }
        for service in target.SERVICES
    ]


class FakeDocker:
    """Exercise real preflight/lifecycle/read-helper commands against a fake engine."""

    def __init__(self, running: bool = False) -> None:
        self.projects = {target.PROJECT_NAME: containers(target.PROJECT_NAME) if running else []}
        self.network_names: dict[str, str] = {}
        self.volume_names = {"pre_existing_volume"}
        self.commands: list[list[str]] = []
        self.fail_up = False
        self.fail_stop = False
        self.schema_rows = '"schema_name"\n'
        self.object_result: dict | None = None

    def run(self, command, **kwargs):
        self.commands.append(list(command))
        assert kwargs["cwd"] == target.ROOT
        assert kwargs["timeout"] == 300
        assert not any(key.startswith("COMPOSE_") for key in kwargs["env"])
        output = ""
        code = 0
        if command[:2] == ["docker", "compose"]:
            assert command[2:6] == ["--project-directory", str(target.ROOT), "-f", str(target.COMPOSE_FILE)]
            project = command[7]
            args = command[8:]
            if args[:2] == ["config", "--hash"]:
                output = "\n".join(f"{service} {value}" for service, value in HASHES.items())
            elif args == ["config", "--quiet"]:
                pass
            elif args[0] == "up":
                assert "--no-recreate" in args and "--no-build" in args
                assert args[args.index("--pull") + 1] == "never"
                self.projects[project] = containers(project)[:2] if self.fail_up else containers(project)
                self.network_names[f"{project}_lakehouse"] = f"{project}-network-id"
                self.volume_names.add(f"{project}_rustfs-data")
                code = 1 if self.fail_up else 0
            elif args[0] == "exec":
                assert args[-1].startswith("SELECT schema_name FROM lakehouse.information_schema.schemata")
                output = self.schema_rows
            elif args[0] == "run":
                assert args[args.index("--pull") + 1] == "never"
                assert "--rm" in args and "--no-deps" in args
                prefix = args[args.index("--prefix") + 1]
                output = json.dumps(self.object_result if self.object_result is not None else {"Prefix": prefix})
            else:
                raise AssertionError(f"unexpected compose command {args}")
        elif command[:3] == ["docker", "ps", "-aq"]:
            project = command[-1].rsplit("=", 1)[1]
            output = "\n".join(row["id"] for row in self.projects.get(project, []))
        elif command[:2] == ["docker", "inspect"]:
            rows = [row for values in self.projects.values() for row in values if row["id"] in command[4:]]
            output = "\n".join(json.dumps(row) for row in rows)
        elif command[:3] == ["docker", "volume", "ls"]:
            output = "\n".join(sorted(self.volume_names))
        elif command[:3] == ["docker", "network", "ls"]:
            project = command[4].rsplit("=", 1)[1]
            assert "--no-trunc" in command
            output = "\n".join(f"{identity} {name}" for name, identity in self.network_names.items() if name.startswith(f"{project}_"))
        elif command[:2] == ["docker", "stop"]:
            if self.fail_stop:
                code = 1
            else:
                for rows in self.projects.values():
                    for row in rows:
                        if row["id"] in command[4:]:
                            row["state"] = "exited"
        elif command[:2] == ["docker", "rm"]:
            for project, rows in self.projects.items():
                self.projects[project] = [row for row in rows if row["id"] not in command[2:]]
        elif command[:3] == ["docker", "network", "rm"]:
            name = next(name for name, identity in self.network_names.items() if identity == command[-1])
            del self.network_names[name]
        else:
            raise AssertionError(f"unexpected docker command {command}")
        return SimpleNamespace(stdout=output, stderr="simulated failure" if code else "", returncode=code)

    def mutations(self):
        return [command for command in self.commands if command[1] in {"stop", "rm"} or "up" in command or command[1:3] == ["network", "rm"]]


class AllowlistTests(unittest.TestCase):
    def setUp(self):
        self.allowlist = target.TaskAllowlist("tt_env001")

    def test_exact_five_schemas_and_locations(self):
        self.assertEqual(self.allowlist.schemas, (
            "tt_env001_source_fixtures", "tt_env001_source_bronze",
            "tt_env001_source_silver", "tt_env001_source_gold", "tt_env001_time_travel",
        ))
        for schema in self.allowlist.schemas:
            self.allowlist.require_schema(schema)
            self.allowlist.require_location(schema, f"s3://{target.BUCKET}/warehouse/{schema}/")
            self.allowlist.require_object(f"warehouse/{schema}/table-uuid/data/a.parquet")

    def test_invalid_run_ids(self):
        for value in ("", "ab", "UPPER", "x' OR 1=1", "a/b", "a" * 33):
            with self.subTest(value=value), self.assertRaises(target.AcceptanceError):
                target.TaskAllowlist(value)

    def test_prefix_siblings_traversal_and_foreign_locations_rejected(self):
        for schema in ("tt_env001_time_travel_other", "tt_env001_source", "gold"):
            with self.subTest(schema=schema), self.assertRaises(target.AcceptanceError):
                self.allowlist.require_schema(schema)
        for key in (
            "warehouse/tt_env001_time_travel_other/data/a", "warehouse/tt_env001_time_travel/../foreign",
            "warehouse/tt_env001_time_travel/%2e%2e/x", "warehouse/tt_env001_time_travel//x",
            "warehouse/tt_env001_time_travel/./x", "warehouse/tt_env001_time_travel/x\\y",
            "warehouse/other/a",
        ):
            with self.subTest(key=key), self.assertRaises(target.AcceptanceError):
                self.allowlist.require_object(key)
        with self.assertRaises(target.AcceptanceError):
            self.allowlist.require_location(self.allowlist.schemas[0], "s3://foreign/warehouse/x/")


class ContainerIdentityTests(unittest.TestCase):
    def test_exact_healthy_stack(self):
        target.validate_containers(containers(target.PROJECT_NAME), target.PROJECT_NAME, HASHES, ready=True)

    def test_identity_state_mutations_rejected(self):
        mutations = {
            "project": "foreign", "hash": "changed", "files": "/other/compose.yaml",
            "directory": "/other", "oneoff": "True", "health": "unhealthy",
            "state": "exited", "service": "dbt", "id": "",
        }
        for field, value in mutations.items():
            rows = containers(target.PROJECT_NAME)
            rows[0][field] = value
            with self.subTest(field=field), self.assertRaises(target.AcceptanceError):
                target.validate_containers(rows, target.PROJECT_NAME, HASHES, ready=True)

    def test_partial_duplicate_stopped_and_failed_setup_rejected(self):
        rows = containers(target.PROJECT_NAME)
        variants = [[], rows[:2], rows + [rows[0]], copy.deepcopy(rows), copy.deepcopy(rows)]
        variants[-2][-1]["exit_code"] = 1
        variants[-1][-1]["state"] = "running"
        for variant in variants:
            with self.subTest(variant=variant), self.assertRaises(target.AcceptanceError):
                target.validate_containers(variant, target.PROJECT_NAME, HASHES, ready=True)


class EnvironmentFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.evidence_root = Path(self.temp.name) / "acceptance"
        self.enterContext(patch.object(target, "DEFAULT_EVIDENCE_ROOT", self.evidence_root))
        self.enterContext(patch.object(target, "load_project_env"))
        self.enterContext(patch.dict(os.environ, {
            **{name: f"secret-for-{name}" for name in target.REQUIRED_ENV},
            "COMPOSE_FILE": "/foreign/compose.yaml", "COMPOSE_PROJECT_NAME": "foreign",
        }))
        self.engine = FakeDocker()
        self.enterContext(patch.object(target.subprocess, "run", side_effect=self.engine.run))
        self.enterContext(patch.object(target.TimeTravelAcceptanceRun, "fetch_polaris_catalog", return_value=copy.deepcopy(CATALOG)))
        self.runner = target.TimeTravelAcceptanceRun("tt_env001", self.evidence_root / "tt_env001")

    def checkpoint(self):
        return json.loads((self.runner.evidence_dir / "environment_checkpoint.json").read_text())

    def test_only_initializing_sql_error_is_retried(self):
        self.runner.evidence_dir.mkdir(parents=True)
        path = self.runner.evidence_dir / "ready.csv.stderr.log"
        path.write_text("Trino server is still initializing")
        with patch.object(target.AcceptanceRun, "query_csv", side_effect=[target.AcceptanceError("startup"), [["ready"], ["1"]]]) as query, patch.object(target.time, "sleep"):
            self.assertEqual(self.runner.query_csv("ready.csv", "SELECT 1"), [["ready"], ["1"]])
            self.assertEqual(query.call_count, 2)
        path.write_text("Connection refused")
        with patch.object(target.AcceptanceRun, "query_csv", side_effect=target.AcceptanceError("connection")) as query, patch.object(target.time, "sleep"):
            with self.assertRaises(target.AcceptanceError):
                self.runner.query_csv("ready.csv", "SELECT 1")
            self.assertEqual(query.call_count, 1)

    def test_own_startup_restored_exact_ids_volumes_preserved_no_full_pass(self):
        self.runner.run()
        self.assertEqual(self.runner.initial_state, "initial_stopped")
        self.assertTrue(self.runner.allowlist_verified)
        self.assertFalse(self.engine.projects[self.runner.project])
        self.assertFalse(self.engine.network_names)
        self.assertEqual(self.engine.volume_names, {"pre_existing_volume", f"{self.runner.project}_rustfs-data"})
        self.assertTrue(self.engine.mutations())
        pinned = json.loads((self.runner.evidence_dir / "runtime/owned_resources.json").read_text())
        self.assertEqual(set(pinned["container_ids"]), {row["id"] for row in containers(self.runner.project)})
        network_removes = [command[-1] for command in self.engine.commands if command[:3] == ["docker", "network", "rm"]]
        self.assertEqual(network_removes, [f"{self.runner.project}-network-id"])
        self.assertEqual(self.checkpoint()["outcome"], "ENVIRONMENT_READY")
        self.assertEqual(set(self.checkpoint()["ac_results"].values()), {"NOT_RUN"})
        self.assertFalse((self.runner.evidence_dir / "acceptance_summary.json").exists())
        for command in self.engine.commands:
            self.assertNotIn("down", command)
            self.assertNotIn("--force", command)
            self.assertNotEqual(command[1:3], ["volume", "rm"])
        allowlist = json.loads((self.runner.evidence_dir / "preflight/task_allowlist.json").read_text())
        self.assertEqual(allowlist["schemas"], list(self.runner.allowlist.schemas))
        self.assertTrue(allowlist["verified_absent"])

    def test_running_stack_is_borrowed_and_not_stopped_even_on_collision(self):
        for collision in (False, True):
            with self.subTest(collision=collision):
                if collision:
                    self.runner = target.TimeTravelAcceptanceRun("tt_other", self.evidence_root / "tt_other")
                    self.engine.schema_rows += '"tt_other_time_travel"\n'
                self.engine.projects[target.PROJECT_NAME] = containers(target.PROJECT_NAME)
                before = copy.deepcopy(self.engine.projects)
                if collision:
                    with self.assertRaisesRegex(target.AcceptanceError, "schema collision"):
                        self.runner.run()
                else:
                    self.runner.run()
                self.assertEqual(self.engine.projects, before)
                self.assertEqual(self.engine.mutations(), [])
                self.assertEqual(self.runner.initial_state, "initial_running")

    def test_partial_or_stopped_foreign_stack_is_refused_without_mutation(self):
        for rows in (containers(target.PROJECT_NAME)[:1], containers(target.PROJECT_NAME)):
            with self.subTest(partial=len(rows)):
                rows[0]["state"] = "exited"
                self.engine.projects[target.PROJECT_NAME] = rows
                before = copy.deepcopy(self.engine.projects)
                with self.assertRaises(target.AcceptanceError):
                    self.runner.run()
                self.assertEqual(self.engine.projects, before)
                self.assertEqual(self.engine.mutations(), [])
                # Allow next subcase to use a different fresh evidence directory.
                self.runner = target.TimeTravelAcceptanceRun("tt_other", self.evidence_root / "tt_other")

    def test_failed_partial_up_still_removes_only_own_resources(self):
        self.engine.fail_up = True
        with self.assertRaisesRegex(target.AcceptanceError, "command failed"):
            self.runner.run()
        self.assertFalse(self.engine.projects[self.runner.project])
        self.assertFalse(self.engine.network_names)
        pinned = json.loads((self.runner.evidence_dir / "runtime/owned_resources.json").read_text())
        self.assertEqual(len(pinned["container_ids"]), 2)
        self.assertTrue(self.runner.ownership_captured)
        self.assertIn("pre_existing_volume", self.engine.volume_names)
        self.assertEqual(self.checkpoint()["outcome"], "FAIL")
        self.assertFalse(self.runner.allowlist_verified)

    def test_stop_failure_is_not_green(self):
        self.engine.fail_stop = True
        with self.assertRaisesRegex(target.AcceptanceError, "lifecycle cleanup failed"):
            self.runner.run()
        self.assertEqual(self.checkpoint()["outcome"], "FAIL")
        self.assertTrue(self.runner.owns_stack)
        self.assertTrue(self.engine.projects[self.runner.project])

    def test_schema_collision_does_not_claim_ownership(self):
        self.engine.schema_rows += '"tt_env001_time_travel"\n'
        with self.assertRaisesRegex(target.AcceptanceError, "schema collision"):
            self.runner.run()
        self.assertFalse(self.runner.allowlist_verified)
        self.assertFalse(self.engine.projects[self.runner.project])

    def test_bad_catalog_and_object_shapes_fail_before_claim(self):
        for listing in ({}, {"IsTruncated": True}, {"Contents": [{"Key": "occupied"}]}):
            with self.subTest(listing=listing):
                self.runner.list_objects = lambda prefix: {"Prefix": prefix, **listing} if listing else {}
                self.runner.query_csv = lambda relative_path, sql: [["schema_name"]]
                with self.assertRaisesRegex(target.AcceptanceError, "object collision"):
                    self.runner.assert_allowlist_absent()
                self.assertFalse(self.runner.allowlist_verified)
        with patch.object(self.runner, "fetch_polaris_catalog", return_value={"properties": {"default-base-location": "s3://foreign/path"}}):
            with self.assertRaisesRegex(target.AcceptanceError, "catalog base location"):
                self.runner.assert_allowlist_absent()

    def test_explicit_and_pinned_stack_empty_listing_forms_accepted(self):
        self.runner.query_csv = lambda relative_path, sql: [["schema_name"]]
        for explicit in (False, True):
            with self.subTest(explicit=explicit):
                self.runner.list_objects = lambda prefix: {"Prefix": prefix, **({"IsTruncated": False, "Contents": [], "KeyCount": 0} if explicit else {})}
                self.runner.assert_allowlist_absent()
                self.assertTrue(self.runner.allowlist_verified)

    def test_run_id_resource_collision_is_not_cleaned(self):
        self.engine.projects[self.runner.own_project] = containers(self.runner.own_project)
        before = copy.deepcopy(self.engine.projects)
        with self.assertRaisesRegex(target.AcceptanceError, "resources already exist"):
            self.runner.run()
        self.assertEqual(self.engine.projects, before)
        self.assertEqual(self.engine.mutations(), [])

    def test_existing_evidence_not_overwritten(self):
        self.runner.evidence_dir.mkdir(parents=True)
        marker = self.runner.evidence_dir / "marker.txt"
        marker.write_text("preserve")
        with self.assertRaises(target.AcceptanceError):
            self.runner.run()
        self.assertEqual(marker.read_text(), "preserve")
        self.assertFalse(self.engine.commands)
        self.assertFalse((self.runner.evidence_dir / "environment_checkpoint.json").exists())

    def test_same_instance_cannot_overwrite_its_successful_checkpoint(self):
        self.runner.run()
        path = self.runner.evidence_dir / "environment_checkpoint.json"
        before = path.read_bytes()
        command_count = len(self.engine.commands)
        with self.assertRaises(target.AcceptanceError):
            self.runner.run()
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(len(self.engine.commands), command_count)

    def test_external_or_symlink_evidence_path_refused(self):
        self.runner.evidence_dir = Path(self.temp.name) / "external"
        with self.assertRaisesRegex(target.AcceptanceError, "canonical"):
            self.runner.run()
        self.assertFalse(self.engine.commands)
        self.evidence_root.mkdir()
        (self.evidence_root / "tt_env001").symlink_to(Path(self.temp.name), target_is_directory=True)
        self.runner = target.TimeTravelAcceptanceRun("tt_env001", self.evidence_root / "tt_env001")
        with self.assertRaisesRegex(target.AcceptanceError, "canonical"):
            self.runner.run()
        self.assertFalse(self.engine.commands)

    def test_missing_credentials_do_not_create_evidence_or_run_docker(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(target.AcceptanceError, "missing local environment"):
                self.runner.run()
        self.assertFalse(self.runner.evidence_dir.exists())
        self.assertFalse(self.engine.commands)

    def test_malformed_inventory_is_fail_closed(self):
        for text in ("{broken", "[]", "null"):
            with self.subTest(text=text), patch.object(self.runner, "capture", side_effect=[
                SimpleNamespace(stdout="container-id"), SimpleNamespace(stdout=text),
            ]), self.assertRaisesRegex(target.AcceptanceError, "malformed"):
                self.runner.inventory(target.PROJECT_NAME)

    def test_borrowed_stack_identity_drift_is_rejected(self):
        self.engine.projects[target.PROJECT_NAME] = containers(target.PROJECT_NAME)
        self.runner.preflight()
        self.engine.projects[target.PROJECT_NAME][0]["id"] = "replacement-id"
        with self.assertRaisesRegex(target.AcceptanceError, "changed after preflight"):
            self.runner.start_stack()
        self.assertEqual(self.engine.mutations(), [])

    def test_owned_cleanup_refuses_unknown_container(self):
        self.runner.preflight()
        self.runner.start_stack()
        self.engine.projects[self.runner.project][0]["hash"] = "foreign-hash"
        before = len(self.engine.mutations())
        with self.assertRaisesRegex(target.AcceptanceError, "unknown"):
            self.runner.stop_stack()
        self.assertEqual(len(self.engine.mutations()), before)

    def test_owned_cleanup_refuses_replacement_container_with_same_labels(self):
        self.runner.preflight()
        self.runner.start_stack()
        self.engine.projects[self.runner.project][0]["id"] = "replacement-id"
        before = len(self.engine.mutations())
        with self.assertRaisesRegex(target.AcceptanceError, "identity changed"):
            self.runner.stop_stack()
        self.assertEqual(len(self.engine.mutations()), before)
        self.assertFalse(any("replacement-id" in command for command in self.engine.mutations()))

    def test_owned_cleanup_refuses_replacement_network_with_same_name(self):
        self.runner.preflight()
        self.runner.start_stack()
        self.engine.network_names[f"{self.runner.project}_lakehouse"] = "replacement-network-id"
        before = len(self.engine.mutations())
        with self.assertRaisesRegex(target.AcceptanceError, "identity changed"):
            self.runner.stop_stack()
        self.assertEqual(len(self.engine.mutations()), before)

    def test_cleanup_without_ownership_snapshot_refuses_all_mutation(self):
        self.runner.owns_stack = True
        with self.assertRaisesRegex(target.AcceptanceError, "ownership was not captured"):
            self.runner.stop_stack()
        self.assertFalse(self.engine.commands)

    def test_catalog_storage_identity_is_required_before_any_listing(self):
        variants = []
        for key in ("storageConfigInfo", "name", "type"):
            missing = copy.deepcopy(CATALOG)
            del missing[key]
            variants.append(missing)
        for key in CATALOG["storageConfigInfo"]:
            missing = copy.deepcopy(CATALOG)
            del missing["storageConfigInfo"][key]
            variants.append(missing)
        for key, value in (
            ("endpoint", "http://foreign-storage:9000"),
            ("endpointInternal", "http://foreign-storage:9000"),
            ("storageType", "AZURE"), ("pathStyleAccess", False), ("pathStyleAccess", 1),
            ("region", "foreign-region"), ("allowedLocations", ["s3://foreign/warehouse"]),
            ("allowedLocations", [f"s3://{target.BUCKET}/warehouse", "s3://foreign/path"]),
        ):
            foreign = copy.deepcopy(CATALOG)
            foreign["storageConfigInfo"][key] = value
            variants.append(foreign)
        for catalog in variants:
            with self.subTest(catalog=catalog), patch.object(self.runner, "fetch_polaris_catalog", return_value=catalog), patch.object(self.runner, "query_csv", return_value=[["schema_name"]]) as query, patch.object(self.runner, "list_objects", side_effect=lambda prefix: {"Prefix": prefix}) as objects:
                with self.assertRaisesRegex(target.AcceptanceError, "catalog storage"):
                    self.runner.assert_allowlist_absent()
                query.assert_not_called()
                objects.assert_not_called()
                self.assertFalse(self.runner.allowlist_verified)

    def test_capture_redacts_credentials(self):
        secret = os.environ["POLARIS_CLIENT_SECRET"]
        with patch.object(target.subprocess, "run", return_value=SimpleNamespace(stdout=secret, stderr=secret, returncode=0)):
            self.runner.evidence_dir.mkdir(parents=True)
            result = self.runner.capture(["docker", "version"], "redaction.txt")
        self.assertEqual(result.stdout, "[REDACTED]")
        self.assertNotIn(secret, (self.runner.evidence_dir / "redaction.txt").read_text())

    def test_inherited_dbt_commands_use_pinned_project_and_never_pull(self):
        self.runner.evidence_dir.mkdir(parents=True)
        with patch.object(target.subprocess, "run", return_value=SimpleNamespace(stdout="loaded", stderr="", returncode=0)) as call:
            self.runner.load_fixtures("tt_env001_source", "baseline", "batch_1", "load.log")
        command = call.call_args.args[0]
        self.assertEqual(command[2:8], ["--project-directory", str(target.ROOT), "-f", str(target.COMPOSE_FILE), "-p", self.runner.project])
        run = command.index("run")
        self.assertEqual(command[run + 1:run + 3], ["--pull", "never"])
        self.assertIn("DBT_TRINO_SCHEMA=tt_env001_source", command)

    def test_subprocess_timeout_is_failure_not_full_pass(self):
        with patch.object(target.subprocess, "run", side_effect=subprocess.TimeoutExpired("docker", 300)):
            with self.assertRaises(target.AcceptanceError):
                self.runner.run()
        self.assertEqual(self.checkpoint()["outcome"], "FAIL")
        self.assertEqual(set(self.checkpoint()["ac_results"].values()), {"NOT_RUN"})


class EvidenceTests(unittest.TestCase):
    def test_boundary_skips_virtual_tables_but_tracks_real_catalog_pointers(self):
        with tempfile.TemporaryDirectory() as directory:
            runner = target.TimeTravelWorkflow("tt_boundary", Path(directory))
            tables = [["table_schema", "table_name", "table_type"], ["system", "iceberg_tables", "BASE TABLE"], ["information_schema", "columns", "BASE TABLE"], ["existing", "fact", "BASE TABLE"]]
            with patch.object(runner, "query_csv", side_effect=[[["schema_name"], ["system"], ["existing"]], tables]), patch.object(runner, "list_objects", return_value={"Prefix": "warehouse/"}), patch.object(runner, "metadata", return_value={"metadata-location": "s3://bucket/existing/metadata"}) as metadata:
                state = runner.boundary("before")
            metadata.assert_called_once_with("existing", "fact")
            self.assertEqual(state["pointers"], {"existing.fact": "s3://bucket/existing/metadata"})

    def test_listing_rejects_truncation_duplicates_and_foreign_keys(self):
        valid = {"Prefix": "warehouse/task/", "Contents": [{"Key": "warehouse/task/a", "Size": 3, "ETag": "abc"}]}
        self.assertEqual(len(target.object_inventory(valid, "warehouse/task/")), 1)
        mutations = []
        for key, value in [("IsTruncated", True), ("NextContinuationToken", "next"), ("Contents", None), ("Prefix", "other/")]:
            mutations.append({**valid, key: value})
        mutations.append({**valid, "Contents": valid["Contents"] * 2})
        mutations.append({**valid, "Contents": [{"Key": "warehouse/task_sibling/a", "Size": 3, "ETag": "abc"}]})
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(target.AcceptanceError):
                target.object_inventory(mutation, "warehouse/task/")

    def test_manifest_detects_missing_extra_and_changed_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = target.TimeTravelWorkflow("tt_manifest", root)
            runner.write_text("proof.json", "{}")
            runner.write_evidence_manifest()
            target.verify_manifest(root, {"proof.json"})
            with self.assertRaises(target.AcceptanceError):
                target.verify_manifest(root, {"missing.json"})
            runner.write_text("proof.json", "changed")
            with self.assertRaises(target.AcceptanceError):
                target.verify_manifest(root, {"proof.json"})
            runner.write_evidence_manifest()
            runner.write_text("extra.json", "extra")
            with self.assertRaises(target.AcceptanceError):
                target.verify_manifest(root, {"proof.json"})

    def test_cleanup_failure_excludes_pass_even_when_all_ac_claimed_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runner = target.TimeTravelWorkflow("tt_failure", root)
            runner.evidence_reserved = True
            runner.allowlist_verified = True
            runner.initial_state = "initial_running"
            runner.ac_results = {key: "PASS" for key in runner.ac_results}
            with patch.object(runner, "preflight"), patch.object(runner, "start_stack"), patch.object(runner, "assert_allowlist_absent"), patch.object(runner, "immutable", return_value={"file": "hash"}), patch.object(runner, "boundary", return_value={}), patch.object(runner, "cleanup_task_data", side_effect=target.AcceptanceError("delete failed")), patch.object(runner, "assert_environment_restored"):
                with self.assertRaises(target.AcceptanceError):
                    runner.run_slice(lambda: None, complete=True)
            summary = json.loads((root / "acceptance_summary.json").read_text())
            self.assertEqual(summary["outcome"], "FAIL")
            self.assertIn("delete failed", summary["error"])
            self.assertEqual(summary["ac_results"]["AC-033"], "NOT_RUN")


class SnapshotInvariantTests(unittest.TestCase):
    def metadata(self):
        return {"table-uuid": "same-table", "current-schema-id": 0, "schemas": [{"schema-id": 0}], "current-snapshot-id": 70,
                "snapshots": [{"snapshot-id": 90, "timestamp-ms": 100}, {"snapshot-id": 20, "parent-snapshot-id": 90, "timestamp-ms": 110}, {"snapshot-id": 70, "parent-snapshot-id": 20, "timestamp-ms": 120}],
                "snapshot-log": [{"snapshot-id": 90, "timestamp-ms": 100}, {"snapshot-id": 20, "timestamp-ms": 110}, {"snapshot-id": 70, "timestamp-ms": 120}]}

    def states(self):
        before = {"metadata": self.metadata(), "metadata_location": "old.json", "objects": {"warehouse/table/data/delete.parquet": {"size": 9}}, "sha256": {"warehouse/table/data/delete.parquet": "content-hash"}}
        after = copy.deepcopy(before)
        after["metadata_location"] = "new.json"
        after["metadata"]["current-snapshot-id"] = 20
        after["metadata"]["snapshot-log"].append({"snapshot-id": 20, "timestamp-ms": 130})
        return before, after

    def test_chain_uses_history_not_numeric_snapshot_order(self):
        self.assertEqual(target.snapshot_chain(self.metadata(), 3), [90, 20, 70])
        for field, value in [("current-snapshot-id", 90), ("snapshot-log", []), ("snapshots", [])]:
            state = self.metadata()
            state[field] = value
            with self.subTest(field=field), self.assertRaises(target.AcceptanceError):
                target.snapshot_chain(state, 3)
        state = self.metadata()
        state["snapshots"][1]["parent-snapshot-id"] = 70
        with self.assertRaises(target.AcceptanceError):
            target.snapshot_chain(state, 3)

    def test_rollback_rejects_file_schema_history_and_pointer_mutations(self):
        before, after = self.states()
        target.assert_rollback(before, after, [90, 20, 70])
        mutations = []
        for key, value in [("current-snapshot-id", 70), ("current-schema-id", 1), ("table-uuid", "replacement"), ("snapshots", []), ("snapshot-log", [])]:
            changed = copy.deepcopy(after)
            changed["metadata"][key] = value
            mutations.append(changed)
        for key, value in [("sha256", {}), ("sha256", {"warehouse/table/data/delete.parquet": "changed-content"}), ("metadata_location", "old.json")]:
            mutations.append({**after, key: value})
        for changed in mutations:
            with self.subTest(changed=changed), self.assertRaises(target.AcceptanceError):
                target.assert_rollback(before, changed, [90, 20, 70])


if __name__ == "__main__":
    unittest.main()
