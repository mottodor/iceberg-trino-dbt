# План реализации: Schema evolution

**ID плана:** `BOOTSTRAP-PLAN-SCHEMA-EVOLUTION-001`
**Версия skill:** Bootstrap `0.1.0`
**Статус плана:** `READY_FOR_REVIEW`
**Режим:** только планирование; DDL, сервисы, тесты и probes в этом запуске не выполнялись
**Дата инвентаризации:** 2026-10-29

## 1. Вход, согласованный scope и fingerprints

### Входные файлы

- Утверждённая спецификация: [`docs/spec.md`](./spec.md), раздел 8, DEC-028–DEC-033 и AC-013–AC-020.
- Исходный brief: [`docs/idea.md`](./idea.md).
- Принятый план и evidence core vertical slice: [`docs/bootstrap.md`](./bootstrap.md), [`docs/status.md`](./status.md), [`artifacts/acceptance/imp007_final5/acceptance_summary.json`](../artifacts/acceptance/imp007_final5/acceptance_summary.json).
- Текущий пользовательский запрос: реализовывать только утверждённый срез **Schema evolution**, переиспользуя принятую core-инфраструктуру.
- Целевой файл плана: `docs/bootstrap-schema-evolution.md`; до записи отсутствовал и не являлся symlink.

### Fingerprints

| Источник | Fingerprint |
|---|---|
| Git commit | `e40dc8121e621e568df95761c0922229e1bde18c` |
| Git status до записи | чистая ветка `main`, 64 tracked files, 0 изменений |
| `docs/spec.md` | SHA-256 `105aea0cd3b88042282b870dcb62c83f83b0a3255bf5e7fae32680919cbb8641` |
| `docs/idea.md` | SHA-256 `7755620909b9cd65d1a6e8fa9c8fc805344f7f95a0fac2f123f08f7b78a8bccf` |
| `docs/bootstrap.md` | SHA-256 `15ff75ef6db6bacee86d36009a04069c9abce848187921d225012f8174a4b162` |
| `docs/status.md` | SHA-256 `7a24714765133ec6305b0e2176b67f2f02bb110134f3bb6a059671606317fa21` |
| `compose.yaml` | SHA-256 `55c832a2297d8f13fbd1635c0bba6ce0912b785b31f943cb851a9e92f46f0bdd` |
| `scripts/run_acceptance.py` | SHA-256 `39c87bec954d6a820352968839019e31f8278a2212eea471b653fd4880bd068c` |
| `gold_package_delivery_fact.sql` | SHA-256 `9a449179e54d1e8744f688da0e31edfb88dd449c98206ee5487934d33aeba704` |
| core Gold contract test | SHA-256 `477993d728d241acdcb5bff1073744ec1acc0534becf052ec82910569617ca21` |
| Bootstrap skill | SHA-256 `1af89767288212b543a0c2eb0d0a44fd5d7f86035a18624eb3c6c9c1afc5e1fd` |

### Выбранный scope

В реализацию входят только:

- отдельная task-owned Iceberg-таблица `<run_prefix>_evolution.schema_evolution_package_delivery`;
- создание состояния S0 из принятого `gold_package_delivery_fact`;
- последовательные rename, widening и add-column операции из DEC-030;
- доказательство metadata-only evolution, reader/writer compatibility и snapshot chain S0 → S1;
- отрицательные операции со старым именем и narrowing-типа;
- core regression до и после упражнения;
- автоматизированный evidence workflow и безопасный cleanup для AC-013–AC-020.

### Исключения

Не изменять и не расширять:

- CSV fixtures, fixture loader, Bronze/Silver/Gold-модели и их schema contracts;
- core tests и ожидаемые результаты AC-003–AC-012;
- `delivery_priority` в core analytics;
- partition spec, полноценный time-travel slice, branches/tags/rollback;
- snapshot expiration, orphan cleanup, compaction и small-files remediation;
- Compose stack, pinned versions, dependency locks и CI без отдельной необходимости.

## 2. Наблюдаемое состояние репозитория, среды и Pi

### Репозиторий и принятый core slice

Наблюдалось локально:

