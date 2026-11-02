# Iceberg + Trino + dbt Learning Lakehouse

A hands-on project for learning lakehouse architecture through a small logistics domain. You will start a local stack, load deterministic delivery events, and transform raw data into tested analytical models.

Five learning slices are **implemented and committed**: the core lakehouse, schema evolution, partitioning/file pruning, time travel/rollback, and maintenance. Each has a passing end-to-end acceptance run. Incremental-predicate coverage and AC-002 remain open.

## Project status

Status reconciled on **2026-11-02**, through Time travel implementation commit `1bf0c5a`.

| Completed slice | Verified scope | Retained acceptance evidence |
|---|---|---|
| **Core lakehouse** | RustFS/Polaris/Trino/dbt stack; Bronze/Silver/Gold; SCD Type 2; duplicates and late events; DQ and reconciliation. | `imp007_final5` — PASS, 2026-10-29; AC-001 and AC-003–AC-012. |
| **Schema evolution** | Metadata-only add/rename/type widening; old-file reads; writer compatibility; typed S0/S1 historical projections; rejected narrowing without partial changes; core regression. | `seimp006_final2` — PASS, 2026-10-30; AC-013–AC-020. |
| **Partitioning / file pruning** | Balanced and skewed datasets of 256,000 rows each; eight U/D/R/DR tables; 52 query/layout cases with exact results, plans, file inventories, and physical-input evidence. | `pfimp006_final` — PASS, 2026-11-01; AC-021–AC-027. |
| **Time travel / rollback** | Real staged H0/H1/Hbad; three ID reads and five UTC timestamp cases; three atomic negative operations; rollback preserving historical data/delete files; final baseline build and isolated cleanup. | `tt_imp006_final` — PASS, 2026-11-02; AC-028–AC-033. |

| **Maintenance** | Small-files diagnostics, compaction, safe two-snapshot expiration, age/location-bounded orphan cleanup, session retention and complete evidence/cleanup. | `ma_imp005_final` — PASS, 2026-11-02; AC-034–AC-040. |

Run directories are under `artifacts/acceptance/` and are ignored by Git; they are local evidence, not files supplied by a fresh clone. See [docs/status.md](docs/status.md) for task completion commits and detailed acceptance/review history. AC-002 (full learning-outcome coverage) remains open until the remaining scope is implemented.

## What you will learn

- where object data, Iceberg metadata, and catalog entries live;
- how Apache Iceberg uses snapshots, manifests, and data files;
- how Trino reads and writes Iceberg tables through a REST catalog;
- how dbt builds Bronze, Silver, and Gold layers;
- how to handle duplicates and late-arriving events;
- how to model SCD Type 2 and an accumulating snapshot;
- how to validate data with dbt tests and reconciliation checks;
- how schema evolution preserves old data files and how historical snapshot schemas affect reads;
- how partition layouts and skew affect pruning, using query plans and physical-input evidence rather than elapsed time alone;
- how historical reads differ from rollback, and commit time differs from business event time;
- how to verify historical snapshots, rollback atomicity, and preservation of data/delete files.

## Architecture

```text
CSV fixtures
    │
    ▼
RustFS (S3-compatible object storage)
    ▲
    │ data files and Iceberg metadata
    ▼
Apache Polaris (Iceberg REST catalog)
    ▲
    │ catalog API
    ▼
Trino (SQL query engine)
    ▲
    │
    ▼
dbt Core: Bronze → Silver → Gold + tests
```

| Component | Role in this project |
|---|---|
| **RustFS** | Stores Parquet files and Iceberg metadata. |
| **Apache Polaris** | Registers Iceberg tables and provides the REST catalog. |
| **Apache Iceberg** | Defines the table format, snapshots, and metadata evolution. |
| **Trino** | Executes SQL against Iceberg tables. |
| **dbt Core + dbt-trino** | Builds models, dependencies, and data tests. |
| **Docker Compose** | Runs the complete stack without installing Trino or dbt on the host. |

## Quick start

### 1. Requirements

- Docker Engine and Docker Compose;
- Python 3.12+ for the acceptance runners and host-side unit tests;
- approximately 4 CPUs and 8 GB of memory available to Docker.

Container versions and Python dependencies are pinned in the repository.

### 2. Create the local environment file

Copy the tracked template and keep the resulting `.env` file local:

```bash
cp .env.example .env
```

