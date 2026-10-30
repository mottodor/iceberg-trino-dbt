# План реализации: partitioning и file-pruning benchmark

**ID плана:** `BOOTSTRAP-PLAN-PARTITIONING-FILE-PRUNING-001`

**Версия skill:** Bootstrap `0.1.0`

**Статус плана:** `READY_FOR_REVIEW`

**Одобрение:** пользователь явно одобрил этот план 2026-10-30; применение, probes и реализация не запускались

**Режим:** только планирование; сервисы, SQL, benchmark, probes и тесты в этом запуске не выполнялись

**Дата инвентаризации:** 2026-10-30

## 1. Вход, выбранный scope и fingerprints

### Входные материалы

- Утверждённая спецификация: [`docs/spec.md`](./spec.md), раздел 11, AC-021–AC-027.
- Исходный brief: [`docs/idea.md`](./idea.md).
- Завершённые slices и их evidence history: [`docs/status.md`](./status.md).
- Существующая инфраструктура и lifecycle: [`compose.yaml`](../compose.yaml), [`scripts/run_acceptance.py`](../scripts/run_acceptance.py), [`scripts/run_schema_evolution_acceptance.py`](../scripts/run_schema_evolution_acceptance.py).
- Пользовательское ограничение: работать только в рамках partitioning/file-pruning slice.
- Целевой файл плана: `docs/bootstrap-partitioning-file-pruning.md`; до записи отсутствовал и не являлся symlink.

### Fingerprints

| Источник | Fingerprint / состояние |
| --- | --- |
| Git HEAD | `2e5ad98e322642b278686c30c3d95c58069afd65` |
| Git status до записи плана | ветка `main`; пользовательское изменение `M docs/spec.md` |
| `docs/spec.md` | SHA-256 `afb9ab18d968d91d3d6cce591b88f7ac170d01612299f3673f88ee80648ba16a` |
| `docs/idea.md` | SHA-256 `7755620909b9cd65d1a6e8fa9c8fc805344f7f95a0fac2f123f08f7b78a8bccf` |
| `README.md` | SHA-256 `f3b29a39f3cabb03ce2f657a0fdd6eb34f0d64ebd5df5893a044a82f3692c14f` |
| `compose.yaml` | SHA-256 `55c832a2297d8f13fbd1635c0bba6ce0912b785b31f943cb851a9e92f46f0bdd` |
| `scripts/run_acceptance.py` | SHA-256 `b2d96a1f6a44e228e786718894b5827ae2129c8d8bcf1da799754ffc63c549f8` |
| `scripts/run_schema_evolution_acceptance.py` | SHA-256 `245034f743fbae1d9099fa8d95cee4c783e2e18c6633772a1852ee75ebcdb2bb` |
| `dbt/dbt_project.yml` | SHA-256 `0913254da1f9a4b6ae0a43b602592dfe40d7e233d4c2e2df9d4c282da4e924e1` |
| Bootstrap skill | версия `0.1.0` из фактического `SKILL.md` |

Глобальный заголовок `docs/spec.md` по-прежнему называет только ранее одобренные core/schema-evolution slices, но локальный раздел 11 имеет статус `APPROVED`, а пользователь явно выбрал его текущим срезом. Это не блокирует план; предыдущие разделы не изменяются.

### Выбранный scope

План покрывает только:

- task-owned benchmark schema;
- два детерминированных dataset — balanced и skewed;
- восемь Iceberg tables с layout `U`, `D`, `R`, `DR`;
- exact reconciliation, partition/file metadata, `EXPLAIN`, `EXPLAIN ANALYZE` и physical-input evidence;
- file-topology/bounds gate;
- impact-based regression boundary;
- catalog/object evidence и безопасный cleanup для AC-021–AC-027.

### Явные исключения

Не изменять и не включать:

- core fixtures, Bronze/Silver/Gold models/tests и их результаты;
- schema-evolution runner и контракты AC-013–AC-020;
- Compose stack, catalog configuration, image pins и dependency locks без доказанной необходимости;
- dbt DAG для benchmark;
- sorting/`sorted_by`, clustering, compaction, snapshot expiration, orphan cleanup;
- small-files remediation и wall-clock pass/fail thresholds;
- partition evolution существующих core tables;
- CI, production security и новые сервисы.

## 2. Наблюдаемое состояние репозитория, среды и Pi

