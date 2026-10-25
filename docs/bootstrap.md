# План bootstrap: Iceberg + Polaris + Trino + dbt

**ID плана:** `BOOTSTRAP-PLAN-001`  
**Версия skill:** Bootstrap `0.1.0`  
**Статус плана:** `READY_FOR_REVIEW`  
**Одобрение:** пользователь явно одобрил `BOOTSTRAP-PLAN-001` 2026-10-25; это не разрешение на автоматическое применение в рамках Bootstrap skill  
**Режим:** только планирование; ничего из описанного ниже не применялось и не запускалось  
**Дата инвентаризации:** 2026-10-25

## 1. Вход, scope и fingerprints

### Входные файлы

- Спецификация: [`docs/spec.md`](./spec.md), статус `APPROVED`.
- Исходный brief: [`docs/idea.md`](./idea.md).
- План: `docs/bootstrap.md`; до текущего запуска файл отсутствовал, путь не был symlink.
- Bootstrap skill: `/home/kantemir/.pi/agent/skills/bootstrap/SKILL.md`, версия `0.1.0`.

### Fingerprints

- Git commit: `fb48aa002c68c2e607d7a12ae23149d32449e59c`.
- Git status до записи плана: чистая ветка `main`.
- `docs/spec.md`: SHA-256 `7153dfba7a3b7926e24e147c7b8b27e9e58e3209a2c08e910dd95f19ca64d36f`.
- `docs/idea.md`: SHA-256 `7755620909b9cd65d1a6e8fa9c8fc805344f7f95a0fac2f123f08f7b78a8bccf`.
- Bootstrap skill: SHA-256 `1af89767288212b543a0c2eb0d0a44fd5d7f86035a18624eb3c6c9c1afc5e1fd`.
- Pi settings: SHA-256 `d5eb7026c463c2dbbe112adec01b2eb4ed2f724b8451e96a75eecb70aaa76a15`.
- Pi package manifest: SHA-256 `78b13155b1a0c72f20fa4a0006e91f94649b470c363b56b0dee3569ad0cec13d`.

### Выбранный scope

Ближайший однозначно согласованный срез — **core vertical slice** из раздела 7 спецификации:

- RustFS как S3-compatible object storage;
- Apache Polaris как Iceberg REST catalog;
- Trino с Iceberg connector;
- dbt Core + dbt-trino;
- deterministic fixtures `P1`–`P4` и отдельные отрицательные DQ-сценарии;
- immutable Bronze, typed/canonical Silver, SCD2 route plan;
- Gold package accumulating snapshot, hub visits и route-version aggregates;
- проверки AC-001 и AC-003–AC-012.

AC-002 относится к завершению **полного** проекта и не может считаться выполненным после этого среза. Последующие срезы — schema evolution, отдельный time travel exercise, partitioning/`EXPLAIN`, small-files diagnostics, expiration и compaction — не реализуются сейчас, но текущая структура не должна их блокировать.

### Исключения

Сохраняются исключения спецификации: ingestion/CDC/orchestration, Kafka/Debezium, Airflow, Spark, ClickHouse/Superset, Data Vault, несколько доменов и production-grade security не добавляются.

## 2. Наблюдаемое состояние

### Репозиторий

Наблюдалось локально:

- репозиторий содержит только `docs/idea.md` и `docs/spec.md`;
- `AGENTS.md`, README, dependency manifests, lock-файлы, Compose, dbt project, CI и команды проверки отсутствуют;
- пользовательских незакоммиченных изменений до создания этого плана не было;
- проектные или родительские `AGENTS.md` для этого репозитория не обнаружены.

Вывод: проект ещё не имеет ни среды, ни реализации, ни тестового контура. Наличие утверждённой спецификации не является evidence работоспособности.

### Машина и установленные CLI

Наблюдалось локально:

| Компонент | Состояние |
|---|---|
| ОС | Linux `6.18.33.2-microsoft-standard-WSL2`, `x86_64` |
| CPU/RAM, видимые Docker daemon | 16 CPU, около 25 GB RAM |
| Docker | client/server `29.8.0` |
| Docker Compose | `v5.5.1` |
| Python host | `3.12.3` |
| Node.js/npm | `24.15.0` / `11.12.1` |
| Git | `2.43.0` |
| Pi | `1.4.0` |
| dbt CLI | отсутствует на host |
| Trino CLI | отсутствует на host |
| Java | отсутствует на host |