The template contains non-production training credentials. Docker Compose and the acceptance scripts load the root `.env` automatically; shell variables still take precedence when explicitly set.

`DBT_TRINO_SCHEMA` is the prefix for an isolated learning run. With the template value, models are created in the `learn_bronze`, `learn_silver`, and `learn_gold` schemas.

### 3. Start the stack

```bash
docker compose --profile tools config --quiet
docker compose --profile tools build dbt
docker compose up -d --wait --wait-timeout 240 rustfs polaris trino
```

Available endpoints:

- Trino: <http://localhost:8080>
- Polaris API: <http://localhost:8181>
- RustFS API: <http://localhost:9000>
- RustFS Console: <http://localhost:9001>

Check the stack:

```bash
docker compose ps -a
docker compose exec -T trino trino --execute "SELECT 1"
```

If the first query reports that Trino is still starting, wait a few seconds and retry.

### 4. Validate and load the fixtures

You can validate all CSV files without connecting to Trino:

```bash
docker compose --profile tools run --rm --no-deps \
  --entrypoint python dbt scripts/load_fixtures.py --validate-only
```

Load the first batch:

```bash
docker compose --profile tools run --rm --no-deps \
  --entrypoint python dbt \
  scripts/load_fixtures.py --scenario baseline --batch batch_1
```

### 5. Build the first model state

```bash
docker compose --profile tools run --rm dbt debug

docker compose --profile tools run --rm dbt run \
  --select tag:bronze tag:silver tag:gold
```

Inspect package `P3` before its late events arrive:

```bash
docker compose exec -T trino trino --execute "
SELECT
  package_id,
  current_status,
  delivery_duration_hours,
  is_on_time,
  visit_count,
  completed_dwell_hours,
  actual_distance_meters / planned_distance_meters AS route_ratio
FROM lakehouse.learn_gold.gold_package_delivery_fact
WHERE package_id = 'P3'
"
```

Expected result: the package is already delivered, no hub visits are known yet, and the actual-to-planned route ratio is `1.0`.

### 6. Add late events and run the full build

```bash
docker compose --profile tools run --rm --no-deps \
  --entrypoint python dbt \
  scripts/load_fixtures.py --scenario baseline --batch batch_2

docker compose --profile tools run --rm dbt build \
  --select tag:bronze tag:silver tag:gold
```

Run the `P3` query again. Delivery status, duration, and `is_on_time` remain unchanged, while two hub visits, three hours of dwell time, and a route ratio of `1.5` appear.

This is the main learning scenario: **late-arriving events recalculate dependent metrics without changing an already known final delivery state**.

## Explore the layers

### Bronze — preserve raw rows

```bash
docker compose exec -T trino trino --execute \
  "SELECT count(*) FROM lakehouse.learn_bronze.bronze_tracking_events"
```

Bronze preserves both rows of an exact duplicate. The complete baseline contains 28 event rows.

### Silver — canonical events and typed state

```bash
docker compose exec -T trino trino --execute \
  "SELECT count(*) FROM lakehouse.learn_silver.silver_tracking_events"
```

Silver keeps one canonical row per `event_id`. The complete baseline contains 27 canonical events.

### Gold — analytical results

```bash
docker compose exec -T trino trino --execute "
SELECT
  package_id,
  current_status,
  delay_hours,
  is_on_time,
  final_route_deviation_pct
FROM lakehouse.learn_gold.gold_package_delivery_fact
ORDER BY package_id
"
```

The fixtures cover four scenarios:

- `P1` — an on-time delivery following the original route plan;
- `P2` — a late delivery with a route deviation;
- `P3` — an exact duplicate and late-arriving events;
- `P4` — an active delivery with an open hub visit.

### Iceberg snapshots

```bash
docker compose exec -T trino trino --execute "
SELECT committed_at, snapshot_id, operation
FROM lakehouse.learn_gold.\"gold_package_delivery_fact\$snapshots\"
ORDER BY committed_at
"
```

Use the RustFS Console to find the corresponding Parquet files, metadata JSON files, and Avro manifests.

## Run acceptance workflows

Create the local `.env` and build the dbt image as described above. Run the workflows sequentially, with a fresh run ID for each invocation. Stop the manually started stack first so each runner can start and restore an initially stopped environment:

```bash
docker compose down
```

### Core lakehouse

Runs the baseline, compares the state before and after late events, and executes three isolated negative data-quality scenarios:

```bash
python3 scripts/run_acceptance.py --run-id learn_acceptance
```