### Репозиторий

Наблюдалось локально без запуска проектного кода:

- проект не содержит `AGENTS.md`, project-level Pi config или CI;
- `artifacts/acceptance/` уже исключён из Git;
- существующие acceptance runners используют Python stdlib, Docker Compose и Trino CLI внутри контейнера;
- `AcceptanceRun` уже реализует env loading, preflight, ownership gate, Compose lifecycle, command journal, Trino CSV queries, Polaris/RustFS evidence, secret scan, manifest и environment restoration;
- schema-evolution runner наследует `AcceptanceRun` и подтверждает применимость отдельного slice-specific entry point без изменения default core workflow;
- schema-evolution workflow уже применяет итоговый gate: последний AC получает PASS только после behavior checks, cleanup, restoration, secret scan и manifest validation;
- в репозитории нет отдельного Python test framework или pytest dependency;
- пользовательское изменение `docs/spec.md` не исправлялось и не откатывалось.

Review graph pi-lens покрывает только 5 из 14 известных файлов и отмечен stale относительно HEAD, поэтому он использовался только как навигационная подсказка. Решения плана основаны на прямом чтении актуальных файлов.

### Закреплённый stack

| Компонент | Наблюдалось локально / в репозитории |
| --- | --- |
| ОС | Linux WSL2 `x86_64`, kernel `6.18.33.2-microsoft-standard-WSL2` |
| Python host | `3.12.3` |
| Git | `2.43.0` |
| Docker CLI | `29.8.0` |
| Docker Compose | `v5.5.1` |
| Node.js / npm | `v24.15.0` / `11.12.1` |
| Pi | `1.4.0` |
| RustFS | `1.0.4` с digest в `compose.yaml` |
| Apache Polaris | `1.8.0` с digest |
| Trino | `484` с digest |
| dbt Core / dbt-trino | `1.11.11` / `1.10.2`, hash-locked image |
| Compose limits | Trino 2 CPU / 4 GiB; Polaris 1 CPU / 2 GiB; RustFS 0.5 CPU / 1 GiB |
| Host capacity | наблюдалось 16 logical CPU и около 24 GiB RAM; это не разрешение использовать весь ресурс |

Команды версий не доказывают доступность Docker daemon, свободные порты, наличие image cache или прохождение benchmark. `.env` и credentials не читались.

### Pi и доступные ресурсы

В `~/.pi/agent/settings.json` настроены пакеты:

| Пакет | Версия из локального lock/package | Состояние для задачи |
| --- | ---: | --- |
| `@upstash/context7-pi` | `0.1.3` | настроен; tools доступны и использованы для документации Trino 484 |
| `pi-lens` | `4.4.4` | настроен; diagnostics/navigation доступны; project config отсутствует |
| `pi-lmstudio` | `1.5.0` | настроен, но для плана и реализации среза не требуется |
| `pi-subagents` | `0.81.0` | настроен, но делегирование в Bootstrap не разрешено и не требуется |

Для нового Markdown plan pi-lens выбирает marksman и typos, а также markdownlint/spellcheck/vale runners. Project/global pi-lens config для workspace отсутствует; действуют defaults. Запись плана может запускать post-write diagnostics, поэтому итоговый файл требуется перечитать и проверить после записи.

Новые skills, extensions, MCP servers, model providers и Pi settings не нужны.

## 3. Выбор возможностей