Docker daemon отвечал на read-only metadata query. Это не доказывает возможность pull образов, наличие свободных портов, здоровье будущих сервисов или совместимость компонентов.

Предложение: не устанавливать Java, Trino и dbt глобально на host; запускать проектный стек и dbt в контейнерах. Для первого среза ограничить весь Compose-проект ориентировочно 4 CPU и 8 GB RAM, а не использовать все ресурсы машины.

### Pi и ресурсы агента

Наблюдалось локально:

- текущий provider/model: `openai/gpt-5.6-sol`, reasoning `high`;
- в `~/.pi/agent/settings.json` настроены пакеты:
  - `@upstash/context7-pi` — установлен `0.1.3`;
  - `pi-lens` — установлен `4.4.4`;
  - `pi-lmstudio` — установлен `1.5.0`;
  - `pi-subagents` — установлен `0.81.0`;
- Context7 tools, pi-lens tools и loader `subagents_enable` доступны в текущей сессии;
- `PI_LENS_DISABLE_LSP_INSTALL=1` и `PI_LENS_DISABLE_TOOL_INSTALL=1` запрещают pi-lens автоматически устанавливать LSP/анализаторы;
- глобальный и проектный pi-lens config не обнаружены; действуют defaults: read guard, deferred format/autofix, diagnostics и on-write test detection включены, но отсутствующие инструменты не должны автоматически устанавливаться;
- `pi-subagents` не запускает child agents автоматически; делегирование в этом bootstrap запрещено и не выполнялось;
- `pi-lmstudio` установлен как provider extension, но текущая модель не LM Studio;
- credentials, auth-файлы, `.env`, session transcripts и секретные значения не читались.

Риск текущей сессии: pi-lens может форматировать или autofix-ить разрешённый к записи файл после `write/edit`. Для будущей реализации это требует read-before-edit и повторного чтения изменённых файлов; отдельное отключение защиты не предлагается.

## 3. Выбор возможностей

| Потребность | Существующая возможность | Решение | Основание / ограничение |
|---|---|---|---|
| Чтение, редактирование, Git-инвентаризация | Встроенные `read`, `write/edit`, `bash`, Git | Использовать | Достаточно для реализации и review; не нужен новый MCP |
| Актуальные API Trino/Polaris/dbt | Context7 `0.1.3` | Использовать по необходимости | Запросы отправляют внешнему сервису только общие технические термины; private fixtures/секреты не передавать |
| Навигация и диагностика кода | pi-lens `4.4.4` | Оставить доступным | SQL/YAML/Markdown проверки полезны; отсутствие установленного runner не считать чистым результатом |
| Делегирование и параллельные reviewers | pi-subagents `0.81.0` | Не использовать на этом этапе | Bootstrap skill запрещает subagents; позднее — только по явному разрешению |
| Локальная модель | pi-lmstudio `1.5.0` | Не использовать на этом этапе | Не требуется для scope; локальный server не проверялся |
| Команды проекта | Docker Compose + dbt CLI в контейнере | Использовать | Уже установлен Compose; host-зависимости не нужны |
| Повторяемые команды | Прямые `docker compose`/`dbt` команды | Использовать сначала | Не добавлять Make/Task/Just-обвязку без повторяемой проблемы |
| Проверка ожидаемого провала DQ | Небольшой shell helper | Требуется дополнение | Обычный `dbt test` вернёт non-zero; helper должен подтвердить конкретное имя теста, а не просто любой провал |
| CI | Отсутствует | Не добавлять в первом применении | Сначала получить локальный доказанный baseline; CI без проверенного стека создаст вторую неизвестную среду |

**Итог:** новых skills, extensions, MCP или глобальных изменений Pi не требуется. Не предлагается менять `.pi/settings.json`, provider/model или trust.

## 4. Техническое предложение

### 4.1. Компоненты и версии-кандидаты

Проверено по официальным источникам 2026-10-25:

