# Task status

## TASK_ID: PROBE-001

- Source: `docs/bootstrap.md`, section 4.4, “PROBE-001 — совместимость pinned stack”
- Status: REVIEW_READY
- Updated: 2026-10-29T10:23:25+03:00
- Baseline HEAD: 0e0049d77b9995a8dfd3dd81d1c0a1a51b5c2827

### Progress
- Implemented: the isolated pinned stack started healthy; OAuth token acquisition succeeded; Trino 484 created `probe001.smoke`, inserted and read one exact row; Polaris/Trino listings succeeded; RustFS contains only the project bucket with seven Iceberg data/metadata objects under the `probe001/` prefix; the corrected missing-table negative assertion passed; the Compose project was stopped and removed while its named RustFS volume was preserved.
- Remaining: none.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/bootstrap.md` §4.4 PROBE-001, expected signal: service health and OAuth token | PASS | acceptance: `docker compose up -d --wait --wait-timeout 240` exited 0 in 34 seconds; RustFS, Polaris, setup, and Trino reported healthy; independent token request asserted `oauth_token_present=yes`. |
| `docs/bootstrap.md` §4.4 PROBE-001, expected signal: `CREATE TABLE`, `INSERT`, `SELECT` | PASS | acceptance: Trino CLI 484 completed `CREATE SCHEMA`, `CREATE TABLE`, `INSERT: 1 row`, and `SELECT`; exact assertion returned `true` for one row `(1, 'pinned-stack-ok')`. |
| `docs/bootstrap.md` §4.4 PROBE-001, additional signal: Iceberg metadata/data objects and Polaris/Trino listing | PASS | acceptance: Polaris management listed `quickstart_catalog`; Trino listed `probe001.smoke`; RustFS listed only `probe001-bucket` and seven Iceberg data/metadata objects (21,764 bytes) under `probe001/`. |

### Issues
#### PROBE-001/B01
- State: RESOLVED
- Category: ENVIRONMENT
- Affects: `docs/bootstrap.md` §4.4 PROBE-001 and mandatory EVIDENCE_GATE
- Problem: the required Docker CLI/runtime was not accessible from this WSL distribution, so the pinned-stack compatibility experiment could not run.
- Evidence: the previous attempt observed both Docker commands exit 1 with a Docker Desktop WSL integration error.
- Unblock: provide an accessible Docker Engine and Compose in this WSL distribution.
- Resolution: `docker version --format 'client={{.Client.Version}} server={{.Server.Version}}'` exited 0 with `client=29.8.0 server=29.8.0`; `docker compose version` exited 0 with `v5.5.1`.

#### PROBE-001/B02
- State: RESOLVED
- Category: ENVIRONMENT
- Affects: `docs/bootstrap.md` §4.4 PROBE-001 acceptance environment
- Problem: the first pinned-image pull was interrupted by a registry connection failure before the stack could start.
- Evidence: `docker compose pull` exited 1 after 321 seconds with an EOF while reading a Trino layer; only `amazon/aws-cli:2.36.44` was then present as a complete tagged image.
- Unblock: restore registry connectivity and rerun the same pinned-image pull without changing versions.
- Resolution: after the user reported connectivity restored, `docker compose pull --quiet` exited 0 in 1092 seconds; all five tags are present and the three specified digests match the bootstrap plan.

#### PROBE-001/B03
- State: RESOLVED
- Category: TEST
- Affects: mandatory EVIDENCE_GATE negative assertion
- Problem: the first negative-table assertion expected the symbolic text `TABLE_NOT_FOUND`, but Trino CLI 484 emitted only the equivalent human-readable “Table ... does not exist” message.
- Evidence: the missing-table query exited 1 with the correct missing-table message, while the wrapper exited 1 because its grep expected a symbolic error code absent from CLI output.
- Unblock: match the observed Trino CLI message and still require a non-zero query exit.
- Resolution: the corrected assertion required exit 1 plus the exact “Table 'polaris.probe001.missing_table' does not exist” message and passed.

### Review
- Verdict: OK
- Calls: 2
- Fix iterations: 1
- Details: the first fresh read-only reviewer returned `VERDICT OK` for the pinned-stack evidence, scope, cleanup, temporary configuration, and repository diff, with one non-blocking editorial synchronization improvement. After the status-only fix, a second fresh targeted reviewer found no BLOCKER, DEFERRED, or IMPROVEMENT and returned `VERDICT OK`.

### Next action
User authorized staging and committing this reviewed checkpoint; no push or transition to another task is authorized.

## TASK_ID: PROBE-002

- Source: `docs/bootstrap.md`, section 4.4, “PROBE-002 — dbt adapter handshake”
- Status: REVIEW_READY
- Updated: 2026-10-29T11:22:09+03:00
- Baseline HEAD: 0fe79f1897e1310b35265c29e908b718c9493f05

### Progress
- Implemented: added the pinned Python dbt image definition, hash-locked dependency set, environment-driven Trino profile, one smoke model, and one exact-row singular test; the final image builds with Git, reports exact versions, parses one model/test, passes `dbt debug`, creates the Iceberg table, and passes the test. A deliberate extra-row mutation produced the intended named test failure; after enabling task-owned Polaris purge support, the model/test were restored and passed again. Trino showed one exact row and only the smoke schema/table; RustFS showed five Iceberg objects under the smoke prefix.
- Remaining: none.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/bootstrap.md` §4.4 PROBE-002, expected signal: exact dbt versions | PASS | acceptance: final rebuilt image `dbt --version` exited 0 and reported dbt Core `1.11.11` and Trino plugin `1.10.2` exactly. |
| `docs/bootstrap.md` §4.4 PROBE-002, expected signal: successful connection | PASS | acceptance: final rebuilt image `dbt debug` exited 0 with valid profile/project, Git dependency found, Trino adapter `1.10.2`, `[OK connection ok]`, and `All checks passed!`. |
| `docs/bootstrap.md` §4.4 PROBE-002, expected signal: smoke model and test | PASS | acceptance: final-state `dbt run --select probe002_smoke` exited 0 with `CREATE TABLE (1 rows)` and `dbt test --select assert_probe002_smoke` exited 0 with exactly one PASS; Trino returned only `(1, 'dbt-adapter-ok')`, only schema/table `probe002_smoke`, and RustFS contained five objects (14,800 bytes) under that prefix. Mutation probe inserted an extra row and the wrapper passed only after dbt exited 1 with `FAIL 2 assert_probe002_smoke`; rerun restored the final PASS. |
| `docs/bootstrap.md` §4.4 PROBE-002, cleanup | PASS | acceptance: `DROP SCHEMA polaris.probe002_smoke CASCADE` exited 0; follow-up checks found no smoke schema and zero objects under its RustFS prefix while the project bucket remained. `docker compose down` exited 0, removed only task-owned containers/network, and preserved `iceberg-trino-dbt-probe002_rustfs-data`; the pre-existing PROBE-001 volume was untouched. |

