# Bootstrap: Time travel и rollback — TT-1

## 1. Статус, согласование и входы

- **Skill:** Bootstrap 0.1, только планирование.
- **Статус плана:** `READY_FOR_REVIEW`. Это статус планового документа, не готовности среды или реализации. Одобрение фиксируется отдельно ниже; новый статус вне словаря skill не вводится.
- **Одобрение плана:** пользователь явно ответил «согласовываю» на план TT-1 в текущем диалоге.
- **Разрешение записи:** после согласования пользователь отдельно ответил «разрешаю post-write hooks». Разрешение относится к автоматическим hooks записи этого плана; оно не запускает реализацию, сервисы или probes и не является поручением менять конфигурацию hooks, trust или права.
- **Единственный разрешённый файл записи этого запуска:** `docs/bootstrap-time-travel.md`. До записи файл отсутствовал; канонический путь находится внутри реального каталога `docs/`, symlink назначения не обнаружен.
- **Дата технической проверки источников:** 2026-11-01.

### Входные документы и scope

- Контракт: [`docs/spec.md`](./spec.md), раздел 12, версия **TT-1**, статус `APPROVED`; DEC-034–DEC-040, AC-028–AC-033.
- Brief: [`docs/idea.md`](./idea.md).
- Контекст и handoff: разделы 1–11 спецификации, [`docs/status.md`](./status.md), корневой `README.md`.
- Существующие средства: `compose.yaml`, dbt-конфигурация и Gold-модель, baseline batch_2 fixtures, Dockerfile и dependency manifests, три acceptance runners и сохранённые итоговые summaries. Существенные участки runners прочитаны как исходный код, а не выполнены.

**Только новый срез:** historical reads по snapshot ID и timestamp, staged-источник до/после поздних событий P3, намеренная ошибка `36 → 360`, rollback к H1 с сохранением historical Hbad.

**Не входят:** повторная реализация завершённых срезов, branches/tags, timestamp semantics после rollback, maintenance, изменение core fixtures/моделей и закрытие общего AC-002. Последующие срезы учитываются только как ограничения совместимости.

Устаревшие формулировки `README.md` и `docs/status.md` о том, что следующий срез ещё не выбран, расходятся с актуальным разделом 12. Источником scope принимается раздел 12. Формулировки о следующих срезах в прежних разделах спецификации сохраняют историческую роль согласно §12.1. Исходные документы этим запуском не меняются.

### Fingerprints

Git HEAD при подготовке и перед сохранением плана: `e955f3d6713095c28b87802ad8c41218c6639cdb`. Рабочее дерево перед записью чистое. Повторная проверка не выявила изменения следующих входов относительно первоначального планирования:

| Файл | SHA-256 |
| --- | --- |
| `docs/spec.md` | `d97926441f8f481714dace86428b3cdf2b7e4537d124ad40e119bf1222e76bd1` |
| `docs/idea.md` | `7755620909b9cd65d1a6e8fa9c8fc805344f7f95a0fac2f123f08f7b78a8bccf` |
| `docs/status.md` | `4db0ccb79fdecbd9fdfa0178dc94ade1fff5729d4b6759ccd628c8de9c48b2e2` |
| `README.md` | `26492ea657b8e3cec8272cd487efb033bb6fab1f94584181e2c80339d07ab743` |
| `compose.yaml` | `55c832a2297d8f13fbd1635c0bba6ce0912b785b31f943cb851a9e92f46f0bdd` |
| `docker/dbt/requirements.in` | `41cfa5510fbe15ac59503aa082ccfe9ba00cd53929163f0772b127d370dfa2d9` |
| `docker/dbt/requirements.lock` | `d39a006b767024dfe5128cde43a5ee22b8744496bfcb122fffb4eff7325bb8f3` |
| `scripts/run_acceptance.py` | `b2d96a1f6a44e228e786718894b5827ae2129c8d8bcf1da799754ffc63c549f8` |
| `scripts/run_schema_evolution_acceptance.py` | `245034f743fbae1d9099fa8d95cee4c783e2e18c6633772a1852ee75ebcdb2bb` |
| `scripts/run_partitioning_file_pruning_acceptance.py` | `c4d5c9dbb84cc1f8d98592357d59101729f9cd60426dc49e8fbafbaad8c4a3b5` |

Одобрение относится к этому ограниченному предложению и указанным входам. Изменение входов требует переоценки затронутых частей, а не автоматического переноса одобрения.

## 2. Наблюдаемое состояние и пределы проверки