| Компонент | Предлагаемая версия | Источник и основание | Статус |
|---|---:|---|---|
| Apache Polaris | `1.8.0` | GitHub release `apache-polaris-1.8.0`; Docker Hub tag `apache/polaris:1.8.0`, manifest digest `sha256:347615e736cab2c9be0d8c464552ac930be4755302bb0aeb745216bbae99ba5b` | Предложено; exact integration не запускалась |
| Trino | `484` | GitHub release `484`; Docker Hub `trinodb/trino:484`, manifest digest `sha256:2704eb53935af5e582d63d6033e9bf99d20c325e9b0e30b1016ef59a4773979f` | Предложено; exact integration не запускалась |
| RustFS | `1.0.4` | GitHub release `1.0.4`; Docker Hub `rustfs/rustfs:1.0.4`, manifest digest `sha256:ed9210d6411d77ffceb70d94b964a3cb7d225983368bc25bebe01e995293dcc2` | Предложено; Polaris guide использует более ранний beta tag, поэтому нужен probe |
| Python base для dbt | `3.12.15-slim-bookworm` | Docker Hub official image, manifest digest `sha256:6a0e06f5ba0b373d051aabd3fffb9b873f27f9a2a3a14bcbe37dee6f0e3bbc70` | Предложено |
| dbt Core | `1.11.11` | dbt compatible-track changelog от 2026-06-15 | Документированная совместимая линия |
| dbt-trino | `1.10.2` | Тот же compatible track; PyPI требует Python `>=3.9`, dbt Core `>=1.8.0` | Документированная совместимая линия |
| Bucket bootstrap | `amazon/aws-cli:2.36.44` | Pin из Polaris `1.8.0` tagged guide | Предложено |
| HTTP bootstrap | `alpine/curl:8.22.0` | Pin из Polaris `1.8.0` tagged guide | Предложено |

Не использовать `latest`. Digests выше наблюдались как multi-platform manifest digests на дату проверки; перед записью lock/Compose в будущем применении их следует повторно проверить. Если tag и digest расходятся, остановиться и обновить решение в плане, а не молча перейти на другой образ.

Почему dbt не берётся в текущем latest `1.12.x`: официальная compatible track фиксирует совместно проверенный набор `dbt-core==1.11.11` и `dbt-trino==1.10.2`. Переход на более новую линию не нужен первому срезу.

### 4.2. Архитектура локального контура

Предложено:

1. Один изолированный Docker Compose project с фиксированным project name.
2. Сервисы:
   - `rustfs` с named volume;
   - `bucket-setup`, создающий только проектный bucket;
   - `polaris` с in-memory metastore для воспроизводимого учебного reset;
   - `polaris-setup`, создающий catalog/roles/grants только после healthcheck;
   - single-node `trino`;
   - run-on-demand `dbt` container.
3. Trino подключается к Polaris через Iceberg REST catalog и OAuth2 client credentials.
4. Polaris выдаёт credentials для доступа к RustFS; включаются S3 endpoint и path-style access по tagged Polaris guide.
5. Внешние порты по умолчанию: Trino `8080`, Polaris `8181`, RustFS API `9000`, console `9001`. Перед запуском требуется проверить занятость, не завершать чужие процессы.
6. Credentials первого среза являются только локальными учебными значениями и поступают из untracked `.env`; в Git попадает только `.env.example` без production secrets.
7. Default-команды не удаляют volumes. Полный reset (`down -v`) — только отдельная явно destructive команда для ресурсов этого Compose project.

In-memory Polaris выбран как минимальный вариант первого среза и соответствует official getting-started guide. Он не обещает сохранение catalog state после полного пересоздания контейнера. Если последующие упражнения потребуют сохранения состояния между перезапусками, persistence будет отдельным изменением, а не скрытым расширением первого среза.

### 4.3. Структура данных и dbt

Предложено, без изменения бизнес-контракта спецификации:

- один Trino catalog `lakehouse`;
- схемы с run prefix, затем layer suffix: `fixtures`, `bronze`, `silver`, `gold`;
- каждый acceptance/negative run получает отдельный prefix, чтобы не портить baseline;
- fixture rows имеют технический `fixture_row_id`, `batch_id` и согласованные бизнес-поля;
- `event_id` остаётся бизнес-ключом канонизации; два разных `fixture_row_id` могут содержать точный повтор одного `event_id`;
- Bronze хранит исходные строковые значения и batch metadata без deduplication;
- Silver приводит типы, проверяет payload conflict и выбирает каноническую запись по `event_id`;
- current package state определяется порядком `(event_at, received_at, event_id)`;
- route-plan source хранит изменения с `effective_at`, а SCD2-модель вычисляет `valid_to` через следующую версию;
- route checkpoints нормализованы отдельными строками с `checkpoint_seq`;
- planned/actual distance считается в Trino через `ST_Point(longitude, latitude)`, `to_spherical_geography` и `ST_Distance`;
- Gold включает только три результата DEC-026: package fact, hub-visit fact и route-version aggregate;
- модели первого среза могут пересобираться как таблицы из малых deterministic fixtures; semantic accumulating snapshot обеспечивается grain и обновлением одной package-row, а не обязательной incremental materialization. Оптимизация incremental predicates остаётся отдельной учебной задачей полного scope.

