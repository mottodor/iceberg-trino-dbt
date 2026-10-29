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

## TASK_ID: BOOT-ENV-001

- Source: `docs/bootstrap.md`, section 5.2, “BOOT-ENV-001 — Compose stack”
- Status: REVIEW_READY
- Updated: 2026-10-29T12:27:04+03:00
- Baseline HEAD: 527f47374615061716593c84789bf596def0ab52

### Progress
- Implemented: added root `compose.yaml` with the RustFS, Polaris, Trino, and on-demand dbt services, project-scoped network/volume, health-gated dependencies, resource limits, and pinned images/build inputs; rendered and mutation assertions passed; the default stack reached healthy state and was stopped while its named RustFS volume and both pre-existing probe volumes were preserved.
- Remaining: none.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/bootstrap.md` §5.2 BOOT-ENV-001, required Compose artifacts | PASS | fast: rendered JSON assertion passed for the exact four services, project-scoped `iceberg-trino-dbt_lakehouse` network and `iceberg-trino-dbt_rustfs-data` volume, three healthchecks, health-gated dependency chain, per-service CPU/memory limits, and the on-demand `tools` profile. |
| `docs/bootstrap.md` §5.2 BOOT-ENV-001, `docker compose config` and pinned images | PASS | fast: `docker compose --profile tools config --quiet` exited 0; image assertion found the three exact tag+digest runtime pins plus versioned local dbt image and no `latest` reference. |
| `docs/bootstrap.md` §5.2 BOOT-ENV-001, health-gated startup semantics | PASS | standard: `docker compose up -d --wait --wait-timeout 240 rustfs polaris trino` exited 0 in 37 seconds and started dependencies in RustFS → Polaris → Trino order; all three containers were healthy on the project network with the declared runtime limits, host endpoint probes returned HTTP 200 when bypassing the shell proxy, and a condition mutation was detected by the gate assertion. |

### Issues
#### BOOT-ENV-001/B01
- State: RESOLVED
- Category: TEST
- Affects: mandatory fast-check and EVIDENCE_GATE
- Problem: the first validation harness did not include the profiled dbt service and invoked an unavailable `python` alias, so the complete structure/image assertions did not execute successfully.
- Evidence: the image wrapper exited 1 after listing only the three default-profile runtime images; the JSON structure wrapper exited 127 with `python: command not found`.
- Unblock: rerun with `docker compose --profile tools config` and the available `python3` binary.
- Resolution: rerunning with `docker compose --profile tools config` and `python3` made both the complete image assertion and JSON structure assertion exit 0.

#### BOOT-ENV-001/B02
- State: RESOLVED
- Category: TEST
- Affects: `docs/bootstrap.md` §5.2 BOOT-ENV-001 health-gated startup evidence
- Problem: the first post-start inspection omitted the required Compose interpolation environment, and the combined host endpoint probe did not identify which URL failed.
- Evidence: the inspection wrapper emitted missing-variable errors and empty container IDs; the endpoint wrapper exited 22 without its success marker, while the preceding `docker compose up -d --wait` had exited 0 after all three services became healthy.
- Unblock: rerun Compose inspection with the same local test environment and probe each endpoint separately before deciding which evidence is applicable.
- Resolution: exporting the required local test variables made runtime inspection succeed for all containers; individual endpoint probes showed the shell proxy caused the misleading 403 responses, and `curl --noproxy '*'` returned HTTP 200 for both RustFS endpoints and Trino `/v1/info`.

### Review
- Verdict: OK
- Calls: 1
- Fix iterations: 0
- Details: one fresh read-only reviewer inspected the complete tracked/untracked diff, all of `compose.yaml`, the BOOT-ENV-001 source and status section, unchanged prior task sections, supplied runtime/config/mutation/cleanup evidence, scope boundaries, resource limits, credentials handling, and compatibility with BOOT-ENV-002/004; it found no BLOCKER, DEFERRED, or IMPROVEMENT and returned `VERDICT OK`.

### Next action
User reviews the checkpoint and, if accepted, stages and commits `compose.yaml` and `docs/status.md`; no push or next-task transition is authorized.

## TASK_ID: BOOT-ENV-002

- Source: `docs/bootstrap.md`, section 5.2, “BOOT-ENV-002 — конфигурация Trino/Polaris/RustFS”
- Status: REVIEW_READY
- Updated: 2026-10-29T13:05:38+03:00
- Baseline HEAD: 540fc19b1f77b3e34c3a9877345e87615a5be948

### Progress
- Implemented: added project-scoped RustFS bucket and Polaris catalog bootstrap scripts, pinned one-shot setup services, the Trino Iceberg REST/OAuth2/vended-credentials catalog, catalog-level purge support, and the dbt catalog default; a fresh stack started healthy, two consecutive dbt table materializations and the singular test passed, Trino/Polaris/RustFS listings matched, and task objects/containers/network were removed while named volumes were preserved.
- Remaining: none.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/bootstrap.md` §5.2 BOOT-ENV-002, required configuration/bootstrap assets | PASS | fast: shell syntax, `docker compose --profile tools config --quiet`, rendered service/dependency/resource/image assertions, and exact Trino property assertions passed; removing the vended-credentials property made the mutation assertion fail as intended. |
| `docs/bootstrap.md` §5.2 BOOT-ENV-002, REST catalog, OAuth2, vended credentials, and S3-compatible path-style access | PASS | acceptance: the fresh stack became healthy in 37 seconds; Polaris stored the exact S3 endpoint/path-style and `polaris.config.drop-with-purge.enabled=true` catalog properties; two consecutive dbt table runs exited 0 with one row, and the singular test passed. The pre-fix second-run HTTP 403 proved the purge assertion detects the missing catalog property. |
| `docs/bootstrap.md` §5.2 BOOT-ENV-002, PROBE-001 plus catalog/schema/table and object listing | PASS | acceptance: Trino listed `lakehouse`, schema `boot_env_002`, table `probe002_smoke`, and one exact row; Polaris management returned the expected catalog/storage properties; RustFS listed only project bucket `iceberg-trino-dbt` with five final Iceberg data/metadata objects (14,873 bytes) under the task schema prefix. Cleanup dropped the schema, removed that prefix, stopped project services, and preserved all three named RustFS volumes. |