| Область | Наблюдалось локально | Предел проверки |
| --- | --- | --- |
| Завершённые срезы | Summaries `imp007_final5`, `seimp006_final2`, `pfimp006_final` прочитаны; содержат `outcome=PASS`, `error=null` и PASS своих AC | Это сохранённые результаты, не новый acceptance; весь evidence заново не проверялся |
| Стек | Trino 484, Polaris 1.8.0, RustFS 1.0.4; образы закреплены tag+digest в Compose | Доступность образов и daemon не проверялась |
| dbt | Core 1.11.11, dbt-trino 1.10.2; hash-locked зависимости, Python 3.12.15 в Dockerfile | Сборка и команды dbt не запускались |
| Host инструментов агента | WSL2 Linux x86_64; Python 3.12.3, Node 24.15.0, uv 0.11.3, Docker CLI 29.8.0, Compose 5.5.1 | Это не доказательство готовности Docker Engine и не описание будущей машины пользователя |
| Ресурсы | Видны 16 logical CPU и около 23,5 GiB RAM; Compose уже содержит CPU/memory limits | Лимиты Docker и разрешённый бюджет проекта не установлены; увеличивать текущие лимиты не предлагается |
| Проверки | Три acceptance runner; существующий `unittest`-контур в `scripts/tests/` | Тесты не запускались |
| Инструкции и CI | Релевантные `AGENTS.md`, проектная `.pi/settings.json`, Makefile и CI не обнаружены | Их отсутствие само по себе не требует добавления |
| Локальная конфигурация проекта | При первоначальной инвентаризации корневой `.env` не обнаружен | Credentials и auth-хранилища не читались; наличие необходимых переменных в среде не устанавливалось |

### Существенный пробел существующего lifecycle

`AcceptanceRun.preflight()` в `scripts/run_acceptance.py` отказывается работать при любых существующих контейнерах проекта, а lifecycle рассчитан на запуск и последующий `compose down`. Это **не покрывает** требование TT-1 сохранить исходно работающий stack. Простое наследование старого lifecycle без адаптации недопустимо.

`AcceptanceRun.finalize()` также может назначить PASS всем своим AC при отсутствии общей ошибки. Новый runner должен иметь собственные явные gates и не переносить blanket-PASS на AC нового среза.

Существующие staged helpers уже умеют загрузить batch_1, выполнить core-модели, затем загрузить batch_2 и выполнить полный build. Gold-модель содержит поля для проекции §12.4; её менять не требуется. Полный baseline нельзя подставить вместо реального staged H0.

## 3. Работа агента и выбор возможностей

### Pi и ресурсы

Локальные package manifests при первоначальной оценке показывают: pi **1.4.0**, Context7 **0.1.3**, pi-lens **4.4.7**, pi-lmstudio **1.5.0**, pi-subagents **0.84.0**. Эти четыре пакета указаны в пользовательских настройках. Инструменты Context7, pi-lens и loader subagents доступны в текущей сессии; работоспособность делегирования и LM Studio не проверялась. Версия pi установлена чтением package metadata, без новой сессии pi.

Проверены стандартный agent directory и доступные несекретные переопределения путей; переопределение agent directory не обнаружено. В пользовательских ресурсах обнаружены локальные skills `specify`, `implement`, `bootstrap`; проектных подключений ресурсов не обнаружено. Каталог `extensions/pi-permission-system` не доказывает загрузку extension; его содержимое с логами не читалось.

Перед сохранением обнаружено внешнее изменение пользовательских настроек: дополнительно указан `npm:pi-web-access`; локальный manifest показывает **0.46.0**. Просмотрены manifest и релевантная часть README. Пакет не добавлялся агентом, его tools в этом запуске не вызывались, загрузка и работоспособность не подтверждались. Это наблюдение не меняет согласованный выбор возможностей: нового компонента для TT-1 не требуется. Конфигурация web-search с возможными credentials не читалась.

| Потребность | Существующая возможность | Решение | Основание / ограничение |
| --- | --- | --- | --- |
| Навигация и передача состояния | `docs/spec.md`, этот план, `docs/status.md` | Использовать; новые state-файлы и AGENTS не добавлять | Существующих документов достаточно |
| Версионная документация | Context7 | Использовать сейчас для существенных вопросов | Отправлялись только общие технические запросы, не частное описание или credentials |
| Локальные проверки Python | Python + `unittest` | Использовать при будущей реализации | Не нужны pytest и дополнительные зависимости |
| Команды, evidence, SQL, storage | Существующие acceptance helpers | Переиспользовать выборочно, без изменения старых runners | Lifecycle и финальный PASS требуют TT-specific логики |
| Code intelligence | pi-lens | Оставить доступным по необходимости на этапе реализации | Диагностика не заменяет runtime AC; возможны автозапуски |
| Делегирование | pi-subagents | Не использовать в bootstrap | Текущий skill запрещает запуск |
| Локальная модель | pi-lmstudio | Не использовать для этого этапа | Незакрытого требования к ней нет |
| Общий web research | Настроенный pi-web-access | Не использовать на этом этапе | Существенные вопросы закрыты версионной документацией через Context7 |
| Новый extension/MCP | Не требуется | Ничего не добавлять | Пробел — в acceptance workflow, а не в наборе tools |

Новые пакеты, миграции и глобальные настройки не предлагаются. Сравнение кандидатов не требуется: отсутствует незакрытая потребность в новом компоненте. «Не использовать» не означает удалить или выгрузить уже установленный ресурс. Model provider сохраняется.

### Post-write hooks и предел разрешения

По локальным README/документации pi-lens 4.4.7 у него включены по умолчанию format/autofix/tests и существуют пути автоматической установки инструментов. `effective_config` для целевого Markdown-файла не обнаружил конфигурационных overrides и показал выбранные Markdown-проверки; отключающие mutation-флаги процесса при первоначальной проверке также не обнаружены. Это конфигурационное наблюдение, не runtime-проверка конкретного hook.