- core vertical slice реализован и закоммичен; `README.md` описывает рабочий путь, а `docs/status.md` фиксирует завершение PROBE-001–003, BOOT-ENV-001–003 и IMP-001–007;
- historical acceptance run `imp007_final5` имеет `outcome=PASS` для AC-001 и AC-003–AC-012; это evidence прошлого запуска, а не повторная проверка в текущем plan-only режиме;
- `scripts/run_acceptance.py` уже реализует безопасные preflight/ownership gates, Compose lifecycle, fixture/dbt execution, SQL CSV evidence, Polaris/RustFS listing, secret scan, atomic summary, manifest и cleanup;
- принятый Gold source содержит необходимые поля: `package_id`, `route_version_id`, `current_status`, `completed_visit_count`, `delivery_duration_hours`, `is_on_time`;
- artifacts path `artifacts/acceptance/` уже исключён из Git;
- `AGENTS.md`, project-level Pi config и CI отсутствуют; для этого среза они не требуются.

Текущий diff до создания плана был пуст. Имеющиеся пользовательские изменения не исправлялись и не откатывались.

### Закреплённая среда

| Компонент | Наблюдалось локально / в репозитории |
|---|---|
| ОС | Linux WSL2 `x86_64` |
| Python host | `3.12.3` |
| Git | `2.43.0` |
| Docker | client `29.8.0` |
| Docker Compose | `v5.5.1` |
| Pi | `1.4.0` |
| RustFS | pinned `1.0.4` + digest в `compose.yaml` |
| Apache Polaris | pinned `1.8.0` + digest |
| Trino | pinned `484` + digest |
| dbt Core / dbt-trino | `1.11.11` / `1.10.2`, hash-locked container image |
| host dbt / Trino CLI / Java | отсутствуют; проект использует контейнеры |

Версии и наличие CLI не доказывают текущую готовность daemon, свободные порты или прохождение нового schema-evolution сценария. В этом режиме Docker services не запускались.

### Pi и загруженные ресурсы

Наблюдалось локально:

- настроены `@upstash/context7-pi 0.1.3`, `pi-lens 4.4.4`, `pi-lmstudio 1.5.0`, `pi-subagents 0.81.0`;
- Context7 и pi-lens tools доступны в текущей сессии; subagents не запускались;
- project/global pi-lens config отсутствует, поэтому действуют defaults: read guard, deferred formatting и deterministic autofix включены; actionable-warning autofix выключен;
- для Markdown выбраны marksman/typos и Markdown runners. После записи этого плана файл требуется перечитать и проверить diff, поскольку extension hooks могут менять записанный файл;
- credentials, `.env`, auth stores и session transcripts не читались.

## 3. Выбор возможностей

| Потребность | Существующая возможность | Решение | Основание / ограничение |
|---|---|---|---|
| Поднять lakehouse stack | Текущий `compose.yaml` и bootstrap assets | Использовать без изменений | Core acceptance уже доказал связку RustFS–Polaris–Trino–dbt |
| Создать core baseline | Существующие fixtures, loader и `dbt build` | Использовать | Новые fixtures и модели запрещены DEC-028/029 |
| Оркестрировать exercise | Python stdlib + паттерны `scripts/run_acceptance.py` | Добавить отдельный runner | Не смешивать imperative DDL exercise с dbt DAG и не менять default core workflow |
| Общие lifecycle/evidence helpers | `AcceptanceRun` и pure helpers в текущем runner | Переиспользовать через import/composition | Не копировать auth, secret scan, manifest и cleanup; core CLI должен сохранить текущее поведение |
| Проверить schema/snapshots/files | Trino `DESCRIBE`, `information_schema`, `$snapshots`, `$files`, `$metadata_log_entries` | Использовать | Поддерживается Trino 484 |
| Проверить field IDs/schema IDs | Iceberg metadata JSON в RustFS | Использовать | Trino SQL не показывает все field IDs; JSON — source of truth |
| Проверить неизменность Parquet | `$files`, object listing и streamed SHA-256 | Добавить небольшой helper в runner | Сравнивать path, size и digest; не сохранять содержимое Parquet в evidence |
| Проверить pure invariant logic | Python stdlib `unittest` | Добавить небольшие unit tests | Новая зависимость/pytest не нужны |
| Документация пользователя | Существующий `README.md` | Кратко дополнить | Только команда slice, evidence и cleanup; спецификацию не дублировать |
| Новые Pi skills/extensions/MCP | Текущий набор достаточен | Не добавлять | Нет незакрытой возможности |
| CI | Отсутствует | Не добавлять сейчас | Сначала доказать локальный acceptance на принятом pinned stack |