Для staged проверки `P3` fixture loader должен быть идемпотентным по `fixture_row_id` и позволять отдельно применить `batch_1`, затем `batch_2`. Повтор команды для того же batch не должен добавлять третью копию строки, но две исходные строки точного дубля с разными `fixture_row_id` должны остаться в Bronze.

В спецификации встречаются оба значения `departed_hub` и `departed_at_hub`. Предлагаемая совместимая нормализация:

- Bronze сохраняет исходное значение;
- Silver принимает оба значения и приводит их к каноническому `departed_at_hub`;
- fixtures и DQ-тесты первого среза используют `departed_at_hub`, поскольку именно оно используется в подробных pairing-контрактах и AC-009.

Это техническая нормализация одного смысла, а не изменение жизненного цикла.

### 4.4. Неизвестные и минимальные probes

Ни один probe в Bootstrap не выполнялся.

#### PROBE-001 — совместимость pinned stack

- **Неизвестность:** Polaris `1.8.0`, Trino `484` и RustFS `1.0.4` не проверялись вместе локально; tagged Polaris guide использует unpinned Trino/Polaris и RustFS `1.0.0-beta.8`.
- **Минимальный эксперимент:** pull только перечисленных pinned images; поднять изолированные `rustfs`, setup, `polaris`, `trino`; создать один namespace/table, вставить одну строку и прочитать её.
- **Ожидаемый сигнал:** healthchecks green; OAuth token получен; `CREATE TABLE`, `INSERT`, `SELECT` успешны.
- **Дополнительный signal:** в RustFS появились Iceberg metadata/data objects, а table видна через Polaris/Trino listing.
- **Стоп:** первый unhealthy service, auth error, unsupported config property или запись вне проектного bucket.
- **Очистка:** остановить только Compose project; volume не удалять автоматически. Отдельный approved reset удаляет только его named volumes.
- **Решение:** при успехе закрепить pins; при неуспехе сравнить максимум два варианта — RustFS guide pin и текущий stable — без перехода на новый storage family.

#### PROBE-002 — dbt adapter handshake

- **Неизвестность:** exact dbt image и profile ещё не собирались.
- **Минимальный эксперимент:** собрать dbt image из hash-locked dependencies; выполнить `dbt --version`, `dbt debug`, одну smoke model и один test в отдельной smoke schema.
- **Ожидаемый сигнал:** версии ровно `1.11.11`/`1.10.2`; connection successful; model создаётся в Iceberg catalog; test проходит.
- **Стоп:** dependency resolution drift, несовпадение версий, profile/auth error или создание объектов вне smoke schema.
- **Очистка:** удалить только smoke schema явной командой после сохранения evidence.
- **Решение:** при успехе использовать image для среза; при конфликте проверить официальный compatible track, не обновлять весь stack автоматически.

#### PROBE-003 — геодезические ожидания fixtures

- **Неизвестность:** фактическая численная погрешность Trino `484` для выбранных координат не наблюдалась.
- **Минимальный эксперимент:** SQL-only запрос для planned `A→B→C`, `A→D→C` и actual `A→B→X→D→C`.
- **Ожидаемый сигнал:** обе planned distance равны в пределах 1 м; actual/planned для P2 равно `1.5` в пределах допуска 0.01 процентного пункта.
- **Стоп:** `NULL`, ошибка geography, неверный порядок longitude/latitude или выход за tolerance.
- **Очистка:** не требуется, запрос не создаёт данных.
- **Решение:** закрепить выражение в reusable dbt macro; не подменять вычисление готовой дистанцией во fixture.

#### PROBE-004 — staged late-event path

