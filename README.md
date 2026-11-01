# Iceberg + Trino + dbt Learning Lakehouse

A hands-on project for learning lakehouse architecture through a small logistics domain. You will start a local stack, load deterministic delivery events, and transform raw data into tested analytical models.

Three learning slices are **implemented, reviewed, and committed**: the core lakehouse, schema evolution, and partitioning/file pruning. Each has a passing end-to-end acceptance run. The full project scope is not yet complete; dedicated time-travel and maintenance exercises remain.

## Project status

Status reconciled on **2026-11-01**, through commit `88fc7db`.

| Completed slice | Verified scope | Retained acceptance evidence |
|---|---|---|
| **Core lakehouse** | RustFS/Polaris/Trino/dbt stack; Bronze/Silver/Gold; SCD Type 2; duplicates and late events; DQ and reconciliation. | `imp007_final5` — PASS, 2026-10-29; AC-001 and AC-003–AC-012. |
| **Schema evolution** | Metadata-only add/rename/type widening; old-file reads; writer compatibility; typed S0/S1 historical projections; rejected narrowing without partial changes; core regression. | `seimp006_final2` — PASS, 2026-10-30; AC-013–AC-020. |
| **Partitioning / file pruning** | Balanced and skewed datasets of 256,000 rows each; eight U/D/R/DR tables; 52 query/layout cases with exact results, plans, file inventories, and physical-input evidence. | `pfimp006_final` — PASS, 2026-11-01; AC-021–AC-027. |

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
- how partition layouts and skew affect pruning, using query plans and physical-input evidence rather than elapsed time alone.

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

### Fast unit tests

The partitioning/pruning helper suite runs without Docker. The current suite contains 54 positive and mutation tests:

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
scripts/tests/              partitioning/pruning helper unit tests
docs/spec.md                approved contracts and full project scope
docs/bootstrap.md           plan for the completed core slice
docs/bootstrap-schema-evolution.md
                            plan for the completed schema evolution slice
docs/bootstrap-partitioning-file-pruning.md
                            plan for the completed partitioning/pruning slice
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

The completed schema evolution and partitioning/file-pruning slices are available through the runners above. The remaining full-project scope still needs dedicated specification and implementation:

- **Time travel:** a broader exercise beyond the S0/S1 snapshot-schema compatibility checks already covered by schema evolution; timestamp-based reads, branches/tags, and rollback are outside that completed slice.
- **Maintenance:** small-files diagnostics/remediation, snapshot expiration, orphan-file cleanup, and compaction.
- **Full learning-outcome coverage (AC-002):** trace all required competencies to exercises and evidence after the remaining slices are complete.

See `docs/spec.md` for scope boundaries. The next slice has not been selected or implemented by this documentation update.