| Потребность | Существующая возможность | Решение | Основание / ограничение |
| --- | --- | --- | --- |
| Управление stack и ownership | `AcceptanceRun` | Переиспользовать наследованием | Уже содержит preflight, lifecycle, cleanup и restoration; default core CLI не менять |
| Trino SQL и CSV evidence | `AcceptanceRun.query_csv`/`capture` | Переиспользовать | Достаточно для DDL, aggregate results и metadata tables |
| Deterministic row generation | Trino 484 table function `sequence` и SQL CTE/`VALUES` | Использовать | Не нужны CSV fixtures, dbt или новая зависимость |
| Partition metadata | Iceberg `$partitions`, `$files`, table metadata | Использовать | Требуется probe фактической схемы `$files` в Trino 484 |
| Logical plan | `EXPLAIN (TYPE DISTRIBUTED, FORMAT JSON)` | Использовать | JSON format документирован, но не гарантирован между версиями; stack pinned на 484 |
| Runtime scan metrics | `EXPLAIN ANALYZE` text | Использовать с bounded parser и raw evidence | Отдельный JSON format для `EXPLAIN ANALYZE` документацией не подтверждён |
| Pure contract/parser tests | Python stdlib `unittest` | Добавить | Новая test dependency не нужна |
| Object/catalog evidence | существующие Polaris/RustFS helpers | Переиспользовать | Уже доказаны завершёнными workflows |
| Documentation | существующий `README.md` | Кратко дополнить | Только команда benchmark, evidence и cleanup semantics |
| Task history | существующий `docs/status.md` | Обновлять при реализации | Не создавать новый status/handoff файл |
| Up-to-date docs | Context7 | Оставить доступным по необходимости | Использовать только для конкретных Trino/Iceberg вопросов |
| CI | отсутствует | Не добавлять | Сначала доказать локальный pinned-stack workflow |
| dbt | установлен и закреплён | Не использовать в benchmark | Срез проверяет физический Iceberg layout, а не dbt DAG |

**Итог:** не добавлять пакеты, images, services, AGENTS.md, Pi config или CI.

## 4. Техническое предложение и необходимые probes

### 4.1. Новый entry point

Предлагается добавить:

- `scripts/run_partitioning_file_pruning_acceptance.py` — isolated workflow AC-021–AC-027;
- `scripts/tests/test_partitioning_file_pruning_acceptance.py` — stdlib unit tests pure helpers/parsers;
- короткий раздел в `README.md`;
- task records в существующем `docs/status.md` по мере реализации.

Runner наследует `AcceptanceRun`, как schema-evolution runner, но не импортирует slice-specific helpers из schema-evolution script. Все новые constants, SQL builders, expected matrices, `$files` parsing и `EXPLAIN ANALYZE` parsing остаются локальными новому runner.

Предпочтительный diff не меняет:

- `scripts/run_acceptance.py`;
- `scripts/run_schema_evolution_acceptance.py`;
- `compose.yaml`, `infra/`, `docker/`, `dbt/`;
- `docs/spec.md`.

Если реализации всё же потребуется изменить shared component, AC-021 требует повторного acceptance затронутого завершённого slice; такое расширение должно быть явно видно в diff и status evidence.

### 4.2. Runtime namespace и tables

Предлагаемый task-owned namespace:

- schema: `<run_id>_partition_benchmark`;
- object prefix: `warehouse/<run_id>_partition_benchmark/`;
- evidence: `artifacts/acceptance/<run_id>/`.

В schema создаются только восемь tables:

- `balanced_u`, `balanced_d`, `balanced_r`, `balanced_dr`;
- `skewed_u`, `skewed_d`, `skewed_r`, `skewed_dr`.

Дополнительные persistent staging tables/views не создавать, чтобы AC-027 сохранял exact eight-table contract. Rows строятся повторяемым SQL expression для каждого CTAS/INSERT path и затем сверяются full-row reconciliation.

### 4.3. Deterministic generation

Предлагаемый SQL approach:

1. Получить первые подходящие `BENCH-Rnnnn` через `system.bucket(route_id, 4)` и построить mapping 3/3/2/2 с hot routes в buckets 0 и 1.
2. Сохранить exact route mapping до создания данных.
3. Использовать Trino table function `TABLE(sequence(...))`, а не один большой array `UNNEST(sequence(...))`.
4. Balanced генерировать как cross product 50 days × 10 routes × 512 positions.
5. Skewed генерировать четырьмя fixed-size branches или эквивалентным deterministic expression для sizes 8192/512/512/32.
6. `package_id` формировать из dataset/day/route/position так, чтобы uniqueness выводилась независимо.
7. State/timestamps вычислять только из утверждённого 16-row cycle и SLA 48h.

Генератор не читает core Gold и не создаёт raw fixtures.

### 4.4. Layout creation и write protocol

Каждый layout создаётся с явной восьмиколоночной schema:

- `U`: без `partitioning`;
- `D`: `partitioning = ARRAY['day(picked_up_at)']`;
- `R`: `partitioning = ARRAY['bucket(route_id, 4)']`;
- `DR`: `partitioning = ARRAY['day(picked_up_at)', 'bucket(route_id, 4)']`.

`sorted_by`, optimize/compact procedures и maintenance operations запрещены.