### Issues
#### BOOT-ENV-002/B01
- State: RESOLVED
- Category: TEST
- Affects: mandatory fast-check and EVIDENCE_GATE
- Problem: the first rendered-Compose assertion looked for resource limits under a nonexistent `deploy.resources` key, so the complete static gate did not finish.
- Evidence: the assertion command exited 1 at service `rustfs`; inspection showed Compose renders the configured limits as top-level `cpus` and `mem_limit` fields for all six services.
- Unblock: correct the assertion to inspect the rendered top-level fields and rerun the full static gate.
- Resolution: the corrected assertion checked top-level `cpus` and `mem_limit`; the complete static and vended-credentials mutation gates exited 0.

#### BOOT-ENV-002/B02
- State: RESOLVED
- Category: TEST
- Affects: runtime acceptance evidence collection
- Problem: the combined stack-start wrapper reached a healthy stack but exited non-zero because its Python post-inspection one-liner had invalid quoting.
- Evidence: `docker compose up -d --wait --wait-timeout 240 rustfs polaris trino` completed in 45 seconds with all dependencies healthy/completed, then the inspection one-liner raised `SyntaxError`; direct follow-up showed RustFS, Polaris, and Trino healthy and both setup jobs exited 0.
- Unblock: run a correctly quoted state assertion before continuing acceptance checks.
- Resolution: a file-based JSON assertion verified the three runtime services are running/healthy and both setup jobs exited 0.

#### BOOT-ENV-002/B03
- State: RESOLVED
- Category: TEST
- Affects: repeated dbt table materialization acceptance assertion
- Problem: the first Compose run passed an extra `dbt` token to an image whose entrypoint is already `dbt`, so the model did not execute.
- Evidence: the cached image build completed, then dbt exited 2 with `No such command 'dbt'`.
- Unblock: invoke the service as `... dbt run ...` without the duplicate executable token and rerun the materialization assertion.
- Resolution: the corrected invocation created the one-row model; after the catalog-property fix, two consecutive corrected runs and the named singular test all exited 0.

