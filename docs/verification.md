# Verification and acceptance results

Acceptance runners validate the six [learning exercises](exercises.md) against the [specification](spec.md). They produce local evidence and clean their task-owned data. The completion auditor checks the retained reports and [all 14 learning competencies](learning-outcomes.md).

Run commands from the repository root. For an interactive SQL session, start with [the manual walkthrough](quickstart.md).

## Prepare the environment

You need Docker Engine with Compose, Python 3.12+, and approximately 4 CPUs / 8 GB available to Docker. Container versions and dbt dependencies are pinned in the repository.

```bash
if [ ! -f .env ]; then
  cp .env.example .env
fi
docker compose --profile tools config --quiet
docker compose --profile tools build dbt
```

The tracked template contains local training credentials. `.env` remains untracked; both Compose and the runners load it, and explicit shell variables take precedence. Keep existing `.env` values when repeating these steps.

The core runner starts the pinned services and can populate a fresh image cache. To run only time travel, maintenance or incremental from a fresh cache, preload their runtime images; those isolated runners refuse implicit image pulls/builds:

```bash
docker compose pull rustfs bucket-setup polaris polaris-setup trino
```

## Stack ownership and cleanup

| Runners | Initial default project | Result |
|---|---|---|
| Core, schema evolution, partitioning | No existing default-project containers, running or stopped | Start and remove the default project; preserve pre-existing volumes |
| Time travel, maintenance, incremental | Healthy default stack or no default project | Borrow a healthy stack and leave it running, or manage a fresh task-specific project; refuse partial/unknown default state |

After a manual walkthrough, stop and remove its default-project containers before using the first group:

```bash
docker compose down
```

Run workflows sequentially. Each invocation needs a fresh run ID matching `[a-z][a-z0-9_]{2,31}`: 3–32 lowercase letters, digits or underscores, starting with a letter. Existing evidence or occupied task prefixes cause refusal. Successful full runs remove their owned schemas/object prefixes and restore the initial stack state. Named volumes are preserved. [Resetting the manual project](quickstart.md#stop-or-reset-the-project) is a separate operation.

## Read a report

Evidence is stored under `artifacts/acceptance/<run-id>/` and is Git-ignored. A fresh clone generates these directories by executing the runners.

| Artifact | What to inspect |
|---|---|
| `acceptance_summary.json` | `outcome`, individual `ac_results`, and `error` |
| `commands.jsonl` | Commands, exit codes and measured durations |
| `evidence_manifest.json` | Covered paths, file sizes and SHA-256 hashes |
| `secret_scan.json` | Credential scan results |
| Scenario directories | SQL, typed rows, plans, metadata, hashes and comparisons |
| `cleanup/` | Task-data cleanup and environment restoration |

A complete acceptance run has `outcome=PASS`, no error and PASS for every assigned criterion. Environment/probe/development CHECKPOINT runs are intermediate results. Time travel's environment-only mode instead writes `environment_checkpoint.json` with `ENVIRONMENT_READY`; full time-travel criteria remain NOT_RUN. Expected negative operations are validated by their specific diagnostic and state invariants, so a nonzero command alone is insufficient.

## Unit tests

The suite runs without Docker and contains 126 positive and mutation tests across the acceptance helpers and completion auditor:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/tests -v
```

## Retained results

The agreed scope is complete. The retained completion audit `project_final_001` records all 45 criteria and all 14 competencies as PASS. It verifies six slice reports, 3559 manifest-covered files, the completed implementation boundary and task-runtime cleanup. Per-stage commits and diagnostic history are in [status](status.md).

| Completed slice | Verified scope | Retained acceptance evidence |
|---|---|---|
| **Core lakehouse** | RustFS/Polaris/Trino/dbt stack; Bronze/Silver/Gold; SCD Type 2; duplicates and late events; DQ and reconciliation. | `imp007_final5` — PASS, 2026-10-29; AC-001 and AC-003–AC-012. |
| **Schema evolution** | Metadata-only add/rename/type widening; old-file reads; writer compatibility; typed S0/S1 historical projections; rejected narrowing without partial changes; core regression. | `seimp006_final2` — PASS, 2026-10-30; AC-013–AC-020. |
| **Partitioning / file pruning** | Balanced and skewed datasets of 256,000 rows each; eight U/D/R/DR tables; 52 query/layout cases with exact results, plans, file inventories, and physical-input evidence. | `pfimp006_final` — PASS, 2026-11-01; AC-021–AC-027. |
| **Time travel / rollback** | Real staged H0/H1/Hbad; three ID reads and five UTC timestamp cases; three atomic negative operations; rollback preserving historical data/delete files; final baseline build and isolated cleanup. | `tt_imp006_final` — PASS, 2026-11-02; AC-028–AC-033. |
| **Maintenance** | Small-files diagnostics, compaction, safe two-snapshot expiration, age/location-bounded orphan cleanup, session retention and complete evidence/cleanup. | `ma_imp005_final` — PASS, 2026-11-02; AC-034–AC-040. |
| **Incremental predicates** | Real dbt merge, independent full rebuild, late/duplicate events, replay/full-refresh, source/target counterexamples and scan evidence. | `inc_imp001_final2` — PASS, 2026-11-02; AC-041–AC-045. |

These run IDs identify the local reports checked by the auditor. For a new standalone experiment, use the fresh example IDs in [the exercises](exercises.md). To reproduce the full audit on a fresh clone, execute the six runners in this order with the exact IDs below:

```bash
python3 scripts/run_acceptance.py --run-id imp007_final5
python3 scripts/run_schema_evolution_acceptance.py --run-id seimp006_final2
python3 scripts/run_partitioning_file_pruning_acceptance.py --run-id pfimp006_final
python3 scripts/run_time_travel_acceptance.py --run-id tt_imp006_final
python3 scripts/run_maintenance_acceptance.py --run-id ma_imp005_final
python3 scripts/run_incremental_acceptance.py --run-id inc_imp001_final2
```

On an existing checkout, retain the accepted reports. Occupied IDs are refused rather than overwritten.

## Completion audit

Recheck retained evidence with a fresh report ID:

```bash
python3 scripts/verify_project_completion.py --run-id project_recheck_001 --check-docker
```

The auditor expects the exact six retained run IDs above. It verifies summaries/manifests, raw time-travel/maintenance/incremental evidence, criterion ownership, competency coverage, unchanged implementation files and preserved earlier contract prefixes. `--check-docker` additionally checks that task-owned containers/networks are absent; omitting it uses retained cleanup evidence. This audit reads reports and performs no data writes.

Historical Specify/Bootstrap stopping points remain in planning documents. Current completion is defined by the accepted reports, [the outcome matrix](learning-outcomes.md) and [status](status.md). Branches/tags, CDC/orchestration and production security remain outside the agreed learning scope.

[Back to the project overview](../README.md)