Write order должен interleave days/routes, а не группировать по partition predicates. Точный способ — single CTAS, deterministic mixing key или bounded INSERT batches — выбирается только после topology probe. Нельзя менять rows, partition specs, expected matrices или общий объём ради удобной topology.

### 4.5. Evidence architecture

Для каждого из 13 cases × 4 layouts сохранять:

- normalized SQL;
- exact aggregate CSV;
- distributed `EXPLAIN ... FORMAT JSON` raw output;
- raw `EXPLAIN ANALYZE` text;
- parsed scan summary JSON;
- eligible partition tuples;
- eligible file inventory с record counts/sizes;
- comparison с `U` и expected matrix.

Рекомендуемый evidence layout:

```text
artifacts/acceptance/<run_id>/
  preflight/
  generation/
  layouts/<dataset>/<layout>/
  workload/<dataset>/<case>/<layout>/
  runtime/
  cleanup/
  commands.jsonl
  secret_scan.json
  evidence_manifest.json
  acceptance_summary.json
```

`EXPLAIN ANALYZE` parser должен:

- работать только с pinned Trino 484 output;
- требовать ровно один relevant Iceberg scan для single-table aggregate;
- извлекать physical input positions/size из scan fragment;
- сохранять raw text;
- отклонять отсутствующие, неоднозначные или unparsable stats;
- иметь positive и mutation unit tests для units B/kB/MB/GB и лишнего scan node.

Wall-clock/CPU могут сохраняться, но не участвуют в PASS/FAIL.

### 4.6. Metadata и bounds

- `$partitions` является source of truth для tuple count, record count, file count и total size.
- `$files` является source of truth для file path, record count, format, size и lower/upper bounds.
- Trino 484 использует typed `row` для `$files.lower_bounds`/`upper_bounds`, а не старый `map(integer, varchar)`; field access необходимо подтвердить probe.
- Если `$files` не содержит удобной partition identity, допускается supporting use `$entries` или partition path parsing для связи file → tuple, но sizes/counts остаются из `$files`; это не меняет AC.
- Bounds gate должен машинно доказывать, что representative predicate не исключает дополнительные files внутри уже выбранных partition tuples.

### 4.7. Impact-based regression

При предлагаемом isolated diff старые full workflows не повторяются. Проверяются:

- unchanged fingerprints/path diff для core/schema-evolution artifacts;
- отсутствие writes вне benchmark schema/prefix;
- Python compilation/import compatibility существующих runners.

Если меняется shared lifecycle, Compose, infra или completed-slice code, выполнить полный affected acceptance workflow и приложить PASS evidence согласно AC-021.

### 4.8. Минимальные probes будущего этапа

#### PART-PROBE-001 — writer topology и `$files` schema

- **Неизвестность:** single CTAS/INSERT topology на pinned Trino 484 и точный доступ к typed lower/upper bounds.
- **Минимальный эксперимент:** в отдельной schema `<probe_run_id>_partition_benchmark` создать только balanced `U/D/R/DR` полного утверждённого размера, применив один candidate write protocol; сохранить `SHOW CREATE TABLE`, `DESCRIBE <table$files>`, `$partitions`, `$files` и representative bounds checks.
- **Изменяемые ресурсы:** четыре probe tables и объекты только под probe prefix; Compose project без volume deletion.
- **Ожидаемый сигнал:** 256000 rows в каждой table, tuples 50/4/200, все tuples non-empty, file bounds не подменяют partition pruning, typed bounds доступны машинной проверке.
- **Решение:** закрепить минимальный write protocol; при провале изменить только batching/interleaving и повторить с новым run ID. Если contract недостижим на pinned stack в согласованных ресурсах — остановиться, не ослаблять AC.
- **Cleanup:** exact `DROP SCHEMA ... CASCADE`, empty probe object prefix, `docker compose down` без `-v`, preserve pre-existing volumes.

#### PART-PROBE-002 — plan/stats capture

- **Неизвестность:** стабильные anchors physical input и partition constraints для machine evidence.
- **Минимальный эксперимент:** на probe tables выполнить один date, один route и один combined case; сохранить `EXPLAIN (TYPE DISTRIBUTED, FORMAT JSON)` и `EXPLAIN ANALYZE` text.
- **Ожидаемый сигнал:** один Iceberg scan, видимый constraint, parseable physical input и ожидаемое relative reduction.
- **Решение:** закрепить parser/summary schema. Если text неоднозначен, исследовать pinned Trino query-stat JSON как отдельный bounded fallback; нельзя заменять runtime evidence одним estimated plan.
- **Cleanup:** тот же probe ownership contract.