Поэтому первоначальный план был выдан только в диалоге. После явного ответа пользователя «разрешаю post-write hooks» разрешена запись этого плана с автоматическими hooks. Настройки, trust и защиты не меняются; hooks не обходятся записью через другой инструмент. Нельзя на основании plan-only обещать отсутствие побочных эффектов всех загруженных extensions или всей сессии. Агент не запускает отдельно тесты, установки, сервисы или LSP probes ради сохранения Markdown-плана; фактические сообщения автоматических hooks нужно отличать от таких команд и от проверки AC.

## 4. Техническое предложение, источники и неизвестные

### Сохранить pinned stack

Сохранить весь текущий stack без обновлений. Источники версий — `compose.yaml`, `docker/dbt/Dockerfile`, `requirements.in` и `requirements.lock`. Существующие tag+digest pins не заменять непроверенными digest. Старые summaries свидетельствуют о прежней интеграции компонентов, но не о выполнении TT-1.

### Минимальная архитектура результата — предложено

1. Один новый runner: `scripts/run_time_travel_acceptance.py`.
2. Один новый unit-test module: `scripts/tests/test_time_travel_acceptance.py`.
3. Без новых dbt-моделей, fixtures, Compose overrides, skills, extensions и dependency changes.
4. Source build — в новом task-owned prefix; учебная таблица — отдельно, согласно §12.4 спецификации. Точный schema/object allowlist фиксируется и проверяется до первой записи.
5. H0 создаётся из реального Gold после batch_1. H1 — одной data-операцией из проверенного Gold после batch_2; кандидат — `MERGE` с обновлением только трёх показателей P3. Hbad — одним `UPDATE` duration P3.
6. Учебная таблица создаётся сразу с постоянной typed-схемой и Iceberg format v2. Между H0/H1/Hbad не допускается её пересоздание, замена CTAS или dbt table materialization.
7. Commit times разделяются и проверяются по metadata с сохранением миллисекунд и явной UTC. Snapshot IDs не сортируются численно и не хардкодятся.
8. После rollback current определяется по актуальному catalog metadata pointer и `current-snapshot-id`, а не по максимальному времени `$snapshots` или имени metadata-файла.
9. Проверка файлов охватывает historical data/delete files, а не только current `$files`; checksum — фактический SHA-256 либо подтверждённый object checksum, не предположение об ETag.
10. Поздние события P3 не считаются ошибкой: rollback выполняется к H1, а не к H0. Эталон не вычисляется из испорченной строки или результата проверяемой SQL-логики.

### Подтверждается документацией

Официальная документация проверена 2026-11-01 через Context7, выбранный ID `/trinodb/trino/484`, ref **484**:

