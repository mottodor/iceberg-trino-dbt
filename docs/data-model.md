# Data model and SQL queries

The core project models parcel deliveries, route plans and hub visits. A package is the analytical unit; tracking events describe its lifecycle. SQL examples below assume the [manual walkthrough](quickstart.md) has loaded both batches into the default `learn_*` schemas.

## Layers and grain

| Layer or relation | Grain and purpose |
|---|---|
| Fixture sources | Deterministic CSV rows, including exact duplicates and late events |
| Bronze | Raw fixture rows, preserving the original values and duplicates |
| `silver_tracking_events_typed` | Typed raw events and payload fingerprints |
| `silver_tracking_events` | One canonical event per `event_id` |
| `silver_route_plan_versions` | One route-plan version with `valid_from`/`valid_to` SCD Type 2 intervals |
| `silver_route_plan_checkpoint_segments` | One route-version checkpoint with coordinates and distance from the previous checkpoint |
| `silver_package_route_binding` | One package bound to the plan version active at pickup |
| `silver_package_current_state` | One package's latest state, ordered by business event time |
| `gold_package_delivery_fact` | One accumulating fact row per picked-up package |
| `gold_hub_visits` | One visit, identified by package and visit sequence, including an open visit |
| `gold_route_version_efficiency` | Delivery metrics per route and route-plan version |
| `gold_route_version_hub_dwell` | Completed dwell metrics per route-plan version and hub |

Silver orders events by `(event_at, received_at, event_id)`. Bronze retains exact repeats; Silver selects one canonical payload. Conflicting payloads and invalid arrival/departure sequences are checked by data-quality tests.

Gold combines delivery duration, SLA delay, geodesic route distance and hub dwell. An active delivery keeps final delivery fields as SQL NULL. The core models are rebuilt as tables; the separate [incremental exercise](exercises.md#incremental-predicates) explores merge predicates.

## Read the models

1. `bronze_tracking_events.sql`;
2. `silver_tracking_events_typed.sql`;
3. `silver_tracking_events.sql`;
4. `silver_route_plan_versions.sql`;
5. `silver_package_route_binding.sql`;
6. `gold_hub_visits.sql`;
7. `gold_package_delivery_fact.sql`;
8. Gold aggregate models and reconciliation tests.

## Query the layers

### Bronze

```bash
docker compose exec -T trino trino --execute \
  "SELECT count(*) FROM lakehouse.learn_bronze.bronze_tracking_events"
```

Bronze preserves both rows of an exact duplicate. The complete baseline contains 28 event rows.

### Silver

```bash
docker compose exec -T trino trino --execute \
  "SELECT count(*) FROM lakehouse.learn_silver.silver_tracking_events"
```

Silver keeps one canonical row per `event_id`. The complete baseline contains 27 canonical events.

### Gold

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

A rebuilt core table can have a new table history. The [time-travel exercise](exercises.md#time-travel-and-rollback) uses one separate learning table so H0/H1/Hbad survive source-model rebuilds.

## Repository map

| Path | Contents |
|---|---|
| `compose.yaml`, `infra/` | Stack configuration and RustFS/Polaris/Trino bootstrap |
| `docker/dbt/` | dbt image and dependency lock |
| `dbt/fixtures/` | Core baseline batches and negative fixtures |
| `dbt/models/` | Bronze, Silver and Gold transformation layers |
| `dbt/tests/` | Business, data-quality and reconciliation checks |
| `dbt/exercises/incremental/` | Independent incremental dbt project and fixtures |
| `scripts/` | Acceptance runners and completion auditor |
| `scripts/tests/` | Acceptance helper unit and mutation tests |
| `docs/` | Guides, specification, competency matrix and task history |

## Technology documentation

- [Apache Iceberg](https://iceberg.apache.org/docs/latest/)
- [Trino Iceberg connector](https://trino.io/docs/current/connector/iceberg.html)
- [Trino and Iceberg REST catalogs](https://trino.io/docs/current/object-storage/metastores.html)
- [Apache Polaris](https://polaris.apache.org/)
- [dbt Core](https://docs.getdbt.com/docs/core)
- [RustFS](https://docs.rustfs.com/)
- [Docker Compose](https://docs.docker.com/compose/)

[Back to the project overview](../README.md)
