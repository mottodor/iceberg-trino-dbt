# Iceberg + Trino + dbt Learning Lakehouse

A hands-on project for learning lakehouse architecture through a small logistics domain. You will start a local stack, load deterministic delivery events, and transform raw data into tested analytical models.

The current **core vertical slice is complete**: infrastructure, Bronze/Silver/Gold models, SCD Type 2, data quality tests, and the end-to-end acceptance workflow work together.

## What you will learn

- where object data, Iceberg metadata, and catalog entries live;
- how Apache Iceberg uses snapshots, manifests, and data files;
- how Trino reads and writes Iceberg tables through a REST catalog;
- how dbt builds Bronze, Silver, and Gold layers;
- how to handle duplicates and late-arriving events;
- how to model SCD Type 2 and an accumulating snapshot;
- how to validate data with dbt tests and reconciliation checks.

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
- Python 3.12+ only for the acceptance script;
- approximately 4 CPUs and 8 GB of memory available to Docker.

Container versions and Python dependencies are pinned in the repository.

### 2. Set local training credentials

Use non-production values dedicated to this local project:

```bash
export RUSTFS_ACCESS_KEY=training-access-key
export RUSTFS_SECRET_KEY=training-secret-key-change-me
export POLARIS_CLIENT_ID=training-client
export POLARIS_CLIENT_SECRET=training-client-secret-change-me
export DBT_TRINO_SCHEMA=learn
```

`DBT_TRINO_SCHEMA` is the prefix for an isolated learning run. The models will be created in `learn_bronze`, `learn_silver`, and `learn_gold` schemas.

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

## Run the complete acceptance workflow

The acceptance workflow runs the baseline, compares the state before and after late events, executes three isolated negative data-quality scenarios, captures evidence, and removes the schemas it created.

Stop the manually started stack first:

```bash
docker compose down
python3 scripts/run_acceptance.py --run-id learn_acceptance
```

Evidence is saved under `artifacts/acceptance/learn_acceptance/`. This directory is ignored by Git. The script preserves an existing Docker volume.

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
scripts/run_acceptance.py    end-to-end automated verification
docs/spec.md                 approved business contracts
docs/bootstrap.md            plan for the completed core slice
docs/status.md               task history and acceptance evidence
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

## Next learning slices

The full project scope also includes schema evolution, time travel, partitioning and file pruning, small-files diagnostics, snapshot expiration, and compaction. These topics are listed in `docs/spec.md` and will be specified and implemented as separate slices.
