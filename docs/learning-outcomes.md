# Покрытие учебных результатов

Матрица соответствует всем 14 компетенциям [исходной идеи](idea.md#приобретаемые-компетенции) и служит проверкой AC-002. Состояние после завершения TT-1: три пробела — incremental predicates, small files и maintenance. Итоговый PASS AC-002 возможен после их фактической приёмки. Raw reports находятся в Git-ignored `artifacts/acceptance/`; свежий clone воспроизводит их documented runners.

| № | Компетенция | Задание или результат | Критерии и evidence | Состояние |
|---|---|---|---|---|
| 1 | Роли storage, Iceberg, catalog, query engine | Архитектура README; core SQL/Polaris/S3 inspection | AC-012; `imp007_final5` catalog/object evidence | Подтверждено |
| 2 | Создание/чтение через REST catalog | Core registrations и queries; TT catalog metadata pointers | AC-012, AC-033; `imp007_final5`, `tt_imp006_final` | Подтверждено |
| 3 | Data, metadata, manifests, snapshots | Schema evolution metadata-only DDL; TT S3/catalog/file bundles | AC-015, AC-029–030; `seimp006_final2`, `tt_imp006_final/states/` | Подтверждено |
| 4 | Immutable Bronze fixtures | Bronze сохраняет raw duplicate и batch fidelity | AC-004; core layer reconciliation | Подтверждено |
| 5 | Typed Silver state | Typed/canonical events, current package state | AC-004–005, AC-011; core model/tests | Подтверждено |
| 6 | Kimball facts и dimensions | Package accumulating fact, hub visits, route-version dimension и aggregates | AC-006–008, AC-010; Gold/Silver models и independent baseline | Подтверждено |
| 7 | SCD Type 2 | Plan versions и package binding по picked_up_at | AC-003; `imp007_final5` route binding | Подтверждено |
| 8 | dbt tests и reconciliation | Negative DQ, business tests, cross-layer reconciliation | AC-009, AC-011; core negative scenarios и full builds | Подтверждено |
| 9 | Incremental predicates | Нужен отдельный bounded-lateness dbt merge exercise и контрпримеры | INC-SPEC-001, INC-IMP-001; критерии будут добавлены в spec §14 | Открыто |
| 10 | Partitioning по workload | Balanced/skewed U/D/R/DR, exact directional comparison | AC-021–025; `pfimp006_final` 52 cases | Подтверждено |
| 11 | EXPLAIN и file pruning | Distributed/IO/analyze планы, physical input и file bounds | AC-024–026; `pfimp006_final` causal matrix | Подтверждено |
| 12 | Snapshot/time travel | Три ID и пять timestamp reads, rollback и negative cases | AC-029–033; `tt_imp006_final` | Подтверждено |
| 13 | Small-files diagnostics | Детерминированный workload и file size distribution | AC-035; MA-IMP-001 | Открыто |
| 14 | Snapshot expiration и compaction | Isolated optimize/expire/orphan cleanup с retained file safety | AC-036–040; MA-IMP-002–005 | Открыто |

## Условия итоговой проверки

Для каждой строки нужны доступные код/задание, критерий и достаточный retained report. Старые PASS применимы к неизменным contract/code boundaries; append-only новые разделы spec и отдельный dbt project не означают повторную реализацию core. FINAL-001 связывает оставшиеся live reports, FINAL-002 проверяет summaries/manifests, fingerprints, documented commands и cleanup.