**Итог:** новые пакеты, сервисы, images, model provider, Pi config, AGENTS.md и CI не требуются.

## 4. Техническое предложение, источники и probes

### 4.1. Архитектура реализации

Предлагается один новый entry point:

- `scripts/run_schema_evolution_acceptance.py` — отдельный isolated workflow для AC-013–AC-020;
- `scripts/tests/test_schema_evolution_acceptance.py` — pure stdlib tests для разбора metadata JSON, snapshot chain и invariant comparisons;
- краткое дополнение `README.md`; во время реализации использовать существующий `docs/status.md`, не создавать новый журнал.

Runner должен переиспользовать безопасные primitives из `scripts/run_acceptance.py` через import/composition. Default-команда core runner, его summary schema и AC-001/003–012 workflow не меняются. Если потребуется минимально открыть один helper, изменение допускается только с доказательством, что прежний core runner сохраняет CLI и результаты; крупный refactor общего harness в этот срез не включать.

Предлагаемый runtime prefix layout:

- core schemas: `<run_id>_baseline_{fixtures,bronze,silver,gold}`;
- evolution schema: `<run_id>_evolution`;
- evolution table: `schema_evolution_package_delivery`;
- object prefix: `warehouse/<run_id>_`;
- evidence: `artifacts/acceptance/<run_id>/`.

### 4.2. Core regression boundary

До DDL:

1. загрузить обе baseline-партии существующим loader;
2. выполнить полный `dbt build --select tag:bronze tag:silver tag:gold`;
3. потребовать успешные core results и baseline DQ tests;
4. сохранить sorted `information_schema.columns` для всех task-owned core schemas;
5. сохранить детерминированные core outputs: layer counts, package facts, route binding, route/hub aggregates и отсутствие `EVO-P5`.

После evolution exercise:

1. повторить полный core `dbt build` в тех же core schemas;
2. повторить те же запросы и сравнить schemas/results с pre-evolution evidence;
3. подтвердить, что evolution table не является dbt dependency и `EVO-P5` отсутствует в core Gold.

Сравнение относится к schema/data contracts. Физические core data files и snapshot IDs не сравниваются: повторная table-materialization dbt вправе переписать task-owned core tables без изменения утверждённого результата.

### 4.3. S0 и invariant bundle

S0 создаётся CTAS с явной проекцией и явным `CAST(completed_visit_count AS INTEGER)`. После создания фиксируется единый invariant bundle:

- `DESCRIBE` и `information_schema.columns`;
- exact sorted rows P1–P4;
- `$snapshots` и символическое сопоставление фактического snapshot ID → `S0`;
- `$files`: path, format, record count и size;
- RustFS object listing;
- SHA-256 каждого текущего Parquet data file, вычисленный потоково по точному object key без записи data contents в evidence;
- `$metadata_log_entries`;
- копия/хеш актуального metadata JSON, `current-schema-id`, `current-snapshot-id`, `last-column-id` и field IDs.

После каждого DDL bundle повторяется. До INSERT `EVO-P5` должны быть неизменны S0 snapshot и Parquet identity set `(path, size, sha256)`. Новые metadata JSON/Avro objects допустимы.

### 4.4. Последовательность операций