#### BOOT-ENV-002/B04
- State: RESOLVED
- Category: CODE
- Affects: REST catalog configuration and repeated table materialization acceptance assertion
- Problem: purge support was supplied as a Polaris process environment key, but Polaris 1.8.0 requires `polaris.config.drop-with-purge.enabled` in the catalog properties (or the separate server option `DROP_WITH_PURGE_ENABLED`).
- Evidence: the first dbt run created the table; the second exited 1 with `Failed to drop table 'probe002_smoke__dbt_backup'`; Polaris returned HTTP 403 and explicitly requested the catalog property or server option, while container inspection confirmed the ineffective dotted environment key was present.
- Unblock: move the flag into the catalog creation payload, recreate only the task-owned in-memory catalog/container state, and rerun two consecutive materializations plus the test.
- Resolution: the bootstrap payload now stores the catalog property; a fresh catalog exposed it through the management API, and two consecutive dbt table materializations plus cleanup purge all exited 0.

#### BOOT-ENV-002/B05
- State: RESOLVED
- Category: TEST
- Affects: final Trino row and catalog/object listing evidence
- Problem: the listing wrapper made incorrect assumptions about smoke output formatting and the physical Iceberg path after dbt's rename-based table materialization.
- Evidence: after correcting the column name and quoted boolean, Trino and Polaris assertions passed; the RustFS assertion then rejected the valid `probe002_smoke__dbt_tmp-<uuid>` physical location retained after the logical table rename.
- Unblock: assert the task schema prefix plus required data/metadata object types without requiring the logical final table name in the physical UUID directory.
- Resolution: the corrected object assertion accepted the rename-derived physical directory while requiring the task prefix and Parquet, metadata JSON, and Avro objects; it passed with five objects totaling 14,873 bytes.

#### BOOT-ENV-002/B06
- State: RESOLVED
- Category: TEST
- Affects: mandatory runtime cleanup and environment restoration
- Problem: the cleanup wrapper stopped after the successful schema drop because AWS CLI returned non-zero for an empty prefix listing, before `docker compose down` ran.
- Evidence: Trino no longer listed `boot_env_002` and the captured object listing was empty, but the project containers remained running because the wrapper exited 1 before teardown.
- Unblock: treat the expected empty-prefix listing as success, complete Compose teardown, and assert the named volumes are preserved.
- Resolution: the corrected wrapper accepted the empty prefix, `docker compose down` removed only task project containers/network in 4 seconds, and the default plus both probe RustFS volumes remain present.

### Review
- Verdict: OK
- Calls: 1
- Fix iterations: 0
- Details: one fresh read-only reviewer inspected the complete tracked/untracked diff, all three new infrastructure files, source contracts, final runtime/listing/cleanup evidence, the BOOT-ENV-002 status section, and unchanged prior task sections; it found no BLOCKER or DEFERRED and returned `VERDICT OK`. IMPROVEMENT: on a reused nonconforming existing `lakehouse` catalog, the bootstrap currently accepts HTTP 200 without revalidating all mandatory catalog/storage properties; the reviewer confirmed this does not block the clean-stack acceptance proven for this task.

### Next action
User reviews the checkpoint and, if accepted, stages and commits `compose.yaml`, `infra/rustfs/create-bucket.sh`, `infra/polaris/bootstrap.sh`, `infra/trino/catalog/lakehouse.properties`, and `docs/status.md`; no push or next-task transition is authorized.

## TASK_ID: BOOT-ENV-003

- Source: `docs/bootstrap.md`, section 5.2, “BOOT-ENV-003 — dbt execution image и dependency lock”; verification dependency `docs/bootstrap.md` section 4.4, “PROBE-002 — dbt adapter handshake”
- Status: REVIEW_READY
- Updated: 2026-10-29T13:31:28+03:00
- Baseline HEAD: f1e121a0a911a9a697c07b982f806312fe973ee9