### Issues
#### PROBE-002/B01
- State: RESOLVED
- Category: TEST
- Affects: mandatory fast-check and EVIDENCE_GATE before runtime acceptance
- Problem: the first containerized parse command used unsupported dbt global option `--target-path`, so project parsing did not execute.
- Evidence: `dbt ... --target-path /tmp/target parse ...` exited 2 with `No such option '--target-path'` under dbt Core 1.11.11.
- Unblock: direct dbt artifacts with supported project configuration/environment and rerun parse before stack acceptance.
- Resolution: `DBT_TARGET_PATH=/tmp/target dbt parse` exited 0; `dbt ls --select probe002_smoke assert_probe002_smoke --output name` exited 0 and reported exactly one model and one test.

#### PROBE-002/B02
- State: RESOLVED
- Category: ENVIRONMENT
- Affects: `docs/bootstrap.md` §4.4 PROBE-002 connection/model/test acceptance
- Problem: the first isolated stack start stopped before Polaris/Trino because Compose split the temporary bucket bootstrap shell command into AWS CLI arguments.
- Evidence: `docker compose ... up -d --wait` exited 1 in 7 seconds; `bucket-setup` exited 252 with AWS CLI `the following arguments are required: command`; container inspection showed the shell command had been split into `Cmd` words.
- Unblock: encode the temporary bucket bootstrap as one shell argument, recreate only the failed task-owned containers, and rerun the same isolated stack.
- Resolution: after encoding each bootstrap script as one shell argument, `docker compose ... up -d --wait --wait-timeout 240` exited 0 in 31 seconds; RustFS, Polaris, and Trino became healthy and both setup jobs completed successfully.

#### PROBE-002/B03
- State: RESOLVED
- Category: CODE
- Affects: `docs/bootstrap.md` §4.4 PROBE-002 expected successful `dbt debug`
- Problem: the first runtime `dbt debug` connected successfully to Trino but exited non-zero because the execution image omitted dbt's required `git` executable.
- Evidence: containerized `dbt debug` reported valid project/profile, adapter `1.10.2`, and `[OK connection ok]`, then exited 1 with `Could not find command ... git`.
- Unblock: add the minimal Git runtime package to the dbt image, rebuild it, and rerun version/parse/debug checks before model acceptance.
- Resolution: added the minimal Git runtime package, rebuilt the image, then reran `dbt --version`, `dbt parse`, and networked `dbt debug`; all exited 0 and debug ended with `All checks passed!`.