1. Создать S0 и проверить AC-014.
2. `RENAME COLUMN delivery_status TO current_status`; проверить field ID, schema ID, S0 и data files.
3. Widen `completed_visit_count INTEGER → BIGINT`; повторить invariants.
4. Добавить nullable `delivery_priority VARCHAR AFTER route_version_id`; повторить invariants и порядок колонок.
5. Прочитать P1–P4 текущей схемой; новая колонка должна быть `NULL`.
6. Выполнить INSERT со старым именем; требовать non-zero и полную неизменность bundle.
7. Выполнить корректный INSERT `EVO-P5`; получить `S1`, проверить `parent_id=S0` и ровно пять строк.
8. Выполнить одинаковую явную проекцию для S0, S1 и current; сравнить exact results.
9. Выполнить narrowing `BIGINT → INTEGER`; требовать non-zero и неизменность S1/schema/rows/files.
10. Повторить core regression, собрать evidence и очистить task-owned schemas.

### 4.5. Расхождение внутри утверждённой спецификации

Наблюдается одно внутреннее расхождение порядка:

- раздел 8.5 ставит narrowing до корректного INSERT и S1;
- AC-019 явно задаёт precondition `current snapshot = S1`, то есть narrowing после корректного INSERT.

**Предложение плана:** использовать порядок AC-017 → AC-018 → AC-019: old-name failure → корректный INSERT/S1 → historical reads → narrowing на S1. Это удовлетворяет явным preconditions критериев и DEC-033, не меняя ожидаемый результат отрицательной операции. Если требуется буквально сохранить шаг 7 раздела 8.5, безопасный запасной вариант — выполнить narrowing дважды (до и после S1), но final AC-019 evidence всё равно получать после S1. Молчаливо выбирать иной порядок при реализации нельзя.

### 4.6. Документированные основания

Проверено 2026-10-29 по первоисточникам через Context7:

- Trino 484, `/trinodb/trino/484`: Iceberg connector поддерживает rename/add и widening `INTEGER→BIGINT`; `ADD COLUMN ... AFTER ...`; historical query `FOR VERSION AS OF <snapshot_id>`; metadata tables `$snapshots`, `$files`, `$metadata_log_entries`.
- Apache Iceberg 1.10.1, `/apache/iceberg/apache-iceberg-1.10.1`: schema evolution является metadata-only; projection идёт по field ID; отсутствующее в старом data file новое поле возвращает `NULL`; новая схема получает отдельный schema ID и становится current schema.

Это подтверждает предлагаемый следующий шаг, но не доказывает OPEN-021 на текущей связке Trino 484 + Polaris 1.8.0 + RustFS 1.0.4.

### 4.7. Минимальные probes — только будущий запуск

#### SE-PROBE-001 — current-schema projection для старого snapshot

- **Неизвестность:** Trino 484 должен выполнить явную проекцию текущих имён/типов через `FOR VERSION AS OF S0` после rename/widen/add; именно эта комбинация локально не выполнялась.
- **Минимальный эксперимент:** в отдельной task-owned smoke schema создать малую Iceberg table, зафиксировать S0, выполнить три одобренных DDL и прочитать S0 явной текущей проекцией.
- **Ожидаемый сигнал:** renamed value сохранён, widened type читается как BIGINT, новая nullable column равна `NULL`, snapshot ID не меняется.
- **Стоп:** query resolution error, новый data snapshot, новый Parquet file или позиционное смещение значений.
- **Изменяемые ресурсы:** одна smoke schema/table и её RustFS prefix.
- **Очистка:** `DROP SCHEMA ... CASCADE`, проверка пустого task prefix, `docker compose down` без `-v`.
- **Решение:** при успехе продолжить full runner; при несовпадении остановить реализацию и вернуть OPEN-021/AC-018 в DRAFT, не обходить критерий другой проекцией.

#### SE-PROBE-002 — metadata JSON и checksum path

- **Неизвестность:** точное сопоставление `$metadata_log_entries.file` и RustFS object key, а также потоковое чтение Parquet для SHA-256 ещё не проверялось новым runner.
- **Минимальный эксперимент:** на smoke table получить metadata/data paths из Trino, прочитать только metadata JSON в evidence и вычислить SHA-256 data file без сохранения его содержимого.
- **Ожидаемый сигнал:** один и тот же data object сопоставляется по path/size; digest стабилен до/после schema-only DDL; metadata JSON содержит ожидаемые schema IDs/field IDs.
- **Стоп:** path выходит за project bucket/prefix, размер не совпадает или helper пытается писать data file вне evidence temp area.
- **Очистка:** удалить только smoke schema/objects; временный data-file buffer не сохранять.