### 4.9. Документированные основания

Проверено 2026-10-30 через Context7 по официальному source `/trinodb/trino/484`:

- `connector/iceberg.md`: table property `partitioning`, transforms `day`/`bucket`, `system.bucket`, metadata tables `$partitions`/`$files`;
- release notes 482/484: `$files.lower_bounds` и `upper_bounds` представлены typed `row`, а не legacy map; старый access pattern нельзя предполагать;
- `sql/explain.md`: `EXPLAIN` поддерживает `TYPE DISTRIBUTED` и `FORMAT JSON`; JSON schema не обещана backward-compatible, поэтому parser привязан к pinned 484;
- `sql/explain-analyze.md`: runtime plan содержит scan input/physical-input statistics; документация предупреждает, что timing fast queries может быть неточным;
- `functions/table.md` и `functions/array.md`: table function/integer `sequence` доступны для deterministic generation.

Документация не подтверждает JSON format для `EXPLAIN ANALYZE`; поэтому план сохраняет raw text, требует bounded parser и отдельный runtime probe. Это ограничение нельзя обходить использованием только estimated `EXPLAIN`.

## 5. План будущих изменений

### 5.1. Работа агента

#### PF-AGENT-001 — сохранить текущие инструкции и ресурсы

- **Сохранить:** `docs/spec.md` как source of truth, `docs/status.md` как единый task history, текущие Pi packages/settings.
- **Не добавлять:** AGENTS.md, project Pi config, skill, extension, MCP, отдельный handoff/status.
- **Зачем:** новых полномочий или повторяемой capability gap нет.
- **Зависимость:** нет.
- **Проверка:** diff не содержит `.pi/`, `.pi-lens.json`, AGENTS.md или новых agent resources.
- **Откат:** не требуется; изменение отсутствует.

### 5.2. Среда и проверки

#### PF-ENV-001 — isolated acceptance entry point

- **Добавить:** `scripts/run_partitioning_file_pruning_acceptance.py` с `--run-id`, optional `--evidence-root`, ownership gate, lifecycle, evidence, cleanup и atomic summary.
- **Зачем:** 8 imperative table layouts и 52 query-layout comparisons не являются dbt DAG.
- **Зависимость:** `AcceptanceRun`, pinned Compose stack, локальный `.env` или equivalent shell vars.
- **Проверка:** `py_compile`, `--help`, invalid run ID, missing env, existing evidence-dir/schema collision, injected failure после ownership очищает только собственную schema.
- **Откат:** удалить новый runner; core/schema runners не меняются.

#### PF-ENV-002 — pure helper/parser tests

- **Добавить:** `scripts/tests/test_partitioning_file_pruning_acceptance.py` на stdlib `unittest`.
- **Покрыть:** route selection, group sizes, expected aggregates, eligible matrices, byte-unit parser, plan scan cardinality, bounds decisions, manifest completeness и mutation cases.
- **Зачем:** parser/comparator error может дать ложный PASS.
- **Зависимость:** pure helpers нового runner.
- **Проверка:** positive cases и обязательные mutations обнаруживают неверный bucket, count, bytes, лишний scan, missing case и false cleanup.
- **Откат:** удалить test file; runtime data не затрагиваются.

#### PF-ENV-003 — пользовательская команда и evidence contract

- **Изменить:** `README.md` кратким разделом partition benchmark; при реализации вести checkpoints в `docs/status.md`.
- **Зачем:** воспроизводимая команда, evidence path и безопасный cleanup должны быть видимы без чтения runner source.
- **Зависимость:** стабильный CLI PF-ENV-001.
- **Проверка:** README command совпадает с CLI; не предлагает `down -v`, compaction или expiration.
- **Откат:** удалить только новый README section/status entries.

### 5.3. Реализация результата

#### PF-IMP-001 — route mapping и deterministic generators

