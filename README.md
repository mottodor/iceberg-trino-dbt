# Iceberg + Trino + dbt Learning Lakehouse

A hands-on project for learning lakehouse architecture through a small logistics domain. Load deterministic delivery events and transform them into tested analytical models of package delivery, route efficiency and hub dwell.

Start with the [manual walkthrough](docs/quickstart.md) to explore SQL and late-arriving events, or run the [quick check](#quick-check) below for an automated acceptance report.

## Architecture

```text
CSV fixtures ── loader SQL ──┐
                            ▼
dbt models ── SQL ────────► Trino ── REST catalog ──► Polaris
                            │
                            └── data + Iceberg metadata ──► RustFS
```

- **RustFS** stores Parquet data and Iceberg metadata in S3-compatible object storage.
- **Apache Polaris** registers tables through the Iceberg REST catalog.
- **Trino** reads and writes **Apache Iceberg** tables using SQL.
- **dbt Core + dbt-trino** builds `Bronze → Silver → Gold` models and tests.
- **Docker Compose** runs the stack with pinned container versions and dependencies.

Bronze preserves raw duplicates, Silver types and canonicalizes events and binds packages to route-plan versions, and Gold calculates delivery and hub metrics. Late events update dependent metrics while preserving an already known final delivery state. See [model grain and SQL examples](docs/data-model.md).

## Quick check

Requires Docker Engine with Compose, Python 3.12+, and approximately 4 CPUs / 8 GB available to Docker. Run from the repository root with no existing default-project containers. After a manual session, use `docker compose down` first; see [environment preparation and cleanup](docs/verification.md#prepare-the-environment).

```bash
if [ ! -f .env ]; then
  cp .env.example .env
fi
docker compose --profile tools config --quiet
docker compose --profile tools build dbt
python3 scripts/run_acceptance.py --run-id learn_acceptance
```

The runner starts the stack, checks the baseline and late events, runs negative data-quality scenarios, and cleans its training tables and containers. It preserves existing named volumes. The template uses local training credentials; keep `.env` untracked.

Success means exit code `0` and `outcome=PASS` in:

```text
artifacts/acceptance/learn_acceptance/acceptance_summary.json
```

Reports are local and Git-ignored. Use a fresh run ID on each invocation; existing reports are never overwritten. For tables you can inspect interactively, follow the [manual walkthrough](docs/quickstart.md).

## Learning modules

Work through the modules in order. Each guide includes the command, expected behavior and evidence to inspect.

| Module | What you will practice |
|---|---|
| [Core lakehouse](docs/exercises.md#core-lakehouse) | Bronze/Silver/Gold, SCD Type 2, accumulating facts, duplicates, late events and reconciliation |
| [Schema evolution](docs/exercises.md#schema-evolution) | Add, rename and widen columns; compare historical schemas; reject narrowing |
| [Partitioning and file pruning](docs/exercises.md#partitioning-and-file-pruning) | Compare layouts and skew through file metadata, query plans and physical input |
| [Time travel and rollback](docs/exercises.md#time-travel-and-rollback) | Read historical snapshots by ID/time, inject a fault and restore a known state |
| [Maintenance](docs/exercises.md#maintenance) | Diagnose small files, compact, expire snapshots and remove orphans |
| [Incremental predicates](docs/exercises.md#incremental-predicates) | Apply source/target MERGE predicates and test late events, replay and counterexamples |

## Documentation

| Guide | Use it to |
|---|---|
| [Manual walkthrough](docs/quickstart.md) | Start the stack, load two batches, inspect P3, find endpoints and stop/reset |
| [Learning exercises](docs/exercises.md) | Run all six modules and understand their expected behavior |
| [Data model and SQL queries](docs/data-model.md) | Understand layer grain, query results and navigate the source models |
| [Verification and acceptance results](docs/verification.md) | Run unit tests, read reports, reproduce retained results and audit completion |

Project contracts and implementation history:

- [Specification](docs/spec.md): agreed scope and acceptance criteria.
- [Learning outcomes](docs/learning-outcomes.md): competencies and supporting evidence.
- [Status](docs/status.md): completed tasks, commits and review history.
- Execution plans: [core](docs/bootstrap.md), [schema evolution](docs/bootstrap-schema-evolution.md), [partitioning](docs/bootstrap-partitioning-file-pruning.md), [time travel and completion roadmap](docs/bootstrap-time-travel.md), [maintenance](docs/bootstrap-maintenance.md).

## Completion and verification

All six modules are implemented, tested and committed. The [retained results](docs/verification.md#retained-results) record accepted runs and coverage; the [completion audit](docs/verification.md#completion-audit) explains how to verify them or reproduce the evidence on a fresh clone.