#### PROBE-002/B04
- State: RESOLVED
- Category: ENVIRONMENT
- Affects: final-state model/test evidence and mandatory cleanup
- Problem: after the successful mutation test, rerunning the table model failed while dbt attempted to drop its Iceberg backup relation, so the smoke schema is not yet restored to a verified final state.
- Evidence: the restoration `dbt run --select probe002_smoke` exited 1 with Trino `ICEBERG_CATALOG_ERROR: Failed to drop table 'probe002_smoke__dbt_backup'` after the initial model and positive test had passed and the mutation correctly produced `FAIL 2 assert_probe002_smoke`.
- Unblock: inspect the Trino/Polaris error and current relation state, apply the minimal environment/profile correction or targeted cleanup within the task-owned smoke schema, then rerun model and test before final cleanup.
- Resolution: Polaris logs showed the task-owned catalog rejected dbt's backup-table purge with HTTP 403 because `polaris.config.drop-with-purge.enabled` was absent. Updating that catalog property, dropping only the smoke backup table, and rerunning the model/test produced exit 0; Trino then returned the one expected row and one smoke table.

### Review
- Verdict: OK
- Calls: 1
- Fix iterations: 0
- Details: one fresh read-only reviewer inspected the full tracked/untracked diff, every new file including the hash lock, `docs/status.md`, the PROBE-001 section boundary, source AC, and supplied runtime evidence; it found no BLOCKER or IMPROVEMENT and returned `VERDICT OK`. DEFERRED: BOOT-ENV-002 must persist `polaris.config.drop-with-purge.enabled=true` and verify two consecutive table materializations; the reviewer confirmed this is not a PROBE-002 blocker.

### Next action
After committing this user-authorized reviewed checkpoint, await separate authorization for push or transition to another task.

## TASK_ID: PROBE-003

- Source: `docs/bootstrap.md`, section 4.4, “PROBE-003 — геодезические ожидания fixtures”; `docs/spec.md`, DEC-020 and DEC-024
- Status: REVIEW_READY
- Updated: 2026-10-29T12:11:56+03:00
- Baseline HEAD: af47c524d9a8984eb401f4c5f84845f9145f43e9

### Progress
- Implemented: added a reusable dbt macro for Trino spherical-geography distance and a SQL-only singular test for both planned routes, the P2 actual route, metre units, and coordinate order; dbt parse/selection and the final Trino 484 test passed. Ratio and longitude/latitude mutations produced the intended named failure/error. The task-created Trino container and network were removed, no tables were created, and the pre-existing PROBE-001/002 volumes were preserved.
- Remaining: none.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/bootstrap.md` §4.4 PROBE-003, planned distances `A→B→C` and `A→D→C` differ by at most 1 metre | PASS | acceptance: Trino 484 returned `222390.20235496786` metres for both plans and a `0.0` metre difference; the final singular dbt test exited 0 with one PASS. |
| `docs/bootstrap.md` §4.4 PROBE-003, P2 actual/planned ratio is `1.5` within 0.01 percentage point tolerance | PASS | acceptance: Trino 484 returned actual distance `333585.3035324518` metres, ratio `1.5`, and `150.0%`; changing the detour point in a temporary project made the named test return `FAIL 1` and dbt exit 1. |
| `docs/bootstrap.md` §4.4 PROBE-003, no `NULL`, geography error, or longitude/latitude reversal | PASS | acceptance: the final test exited 0; the asymmetric sentinel returned `109505.75582500256` metres. Swapping longitude/latitude in a temporary macro made the named test error with Trino `INVALID_FUNCTION_ARGUMENT: Latitude must be between -90 and 90`, and the wrapper confirmed exit 1. |

### Issues
none

### Review
- Verdict: OK
- Calls: 1
- Fix iterations: 0
- Details: one fresh read-only reviewer inspected the complete tracked/untracked diff, source contracts, macro, singular test, runtime and mutation evidence, status consistency, and unchanged PROBE-001/002 sections; it found no BLOCKER, DEFERRED, or IMPROVEMENT and returned `VERDICT OK`.

### Next action
User authorized staging and committing this reviewed checkpoint; no push or transition to another task is authorized.
