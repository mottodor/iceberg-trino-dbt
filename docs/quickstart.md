# Manual walkthrough

Build the logistics models in two stages and inspect how late events change package P3. Run all commands from the repository root. The tables remain available for SQL queries during this manual session.

The examples use `DBT_TRINO_SCHEMA=learn` and a fresh set of `learn_*` schemas. For a second staged walkthrough, choose a new prefix in `.env` and update the SQL schema names accordingly. Loading batch_1 again does not remove an already loaded batch_2.

## 1 Requirements

- Docker Engine and Docker Compose;
- Python 3.12+ for the acceptance runners and host-side unit tests;
- approximately 4 CPUs and 8 GB of memory available to Docker.

Container versions and Python dependencies are pinned in the repository.

## 2 Prepare the local environment

Create `.env` from the tracked template if it does not already exist. Keep your existing local values when repeating the walkthrough:

```bash
if [ ! -f .env ]; then
  cp .env.example .env
fi
```

The template contains non-production training credentials. Docker Compose and the acceptance scripts load the root `.env` automatically; shell variables still take precedence when explicitly set.

`DBT_TRINO_SCHEMA` is the prefix for an isolated learning run. With the template value, models are created in the `learn_bronze`, `learn_silver`, and `learn_gold` schemas.

## 3 Start the stack

```bash
docker compose --profile tools config --quiet
docker compose --profile tools build dbt
docker compose up -d --wait --wait-timeout 240 rustfs polaris trino
```

Default endpoints:

| Service | Address |
|---|---|
| Trino | [localhost:8080](http://localhost:8080) |
| Polaris API | [localhost:8181](http://localhost:8181) |
| RustFS API | [localhost:9000](http://localhost:9000) |
| RustFS Console | [localhost:9001](http://localhost:9001) |

Check the stack:

```bash
docker compose ps -a
docker compose exec -T trino trino --execute "SELECT 1"
```

If the first query reports that Trino is still starting, wait a few seconds and retry.

## 4 Load the first batch

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

## 5 Build and inspect the first state

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

## 6 Add late events and rebuild

```bash
docker compose --profile tools run --rm --no-deps \
  --entrypoint python dbt \
  scripts/load_fixtures.py --scenario baseline --batch batch_2

docker compose --profile tools run --rm dbt build \
  --select tag:bronze tag:silver tag:gold
```

Run the `P3` query again. Delivery status, duration, and `is_on_time` remain unchanged, while two hub visits, three hours of dwell time, and a route ratio of `1.5` appear.

This is the main learning scenario: **late-arriving events recalculate dependent metrics without changing an already known final delivery state**.

## Explore the result

Continue with [the data model and layer queries](data-model.md#query-the-layers) to inspect Bronze duplicates, canonical Silver events, Gold metrics and Iceberg snapshots. The [core acceptance exercise](exercises.md#core-lakehouse) additionally checks negative data-quality scenarios and cross-layer reconciliation.

## Stop or reset the project

Stop the Compose project and preserve its RustFS volume:

```bash
docker compose down
```

Delete all local project data:

```bash
docker compose down -v
```

> `down -v` permanently removes the training RustFS volume and all Iceberg files stored in it.

Object files and catalog registrations are separate: this local stack uses an in-memory Polaris catalog, so recreating Polaris resets registrations even when the RustFS volume remains. Use a fresh schema prefix for a new walkthrough.

To switch from the manual session to an automated core/schema/partitioning acceptance run, first use `docker compose down` to remove the default project's containers. See [acceptance preparation](verification.md#prepare-the-environment).

[Back to the project overview](../README.md)
