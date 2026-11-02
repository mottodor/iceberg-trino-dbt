# План выполнения maintenance

Контракт: [spec §13](spec.md#13-maintenance), AC-034–AC-040. Основание исполнения — поручение пользователя завершить весь проект от 2026-11-02. Старые срезы и global retention defaults сохраняются. Этот файл описывает порядок и критерии; фактические состояния задач ведутся только в [status](status.md).

## Последовательность

| Задача | Зависимость | Проверяемый результат |
|---|---|---|
| MA-SPEC-001 | TT-DOC-001 | Контракт и независимые expected sets зафиксированы до записи данных |
| MA-BOOT-001 | MA-SPEC-001 | Этот план, пути изменений, интерфейсы и gates |
| MA-ENV-001 | MA-BOOT-001 | Новый общий слой isolated exercise с точной одной schema/location; reuse проверенного TT lifecycle без изменения старых runners; mutation tests ownership/manifest/finalization |
| MA-IMP-001 | MA-ENV-001 | CTAS + 15 INSERT: 2048 строк, 16 snapshots, минимум 16 файлов <1 MiB; typed oracle, size distribution, EXPLAIN ANALYZE |
| MA-IMP-002 | MA-IMP-001 | optimize уменьшает current files минимум вдвое, строки и historical reads/checksums сохранены |
| MA-IMP-003 | MA-IMP-002 | Append до 2176 строк; атомарный default-retention отказ; session-only override и retain_last=2; expired ID недоступен, оба retained читаются, obsolete data удалены |
| MA-IMP-004 | MA-IMP-003 | Атомарный default orphan-retention отказ; old/young/outside markers; aged marker удалён, все referenced файлы и остальные markers сохранены; defaults прежние |
| MA-IMP-005 | MA-IMP-001–004 | Свежий полный CLI run, replay, все AC PASS, manifest/secret scan, cleanup/изоляция и restored environment |
| MA-DOC-001 | MA-IMP-005 | README с фактическими командами, результатами и ограничениями retention; status сверяется с коммитами |

После каждого этапа — отдельный коммит. Для разработки допустим один owned runtime с остановкой между проверенными этапами; перед финальной приёмкой выполняется свежий самостоятельный run на окончательном коде.

## Файлы и интерфейсы

- `scripts/learning_exercise.py`: lifecycle adapter, single-schema allowlist, snapshot/storage evidence и общие final gates.
- `scripts/run_maintenance_acceptance.py`: конкретный workload и maintenance операции.
- `scripts/tests/test_learning_exercise.py`, `scripts/tests/test_maintenance_acceptance.py`: positive/mutation tests, не запускающие Docker.
- `docs/spec.md`, этот план, `README.md`, `docs/status.md`: контракт, команды и evidence.
- Предлагаемый CLI: `python3 scripts/run_maintenance_acceptance.py --run-id <fresh_id>`. Он объявляется реализованным после MA-IMP-005. Unit command: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/tests -q`.

Единственная mutable schema — `<run_id>_maintenance`; таблицы `maintenance_events` и `control`. Marker keys ограничены этим exact prefix. Session overrides передаются только двум разрешённым maintenance-командам; global properties, Compose и credentials не изменяются. Обычный SHOW SESSION до/после подтверждает defaults.

## Gates

До первого write проверяются свободный run ID, отсутствие schemas/objects, точный catalog storage и ownership сервисов. Сначала дешёвые unit/mutation checks, затем затронутый live stage. Операции с чужой schema/location либо неизвестным состоянием отклоняются до мутации.

После каждого поведения сохраняются raw SQL/results, authoritative catalog metadata плюс S3 copy, complete object inventories/content SHA-256, current files, snapshots/history и control signature. Snapshot expiration проверяет retained references, orphan cleanup — реальные storage timestamps и границу table location. Неожиданный network/syntax failure не заменяет ожидаемый negative PASS.

Общий PASS требует всех AC-034–AC-039, полноты/replay evidence, корректного manifest, отсутствия секретов, cleanup всех task-owned schemas/objects, неизменности foreign resources и восстановления lifecycle без удаления volumes. Ошибка cleanup исключает PASS. Старые business fixtures, модели, runners/tests и зависимости остаются неизменными; при shared implementation change нужна затронутая регрессия.