### Schema evolution

Runs core regression before/after an isolated evolution exercise: capture S0, add/rename/widen columns without rewriting data files, verify readers and writers, create S1, compare typed historical projections, and reject narrowing without state changes:

```bash
python3 scripts/run_schema_evolution_acceptance.py --run-id learn_schema_evolution
```

Historical reads use each snapshot's schema on the pinned Trino version. The S0 comparison explicitly maps the legacy column name, supplies a typed NULL for the added column, and widens the count; it does not assume that S0 exposes the current schema.

### Partitioning and file pruning

Generates balanced/skewed data and compares unpartitioned (U), day-partitioned (D), route-bucketed (R), and combined (DR) layouts. The 52 query/layout cases bind exact results to partition/file metadata, distributed and IO plans, and `EXPLAIN ANALYZE` physical input; elapsed time is not a PASS threshold:

```bash
python3 scripts/run_partitioning_file_pruning_acceptance.py --run-id learn_partition_pruning
```

Each runner writes evidence under `artifacts/acceptance/<run-id>/`, including `acceptance_summary.json`, command records, an evidence manifest, and a secret scan. It cleans up task-owned schemas/object prefixes and restores the initial environment while preserving pre-existing Docker volumes. See the relevant summary's `outcome` and `ac_results`; intentionally incomplete historical checkpoint runs are not overall slice PASS results.

### Time travel and rollback

Run the complete TT-1 exercise with a fresh run ID:

```bash
python3 scripts/run_time_travel_acceptance.py --run-id learn_time_travel
```

The runner builds unchanged core models in isolated source schemas, first from batch_1 and then batch_2. One separate eight-column Iceberg v2 table retains three states:

| P3 metric | H0 before late events | H1 after late events | Hbad after fault injection | Current after rollback |
|---|---:|---:|---:|---:|
| Delivery duration, hours | 36 | 36 | 360 | 36 |
| Completed visits | 0 | 2 | 2 | 2 |
| Completed dwell, hours | 0 | 3 | 3 | 3 |
| Actual/planned distance | 1.0 | 1.5 | 1.5 | 1.5 |

P1/P2/P4 remain unchanged. Snapshot IDs and millisecond UTC commit times come from runtime metadata. Before rollback, three snapshot-ID reads and five timestamp cases verify the saved states. Two unavailable-version reads and one invalid rollback must fail with the expected diagnostic and leave the full state unchanged. Rollback restores H1 while Hbad remains readable by ID, without a fourth data snapshot or new data/delete files. Both post-batch_2 and final baseline dbt builds pass all 128 nodes (15 models and 113 tests).

Evidence under `artifacts/acceptance/<run-id>/` includes typed rows and SQL in `history/`, per-operation negative comparisons in `negative/`, rollback results in `rollback/`, and catalog metadata, object inventories and SHA-256 proofs in `states/`. The runner deletes its five training schemas and all their objects after the checks; use the saved SQL/results to inspect the completed exercise. Overall PASS requires AC-028–AC-033, evidence replay, a complete manifest, secret scan, isolation and environment restoration.

Two smaller modes are also available, each using a fresh ID:

```bash
python3 scripts/run_time_travel_acceptance.py --run-id learn_tt_environment --check-environment
python3 scripts/run_time_travel_acceptance.py --run-id learn_tt_probe --probe
```

The environment mode verifies lifecycle/allowlist and returns `ENVIRONMENT_READY`; it performs no fixture/model/table writes. The probe runs the bounded three-snapshot compatibility experiment and returns `CHECKPOINT`. Neither result is full TT acceptance. A healthy default stack is borrowed and left running; otherwise the runner manages only a new task-specific Compose project and removes its containers/network afterward. Named volumes are preserved. Existing evidence, occupied prefixes and unknown/partial default stacks are refused.