### Progress
- Implemented: confirmed the task artifacts already introduced by the accepted PROBE-002 prerequisite: a digest-pinned minimal Python image running dbt as UID 10001, the direct `dbt-core`/`dbt-trino` pins, and a 58-package SHA-256 lock installed with pip hash checking and no dependency re-resolution. The final image built, parsed the project, connected to the current stack, created and tested the Iceberg smoke model, and exposed the exact expected row; the task schema and objects were then removed and the pre-existing RustFS volume was preserved.
- Remaining: none.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/bootstrap.md` §5.2 BOOT-ENV-003, minimal containerized dbt execution image | PASS | fast: static Dockerfile/Compose assertions and `docker compose --profile tools config --quiet` passed; standard: cached final image build exited 0 in 2 seconds, ran as UID 10001, included Git, and used the pinned Python base digest. |
| `docs/bootstrap.md` §5.2 BOOT-ENV-003, direct pins `dbt-core==1.11.11` and `dbt-trino==1.10.2` | PASS | fast: `requirements.in` contained exactly the two required direct pins; runtime `dbt --version` reported Core `1.11.11` and Trino plugin `1.10.2`; parse passed and quiet selection returned exactly `probe002_smoke` and `assert_probe002_smoke`. |
| `docs/bootstrap.md` §5.2 BOOT-ENV-003, resolved hash lock excludes floating Python transitives | PASS | fast/standard: lock assertion found 58 exact `==` entries, every entry SHA-256 hashed, with lock SHA-256 `d39a006b767024dfe5128cde43a5ee22b8744496bfcb122fffb4eff7325bb8f3`; replacing both dbt-core hashes with invalid values made pip exit 1 in 20 seconds with the intended `THESE PACKAGES DO NOT MATCH THE HASHES` error. |
| `docs/bootstrap.md` §4.4 PROBE-002, adapter handshake | PASS | acceptance: fresh stack reached healthy state in 42 seconds; exact versions passed, `dbt debug` ended with `All checks passed!`, the smoke model created one row, the named singular test passed, and Trino returned exactly `1,dbt-adapter-ok`. Five task objects existed before cleanup and zero after `DROP SCHEMA ... CASCADE`; `docker compose down` restored the initially stopped state in 2 seconds while preserving `iceberg-trino-dbt_rustfs-data`. |

### Issues
#### BOOT-ENV-003/B01
- State: RESOLVED
- Category: TEST
- Affects: mandatory fast-check and EVIDENCE_GATE
- Problem: the first exact dbt selection wrapper counted dbt informational output together with selected node names, so its final two-line assertion exited non-zero after parse and selection had executed.
- Evidence: `dbt parse` exited 0 and `dbt ls` visibly selected `probe002_smoke` and `assert_probe002_smoke`, but the combined wrapper exited 1 because the captured stream also contained dbt log lines.
- Unblock: rerun `dbt ls` in quiet machine-readable mode and assert the exact selected node set.
- Resolution: quiet `dbt ls` exited 0 in 3 seconds and the sorted output matched exactly the two expected node names.

#### BOOT-ENV-003/B02
- State: RESOLVED
- Category: TEST
- Affects: final adapter-handshake row and cleanup evidence
- Problem: the first exact-row wrapper queried nonexistent smoke column `marker`, so it stopped before asserting the row and performing cleanup.
- Evidence: Trino exited 1 with `Column 'marker' cannot be resolved`; the model defines the expected column as `status`.
- Unblock: query the declared `id, status` columns, then perform and verify task-schema cleanup.
- Resolution: the corrected query returned exactly `1,dbt-adapter-ok`; cleanup removed the schema and all five task-prefix objects, then restored the initially stopped Compose state while preserving named volumes.

#### BOOT-ENV-003/B03
- State: RESOLVED
- Category: REVIEW
- Affects: mandatory STATUS_RECORD and FRESH_READ_ONLY_REVIEW gates
- Problem: after final review, `Progress/Remaining` still said that independent review remained, which was inconsistent with the recorded `Verdict: OK` and `REVIEW_READY` outcome.
- Evidence: the reread final section contained `Remaining: independent fresh read-only review only` together with `Review: OK`.
- Unblock: correct `Remaining` to `none`, revalidate the status section and diff, then obtain a fresh read-only re-review because this content change is outside the narrow post-review finalization exception.
- Resolution: `Remaining` now equals `none`; the section assertion and `git diff --check` both passed, and the third fresh reviewer confirmed the corrected final section with `VERDICT OK`.

#### BOOT-ENV-003/B04
- State: RESOLVED
- Category: REVIEW
- Affects: mandatory STATUS_RECORD and FRESH_READ_ONLY_REVIEW gates
- Problem: after resolving B03, `Next action` still instructed the already completed Remaining-field correction and status check, leaving the task record internally stale.
- Evidence: the second fresh reviewer cited `docs/status.md` and returned `VERDICT BLOCK`; B03 Resolution proves the first two actions in the stale `Next action` were already completed.
- Unblock: replace `Next action` with only the still-pending fresh targeted re-review, validate the section, and rerun review.
- Resolution: before the final review, `Next action` named only the pending targeted re-review and the section assertion plus `git diff --check` passed; the third fresh reviewer then confirmed the correction with `VERDICT OK`.

### Review
- Verdict: OK
- Calls: 3
- Fix iterations: 2
- Details: the first fresh reviewer returned `VERDICT OK` before B03 correction. The second fresh reviewer returned `VERDICT BLOCK` for stale `Next action`; after the targeted status fix, the third fresh reviewer inspected the complete corrected section and diff, found no BLOCKER, DEFERRED, or IMPROVEMENT, and returned `VERDICT OK`.

### Next action
User reviews the checkpoint and, if accepted, stages and commits `docs/status.md`; no push or next-task transition is authorized.

## TASK_ID: IMP-001

- Source: `docs/bootstrap.md`, section 5.3, “IMP-001 — dbt skeleton и layer conventions”; `docs/spec.md`, DEC-005, DEC-006, DEC-020, DEC-024, DEC-027, AC-001 and AC-012
- Status: REVIEW_READY
- Updated: 2026-10-29T15:01:26+03:00
- Baseline HEAD: 7f86432a6c6e3e3c315a205b57c5df18b2250026

### Progress
- Implemented: added Bronze/Silver/Gold directory configuration, deterministic fixture source declarations, an explicit run-prefixed `generate_schema_name` macro, and a singular schema-convention assertion.
- Remaining: none.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/bootstrap.md` §5.3 IMP-001, dbt skeleton and layer conventions | PASS | fast: dbt 1.11.11 parse and exact selection passed; manifest contained the five fixture sources plus both required macros. A temporary model in each configured layer parsed without warnings and resolved to the expected schema. |
| `docs/bootstrap.md` §5.3 IMP-001, run-prefixed schema isolation | PASS | fast/acceptance: temporary Bronze/Silver/Gold nodes resolved exactly to the three `imp001_contract_*` schemas, fixture sources resolved to `imp001_check_fixtures`, and the runtime `assert_schema_naming_convention` test passed. Removing the prefix in a temporary macro made that named test fail with exactly 3 rows and exit 1. |
| `docs/bootstrap.md` §5.3 IMP-001, reusable distance macro / PROBE-003 | PASS | acceptance: final-state `assert_probe003_geodesic_expectations` passed against Trino 484 together with the schema-convention test. |
| `docs/spec.md` AC-001 | PASS | fast: final tracked/untracked review shows only dbt project configuration, fixture source declarations, reusable macros/tests, and this task status; no excluded ingestion, CDC, orchestration, Spark, BI, or security scope was added. |
| `docs/spec.md` AC-012, IMP-001 contribution | PASS | acceptance: fresh stack became healthy; `dbt debug` connected; the smoke model created one exact row in `lakehouse.imp001_runtime`; both targeted tests passed; Trino listed only the task schema/table beyond built-ins; RustFS listed five Iceberg objects under `warehouse/imp001_runtime/`. Cleanup removed the task schema/prefix and restored the initially stopped stack while preserving the named volume. |