- **Неизвестность:** выбранный loader ещё не доказал идемпотентность и корректный пересчёт downstream.
- **Минимальный эксперимент:** в отдельном run prefix загрузить batch 1, сохранить строки P3; загрузить batch 2; перестроить Silver/Gold и повторить запрос.
- **Ожидаемый сигнал:** Bronze увеличивается на исходные строки batch 2; canonical count не увеличивается из-за точного дубля; P3 остаётся delivered, visits появляются, route ratio меняется 100% → 150%.
- **Стоп:** повтор batch создаёт дополнительные fixture rows, теряется late event или меняется delivery duration/on-time.
- **Очистка:** удалить только схемы этого run prefix после сохранения evidence.

## 5. План будущих изменений

### 5.1. Работа агента

#### BOOT-AGENT-001 — короткий `AGENTS.md`

- **Добавить:** навигацию к `docs/spec.md` и этому плану; команды запуска/проверки; запрет менять business rules/AC без решения пользователя; правило не выполнять destructive reset по умолчанию; правило не печатать credentials.
- **Зачем:** обеспечить следующий агент локальными инструкциями без копирования спецификации.
- **Зависимость:** согласованный интерфейс команд после PROBE-001/002.
- **Проверка:** файл короткий, ссылки разрешаются, команды совпадают с README/Compose, нет дублирования fixture contracts.
- **Откат:** удалить только `AGENTS.md`.

#### BOOT-AGENT-002 — не добавлять новые Pi resources

- **Сохранить:** текущие settings/packages без project override.
- **Зачем:** существующих built-in tools, Context7 и pi-lens достаточно.
- **Проверка:** будущий diff не содержит `.pi/settings.json`, новых skills/extensions/MCP и глобальных конфигов.
- **Откат:** не требуется, изменение отсутствует.

Новый handoff/status-файл не создавать: `docs/spec.md` и `docs/bootstrap.md` уже дают контракт и план.

### 5.2. Среда и проверки

#### BOOT-ENV-001 — Compose stack

- **Добавить:** root `compose.yaml`, project-scoped network/volumes, healthchecks, service resource limits и pinned images.
- **Зачем:** AC-012 и единый воспроизводимый local stack.
- **Зависимость:** PROBE-001.
- **Проверка:** `docker compose config` успешен; resolved images не содержат `latest`; `docker compose up -d --wait` завершается только при healthy dependencies.
- **Откат:** `docker compose down` для project; volumes сохраняются. Удаление volumes — отдельное подтверждённое действие.

#### BOOT-ENV-002 — конфигурация Trino/Polaris/RustFS

- **Добавить:** Trino Iceberg catalog properties, минимальные Polaris bootstrap assets и bucket/catalog setup.
- **Зачем:** REST catalog, OAuth2, vended credentials и S3-compatible path-style access.
- **Зависимость:** BOOT-ENV-001.
- **Проверка:** PROBE-001; listing catalog/schema/table; object listing без вывода секретов.
- **Откат:** удалить только созданные config/bootstrap files и project objects; не трогать чужие buckets/catalogs.

#### BOOT-ENV-003 — dbt execution image и dependency lock

- **Добавить:** минимальный Dockerfile, direct requirements input и разрешённый hash lock для `dbt-core==1.11.11` + `dbt-trino==1.10.2`.
- **Зачем:** не зависеть от host dbt/Python environment и исключить плавающие transitives.
- **Зависимость:** сетевой доступ на image/package pull при отдельном применении.
- **Проверка:** PROBE-002; build выводит ожидаемые версии; lock diff reviewable.
- **Откат:** удалить image/config files и локальный image этого проекта; host Python не изменяется.

#### BOOT-ENV-004 — env contract и ignore rules

- **Добавить:** `.env.example` только с локальными placeholder values; `.gitignore` для `.env`, dbt `target/`, logs и generated evidence.
- **Зачем:** отделить локальные credentials и generated artifacts от исходников.
- **Зависимость:** согласованные variable names из Compose/profile.
- **Проверка:** `git status` не показывает `.env`/generated outputs; Compose сообщает о недостающих обязательных vars, а не использует production-like defaults.
- **Откат:** удалить эти два файла; пользовательский `.env` не удалять автоматически.

#### BOOT-ENV-005 — человеческий quickstart и evidence contract

