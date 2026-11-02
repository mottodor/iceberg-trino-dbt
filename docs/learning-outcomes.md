# Покрытие учебных результатов

Матрица соответствует всем 14 компетенциям [исходной идеи](idea.md#приобретаемые-компетенции) и служит проверкой AC-002. Все 14 компетенций подтверждены шестью completed acceptance reports. Итоговая машинная проверка AC-002 выполняется командой ниже. Raw reports находятся в Git-ignored `artifacts/acceptance/`; свежий clone воспроизводит их documented runners.

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
| 9 | Incremental predicates | Отдельный dbt merge: safe received_at-window, full rebuild, replay и два неверных predicates | AC-042–045; `inc_imp001_final2` actual MERGE, plans и comparisons | Подтверждено |
| 10 | Partitioning по workload | Balanced/skewed U/D/R/DR, exact directional comparison | AC-021–025; `pfimp006_final` 52 cases | Подтверждено |
| 11 | EXPLAIN и file pruning | Distributed/IO/analyze планы, physical input и file bounds | AC-024–026; `pfimp006_final` causal matrix | Подтверждено |
| 12 | Snapshot/time travel | Три ID и пять timestamp reads, rollback и negative cases | AC-029–033; `tt_imp006_final` | Подтверждено |
| 13 | Small-files diagnostics | Детерминированный workload и file size distribution | AC-035; `ma_imp005_final/fixture/` | Подтверждено |
| 14 | Snapshot expiration и compaction | Isolated optimize/expire/orphan cleanup с retained file safety | AC-036–040; `ma_imp005_final` | Подтверждено |

## Условия итоговой проверки

Для каждой строки нужны доступные код/задание, критерий и достаточный retained report. Старые PASS применимы к неизменным contract/code boundaries; append-only новые разделы spec и отдельный dbt project не означают повторную реализацию core. FINAL-001 связывает оставшиеся live reports, FINAL-002 проверяет summaries/manifests, fingerprints, documented commands и cleanup.

## Итоговая проверка

```bash
python3 scripts/verify_project_completion.py --run-id project_final_001 --check-docker
```

Команда сверяет все шесть summaries и manifests, raw behavior evidence TT/maintenance/incremental, unchanged implementation boundary от `c568502`, append-only старые contracts и 14 строк этой матрицы. Для каждого нового запуска требуется свежий ID. Без `--check-docker` проверка использует retained cleanup evidence; этот flag дополнительно проверяет отсутствие task-owned containers/networks. Reports остаются локальными Git-ignored artifacts; отсутствующий report не считается PASS.
