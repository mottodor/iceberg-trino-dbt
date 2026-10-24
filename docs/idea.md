# Lakehouse modeling: Iceberg, Trino и dbt

## Назначение

Независимый учебный проект для глубокого изучения аналитического моделирования поверх Apache Iceberg. В центре находятся table format, snapshots, schema evolution, Trino SQL и dbt-модели Bronze/Silver/Gold. Источники поступают как готовые deterministic fixtures, поэтому ingestion, CDC и orchestration не отвлекают от lakehouse-задач.

## Приобретаемые компетенции

- объяснять роли object storage, Iceberg, catalog и query engine;
- создавать и читать Iceberg tables через REST catalog;
- понимать разницу между data files, metadata files, manifests и snapshots;
- загружать immutable Bronze fixtures;
- строить typed Silver state;
- проектировать Kimball facts и dimensions;
- реализовать SCD Type 2;
- применять dbt tests и custom reconciliation tests;
- использовать incremental predicates осознанно;
- выбирать partitioning по реальному паттерну запросов;
- анализировать `EXPLAIN` и file pruning;
- воспроизводить historical query через snapshot/time travel;
- диагностировать small-files problem;
- выполнять безопасное snapshot expiration и compaction в отдельном упражнении.

### Входит в scope

- S3-compatible object storage;
- Apache Polaris;
- Trino;
- Apache Iceberg;
- dbt Core + dbt-trino;
- deterministic raw fixtures;
- Bronze/Silver/Gold;
- Kimball subset;
- SCD2;
- schema evolution;
- time travel;
- partitioning benchmark;
- data quality tests;
- maintenance exercises.

### Не входит в scope

- REST ingestion и file delivery lifecycle;
- Kafka/Debezium;
- Airflow;
- ClickHouse и Superset;
- Spark;
- full-scale production security;
- несколько бизнес-доменов;
- Data Vault.