## 5. План будущих изменений

### 5.1. Работа агента

#### SE-AGENT-001 — сохранить текущие инструкции и ресурсы

- **Сохранить:** `docs/spec.md` как source of truth, `docs/status.md` как существующий task history, текущие Pi packages/settings.
- **Не добавлять:** AGENTS.md, новый handoff/status, skill, extension, MCP, project Pi config.
- **Зачем:** новых полномочий или возможностей для этого среза не требуется.
- **Зависимость:** нет.
- **Критерий:** future diff не содержит `.pi/settings.json`, `.pi-lens.json`, новых agent resources или дублирующих state files.
- **Откат:** не требуется, изменение отсутствует.

### 5.2. Среда и проверки

#### SE-ENV-001 — schema-evolution acceptance entry point

- **Добавить:** `scripts/run_schema_evolution_acceptance.py` с unique run ID, preflight, ownership gate, Compose lifecycle, evidence, secret scan, manifest и atomic summary.
- **Зачем:** AC-013–AC-020 требуют последовательных imperative DDL и межшаговых invariants, что не является dbt DAG.
- **Зависимость:** существующий `scripts/run_acceptance.py`, Compose stack и локальные training credentials.
- **Проверка:** `py_compile`, `--help`, invalid-run-id/missing-env paths, collision refusal без cleanup чужой schema; injected failure после ownership вызывает cleanup только своего prefix.
- **Откат:** удалить новый runner; core runner и stack остаются без изменений.

#### SE-ENV-002 — pure helper tests

- **Добавить:** stdlib unit tests для metadata field-ID parsing, snapshot chain, file identity comparison, exact result comparisons и expected-failure invariants.
- **Зачем:** ошибка parser/comparator может дать ложный PASS без реального изменения Iceberg behavior.
- **Зависимость:** SE-ENV-001.
- **Проверка:** mutation cases должны обнаруживать смену field ID, snapshot, path/size/hash, лишнюю/пропавшую строку и ложный success негативной команды.
- **Откат:** удалить только test file; runtime artifacts не затрагиваются.

#### SE-ENV-003 — пользовательская команда и evidence contract

- **Изменить:** кратко дополнить `README.md` командой schema-evolution acceptance, требованием нового run ID, расположением evidence и safe cleanup semantics.
- **Зачем:** упражнение должно быть воспроизводимо без чтения implementation code.
- **Зависимость:** стабильный CLI SE-ENV-001.
- **Проверка:** команда совпадает с runner; destructive `down -v`, expiration и compaction не предлагаются как default.
- **Откат:** удалить только новый README section.

### 5.3. Реализация результата

#### SE-IMP-001 — pre/post core regression capture

- **Область:** orchestration существующего loader/dbt и сравнение core contracts.
- **Вход:** принятые core fixtures/models/tests без изменений.
- **Зависимость:** SE-ENV-001.
- **Наблюдаемый выход:** два успешных core builds, одинаковые schemas/expected outputs, отсутствие `EVO-P5` в core.
- **AC:** AC-013, AC-020.
- **Откат:** удалить task-owned baseline schemas.

#### SE-IMP-002 — S0 creation и evidence

- **Область:** evolution schema, CTAS explicit projection/cast, initial snapshot/files/metadata capture.
- **Вход:** `gold_package_delivery_fact` после полного baseline build.
- **Зависимость:** SE-IMP-001.
- **Наблюдаемый выход:** четыре exact rows, initial six-column schema, один data snapshot S0, non-empty Parquet set и parsed metadata JSON.
- **AC:** AC-014.
- **Откат:** удалить только `<run_id>_evolution` schema.

#### SE-IMP-003 — metadata-only DDL checkpoints