- [Iceberg connector](https://github.com/trinodb/trino/blob/484/docs/src/main/sphinx/connector/iceberg.md): snapshot/timestamp queries, выбор последнего snapshot до или на timestamp, rollback, `$history`, table property `format_version` с default 2.
- [MERGE](https://github.com/trinodb/trino/blob/484/docs/src/main/sphinx/sql/merge.md): обновление из source relation.
- [Release 484](https://github.com/trinodb/trino/blob/484/docs/src/main/sphinx/release/release-484.md): исправление `$history`, включая время становления snapshot текущим.

Документация подтверждает механизмы, **но не доказывает** требуемые snapshot/file invariants на данном stack. Peer/runtime ranges установленных pi-пакетов также не доказывают корректность конкретного поведения.

### TT-PROBE-001 — будущий ограниченный compatibility checkpoint

- **Неизвестность:** дают ли выбранные write-операции ровно три data snapshots, а rollback — смену current без четвёртого snapshot и потери Hbad.
- **Минимальный эксперимент:** отдельная task-owned таблица с несколькими строками, три состояния, разделённые commit times, rollback ко второму.
- **Ожидаемый сигнал:** корректные parent links, повторная запись H1 в history, сохранённое чтение третьего snapshot; неизменность schema и ранее существовавших data/delete files. Проверяются также current rows и отсутствие новых data/delete files после rollback.
- **Ресурсы и права:** только собственная schema/object prefix; без доступа на запись к пользовательским таблицам, без maintenance и удаления volumes.
- **Ограничения:** предложенный бюджет — до 120 секунд после готовности stack; старт и cleanup отдельно ограничены. Не увеличивать существующие Compose resource limits. Коллизия prefix, выход за allowlist, неоднозначные timestamps или нарушение invariants останавливают checkpoint.
- **Безопасная очистка:** только собственные объекты, включая исторические остатки; работающий до проверки stack не останавливается. Cleanup выполняется и при ошибке; его ошибка не скрывается.
- **Дальнейшее решение:** при успехе использовать механизм в основном workflow; при расхождении остановиться и выяснить причину, не ослаблять AC. Изменение контракта требует решения пользователя по затронутой части спецификации.

Checkpoint можно встроить в первый runtime-этап runner, без отдельного probe-пакета. Он не заменяет staged-сценарий P1–P4 и сам по себе не закрывает AC. Сейчас он не выполнялся.

## 5. Будущие изменения: три отдельные области

### Работа агента и среда/проверки

| ID / область | Что сохранить / добавить / изменить и зачем | Зависимость и критерий проверки | Как отменить только это изменение |
| --- | --- | --- | --- |
| **TT-AGENT-001 — работа агента** | Сохранить ссылки на spec/план; вести задачи в существующем `docs/status.md` | Без новых глобальных инструкций и дублирующих журналов; старые записи сохранены | Удалить только добавленные TT-записи |
| **TT-ENV-001 — среда и проверки** | В новом runner реализовать task ownership и lifecycle: reuse работающего stack либо управление только собственным запуском | До первой записи — проверенный schema/object allowlist. Неизвестное/частичное состояние — безопасный отказ без остановки чужих контейнеров. Собственные запуски возвращаются в исходное состояние | Удалить TT-specific слой; старые helpers не менять |
| **TT-ENV-002 — среда и проверки** | Evidence, checksums, negative-state comparisons, cleanup, явные AC gates | PASS невозможен при NOT_RUN, неполном evidence или ошибке cleanup; не наследовать blanket-PASS старого `finalize()` | Удалить только TT-код и собственные runtime artifacts после проверки ownership |
| **TT-IMP-001–006 — реализация результата** | Реализовать сценарии ниже и их unit tests | AC-028–AC-033 | Удалить новые TT-файлы; не откатывать пользовательские изменения |
| **TT-DOC-001 — документация результата** | После фактической приёмки добавить команды и результаты в README/status | Только наблюдённые результаты; контракты старых срезов не менять | Удалить только TT-дополнения |

Создание AGENTS.md не требуется. Если позже обнаружится конкретная проблема навигации агента, предложение такого файла должно быть отдельным минимальным изменением: навигация, команды, ограничения и ссылки, без копирования спецификации.

### Задачи реализации выбранного среза

| ID | Вход → наблюдаемый выход | Зависимости / AC |
| --- | --- | --- |
| **TT-IMP-001** | Неизменённые fixtures и batch_1 → реальный staged Gold, проверенная проекция H0, одна учебная таблица | TT-ENV-001; AC-032 |
| **TT-IMP-002** | batch_2 → проверенный H1, затем единственная fault injection → Hbad; ровно три snapshots одной таблицы | TT-IMP-001; AC-029, AC-032 |
| **TT-IMP-003** | IDs и metadata timestamps → три ID-read и пять успешных timestamp cases до rollback | TT-IMP-002; AC-029 |
| **TT-IMP-004** | Подтверждённо отсутствующий положительный BIGINT ID и `t0−1 ms` → три содержательные ошибки с отдельными before/after comparisons | TT-IMP-002; AC-031 |
| **TT-IMP-005** | Hbad → rollback к H1 → current=H1, все historical states сохранены, file/history invariants выполнены | TT-IMP-003–004; AC-030 |
| **TT-IMP-006** | Полный workflow → финальный baseline build, isolation, полный evidence, cleanup и восстановление среды | Все предыдущие; AC-028, AC-032–033 |

Эталоны берутся независимо из §12.4 и fixtures; полные source contracts и таблицы здесь не дублируются. Допуск ratio — `0.0001`; часы/counts/boolean/status — точные; SQL NULL и типы проверяются отдельно. Current и historical reads одного snapshot дополнительно сравниваются точно.

Исходные batch_1/batch_2, Gold SQL и старые tests не меняются. Staged H0 проверяется предназначенными для этого assertions, а не полными baseline assertions, ожидающими уже загруженный batch_2. После batch_2 и в финальном состоянии обязателен полный baseline dbt build. Учебная история должна пережить повторный source build.

## 6. Приёмка, команды и evidence

### Быстрые локальные проверки

**Существующая команда**, не выполнявшаяся в bootstrap:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/tests -v
```

После добавления TT-тестов discovery должен находить **непустой набор именно новых тестов**. Нужны положительные и mutation cases: неверные типы/NULL, перепутанные snapshots, потеря миллисекунд, ложный negative PASS при connection error, изменение metadata/files, неполный manifest и неуспешный cleanup. Существующий partitioning suite не подтверждает Time travel AC.

### Итоговая приёмка

**Предлагаемый интерфейс, ещё не реализован:**

```bash
python3 scripts/run_time_travel_acceptance.py --run-id <fresh_run_id>
```

Команда требует будущего отдельного поручения на реализацию/выполнение и доступной среды с pinned stack. Потребность в .env/credentials проверяется без вывода значений; локальные секреты не должны попадать в команды и evidence.

| AC | Проверка / команда внутри будущего workflow | Ожидаемый результат | Evidence |
| --- | --- | --- | --- |
| **AC-028** | Fingerprints, runtime allowlist, catalog pointers и bounded object inventories до/после | Старые контракты и не принадлежащие задаче объекты неизменны; Hbad только в учебной таблице | Path-scoped hashes/diff, listings, metadata pointers, при необходимости regression summaries |
| **AC-029** | ID/time queries, typed expected-row assertions, metadata comparison | Правильные H0/H1/Hbad; пять timestamp cases; чтения не меняют current и metadata/files | SQL, typed results, expected comparisons, mapping IDs/timestamps, P3 event_at/received_at |
| **AC-030** | Rollback, current-vs-H1, три historical reads, полный file inventory | Duration=36, поздние события сохранены, Hbad читается; четвёртого data snapshot и новых data/delete files нет | Current metadata, snapshots/history, schema IDs, rows, file path/size/checksum inventory |
| **AC-031** | Два ошибочных чтения и ошибочный rollback | Нужный класс ошибки и неизменность состояния после каждой операции; без fallback | Non-zero exit codes, содержательная диагностика, отдельные полные before/after comparisons |
| **AC-032** | Staged loader/dbt logs, source projections, финальный baseline build | Реальные H0/H1; source Gold корректен даже при Hbad в учебной таблице; история учебной таблицы не заменена | Staged commands, run_results, source queries, независимые ожидаемые строки |
| **AC-033** | Summary, manifest, secret scan, cleanup и environment assertions | Все gates выполнены; собственные schemas и все их объекты удалены; чужие tables/volumes сохранены; lifecycle восстановлен | Catalog/storage evidence, command log, manifest, secret scan, post-cleanup listings, environment comparison |

Отрицательная SQL-операция считается успешной проверкой только при нужной содержательной причине отказа и выполненных invariants; connection/syntax error не заменяет ожидаемую ошибку недоступной версии. Fault injection `36 → 360` — успешная запись, а не ожидаемый SQL failure.

Evidence сохраняется только в предусмотренном `artifacts/acceptance/<run-id>/`. Summary получает PASS **после** завершения всех gates. Заглушка с exit 0, пустой набор тестов, запуск процессов или текстовый отчёт не подтверждают AC.

Cleanup охватывает собственные source schemas, учебную schema и все их object prefixes, включая historical Hbad и delete files. Перед удалением проверяются ownership и точные разрешённые locations. Snapshot expiration, orphan cleanup и compaction не выполняются; volumes не удаляются. Остатки и ошибки cleanup исключают PASS.

### Регрессия завершённых срезов

Без shared changes полные старые acceptance повторять не требуется; staged core builds и финальный baseline build остаются обязательными. Если shared path всё же изменится, обязательны существующие runners каждого затронутого среза с отдельными fresh run IDs:

- `python3 scripts/run_acceptance.py --run-id <fresh_core_run_id>`;
- `python3 scripts/run_schema_evolution_acceptance.py --run-id <fresh_schema_run_id>`;
- `python3 scripts/run_partitioning_file_pruning_acceptance.py --run-id <fresh_partition_run_id>`.

Это существующие интерфейсы, а не выполненные команды. Их собственные preflight/lifecycle ограничения нужно соблюдать; автоматическая остановка чужого stack ради регрессии не разрешается. Прежние PASS не заменяют обязательную регрессию после shared change. Предпочтение — оставить shared paths неизменными.

### Приёмка будущего применения обвязки

- Только разрешённый diff: новые TT runner/tests и согласованные точечные README/status дополнения; без изменения завершённых контрактов и конфигурации pi.
- Команды и ресурсы явно доступны либо помечены непроверенными; неизвестная среда не объявляется готовой.
- Никаких разрушительных defaults, удаления чужих ресурсов или автоматических upgrades.
- Повтор с занятым run ID/prefix должен завершаться отказом без записи, а не перетирать evidence или дописывать данные.
- Повторное применение без новых входов не дублирует файлы, задачи и инструкции. Это требование, пока не проверенное.

## 7. Права, пределы и остановка

**Согласованное минимальное предложение:** два новых Python-файла — TT runner и его unit tests; существующий stack, fixtures, модели и старые runners сохранить. Новые пакеты и отдельная агентская обвязка **не нужны**.

**Что разрешено этим запуском:** чтение, ограниченная инвентаризация, техническая документация, запись только этого плана и явно разрешённые пользователем автоматические post-write hooks записи. Настройки pi, trust, credentials, исходники, спецификация, README/status не изменяются.

**Что требует отдельного поручения:** реализация runner/tests, запуск compatibility checkpoint, Docker lifecycle, dbt builds, SQL writes/rollback, запись runtime evidence и cleanup собственных ресурсов. Полномочия будущего workflow должны включать только task-owned schemas/prefixes и допустимое управление собственными сервисами. Установка/скачивание недостающих компонентов не подразумевается молча.

**Не проверены:** Docker daemon, наличие образов, runtime writes/rollback, timestamp boundaries, новый acceptance, идемпотентность, cleanup и восстановление среды TT-1. Probes, сервисы, тесты, сборки и установки агентом отдельно не запускались. Автоматические hooks записи не являются PASS среза.

**Блокер сохранения первоначального плана:** риск post-write hooks был показан пользователю; после отдельного разрешения hooks план сохраняется без изменения конфигурации. Это не подтверждение отсутствия побочных эффектов extensions и не разрешение на выполнение всего среза.

**Точка остановки:** план согласован пользователем и сохранён. Bootstrap 0.1 завершает работу; одобрение плана и разрешение hooks не запускают применение, эксперименты или реализацию. Следующий ограниченный шаг — отдельное поручение на реализацию TT-ENV-001 и TT-IMP-001 с последующей предусмотренной проверкой, без расширения scope.

## 8. Проверка оставшихся работ на 2 ноября 2026 года

Это дополнение подготовлено по поручению проверить незавершённые задачи и запланировать завершение всего проекта. Разделы 1–7 сохраняют исходный согласованный план TT-1 и исторические ограничения того запуска. Текущий контракт TT-1 — [спецификация, раздел 12](spec.md#12-новый-срез-time-travel-и-rollback). Новые задачи maintenance и покрытия компетенций ниже являются предложенным разбиением оставшегося scope; их детальные критерии ещё предстоит определить. Журнал фактического выполнения остаётся только в [docs/status.md](status.md).

### Что завершено и что требует продолжения

| Область | Проверенное состояние | Оставшаяся работа |
| --- | --- | --- |
| Core lakehouse | 13 задач DONE; `imp007_final5/acceptance_summary.json` содержит PASS для AC-001 и AC-003–AC-012 | Сохранить контракты; повторять затронутую регрессию при shared changes |
| Schema evolution | 8 задач DONE; `seimp006_final2/acceptance_summary.json` содержит PASS для AC-013–AC-020 | Сохранить контракты и применимость evidence |
| Partitioning/file pruning | 10 задач DONE; `pfimp006_final/acceptance_summary.json` содержит PASS для AC-021–AC-027 | Сохранить контракты и применимость evidence |
| TT-AGENT-001 | Навигация и запись задачи уже закоммичены в `44eaef7`; в журнале остался REVIEW_READY | Согласовать запись статуса с существующим коммитом, без повторной реализации |
| TT-ENV-001 | Runner и 28 TT-тестов подготовлены; запись REVIEW_READY. Два Python-файла untracked, изменение status не закоммичено | Принять текущий checkpoint; подтвердить среду реальным authenticated checkpoint. Симуляция не подтверждает live integration |
| Остальной TT-1 | Runner реализует только `--check-environment`; полный режим явно отклоняется. TT acceptance evidence отсутствует | TT-ENV-002, TT-PROBE-001, TT-IMP-001–006, TT-DOC-001 |
| Maintenance | Отдельных упражнений/runner и детального контракта нет | Диагностика small files, compaction, snapshot expiration, orphan-file cleanup, evidence и приёмка |
| Полное покрытие компетенций | AC-002 открыт; итоговая матрица отсутствует | Проверить все компетенции из idea, закрыть пробелы и сформировать итоговую трассировку |

Три завершённых среза подтверждены сохранёнными локальными summaries, не новым Docker-прогоном. В этой беседе локальная команда `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/tests -q` прошла 82/82 теста. Это 54 partitioning-теста и 28 TT environment-тестов; результат не подтверждает AC-028–AC-033.

В исходном scope есть компетенция «использовать incremental predicates осознанно». В текущем `dbt_project.yml` задано `materialized: table`; в моделях нет `is_incremental`, `incremental_predicates` или отдельного incremental-упражнения. Этот пробел необходимо разобрать при трассировке AC-002; миграция действующих core-моделей на incremental из этого автоматически не следует.

В текущей среде отсутствует корневой `.env`; предыдущая read-only проверка Docker в этой беседе получила отказ доступа к socket. Перед runtime-задачами исполнитель должен проверить доступ и подготовить локальную учебную конфигурацию из `.env.example`, не выводя credentials. Эти условия не мешают планированию, но не позволяют считать runtime готовым.

### Расхождения документации

- Верхние сводки README/status ещё говорят, что следующий срез не выбран; спецификация раздела 12 и коммиты уже фиксируют TT-1.
- Запись TT-AGENT-001 всё ещё предлагает создать уже существующий коммит.
- Для TT-ENV-001 REVIEW_READY относится к ограниченной задаче подготовки среды; полный TT acceptance остаётся NOT_RUN.

Исправление этих расхождений входит в задачи ниже. Исходный незакоммиченный checkpoint необходимо сохранить и отделить от новых правок.

## 9. Порядок завершения проекта

Выполнять задачи последовательно, по одной через pi implement. Для TT сохраняются существующие ID и AC; новые ID ниже — предлагаемые задачи планирования, не заявления о выполнении. Даты и длительности реализации не назначены: они зависят от доступности Docker и результатов runtime-проверок.

### Этап 1 Закрыть текущий checkpoint и подготовить TT runtime

| Задача | Зависимость | Результат и условие завершения |
| --- | --- | --- |
| Принятие TT-ENV-001 и сверка TT-AGENT-001 | Текущее рабочее дерево | Проверены все три файла checkpoint и применимость review/evidence; запись TT-AGENT-001 ссылается на `44eaef7`. После решения пользователя checkpoint получает отдельный коммит. До этого новые задачи не смешиваются с существующим diff |
| Live-проверка TT-ENV-001 | Доступ к Docker, локальная конфигурация, pinned images | Существующая команда `python3 scripts/run_time_travel_acceptance.py --run-id tt_env_live_001 --check-environment` с новым ID подтверждает allowlist и восстановление среды; сохранён `environment_checkpoint.json`. `ENVIRONMENT_READY` не выдаётся за PASS TT-1. При занятом ID выбрать другой, не перезаписывать evidence |
| TT-ENV-002 | Принятый TT-ENV-001 | TT-specific manifest/checksums, snapshot/state inventories, before/after comparisons, cleanup и финальные AC gates. Cleanup охватывает только собственные schemas/prefixes, включая historical/delete files; volumes сохранены. Unit/mutation cases отклоняют неполное evidence, ложный negative PASS и ошибки cleanup. Неполный workflow не получает общий PASS |
| TT-PROBE-001 | TT-ENV-002 и рабочая среда | Ограниченный эксперимент из §4: три snapshots, timestamp separation и rollback без четвёртого data snapshot. Hbad остаётся читаемым; исторические data/delete files не меняются от rollback. Можно встроить checkpoint в первый runtime-этап, сохранив отдельное evidence; AC основного сценария этим не закрываются |

Сначала нужен безопасный сбор evidence и cleanup, затем probe с записью данных. Все новые runs используют свободные ID и task-owned locations. Работающий чужой stack не останавливается; неизвестное или частичное состояние требует отказа до мутаций.

### Этап 2 Завершить согласованный Time travel

| Задача | Зависимость | Реализация и приёмка |
| --- | --- | --- |
| TT-IMP-001 | TT-ENV-001–002, compatibility checkpoint | Реальный batch_1 → staged Gold → typed H0 по §12.4; одна учебная таблица, четыре уникальных package rows, независимый эталон и корректные SQL NULL. AC-032 в пределах этапа |
| TT-IMP-002 | TT-IMP-001 | Batch_2 → проверенный H1; один commit обновляет три метрики P3, следующий меняет только duration 36 → 360. Ровно H0 → H1 → Hbad с parent links; source Gold остаётся H1. AC-029/032 в пределах этапа |
| TT-IMP-003 | TT-IMP-002 | Три ID-read и пять успешных timestamp cases из §12.5 до rollback. Времена из metadata в UTC с миллисекундами; чтения сохраняют current, metadata и files. Сохранены event_at/received_at P3 для объяснения поздних событий. AC-029 |
| TT-IMP-004 | TT-IMP-003 | Две ошибочные historical query и ошибочный rollback из §12.6; отсутствующий положительный BIGINT ID проверен по metadata. После каждой операции отдельное сравнение полного состояния; network/syntax error не считается ожидаемой ошибкой версии. AC-031 |
| TT-IMP-005 | TT-IMP-003–004 | Rollback к H1: current duration=36, поздние метрики сохранены, H0/H1/Hbad читаются по ID. History показывает H0 → H1 → Hbad → H1; четвёртого data snapshot и новых data/delete files нет. Проверяются реальные checksums всех исторических файлов. AC-030 |
| TT-IMP-006 | Все предыдущие TT-задачи | Полный runtime от staged source до финального baseline dbt build; isolation, AC-028–AC-033, evidence manifest, secret scan, cleanup и восстановление среды. Общий PASS выставляется после всех gates; любая ошибка cleanup исключает PASS |
| TT-DOC-001 | Итоговый TT PASS | Документировать фактический CLI и пример результата, retained run ID, команды чтения/rollback и ограничения. Обновить README и текущую сводку status; завершённые записи сохранять. Проверить ссылки и соответствие утверждений summary |

TT-IMP-004 намеренно поставлен после TT-IMP-003: базовый план допускает обе задачи после TT-IMP-002, но последовательный порядок упрощает проверки перед rollback. Отдельные intermediate задачи подтверждают свои результаты, не общий PASS среза.

Предлагаемый полный интерфейс `python3 scripts/run_time_travel_acceptance.py --run-id <fresh_run_id>` пока не реализован. Он становится runnable и документируемым только после реализации workflow. Branches/tags и timestamp semantics после rollback не добавляются: DEC-036 и §12.5 исключают их из обязательств TT-1.

### Этап 3 Детализировать и выполнить maintenance

Maintenance обязателен по idea/spec, но его подробные критерии ещё не утверждены. Следующие задачи образуют предложение отдельного упражнения после TT; numerical thresholds, retention и SQL capabilities нужно определить в спецификации по pinned stack до destructive probes. Числовые AC-ID назначаются при детализации, а не выдумываются в журнале.

| Предлагаемая задача | Зависимость | Результат и планируемая проверка |
| --- | --- | --- |
| MA-SPEC-001 | TT-DOC-001 | Отдельный контракт maintenance в spec: disposable tables, независимый эталон, workload small files, ожидаемое изменение topology, retention, границы удаления, negative cases и evidence. Явно разрешить вопрос orphan cleanup из README, сохранив исходные обязательства small files/expiration/compaction |
| MA-BOOT-001 | MA-SPEC-001 | Bootstrap с точными задачами, проверками и allowlist; определить поддержку операций/ограничения pinned версий по первичной документации. Назначить отдельные paths и схему evidence; контракты core/TT не менять |
| MA-ENV-001 | MA-BOOT-001 | Подготовка isolated runtime, ownership, snapshots/object inventories, сохранение посторонних ресурсов, cleanup при ошибках и явные AC gates. Collision/mutation tests подтверждают отказ до записи и удаления |
| MA-IMP-001 | MA-ENV-001 | Детерминированно получить small-files workload; измерить file count/size distribution и логический result set. Metadata и object inventory подтверждают проблему; конкретные пороги берутся из MA-SPEC-001 |
| MA-IMP-002 | MA-IMP-001 | Compaction только учебной таблицы: результат строк и типов неизменен, topology улучшилась по согласованному критерию. Сравнить before/after files, snapshots и scan evidence; wall time сам по себе не определяет PASS |
| MA-IMP-003 | MA-IMP-002 | Snapshot expiration с утверждённым retention: заранее выбранные retained snapshots/current остаются читаемыми, выбранные expired versions недоступны. Проверить references, data/delete files и отсутствие удаления файлов, нужных retained history. Не ослаблять глобальные retention defaults ради теста |
| MA-IMP-004 | MA-IMP-003 | Orphan-file exercise, если включён в MA-SPEC-001: создать известный unreferenced object в собственном location, выдержать согласованные ограничения возраста, удалить только допустимые orphan objects. Ни один referenced или чужой object не исчезает |
| MA-IMP-005 | MA-IMP-001–004 | Полный maintenance acceptance: exact results, topology/retention/reference invariants, negative cases, evidence/secret scan, isolation, cleanup и восстановление среды; затронутая регрессия |
| MA-DOC-001 | Maintenance PASS | Учебные команды, наблюдённые результаты, ограничения retention и предупреждение о потере доступности expired versions; актуальные README/status и ссылки на evidence |

Maintenance запускается на собственных disposable данных. Удалять snapshots/files учебной TT-таблицы ради доказательства maintenance нельзя: это нарушит независимость упражнений. Недоступный безопасный сценарий retention означает необходимость пересмотреть технический план до записи/удаления; он не разрешает менять глобальную конфигурацию без согласования.

### Этап 4 Закрыть пробелы компетенций и AC002

| Предлагаемая задача | Зависимость | Результат и условие завершения |
| --- | --- | --- |
| COV-001 | Можно начать после текущего checkpoint | Проверить все 14 компетенций из idea: компетенция → exercise/code/query → критерий → evidence. Использовать существующие core/SE/PF результаты; отдельно отметить TT, maintenance и incremental predicates. Для каждого пробела назначить задачу без повторной реализации уже подтверждённого |
| INC-SPEC-001 | COV-001 | Определить минимальное проверяемое задание для осознанного применения incremental predicates. Предпочтительно отдельное упражнение/модель в task-owned schemas; core остаётся table. Зафиксировать incoming и target predicates, обработку received_at/event_at, поздних событий, дублей, безопасного lookback и независимый full-rebuild эталон. Если существующие материалы действительно закрывают навык, указать проверяемое основание вместо добавления реализации |
| INC-IMP-001 | INC-SPEC-001, если выявленный пробел требует реализации | Выполнить изолированное упражнение: batch_1/batch_2, late events, повтор batch без дублей, сравнение incremental результата с независимым эталоном/full rebuild. Показать, как слишком узкий predicate теряет позднее событие или создаёт дубль, затем корректный вариант. Проверить реальные scan/predicate evidence по принятому контракту, cleanup и isolation; не объявлять SQL merge в TT достаточным доказательством dbt incremental predicates |
| FINAL-001 | TT-DOC-001, MA-DOC-001, закрытые пробелы COV-001/INC | Завершить матрицу AC-002: каждый навык имеет воспроизводимое задание и применимое evidence; в spec/README/status нет незакрытого обязательного scope или противоречивых сводок. PASS AC-002 возможен только после полного scope |
| FINAL-002 | FINAL-001 | Итоговая проверка documented workflows и всех mandatory AC, сохранности старых контрактов, manifests и чистоты task-owned runtime. Проверить применимость прежних PASS; повторить затронутую регрессию. Согласованные checkpoints приняты/закоммичены; проект больше не содержит незавершённой задачи, скрытой под REVIEW_READY |

COV-001 можно подготовить раньше maintenance, чтобы уточнить объём работ. Выполнение остаётся последовательным; это не поручение запускать параллельных агентов. Full production orchestration, CDC, новые бизнес-домены и миграция всего проекта на incremental не входят в этот план.

### Общие правила выполнения и финальная приёмка

Каждый запуск pi implement получает один точный TASK_ID, источник/раздел, разрешённые файлы, AC и точку остановки. После PRECHECK основной агент ведёт секцию в `docs/status.md`, выполняет affected checks, получает предусмотренный skill независимый review и оставляет проверяемый checkpoint. Staging/commit выполняются после решения пользователя; принятие одной задачи предшествует старту следующей. Пункты принятия checkpoint и подготовки runtime не являются отдельными заявлениями об implement/review.

Для TT основной scope изменений — два существующих новых Python-файла и согласованные документационные дополнения. Для maintenance и incremental пути фиксируются их будущими spec/bootstrap. Baseline fixtures, бизнес-правила, core models, pinned dependencies и старые runners сохраняются; необходимость shared changes должна быть явно обоснована и сопровождаться затронутой регрессией.

Окончательное завершение проекта требует одновременно: применимых PASS AC-001–AC-033, критериев нового maintenance/инкрементального упражнения по их принятым контрактам, полной матрицы AC-002, согласованной документации и успешной проверки cleanup. Старые срезы не требуют автоматического повторного многоминутного прогона при неизменных shared paths; изменения evidence или контрактов требуют affected revalidation. Наличие только unit-test PASS и review OK этих условий не заменяет.

**Первый следующий шаг:** принять существующий трёхфайловый checkpoint TT-ENV-001 и согласовать историческую запись TT-AGENT-001 с коммитом `44eaef7`; затем проверить доступную среду и выполнить live checkpoint перед TT-ENV-002. Это дополнение фиксирует планирование; оно не запускает реализацию или Docker workflow.

## 10. Завершение плана

План завершения проекта выполнен 2026-11-02. Все шесть срезов имеют принятую интеграционную приёмку; `project_final_001` подтверждает 45 AC и 14 компетенций. Фактические коммиты и task evidence находятся в [status](status.md), команда повторной проверки — в [README](../README.md#completion-and-verification). Разделы выше сохраняют исторические состояния планирования; незавершённого обязательного scope по этому плану нет.