- **Область:** bucket-aware route selection, balanced/skewed SQL builders, typed row formulas.
- **Вход:** `docs/spec.md` §11.2–11.4.
- **Зависимость:** PF-ENV-001/002.
- **Наблюдаемый выход:** exact 3/3/2/2 bucket mapping, hot routes in separate buckets, independently computed expected counts.
- **AC:** AC-022.
- **Откат:** drop task-owned schema.

#### PF-IMP-002 — eight layouts, reconciliation и topology gate

- **Область:** create/write `U/D/R/DR` для balanced/skewed, partition metadata, full-row parity, bounds checks.
- **Зависимость:** PF-IMP-001, PART-PROBE-001.
- **Наблюдаемый выход:** exact eight tables, 256000 rows each, tuples 50/4/200, no hidden clustering confound.
- **AC:** AC-023, AC-026.
- **Откат:** drop task-owned schema; не выполнять optimize/expiration.

#### PF-IMP-003 — balanced workload

- **Область:** 4 cases × 4 layouts, exact results, eligible metadata и runtime stats.
- **Зависимость:** PF-IMP-002, PART-PROBE-002.
- **Наблюдаемый выход:** matrix из §11.5 и relative physical-input reductions.
- **AC:** AC-024.
- **Откат:** только task-owned evidence/schema.

#### PF-IMP-004 — skewed workload

- **Область:** 9 cases × 4 layouts, hot/cold/peak/off-peak comparisons.
- **Зависимость:** PF-IMP-002/003.
- **Наблюдаемый выход:** exact aggregates и eligible counts 20480/1280, 115200/12800, 9216/576/1024/64.
- **AC:** AC-025.
- **Откат:** только task-owned evidence/schema.

#### PF-IMP-005 — causal evidence matrix

- **Область:** completeness gate для 13 × 4 cases, plan/parser summaries, full-scan negative control.
- **Зависимость:** PF-IMP-003/004.
- **Наблюдаемый выход:** каждый PASS имеет raw SQL/result/plan/analyze/metadata; missing or ambiguous stats fail closed.
- **AC:** AC-026.
- **Откат:** удалить generated evidence directory только отдельной path-scoped командой пользователя; runner автоматически evidence не удаляет.

#### PF-IMP-006 — catalog/object evidence, cleanup и finalization

- **Область:** exact eight-table listing, Polaris/RustFS evidence, schema/object cleanup, environment restoration, secret scan, manifest, summary.
- **Зависимость:** PF-IMP-001–005.
- **Наблюдаемый выход:** AC-021–AC-027 PASS только после cleanup/restoration; zero task schemas/objects/containers; pre-existing volumes preserved.
- **AC:** AC-021, AC-027.
- **Откат:** exact schema drop и Compose down без volume deletion.

## 6. AC → будущая проверка → evidence

Все команды ниже — будущий интерфейс; в текущем plan-only запуске они не выполнялись.

| AC | Проверка / будущая команда | Ожидаемый результат | Evidence |
| --- | --- | --- | --- |
| AC-021 | path fingerprints, namespace preflight, conditional completed-slice regression | completed artifacts unchanged; writes only in benchmark prefix | `preflight/`, diff/fingerprint JSON, optional prior-run summary |
| AC-022 | runner generation assertions | 2 × 256000 rows, exact schema/distribution/state formulas | `generation/route_mapping.csv`, grouped counts, schema/results JSON |
| AC-023 | `SHOW CREATE`, `$partitions`, `$files`, bidirectional reconciliation | 8 exact tables; specs U/D/R/DR; tuples 50/4/200; identical rows | `layouts/*` |
| AC-024 | 4 balanced cases × 4 layouts | exact aggregates/matrix and lower physical input for matching layouts | `workload/balanced/*` |
| AC-025 | 9 skewed cases × 4 layouts | exact hot/cold/peak/off-peak outputs and eligible counts | `workload/skewed/*` |
| AC-026 | topology/bounds gate, EXPLAIN JSON, EXPLAIN ANALYZE parser, 52-case completeness | no file-stats confound; every case has parseable causal evidence; full scan unpruned | plan/analyze raw files, summaries, completeness JSON |
| AC-027 | catalog/object capture, exact cleanup and finalization | 8 tables/objects before cleanup; zero owned resources after; manifest/secret scan clean | `runtime/`, `cleanup/`, manifest, summary |

### Быстрые проверки до runtime