- **Область:** rename, widening, add-after; invariant bundle после каждого шага.
- **Вход:** S0.
- **Зависимость:** SE-IMP-002, успешные SE-PROBE-001/002.
- **Наблюдаемый выход:** seven-column schema; preserved field IDs для rename/widen; новый field ID для priority; изменённый schema ID; S0 и data-file identity неизменны.
- **AC:** AC-015.
- **Откат:** table не откатывать обратными DDL; при провале удалить целиком task-owned evolution schema и перезапустить с новым run ID.

#### SE-IMP-004 — reader/writer compatibility и S1

- **Область:** current-schema read P1–P4, old-name expected failure, корректный `EVO-P5` insert.
- **Вход:** evolved schema при current snapshot S0.
- **Зависимость:** SE-IMP-003.
- **Наблюдаемый выход:** старые строки читаются корректно с priority `NULL`; old-name insert атомарно отклонён; корректный insert создаёт S1 с `parent_id=S0` и ровно пять строк.
- **AC:** AC-016, AC-017.
- **Откат:** удалить task-owned evolution schema; не выполнять row-level delete как cleanup.

#### SE-IMP-005 — S0/S1 historical compatibility и narrowing

- **Область:** exact S0/S1/current result comparison; rejected BIGINT→INTEGER с before/after bundle.
- **Вход:** S0 и S1 IDs, полученные из `$snapshots`.
- **Зависимость:** SE-IMP-004 и одобренное разрешение расхождения порядка из §4.5.
- **Наблюдаемый выход:** S0=4 rows, S1=current=5 rows; narrowing non-zero; schema BIGINT, S1, rows и file identity неизменны.
- **AC:** AC-018, AC-019.
- **Откат:** удалить task-owned evolution schema.

#### SE-IMP-006 — end-to-end evidence и cleanup

- **Область:** Polaris/catalog/table evidence, object listing, metadata copies, commands log, secret scan, manifest, summary и environment restoration.
- **Вход:** все предыдущие checks.
- **Зависимость:** SE-IMP-001–005.
- **Наблюдаемый выход:** AC-013–AC-020 PASS только после cleanup/secret/manifest gates; zero task schemas/objects/containers; pre-existing volumes preserved.
- **AC:** AC-020.
- **Откат:** runtime cleanup удаляет только owned schemas; generated evidence остаётся для review и удаляется только отдельной path-scoped командой пользователя.

## 6. AC → будущая проверка → evidence

Все команды ниже — будущий интерфейс; в текущем plan-only запуске они не выполнялись.

| AC | Проверка / команда | Ожидаемый результат | Evidence |
|---|---|---|---|
| AC-013 | schema-evolution runner: core build и contract capture до/после | Core schemas/results одинаковы; core tests проходят; `EVO-P5` отсутствует | `core/pre`, `core/post`, schema/result diffs, dbt `run_results.json` |
| AC-014 | CTAS S0; `DESCRIBE`; exact row query; `$snapshots` | 4 rows, 6 columns, ровно один snapshot S0 | `evolution/s0/*.csv`, `$files`, metadata JSON copy/hash |
| AC-015 | три DDL по одному + invariant bundle | 7-column schema; S0/file digests неизменны; field IDs корректны; schema ID изменён | `evolution/ddl/01..03/`, metadata comparisons, object deltas |
| AC-016 | явная current-schema projection до нового INSERT | P1–P4, сохранённые status/counts, BIGINT, priority `NULL` | `evolution/read_compat/current_schema_s0.csv` |
| AC-017 | old-name INSERT с allowed non-zero, затем корректный INSERT | ошибка не меняет S0; корректный insert создаёт S1 и `EVO-P5` | stderr/exit record, before/after bundles, snapshot chain CSV |
| AC-018 | одинаковый SELECT `FOR VERSION AS OF S0`, S1 и current | S0=4; S1=current=5; явные колонки; priority semantics соблюдены | три sorted CSV и machine comparison JSON |
| AC-019 | narrowing после S1 с allowed non-zero | type остаётся BIGINT; S1/rows/files неизменны | failure log, before/after schema/snapshot/file bundle |
| AC-020 | полный workflow с catalog/object capture и cleanup | AC-013–019 PASS; одна evolution table до cleanup; zero owned resources после | `acceptance_summary.json`, `commands.jsonl`, Polaris/object evidence, manifest, cleanup JSON, secret scan |