- **Добавить:** краткий `README.md` с prerequisites, baseline flow, late-event flow, negative DQ flow, safe stop и отдельно помеченным reset.
- **Не добавлять:** Makefile/Taskfile на первом проходе.
- **Зачем:** прямых Compose/dbt команд достаточно; лишний wrapper пока не оправдан.
- **Проверка:** все команды copy-pasteable и совпадают с AC matrix; команды, которых ещё нет, явно помечены proposed до реализации.
- **Откат:** удалить README; среда не меняется.

#### BOOT-ENV-006 — helper ожидаемого DQ-провала

- **Добавить:** один небольшой helper, принимающий scenario/test selector и подтверждающий non-zero exit **и** ожидаемое имя упавшего dbt test.
- **Зачем:** AC-009 нельзя доказать произвольной ошибкой команды.
- **Зависимость:** имена negative tests из реализации.
- **Проверка:** intended DQ failure считается успехом helper; connection/syntax/другой test failure считается неуспехом.
- **Откат:** удалить helper; dbt tests остаются.

CI на этом этапе не добавлять. После локального прохождения AC-012 отдельным решением можно добавить parse/unit checks и, только при наличии подходящего runner, integration job.

### 5.3. Реализация результата

#### IMP-001 — dbt skeleton и layer conventions

- **Область:** `dbt_project.yml`, profile template, schema naming, sources, reusable macros.
- **Вход:** DEC-005/006/020/024/027.
- **Зависимость:** BOOT-ENV-002/003.
- **Наблюдаемый выход:** dbt видит catalog; создаёт объекты только в run-prefixed schemas; distance macro проходит PROBE-003.
- **AC:** AC-001, AC-012.

#### IMP-002 — deterministic fixtures и immutable Bronze

- **Область:** hubs, packages/shipments, route changes/checkpoints, event batches 1/2, `fixture_row_id`, `batch_id`; отдельные negative scenarios.
- **Вход:** fixture package раздела 5 спецификации, без дублирования контракта в документах.
- **Зависимость:** IMP-001.
- **Наблюдаемый выход:** staged/idempotent load; Bronze содержит все исходные rows, включая две строки точного дубля P3.
- **AC:** AC-004, AC-005, AC-009, AC-011.

#### IMP-003 — canonical/typed Silver и DQ

- **Область:** casts, event payload fingerprint, canonical event set, current package state, ordering; singular/generic tests для conflict и sequence errors.
- **Вход:** DEC-010/016/022.
- **Зависимость:** IMP-002.
- **Наблюдаемый выход:** одна canonical row на `event_id`; late events занимают место по business time; конфликтующие payload и невозможный hub sequence обнаруживаются предназначенными tests.
- **AC:** AC-004, AC-005, AC-009.

#### IMP-004 — SCD2 route plan и route binding

- **Область:** version intervals, current marker, no-overlap tests, checkpoint distance, package join по `picked_up_at`, promised timestamp.
- **Вход:** DEC-017/020/023/024.
- **Зависимость:** IMP-003.
- **Наблюдаемый выход:** P1 → V1; P2/P3/P4 → V2; planned distances вычислены из coordinates.
- **AC:** AC-003.

#### IMP-005 — hub visits и Gold facts

- **Область:** strict pairing/`visit_seq`; package accumulating snapshot; route and distance metrics; open visit semantics.
- **Вход:** DEC-011–015/021/022/026.
- **Зависимость:** IMP-003/004.
- **Наблюдаемый выход:** package fact grain 1 row/package после pickup; 7 visits, 6 closed + 1 open; P1/P2/P3/P4 соответствуют expected rows.
- **AC:** AC-005–AC-008, AC-011.

#### IMP-006 — Gold aggregates и reconciliation

- **Область:** route-version aggregate, completed hub dwell aggregate, cross-layer counts/relationships.
- **Вход:** DEC-013/026 и AC-010/011.
- **Зависимость:** IMP-005.
- **Наблюдаемый выход:** route-version и hub totals совпадают со спецификацией; S2 имеет две независимые package rows.
- **AC:** AC-010, AC-011.

#### IMP-007 — acceptance workflow и evidence

- **Область:** baseline, staged late-event comparison, three isolated negative runs, stack/object/catalog evidence.
- **Зависимость:** все предыдущие задачи.
- **Наблюдаемый выход:** machine-readable dbt results (`target/run_results.json`), сохранённые SQL result tables/CSV и список object paths; секреты не попадают в evidence.
- **AC:** AC-001, AC-003–AC-012.

## 6. AC → будущая проверка → evidence