### Issues
#### IMP-001/B01
- State: RESOLVED
- Category: TEST
- Affects: mandatory fast-check and EVIDENCE_GATE
- Problem: the first containerized parse/manifest wrapper did not execute because its temporary artifact directory was not writable by the image UID; the diagnostic rerun parsed successfully but its host cleanup also failed on image-owned artifacts.
- Evidence: the first wrapper exited 2 without producing the manifest assertion; after making the mount writable, `dbt parse` exited 0 and wrote the manifest, but host `rm -rf` reported permission denied for files owned by the container UID.
- Unblock: run the container with the host UID/GID, then repeat the complete parse, selection, and manifest assertions with successful cleanup.
- Resolution: the host-UID/GID rerun completed dbt parse and selection and cleaned its temporary directory without a permissions error; the remaining non-zero result came from a separate node-name assertion mismatch.

#### IMP-001/B02
- State: RESOLVED
- Category: TEST
- Affects: mandatory fast-check and EVIDENCE_GATE
- Problem: the corrected selection assertion expected source names with a `source:` prefix, while dbt 1.11.11 `ls --output name` emits them as `fixtures.<table>`.
- Evidence: dbt parse exited 0, then the wrapper observed the exact five sources as `fixtures.hubs`, `fixtures.packages`, `fixtures.route_checkpoints`, `fixtures.route_plan_changes`, and `fixtures.tracking_events` and exited 1 only on the mismatched expected-name list.
- Unblock: align the assertion with the observed machine-readable dbt output and rerun the full manifest contract.
- Resolution: the aligned wrapper exited 0 in 5 seconds, selected the exact five fixture sources and two tests, and verified source schemas plus `generate_schema_name` and `great_circle_distance_meters` in the manifest.

