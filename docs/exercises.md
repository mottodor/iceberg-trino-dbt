# Learning exercises

Work through these six modules after [preparing the environment](verification.md#prepare-the-environment). Run commands from the repository root, sequentially, with a fresh run ID each time. Each full runner saves an acceptance report and cleans its task-owned tables and objects; [the manual walkthrough](quickstart.md) provides tables you can explore interactively.

The [verification guide](verification.md) explains stack ownership, report outcomes and the completion audit. The core, schema-evolution and partitioning runners need the default Compose project removed before they start; after a manual session, use `docker compose down`. The later runners can borrow a healthy default stack.

## Core lakehouse

Runs the baseline, compares the state before and after late events, and executes three isolated negative data-quality scenarios:

```bash
python3 scripts/run_acceptance.py --run-id learn_acceptance
```

## Schema evolution

Runs core regression before/after an isolated evolution exercise: capture S0, add/rename/widen columns without rewriting data files, verify readers and writers, create S1, compare typed historical projections, and reject narrowing without state changes:

```bash
python3 scripts/run_schema_evolution_acceptance.py --run-id learn_schema_evolution
```

Historical reads use each snapshot's schema on the pinned Trino version. The S0 comparison explicitly maps the legacy column name, supplies a typed NULL for the added column, and widens the count; it does not assume that S0 exposes the current schema.

## Partitioning and file pruning

Generates balanced/skewed data and compares unpartitioned (U), day-partitioned (D), route-bucketed (R), and combined (DR) layouts. The 52 query/layout cases bind exact results to partition/file metadata, distributed and IO plans, and `EXPLAIN ANALYZE` physical input; elapsed time is not a PASS threshold:

```bash
python3 scripts/run_partitioning_file_pruning_acceptance.py --run-id learn_partition_pruning
```

## Time travel and rollback

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

Evidence under `artifacts/acceptance/<run-id>/` includes typed rows and SQL in `history/`, per-operation negative comparisons in `negative/`, rollback results in `rollback/`, and catalog metadata, object inventories and SHA-256 proofs in `states/`. The runner deletes its five training schemas and all their objects after the checks; use the saved SQL/results to inspect the completed exercise. A full PASS requires behavior checks, evidence replay, a complete manifest, secret scan, isolation and environment restoration.

Two smaller modes are also available, each using a fresh ID:

```bash
python3 scripts/run_time_travel_acceptance.py --run-id learn_tt_environment --check-environment
python3 scripts/run_time_travel_acceptance.py --run-id learn_tt_probe --probe
```

The environment mode verifies lifecycle/allowlist and returns `ENVIRONMENT_READY`; it performs no fixture/model/table writes. The probe runs the bounded three-snapshot compatibility experiment and returns `CHECKPOINT`. Neither result is full TT acceptance. A healthy default stack is borrowed and left running; otherwise the runner manages only a new task-specific Compose project and removes its containers/network afterward. Named volumes are preserved. Existing evidence, occupied prefixes and unknown/partial default stacks are refused.

Branches/tags, timestamp semantics after rollback and maintenance remain outside TT-1. See [the approved contract](spec.md#12-новый-срез-time-travel-и-rollback) and [the bootstrap plan](bootstrap-time-travel.md).

## Maintenance

```bash
python3 scripts/run_maintenance_acceptance.py --run-id learn_maintenance
```

The disposable `<run-id>_maintenance` schema contains `maintenance_events` and an unchanged control table. Sixteen commits produce 2048 deterministic rows in 16 files below 1 MiB. Compaction reduces the current files from 16 to one while preserving rows and historical reads. An identical-row retention anchor followed by an append allows expiration to retain historical/current states of 2048/2176 rows and reclaim all 16 obsolete small files.

Two default-retention calls must fail atomically. Only the individual maintenance SQL sessions override the minimum retention to 0s; ordinary/global defaults stay 7d. The exercise uses 1s expiration with `retain_last=2`, then 10s orphan cleanup. The expired snapshot becomes unreadable. An aged orphan is removed while a young orphan, an outside-table marker, control and referenced data/delete files survive unchanged. These intervals belong to the isolated learning exercise.

Evidence includes file distributions, plans, catalog/S3 metadata, raw content hashes, retained/expired reads, marker ages and per-operation before/after bundles. All owned data is cleaned at the end, the initial stack state is restored and existing volumes are preserved. The smaller `--check-environment` mode returns CHECKPOINT and performs no data writes. See [the contract](spec.md#13-maintenance) and [execution plan](bootstrap-maintenance.md).

## Incremental predicates

```bash
python3 scripts/run_incremental_acceptance.py --run-id learn_incremental
```

The standalone dbt project in `dbt/exercises/incremental/` uses the same pinned image/profile and one disposable schema. Core models keep their existing table materializations. The safe model applies a seven-day received_at window to incoming data and the target MERGE predicate, using event_id as unique_key. It preserves the older E0 target row and admits late E5 based on received_at.

Initial data produces five rows. The second batch, its replay, a full refresh and the next incremental run all produce the same seven unique rows with amount sum 215, matching a separate full rebuild and independent Python oracle. Two intentionally wrong models make the failure modes visible: an event_at source filter loses E5 (six rows), and an event_at target predicate duplicates E1/E2 (nine rows, seven IDs). Positive dbt tests cover the safe/full models; the wrong models remain isolated counterexamples.

Saved actual MERGE and compiled source SQL, dbt results and IO/ANALYZE plans explain both predicates. After replay the source has 11 raw rows; six canonical IDs meet the window, while the target retains all seven IDs. The window assumes new arrivals satisfy the received_at bound; older received_at backfills require a separate full rebuild. Physical-byte or elapsed-time reduction is not a PASS threshold for this tiny unpartitioned dataset. Evidence is retained and task-owned data is removed after acceptance.

## Continue reading

- [Data model and SQL queries](data-model.md) explains the business domain and model grain.
- [Verification and retained results](verification.md#retained-results) records the accepted runs and criteria.
- [The specification](spec.md) defines exact contracts; [the bootstrap plans](../README.md#documentation) and [status history](status.md) record implementation decisions and task completion.

[Back to the project overview](../README.md)