### Быстрые проверки до runtime

1. `python3 -m py_compile` для core и нового runner.
2. stdlib unit tests pure helpers.
3. CLI `--help`, invalid run ID, missing env и existing evidence-dir refusal.
4. Static review: core fixtures/models/tests, Compose, infra и dependency locks не изменены.
5. `docker compose --profile tools config --quiet` — только после отдельного разрешения на применение, без запуска services.

### Итоговая acceptance-последовательность

1. Проверить clean/differentiable working tree и разрешённый diff.
2. Выполнить static/pure checks.
3. Получить отдельное разрешение на Docker/services/ports и task-owned writes.
4. Выполнить SE-PROBE-001/002 в smoke prefix; при несоответствии остановиться.
5. Запустить новый full runner с уникальным run ID.
6. Runner выполняет pre-core regression, S0, DDL checkpoints, negative writer check, S1, historical reads, narrowing, post-core regression.
7. Сохранить Polaris/RustFS/metadata evidence.
8. Удалить evolution schema, затем core schemas в обратном порядке слоёв.
9. Подтвердить пустой `warehouse/<run_id>_` prefix, отсутствие Compose containers и сохранность pre-existing volumes.
10. Выполнить secret scan, manifest и только затем записать atomic PASS summary.
11. Для независимой итоговой регрессии перед merge повторно запустить существующий core runner с отдельным run ID; его default behavior не должен зависеть от schema-evolution runner.

Пустой test set, один `exit 0`, healthy services или текстовый отчёт не являются evidence AC. Для негативных операций успех проверки требует одновременно non-zero команды и неизменность всех заявленных invariants.

## 7. Права, cleanup, блокеры и следующий шаг

### Будущие действия, требующие отдельного разрешения

- создание/изменение implementation/test/README/status files;
- запуск Docker Compose и занятие портов `8080/8181/9000/9001`;
- возможный build существующего dbt image и network pulls, если локального cache недостаточно;
- создание task-owned schemas/tables и объектов в project bucket;
- выполнение DDL, INSERT, dbt builds, probes и acceptance;
- cleanup task-owned schemas/objects и остановка Compose project;
- повторный core acceptance run.

Не разрешаются по умолчанию: `docker compose down -v`, snapshot expiration, orphan cleanup, compaction, удаление чужих schemas/buckets/volumes, Git commit/push и изменение Pi trust/model/config.

### Safe cleanup contract

- До создания объектов runner делает exact collision query для всех своих schema names.
- Ownership flag выставляется только после успешной проверки отсутствия collisions.
- Failure cleanup разрешён только при `query_ready=true` и `prefixes_owned=true`.
- Удаляются evolution schema и четыре task-owned core schemas; cleanup не использует wildcard и не удаляет catalog/bucket.
- Проверяется отсутствие объектов только под `warehouse/<run_id>_`.
- Compose останавливается без `-v`; все pre-existing project volumes должны сохраниться.
- Evidence directory не удаляется автоматически.

### Блокеры и требующее согласования решение

Технических блокеров для review плана нет. До реализации остаются непроверенными SE-PROBE-001/002 и actual AC-013–AC-020 workflow.

Требуется согласовать одно толкование внутреннего расхождения спецификации: **narrowing выполнять после S1 согласно AC-019**. Запасной более строгий вариант — выполнить его и до, и после S1, не меняя final acceptance precondition.

### Минимальное предложение

Не менять core data/model stack и не добавлять зависимости. Добавить один изолированный schema-evolution acceptance runner, pure tests его invariant logic и короткую README-команду. Переиспользовать существующие Compose, fixtures, dbt build и evidence/cleanup primitives; проверять каждый DDL/expected failure полным schema/snapshot/file bundle.

### Следующий ограниченный шаг

Проверить и одобрить `BOOTSTRAP-PLAN-SCHEMA-EVOLUTION-001`, включая порядок negative narrowing из §4.5. Даже после одобрения Bootstrap skill останавливается: probes и реализация должны быть запрошены отдельно.