Все команды ниже — **предложенный интерфейс**, которого сейчас в репозитории нет. Ни одна команда не запускалась.

| AC | Будущая проверка / команда | Ожидаемый результат | Evidence |
|---|---|---|---|
| AC-001 | Review `docker compose config`, `dbt ls`, tracked manifests | Только заданный stack и fixtures; исключённые технологии отсутствуют | Compose render, dependency/file list, review note |
| AC-002 | Не принимается этим срезом | Только трассировка отложенных competencies, без заявления completion | Обновляемая AC/competency matrix последующих срезов |
| AC-003 | `dbt build --select tag:scd2` + mapping query | P1→V1; P2/P3/P4→V2; no overlap; promised timestamps | `run_results.json`, mapping CSV |
| AC-004 | load batch 1, затем batch 2; reconciliation selector | Bronze хранит обе duplicate rows; canonical хранит одну | counts by layer/batch/event_id |
| AC-005 | сохранить P3 before/after batch 2 | delivered/duration/on-time неизменны; visits B/X; ratio 100%→150% | before/after CSV + test result |
| AC-006 | `dbt test --select tag:expected_p1` | Все P1 expected values с заданными tolerances | test result и expected-row diff |
| AC-007 | `dbt test --select tag:expected_p2` | 48h, 12h delay, dwell 4/10/2, 150%, 50% | test result и expected-row diff |
| AC-008 | `dbt test --select tag:expected_p4` | Одна active row, open D visit, final fields NULL, current distance non-NULL | test result и row snapshot |
| AC-009 | helper для каждого isolated scenario | Падает только предназначенный DQ test; baseline проходит | exit code, exact test name, dbt result JSON |
| AC-010 | `dbt test --select tag:expected_aggregates` | Route/hub aggregates ровно как в спецификации | expected aggregate rows |
| AC-011 | `dbt test --select tag:reconciliation` | package=4, completed=3, active=1; visits=7/6/1; разница Bronze/Silver объяснена дублем | reconciliation query outputs |
| AC-012 | PROBE-001 + `dbt build` baseline | Catalog, object storage, Trino и dbt работают сквозным образом | service health, catalog listing, object paths, `run_results.json` |

### Предлагаемая последовательность acceptance

1. Render/validate Compose config без запуска.
2. Получить отдельное одобрение на image pulls/build и запуск сервисов.
3. Выполнить PROBE-001–003.
4. Создать clean baseline run prefix.
5. Загрузить batch 1 и сохранить P3 before-state.
6. Загрузить batch 2, выполнить baseline `dbt build`, сохранить after-state и reconciliation.
7. Выполнить три negative scenarios в трёх отдельных run prefixes через expected-failure helper.
8. Собрать catalog/object/dbt evidence без credentials.
9. Остановить сервисы без удаления volumes; destructive reset выполнять только по отдельному запросу.

Пустой набор tests, `exit 0`, один только healthy process или текстовый отчёт агента не являются evidence AC.

## 7. Одобрение, права, блокеры и следующий шаг

### Будущие действия, требующие отдельного одобрения

- создание/изменение всех файлов кроме этого плана;
- network pulls контейнеров и Python packages;
- build dbt image и dependency lock;
- запуск Docker services и занятие портов `8080/8181/9000/9001`;
- создание project bucket, Polaris catalog/roles и Trino schemas/tables;
- выполнение probes, dbt builds/tests и negative runs;
- удаление run schemas, containers, images или volumes;
- возможное подключение subagents/reviewers — только по отдельной авторизации.

### Блокеры

Блокеров для review плана нет. Перед реализацией остаются явно непроверенные PROBE-001–004. Они не означают, что среда готова.

### Минимальное предложение

Принять первый срез без новых Pi-пакетов и без CI: pinned Compose stack `RustFS + Polaris + Trino`, отдельный containerized dbt, короткие `AGENTS.md`/README, staged fixtures и dbt tests. Сначала доказать один сквозной Iceberg smoke path, затем реализовать модели и AC; не создавать дополнительную orchestration-обвязку.

### Следующий ограниченный шаг

Одобрение `BOOTSTRAP-PLAN-001` зафиксировано. Bootstrap skill на этом останавливается: применение должно быть запрошено отдельно и начинаться с BOOT-ENV-001/002 и PROBE-001, а не со всей реализации одновременно.