1. `python3 -m py_compile scripts/run_acceptance.py scripts/run_schema_evolution_acceptance.py scripts/run_partitioning_file_pruning_acceptance.py`.
2. `python3 -m unittest scripts.tests.test_partitioning_file_pruning_acceptance` или эквивалентный стабильный stdlib invocation.
3. CLI `--help`, invalid run ID, missing env, existing evidence-dir refusal.
4. Mutation tests pure helpers: bucket mapping, expected rows, bytes, scan count, bounds и missing evidence.
5. `git diff --check` и allowed-path assertion.
6. Static assertion: нет `sorted_by`, optimize/compact/expire/orphan operations и изменений completed-slice paths.
7. LSP diagnostics для новых Python/Markdown paths.

### Итоговая acceptance-последовательность

1. Проверить allowed diff и immutable fingerprints.
2. Выполнить pure/static checks.
3. Получить отдельное разрешение на Docker/services/ports и task-owned writes.
4. Выполнить PART-PROBE-001/002 в fresh probe run ID; закрепить write protocol/parser без изменения AC.
5. Запустить full workflow с новым run ID, например:

   ```bash
   python3 scripts/run_partitioning_file_pruning_acceptance.py \
     --run-id partition_benchmark_01
   ```

6. Runner выполняет preflight, route mapping, generation, layout reconciliation, topology/bounds gate, balanced и skewed workload.
7. Собрать catalog/object evidence.
8. Удалить exact task schema, подтвердить header-only remaining-schema result и empty object prefix.
9. Восстановить исходное состояние Compose без `-v`.
10. Выполнить secret scan и manifest gate; только затем записать AC-027 и общий PASS.
11. Полный core/schema acceptance повторять только если diff затронул shared/completed paths.

Healthy services, exit 0 отдельного SQL, наличие plan text или пустой test set не являются evidence AC.

## 7. Права, cleanup, блокеры и следующий шаг

### Будущие действия, требующие отдельного разрешения

- добавление runner/tests и изменение README/status;
- запуск Docker Compose и занятие портов 8080/8181/9000/9001;
- возможный image pull, если pinned images отсутствуют в cache;
- создание probe и full benchmark schemas/tables/objects;
- выполнение CTAS/INSERT, metadata queries, `EXPLAIN` и `EXPLAIN ANALYZE`;
- cleanup только task-owned schemas/objects и остановка Compose project;
- affected-slice regression, только если изменены shared paths.

Не разрешаются по умолчанию:

- `docker compose down -v`;
- удаление project bucket/catalog/чужих schemas или volumes;
- compaction, optimize, snapshot expiration и orphan cleanup;
- Git commit/push/reset/clean;
- изменение Pi trust/model/settings;
- установка/обновление packages или images вне pinned stack.

### Safe cleanup contract

- Evidence directory и benchmark schema collision проверяются до ownership.
- Ownership выставляется только после query readiness и exact absence schema.
- Failure cleanup разрешён только для exact `<run_id>_partition_benchmark` schema и matching object prefix.
- Wildcard DROP, bucket deletion и volume deletion запрещены.
- После DROP выполняется exact query отсутствия schema и empty-prefix listing.
- Pre-existing volumes должны быть subset final volumes.
- Evidence directory автоматически не удаляется.

### Блокеры и пределы проверки

Блокеров для review плана нет. Не проверены фактическим запуском:

- writer topology и bounds на Trino 484;
- `$files` typed-row access и file-to-partition mapping;
- machine parser фактического `EXPLAIN ANALYZE` output;
- runtime physical-input relationships;
- время, storage footprint и наличие image cache.

Эти неизвестности закрываются PART-PROBE-001/002 и не разрешают ослаблять AC-021–AC-027.

### Минимальное предложение

Не менять stack, dbt, Compose, dependencies или agent configuration. Добавить один isolated Python acceptance runner, один stdlib pure-test module и короткую README-команду; переиспользовать существующий lifecycle/evidence harness. Перед full run выполнить два bounded probes на task-owned schema, затем доказать весь slice одним reproducible workflow.

### Следующий ограниченный шаг

План `BOOTSTRAP-PLAN-PARTITIONING-FILE-PRUNING-001` одобрен пользователем. Bootstrap останавливается: PART-PROBE-001/002 и реализация должны быть запрошены и разрешены отдельно; текущее одобрение плана не предоставляет полномочий на Docker, runtime writes, cleanup, Git commit или push.