#### IMP-001/B03
- State: RESOLVED
- Category: TEST
- Affects: `docs/spec.md` AC-012 contribution and final catalog/object evidence
- Problem: the runtime listing wrapper made two incorrect assumptions about built-in schemas and the configured warehouse prefix, so it did not initially complete the combined evidence assertion.
- Evidence: the first run rejected Trino's built-in `system` schema; after excluding it, the second run found no objects under `imp001_runtime/`. Direct listing showed the five valid Iceberg objects under `warehouse/imp001_runtime/`, including Parquet, metadata JSON, and Avro files.
- Unblock: assert the configured `warehouse/imp001_runtime/` prefix while retaining exact row, task schema, and table checks, then rerun the combined contract.
- Resolution: the corrected combined contract passed with one exact row, only task schema `imp001_runtime`, only table `probe002_smoke`, and five required Iceberg objects.

#### IMP-001/B04
- State: RESOLVED
- Category: TEST
- Affects: mandatory runtime cleanup and environment restoration
- Problem: after the schema drop and final positive test, the cleanup wrapper expected AWS CLI field `KeyCount=0`; RustFS omitted both `KeyCount` and `Contents` for the empty prefix, so the wrapper stopped before `docker compose down`.
- Evidence: `DROP SCHEMA lakehouse.imp001_runtime CASCADE` succeeded; direct follow-up returned an empty prefix response with no `Contents`, while RustFS, Polaris, and Trino remained healthy/running because teardown was not reached.
- Unblock: treat missing/empty `Contents` as zero objects, then complete Compose teardown and verify the project volume is preserved.
- Resolution: the corrected assertion counted missing `Contents` as zero, confirmed zero task schemas and objects, completed `docker compose down` in 3 seconds, removed project containers/network, and preserved `iceberg-trino-dbt_rustfs-data`.

### Review
- Verdict: OK
- Calls: 1
- Fix iterations: 0
- Details: one fresh read-only reviewer inspected the complete tracked/untracked diff, all three new files, source contracts, runtime/mutation/cleanup evidence, the IMP-001 status section, and unchanged prior task sections; it found no BLOCKER, DEFERRED, or IMPROVEMENT and returned `VERDICT OK`.

### Next action
User reviews the checkpoint and, if accepted, stages and commits `dbt/dbt_project.yml`, `dbt/macros/generate_schema_name.sql`, `dbt/models/fixtures/sources.yml`, `dbt/tests/assert_schema_naming_convention.sql`, and `docs/status.md`; no push or next-task transition is authorized.