Branches/tags, timestamp semantics after rollback and maintenance remain outside TT-1. See [the approved contract](docs/spec.md#12-новый-срез-time-travel-и-rollback) and [the bootstrap plan](docs/bootstrap-time-travel.md).

### Maintenance

```bash
python3 scripts/run_maintenance_acceptance.py --run-id learn_maintenance
```

The disposable `<run-id>_maintenance` schema contains `maintenance_events` and an unchanged control table. Sixteen commits produce 2048 deterministic rows in 16 files below 1 MiB. Compaction reduces the current files from 16 to one while preserving rows and historical reads. An identical-row retention anchor followed by an append allows expiration to retain historical/current states of 2048/2176 rows and reclaim all 16 obsolete small files.

Two default-retention calls must fail atomically. Only the individual maintenance SQL sessions override the minimum retention to 0s; ordinary/global defaults stay 7d. The exercise uses 1s expiration with `retain_last=2`, then 10s orphan cleanup. The expired snapshot becomes unreadable. An aged orphan is removed while a young orphan, an outside-table marker, control and referenced data/delete files survive unchanged. These intervals belong to the isolated learning exercise.

`ma_imp005_final` passed AC-034–AC-040 on 2026-11-02. Evidence includes file distributions, plans, catalog/S3 metadata, raw content hashes, retained/expired reads, marker ages and per-operation before/after bundles. All owned data is cleaned at the end, the initial stack state is restored and existing volumes are preserved. The smaller `--check-environment` mode returns CHECKPOINT and performs no data writes. See [the contract](docs/spec.md#13-maintenance) and [execution plan](docs/bootstrap-maintenance.md).

### Fast unit tests

The suite runs without Docker and contains 120 positive and mutation tests across partitioning, Time travel and maintenance at this checkpoint:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/tests -v
```

## Repository guide

```text
compose.yaml                 local lakehouse stack
docker/dbt/                  dbt image and dependency lock
infra/                       RustFS, Polaris, and Trino bootstrap configuration
dbt/fixtures/                baseline and negative scenarios
dbt/models/bronze/           immutable raw layer
dbt/models/silver/           typed/canonical data and SCD Type 2
dbt/models/gold/             facts and aggregates
dbt/tests/                   business, DQ, and reconciliation tests
scripts/run_acceptance.py    core end-to-end acceptance
scripts/run_schema_evolution_acceptance.py
                            schema evolution and core regression
scripts/run_partitioning_file_pruning_acceptance.py
                            partitioning/file-pruning benchmark
scripts/run_time_travel_acceptance.py
                            staged historical reads, rollback, evidence and cleanup
scripts/run_maintenance_acceptance.py
                            small files, compaction, expiration and orphan cleanup
scripts/learning_exercise.py shared isolated lifecycle/evidence adapter
scripts/tests/              lakehouse acceptance helper unit tests
docs/spec.md                approved contracts and full project scope
docs/bootstrap.md           plan for the completed core slice
docs/bootstrap-schema-evolution.md
                            plan for the completed schema evolution slice
docs/bootstrap-partitioning-file-pruning.md
                            plan for the completed partitioning/pruning slice
docs/bootstrap-time-travel.md
                            approved TT plan and project completion roadmap
docs/status.md              current completion summary and task evidence
```

Suggested model reading order:

1. `bronze_tracking_events.sql`;
2. `silver_tracking_events_typed.sql`;
3. `silver_tracking_events.sql`;
4. `silver_route_plan_versions.sql`;
5. `silver_package_route_binding.sql`;
6. `gold_hub_visits.sql`;
7. `gold_package_delivery_fact.sql`;
8. Gold aggregate models and reconciliation tests.

## Stop or reset the project

Stop containers and preserve the data:

```bash
docker compose down
```

Delete all local project data:

```bash
docker compose down -v
```

> `down -v` permanently removes the training RustFS volume and all Iceberg files stored in it.

## Technology documentation

- [Apache Iceberg](https://iceberg.apache.org/docs/latest/)
- [Trino Iceberg connector](https://trino.io/docs/current/connector/iceberg.html)
- [Trino and Iceberg REST catalogs](https://trino.io/docs/current/object-storage/metastores.html)
- [Apache Polaris](https://polaris.apache.org/)
- [dbt Core](https://docs.getdbt.com/docs/core)
- [RustFS](https://docs.rustfs.com/)
- [Docker Compose](https://docs.docker.com/compose/)

## Remaining learning scope

- **Incremental predicates:** map this competency to a verifiable exercise; current core models remain table materializations. Any additional exercise is isolated from their frozen contracts.
- **Full learning-outcome coverage (AC-002):** complete the matrix mapping all 14 competencies to exercises, criteria and applicable evidence after remaining gaps are closed.

Time travel and maintenance are complete. Remaining work is sequenced in [the project completion roadmap](docs/bootstrap-time-travel.md#9-порядок-завершения-проекта); actual task completion is recorded in [docs/status.md](docs/status.md).
