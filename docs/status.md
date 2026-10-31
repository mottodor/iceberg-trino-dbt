# Task status

## TASK_ID: PROBE-001

- Source: `docs/bootstrap.md`, section 4.4, “PROBE-001 — совместимость pinned stack”
- Status: DONE
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
- Status: DONE
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
- Status: DONE
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
- Status: DONE
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
- Status: DONE
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
- Status: DONE
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
- Status: DONE
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

## TASK_ID: IMP-002

- Source: `docs/bootstrap.md`, section 5.3, “IMP-002 — deterministic fixtures и immutable Bronze”; `docs/spec.md`, section 5 fixture package, DEC-010, DEC-016, DEC-022, DEC-025, AC-004, AC-005, AC-009 and AC-011
- Status: DONE
- Updated: 2026-10-29T15:32:44+03:00
- Baseline HEAD: 5da246f8d9eaa89a6c852d68fe63350353f9addf

### Progress
- Implemented: added the deterministic baseline and three isolated negative fixture sets, a validating idempotent Trino loader, five raw Bronze models, model constraints, and fixture/Bronze contract assertions. Both staged batches and their replays passed; the final 28-row baseline passed all 18 Bronze tests and direct duplicate/late-event assertions; the contract mutation produced the intended named failure and was restored; all three negative scenarios were loaded and observed in isolated Bronze schemas; ten baseline tables and 59 Iceberg objects were listed; task schemas/objects were purged and the initially stopped stack was restored with all three named volumes preserved.
- Remaining: none.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/spec.md` AC-004, IMP-002 contribution | PASS | acceptance: batch 1 inserted 40 rows and replay inserted 0; batch 2 inserted five event rows and replay inserted 0. Final Bronze held 28 events, two distinct `fixture_row_id` rows for `P3-E02`, and one distinct business payload; `assert_bronze_matches_fixtures` and the baseline contract test passed. |
| `docs/spec.md` AC-005, IMP-002 contribution | PASS | acceptance: stage 1 held 23 events and one `P3-E02`; after batch 2 Bronze held the exact five expected P3 batch-2 IDs, including four B/X visit rows received after delivery and the duplicate. The downstream Silver/Gold recalculation remains in later tasks. |
| `docs/spec.md` AC-009, IMP-002 contribution | PASS | standard/acceptance: static validation covered all three isolated scenario files; separate schemas produced `P3-E02` with three rows/two longitude payloads, a P4 departure from unopened B, and two P4 arrivals at still-open D. DQ test implementation remains in IMP-003. |
| `docs/spec.md` AC-011, IMP-002 contribution | PASS | acceptance: all 18 Bronze tests passed; exact counts were hubs=5, packages=4, route changes=2, checkpoints=6, events=28; shipment S2 contained independent P2/P3 rows; source-to-Bronze fidelity passed. A one-row Bronze mutation caused the named contract test to `FAIL 1`, then final restoration passed. |

### Issues
#### IMP-002/B01
- State: RESOLVED
- Category: TEST
- Affects: staged runtime evidence for AC-004, AC-005 and AC-011
- Problem: the first batch-1 Bronze materialization command passed a duplicate `dbt` executable token; the next corrected invocation still used default artifact paths that the container UID could not write and also exited 2 before model output.
- Evidence: both batch-1 loader runs passed with 40 inserted rows then 40 existing rows; the two model command attempts exited 2 before model output, while a named diagnostic container confirmed the image entrypoint and runtime itself were healthy.
- Unblock: invoke the service with `run` as the dbt subcommand and direct `DBT_TARGET_PATH`/`DBT_LOG_PATH` to writable task-local `/tmp` paths.
- Resolution: the corrected command created all five Bronze tables with counts 5/4/6/2/23 and exited 0; a direct Trino assertion confirmed 23 stage-1 events and exactly one P3 `picked_up` row.

#### IMP-002/B02
- State: RESOLVED
- Category: TEST
- Affects: final baseline evidence for AC-004, AC-005 and AC-011
- Problem: the baseline Bronze contract test qualifies a column after a Trino `JOIN ... USING`, so the final dbt build errors instead of evaluating the assertion.
- Evidence: batch 2 inserted five rows and replayed with zero inserts; the build created all five final Bronze tables and 17 other tests passed, but `assert_baseline_bronze_contract` errored with `COLUMN_NOT_FOUND: Column 'expected.table_name' cannot be resolved` at its count comparison.
- Unblock: replace the `USING` join with an explicit `ON` predicate, rerun the targeted test, and then rerun the final affected Bronze checks.
- Resolution: both joins now use explicit `ON` predicates; the targeted contract test and all 18 Bronze tests passed, and the final direct 28-row duplicate/late-event assertion returned true.

#### IMP-002/B03
- State: RESOLVED
- Category: TEST
- Affects: mandatory FINAL_EVIDENCE_AND_DIFF_GATE
- Problem: the first untracked-file whitespace wrapper scanned unchanged repository documents instead of only this task's changed/new paths.
- Evidence: final Python compilation, fixture validation, dbt parse, and exact Bronze selection passed; the wrapper then exited 1 only for pre-existing trailing spaces in `docs/bootstrap.md`/`docs/spec.md` and the pre-existing missing final newline in `docs/idea.md`.
- Unblock: scope the whitespace assertion to tracked changes and the explicit untracked task file list, without modifying unrelated documents, then rerun `git diff --check` and the scoped check.
- Resolution: the scoped check covered all 19 changed/new paths and passed; `git diff --check` passed, the IMP-002 section remained unique, and unrelated documents were not modified.

#### IMP-002/B04
- State: RESOLVED
- Category: REVIEW
- Affects: mandatory STATUS_RECORD and FRESH_READ_ONLY_REVIEW gates
- Problem: the first reviewer returned `VERDICT OK`, but `Progress/Remaining` still described that now-completed review as pending; correcting Progress is outside the narrow post-review finalization exception.
- Evidence: the reviewer confirmed all 18 new files and the tracked status diff, found no blocker, and returned `VERDICT OK`; the reviewed section still contained `Remaining: independent fresh read-only review only`.
- Unblock: set `Remaining` to `none`, preserve the reviewer’s non-blocking improvement note, rerun the status/diff checks, and obtain one fresh targeted re-review.
- Resolution: `Remaining` is now `none`; the status/diff checks passed, and the second fresh read-only reviewer confirmed the corrected section, unchanged implementation evidence, and non-blocking improvement with `VERDICT OK`.

### Review
- Verdict: OK
- Calls: 2
- Fix iterations: 1
- Details: the first fresh read-only reviewer inspected the complete tracked/untracked diff and source contracts and returned `VERDICT OK`. After the status-only correction, the second fresh targeted reviewer confirmed the corrected section and returned `VERDICT OK`. IMPROVEMENT: exact tuple assertions for the four P3 late-event payloads would harden future fixture edits; current checked-in values are correct and this remains non-blocking.

### Next action
User reviews the checkpoint and, if accepted, stages and commits the listed IMP-002 files; no push or next-task transition is authorized.

## TASK_ID: IMP-003

- Source: `docs/bootstrap.md`, section 5.3, “IMP-003 — canonical/typed Silver и DQ”; `docs/spec.md`, DEC-010, DEC-016, DEC-022, AC-004, AC-005 and AC-009
- Status: DONE
- Updated: 2026-10-29T16:25:49+03:00
- Baseline HEAD: 5e80c0897d2cd6ea815f11196cb75bbfc88285bf

### Progress
- Implemented: added typed raw Silver events with canonical departure normalization and normalized payload fingerprints, deterministic canonical events and package ordering, current package state, generic model constraints, three named DQ assertions, and a baseline Silver contract including typed/canonical counts. Final staged baseline regression proved duplicate canonicalization and late-event ordering; all baseline tests passed; the canonical/alias mutation passed all generic and sequence-DQ checks; an extra unrelated exact duplicate made the baseline contract fail as intended; all three required negative scenarios still produced their intended named failures. All task schemas, containers, network, and task-created volumes were removed; the three pre-existing volumes were preserved.
- Remaining: none.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/spec.md` AC-004, IMP-003 contribution | PASS | acceptance on final code: batch 1 produced 23 typed/23 canonical events; batch 2 produced exactly 28 typed/27 canonical. `P3-E02` had two raw rows and one canonical row; all 24 final baseline Silver tests passed. Adding an unrelated exact duplicate produced 29 typed/27 canonical rows and made only `assert_baseline_silver_contract` return `FAIL 1`. |
| `docs/spec.md` AC-005, IMP-003 contribution | PASS | acceptance on final code: before and after batch 2, P3 remained `delivered` at `P3-E04`; final order was exactly `E01,E02,E05,E06,E07,E08,E03,E04`. The final baseline contract and direct staged assertions passed. |
| `docs/spec.md` AC-009 | PASS | acceptance on final code: baseline DQ tests passed; an alias duplicate using `departed_hub` normalized both rows to `departed_at_hub`, produced one fingerprint, and passed all 23 generic/DQ tests. Isolated conflict, departure, and repeated-arrival scenarios each returned dbt exit 1 with only the intended named `FAIL 1`, and direct queries identified `P3-E02`, `P4-N01`, and `P4-N02` respectively. |

### Issues
#### IMP-003/B01
- State: RESOLVED
- Category: TEST
- Affects: mandatory fast-check and EVIDENCE_GATE
- Problem: the first exact dbt node-selection wrapper included generic tests selected indirectly from the three Silver models, so its expected seven-node assertion failed after parsing succeeded.
- Evidence: `dbt parse` exited 0; `dbt ls` returned the seven intended models/singular tests plus 21 generic tests, and the wrapper exited 1 only on the exact output comparison.
- Unblock: disable indirect generic-test selection or classify the machine-readable output, then rerun the exact Silver model/singular-test assertion.
- Resolution: final `dbt parse` exited 0; `dbt ls --indirect-selection empty` returned exactly the three Silver models and four named singular tests, and the exact-set assertion passed.

#### IMP-003/B02
- State: RESOLVED
- Category: CODE
- Affects: `docs/bootstrap.md` §4.3 event-type normalization and mandatory FRESH_READ_ONLY_REVIEW gate
- Problem: Silver passes through `departed_hub` unchanged and fingerprints the raw alias, although the approved bootstrap contract requires both departure spellings to normalize to `departed_at_hub` before downstream DQ logic.
- Evidence: the first fresh reviewer identified that the typed model copies `event_type` directly, the accepted-values test rejects `departed_hub`, and both sequence tests ignore it; fixtures use only the canonical spelling, so prior acceptance did not exercise the alias.
- Unblock: normalize both spellings in the typed model and fingerprint, then prove an isolated alias mutation passes generic and sequence-DQ checks.
- Resolution: the typed model now normalizes both spellings before output and fingerprinting. An isolated semantic duplicate with `departed_hub` produced two canonical typed spellings, one fingerprint, one canonical event with raw count 2, and all 23 generic/DQ tests passed.

#### IMP-003/B03
- State: RESOLVED
- Category: TEST
- Affects: AC-004 evidence and mandatory EVIDENCE_GATE
- Problem: the checked-in baseline Silver contract does not assert the proven 28 typed-row count, allowing an unrelated extra exact duplicate to leave all current tests green.
- Evidence: the first fresh reviewer showed that canonical count, P3 duplicate count, ordering, current states, fingerprint conflict, and generic uniqueness can all remain green if a new unique fixture row exactly duplicates another non-P3 event.
- Unblock: assert exactly 28 typed baseline rows and run a mutation with an extra exact duplicate that must make `assert_baseline_silver_contract` fail.
- Resolution: the contract now asserts exactly 28 typed rows. An isolated exact duplicate of `P1-E01` yielded 29 typed/27 canonical rows and made the named baseline contract return `FAIL 1` with dbt exit 1.

#### IMP-003/B04
- State: RESOLVED
- Category: REVIEW
- Affects: mandatory STATUS_RECORD and FRESH_READ_ONLY_REVIEW gates
- Problem: after the successful second reviewer call, `Progress/Remaining` still described that completed re-review as pending; correcting Progress is outside the narrow post-review finalization exception.
- Evidence: the second fresh reviewer returned `VERDICT OK` with no findings, while the reviewed section still contained `Remaining: fresh read-only re-review only`.
- Unblock: set `Remaining` to `none`, validate the status/diff, and obtain one fresh targeted re-review of the corrected section.
- Resolution: `Remaining` is `none`; `git diff --check` passed, and the third fresh reviewer confirmed the corrected status section, complete diff, evidence, counters, and unchanged prior task sections with `VERDICT OK`.

### Review
- Verdict: OK
- Calls: 3
- Fix iterations: 2
- Details: the first fresh reviewer returned `VERDICT BLOCK` for B02/B03. The second fresh reviewer confirmed the targeted code/test fixes and final evidence with `VERDICT OK`. After the status-only B04 correction, the third fresh targeted reviewer verified the complete diff, corrected section, counters, evidence, and unchanged prior task sections; it found no BLOCKER, DEFERRED, or IMPROVEMENT and returned `VERDICT OK`.

### Next action
User reviews the checkpoint and, if accepted, stages and commits the IMP-003 files plus `docs/status.md`; no push or transition to another task is authorized.

## TASK_ID: IMP-004

- Source: `docs/bootstrap.md`, section 5.3, “IMP-004 — SCD2 route plan и route binding”; `docs/spec.md`, DEC-017, DEC-020, DEC-023, DEC-024 and AC-003
- Status: DONE
- Updated: 2026-10-29T16:41:03+03:00
- Baseline HEAD: a09dd66314347ed1aa6963a95e40abe49d81ad3b

### Progress
- Implemented: added typed checkpoint segments with geodesic distances, derived SCD2 route-version intervals/current marker, package binding by pickup time with promised timestamps, model constraints, and baseline/no-overlap assertions. Final parse/selection and whitespace checks passed; the baseline build passed 81/81 nodes; direct queries returned the exact two versions, four bindings, promised timestamps, and equal 222390.20235496786-metre planned distances; the isolated overlap mutation failed only the intended test. Both task prefixes and all six schemas were removed, the initially stopped Compose stack was restored, and all three pre-existing named volumes were preserved.
- Remaining: none.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/spec.md` AC-003; `docs/bootstrap.md` §5.3 IMP-004 | PASS | acceptance: the baseline `dbt build --select tag:bronze tag:silver` passed 81/81 nodes. Direct Trino assertions returned `P1→R1-V1`, `P2/P3/P4→R1-V2`, promised timestamps `2025-01-12T08:00Z`, `2025-02-11T20:00Z`, `2025-02-11T21:00Z`, and `2025-02-13T20:00Z`; both versions had planned distance `222390.20235496786` metres and the expected closed/current intervals. A duplicate-effective-time mutation made only `assert_route_plan_version_intervals` fail with one row. |

### Issues
#### IMP-004/B01
- State: RESOLVED
- Category: ENVIRONMENT
- Affects: `docs/spec.md` AC-003 runtime evidence
- Problem: the first Compose preflight could not render because the required local training credentials were absent from the shell environment.
- Evidence: `docker compose --profile tools config --quiet` exited 1 and named only the four required unset variables; no service was started.
- Unblock: supply temporary non-production local values for the four required variables and rerun config/port preflight before starting the task stack.
- Resolution: the same config/port preflight exited 0 with temporary non-production local values, and all four project ports were free.

#### IMP-004/B02
- State: RESOLVED
- Category: TEST
- Affects: mandatory EVIDENCE_GATE negative assertion
- Problem: the first overlap mutation run produced the intended `FAIL 1 assert_route_plan_version_intervals` but also selected two unrelated Bronze contract tests whose other referenced models were absent.
- Evidence: dbt exited 1 with the intended one-row interval failure plus two `TABLE_NOT_FOUND` errors for unbuilt Bronze package tables, so the run is not an unambiguous negative proof.
- Unblock: materialize the complete required Bronze parents with `dbt run`, then invoke only the named interval test with indirect selection disabled and require it to be the sole failure.
- Resolution: after materializing all required parents, an isolated one-test run exited 1 with exactly `FAIL 1 assert_route_plan_version_intervals`, `ERROR=1`, `TOTAL=1`, and no unrelated database error.

#### IMP-004/B03
- State: RESOLVED
- Category: TEST
- Affects: mandatory runtime cleanup and environment restoration
- Problem: schema drops succeeded, but the cleanup wrapper treated an empty object prefix as an AWS CLI `length(null)` error and stopped before Compose teardown.
- Evidence: all six task schemas returned `DROP SCHEMA`; the first post-drop object query exited 255 because `Contents` was absent, and the three project runtime containers remained healthy/running until the corrected check.
- Unblock: count missing `Contents` as zero, verify both task prefixes are empty, run `docker compose down`, and assert the three pre-existing named volumes remain.
- Resolution: null-safe JSON counting confirmed zero schemas and zero objects under both task prefixes; `docker compose down` restored the initially stopped state and all three pre-existing named volumes remained.

### Review
- Verdict: OK
- Calls: 1
- Fix iterations: 0
- Details: one fresh read-only reviewer inspected the complete tracked/untracked diff, source contracts, implementation, tests, final runtime/mutation/cleanup evidence, the IMP-004 status section, and unchanged prior task sections; it found no BLOCKER or DEFERRED and returned `VERDICT OK`. IMPROVEMENT: add exact six-checkpoint tuple coverage plus `(route_version_id, checkpoint_seq)` duplicate detection in a future hardening change; the reviewer confirmed the checked-in fixtures and current AC-003 evidence are correct, so this is non-blocking.

### Next action
User reviews the checkpoint and, if accepted, stages and commits the IMP-004 files plus `docs/status.md`; no push or transition to another task is authorized.

## TASK_ID: IMP-005

- Source: `docs/bootstrap.md`, section 5.3, “IMP-005 — hub visits и Gold facts”; `docs/spec.md`, DEC-011–DEC-015, DEC-021, DEC-022, DEC-026 and AC-005–AC-008, AC-011
- Status: DONE
- Updated: 2026-10-29T17:29:17+03:00
- Baseline HEAD: ab4cbf0c8c744fb57b6585f134c1c672808e2101

### Progress
- Implemented: added strict hub-visit pairing, the package accumulating snapshot with SLA/distance/dwell metrics, model constraints, and baseline Gold contract assertions. Fast parse/selection passed; batch 1 proved P3 remained delivered/on-time with 36-hour duration, zero visits, and 100% route ratio; after batch 2 the full 107-node build passed, exact rows showed four package facts and seven visits with the specified P1–P4 metrics, and a duplicate-open-visit mutation made only the named Gold visit contract fail before final restoration and 24/24 Gold tests passed. The final package-route implementation includes every canonical coordinate event. After reviewer feedback, the package contract now rejects NULL completed deviation metrics, validates P2/P3 absolute deviation metres, and has an explicit dbt dependency hint; a P2 NULL-deviation mutation produced the sole intended `FAIL 1`, final 16/16 affected tests passed, completed deviation fields were non-null with 0/50/50%, and the task schemas/objects were removed again.
- Remaining: none.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/spec.md` AC-005 | PASS | acceptance: before batch 2 P3 was delivered/on-time with 36-hour duration, zero visits/dwell, and route ratio 1.0; after batch 2 the final Gold contracts passed with B=2h, X=1h, unchanged delivery metrics, and route ratio 1.5. |
| `docs/spec.md` AC-006 | PASS | acceptance: the final package/visit contracts and direct rows showed P1 duration 48h, delay 0, on-time=true, B dwell 4h, route ratio 1.0, and non-null deviation 0%; the final affected test suite passed after the reviewer fix. |
| `docs/spec.md` AC-007 | PASS | acceptance: the final package/visit contracts and direct rows showed P2 duration 48h, delay 12h, on-time=false, dwell B/X/D=4/10/2h, total 16h, route ratio 1.5, and non-null deviation 50% within tolerance. A P2 NULL-deviation mutation made only the named package contract fail with `FAIL 1`; restoration passed 16/16 tests. |
| `docs/spec.md` AC-008 | PASS | acceptance: the final contracts showed one P4 fact in `arrived_at_hub`, one open D visit with null departure/dwell, null final delivery metrics/deviation, and non-null current distance at 75% of plan. |
| `docs/spec.md` AC-011, IMP-005 contribution | PASS | acceptance: the final build and direct assertions showed 4 package facts (3 completed, 1 active), 7 hub visits (6 closed, 1 open), and exactly two independent S2 package rows; final affected Gold tests passed 24/24 and then 16/16 after the route-point hardening change. |

### Issues
#### IMP-005/B01
- State: RESOLVED
- Category: TEST
- Affects: `docs/spec.md` AC-005 staged before/after evidence
- Problem: the first stage-1 wrapper rejected the correct zero P3 visit count because Trino CSV output quoted the scalar value.
- Evidence: the Gold row returned `P3, delivered, 36.0, true, 0, 0.0, 1.0`; the visit query returned `"0"`, and the Python wrapper exited 1 only because it compared that quoted CSV token to unquoted `0`.
- Unblock: parse the scalar as CSV, rerun the stage-1 assertion, and then continue with batch 2.
- Resolution: the corrected wrapper parsed both results as CSV and passed, confirming delivered state, 36-hour duration, on-time=true, zero visits/dwell, and route ratio 1.0 before batch 2.

#### IMP-005/B02
- State: RESOLVED
- Category: TEST
- Affects: final catalog/object evidence and mandatory cleanup
- Problem: the first catalog-listing wrapper expected 14 task tables, but the valid listing contains 18 tables across fixtures, Bronze, Silver, and Gold.
- Evidence: Trino listed the exact four task schemas and 18 tables, including both Gold models; the wrapper exited 1 only at its incorrect `len(tables) == 14` assertion before evaluating the object count.
- Unblock: align the expected count to the observed layer composition, rerun catalog/object assertions, then remove only the task schemas and restore the initially stopped Compose state.
- Resolution: the corrected assertion passed with four schemas, 18 tables, and 99 task-prefix objects; cleanup then removed all four schemas and all task-prefix objects, restored the initially stopped Compose state, and preserved the three pre-existing named volumes.

#### IMP-005/B03
- State: RESOLVED
- Category: TEST
- Affects: mandatory FINAL_EVIDENCE_AND_DIFF_GATE
- Problem: the first final status wrapper searched for an unqualified AC-011 table cell and rejected the valid row labelled `AC-011, IMP-005 contribution`.
- Evidence: `git diff --check` completed before the Python wrapper; diagnostics showed all AC-005–AC-008 conditions true, both issues resolved, and only the exact AC-011 substring condition false.
- Unblock: assert the actual qualified AC-011 source label, rerun the complete static/status gate, and continue to review.
- Resolution: the corrected complete gate passed for all six changed paths, all five PASS rows, the unique IMP-005 section, resolved prior issues, clean whitespace, unchanged HEAD, no task containers, and all three preserved volumes.

#### IMP-005/B04
- State: RESOLVED
- Category: TEST
- Affects: `docs/spec.md` AC-006, AC-007 and mandatory FRESH_READ_ONLY_REVIEW gate
- Problem: the package Gold contract can miss NULL final deviation metrics for completed P1–P3 and does not independently validate P2/P3 absolute deviation metres.
- Evidence: the first fresh reviewer showed that `abs(NULL) > tolerance` evaluates to UNKNOWN, the expected rows omit both deviation columns, and no conditional schema test covers them; it returned `VERDICT: BLOCK`.
- Unblock: make completed-row NULLs explicit violations, validate absolute deviation metres for P2/P3, prove a NULL-deviation mutation fails only the named package contract, restore final state, and obtain fresh re-review.
- Resolution: completed rows now explicitly reject NULL deviation fields; P2/P3 validate absolute deviation against actual-minus-planned and 50% of plan. Updating P2 deviations to NULL made only `assert_baseline_gold_package_fact_contract` return `FAIL 1`; restoration passed all 16 affected tests and direct assertions showed non-null 0/50/50% deviations for P1/P2/P3.

#### IMP-005/B05
- State: RESOLVED
- Category: ENVIRONMENT
- Affects: targeted acceptance evidence for IMP-005/B04
- Problem: after Compose reported Trino healthy, the first fixture-loader query reached Trino while the server still reported `SERVER_STARTING_UP`.
- Evidence: the second task-owned stack start completed healthy in 43.52 seconds; the immediately following loader exited 1 on its first `CREATE SCHEMA` with Trino `INTERNAL_ERROR: SERVER_STARTING_UP`; no model run started.
- Unblock: prove query readiness with a cheap `SELECT 1`, then rerun the unchanged loader and targeted checks once.
- Resolution: `SELECT 1` succeeded; the unchanged loader inserted all 45 baseline rows, all 13 models ran successfully, and the patched package contract passed before mutation.

#### IMP-005/B06
- State: RESOLVED
- Category: TEST
- Affects: targeted negative evidence for IMP-005/B04
- Problem: after mutating P2 deviation fields to NULL, the selected singular test errored during dbt dependency inference instead of evaluating the intended assertion.
- Evidence: Trino `UPDATE` changed one row; dbt exited 1 with `Compilation Error` requesting an explicit `-- depends_on: {{ ref('gold_package_delivery_fact') }}` hint, so the expected `FAIL 1` assertion was not reached.
- Unblock: add the explicit dependency hint, restore the model, rerun the positive contract, reapply the NULL mutation, and require the named test to be the sole `FAIL 1`.
- Resolution: the explicit dependency hint was added; the restored positive contract passed, the repeated NULL mutation produced the sole named `FAIL 1`, and final restoration passed the affected suite.

#### IMP-005/B07
- State: RESOLVED
- Category: REVIEW
- Affects: mandatory STATUS_RECORD and FRESH_READ_ONLY_REVIEW gates
- Problem: after the successful second reviewer call, `Progress/Remaining` still described that completed re-review as pending; correcting Progress is outside the narrow post-review finalization exception.
- Evidence: the second fresh reviewer returned `VERDICT: OK` with no findings, while the reviewed section still contained `Remaining: fresh read-only re-review only`.
- Unblock: set `Remaining` to `none`, validate the status/diff, and obtain one fresh targeted re-review of the corrected section.
- Resolution: `Remaining` was corrected to `none`; the status/diff gate passed, and the third fresh reviewer verified the complete diff, corrected status section, unchanged prior sections, counters, and evidence with `VERDICT: OK`.

### Review
- Verdict: OK
- Calls: 3
- Fix iterations: 2
- Details: the first fresh reviewer returned `VERDICT: BLOCK` for B04. After targeted fix iteration 1, the second fresh reviewer confirmed the corrected code, tests, evidence, scope, and status preservation with `VERDICT: OK`. After the required status-only B07 correction, the third fresh targeted reviewer verified the complete diff and corrected status section, found no BLOCKER, DEFERRED, or IMPROVEMENT, and returned `VERDICT: OK`.

### Next action
IMP-005 is complete and committed as `345be2c`; await separate authorization for push or transition to IMP-006.

## TASK_ID: IMP-006

- Source: `docs/bootstrap.md`, section 5.3, “IMP-006 — Gold aggregates и reconciliation”; `docs/spec.md`, DEC-013, DEC-026, AC-010 and AC-011
- Status: DONE
- Updated: 2026-10-29T17:57:07+03:00
- Baseline HEAD: d1041724a6a9841968f991755985830f16b91bdb

### Progress
- Implemented: added route-version efficiency and route-version/hub completed-dwell aggregates, model constraints, exact baseline contracts, and cross-layer reconciliation. Fast parse/selection passed; the 128-node baseline build, direct aggregate/count assertions, three targeted mutations, final 43-test Gold suite, catalog/object listing, and scoped whitespace checks passed. The four task schemas and 109 task-prefix objects were removed, the initially stopped stack was restored, and all three pre-existing volumes were preserved.
- Remaining: none.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/spec.md` AC-010; `docs/bootstrap.md` §5.3 IMP-006 | PASS | acceptance: the 128-node baseline build passed. Final exact assertions returned `R1-V1` = 1 completed, 0 active, 100% on-time, 0h average delay, 0% average deviation; `R1-V2` = 2 completed, 1 active, 50% on-time, 6h average delay, 50% average deviation. Route-version/hub rows were V1/B=4h and V2/B=6h, X=11h, D=2h with the P4 open visit excluded. Single-row route and hub mutations made only their exact named tests fail with `FAIL 2`; restoration passed the final 43/43 Gold tests. |
| `docs/spec.md` AC-011; `docs/bootstrap.md` §5.3 IMP-006 | PASS | acceptance: final reconciliation passed for 28 Bronze event rows, 27 canonical events with one explained duplicate, 4 package facts (3 completed/1 active), 7 visits (6 closed/1 open), two route aggregates, four route/hub aggregates, model relationships, and independent S2 rows P2/P3. Changing P3 to shipment S9 made only `assert_cross_layer_reconciliation` fail with `FAIL 3`; restoration passed the targeted test and final Gold suite. Trino listed exactly 20 task tables and RustFS listed 109 task-prefix Iceberg objects before cleanup. |

### Issues
#### IMP-006/B01
- State: RESOLVED
- Category: ENVIRONMENT
- Affects: mandatory PRECHECK and safe diff-attribution gate
- Problem: the prior attempt started from a working tree with changes that predated IMP-006, so that run could not safely attribute or isolate the task diff.
- Evidence: at the prior baseline HEAD `345be2c0dca8cbc8e4505241f84bf882b13a7ebd`, `git status --short --untracked-files=all` reported modified `docs/status.md` and untracked `dbt/scripts/__pycache__/load_fixtures.cpython-312.pyc`.
- Unblock: start a new attempt from a clean, distinguishable baseline after preserving or removing the prior changes.
- Resolution: current baseline `d1041724a6a9841968f991755985830f16b91bdb` has an empty `git status --short --untracked-files=all`; the prior status update is committed and the generated Python cache is absent.

#### IMP-006/B02
- State: RESOLVED
- Category: TEST
- Affects: runtime acceptance evidence collection
- Problem: the stack reached healthy state, but the first post-start assertion expected default `docker compose ps` output to include exited one-shot setup services.
- Evidence: `docker compose up -d --wait --wait-timeout 240 rustfs polaris trino` completed in 41 seconds with RustFS, Polaris, and Trino healthy and both setup jobs reported exited; the following wrapper exited 1 because default `docker compose ps --format json` listed only the three running services.
- Unblock: inspect running health and one-shot exit codes with commands that include stopped services, then continue runtime checks without restarting the healthy stack.
- Resolution: `docker compose ps -a --format json` verified all five services, the three runtime services healthy, and both one-shot setup services at exit code 0.

#### IMP-006/B03
- State: RESOLVED
- Category: TEST
- Affects: runtime query-readiness preflight
- Problem: the first Trino readiness wrapper compared CSV output to an unquoted scalar and exited 1 after the query itself succeeded.
- Evidence: the diagnostic rerun showed Trino exit 0 with CSV rows `"_col0"` and `"1"`.
- Unblock: parse the CSV output rather than comparing its quoted wire representation.
- Resolution: the corrected CSV parser asserted the exact header/value rows and printed `trino_query_ready=yes`.

#### IMP-006/B04
- State: RESOLVED
- Category: TEST
- Affects: mandatory EVIDENCE_GATE mutation assertion for AC-010
- Problem: the first route-aggregate mutation wrapper required exactly `FAIL 1`, although the full-outer-join contract can return both the unexpected actual row and missing expected row for one changed aggregate.
- Evidence: the aggregate update changed one `R1-V2` row and the named dbt test returned non-zero; the wrapper restored the model to `completed_package_count=2` before exiting 1 at its overly narrow log assertion.
- Unblock: rerun the same single-row mutation and require a positive failure count for the exact named test, one selected test, and no compilation/database error; then confirm final restoration.
- Resolution: the corrected wrapper observed only `FAIL 2 assert_baseline_gold_route_version_efficiency_contract`, restored the model, and the final targeted tests plus all 43 Gold tests passed.

#### IMP-006/B05
- State: RESOLVED
- Category: REVIEW
- Affects: mandatory STATUS_RECORD and FRESH_READ_ONLY_REVIEW gates
- Problem: the first reviewer returned `VERDICT: OK`, but `Progress/Remaining` still described that now-completed review as pending; correcting Progress is outside the narrow post-review finalization exception.
- Evidence: the fresh reviewer found no blocker and returned `VERDICT: OK`, while the reviewed section still contained `Remaining: independent fresh read-only review only`.
- Unblock: set `Remaining` to `none`, validate the status/diff, and obtain one fresh targeted re-review of the corrected section.
- Resolution: `Remaining` is `none`; the status/diff gate passed, and the second fresh reviewer confirmed the corrected section, unchanged implementation/evidence, counters, and preservation of prior task sections with `VERDICT: OK`.

### Review
- Verdict: OK
- Calls: 2
- Fix iterations: 1
- Details: the first fresh read-only reviewer inspected the complete implementation/status diff and returned `VERDICT: OK` with no BLOCKER or DEFERRED. After the required Progress correction, the second fresh targeted reviewer confirmed the complete corrected diff, evidence, counters, and unchanged prior task sections with `VERDICT: OK`. IMPROVEMENT: make the Gold reconciliation test independently validate that duplicated event IDs have one payload fingerprint; the existing Silver conflict test and full 128-node build already enforce this, so it is non-blocking.

### Next action
User authorized staging and committing this reviewed checkpoint; no push or transition to IMP-007 is authorized.

## TASK_ID: IMP-007

- Source: `docs/bootstrap.md`, section 5.3, “IMP-007 — acceptance workflow и evidence”; `docs/bootstrap.md`, section 6 acceptance sequence; `docs/spec.md`, AC-001 and AC-003–AC-012
- Status: DONE
- Updated: 2026-10-29T21:52:42+03:00
- Baseline HEAD: 64b2eccdea748896c27d81cf1e800c4849f92ddf

### Progress
- Implemented: added the isolated acceptance runner and ignore rules; targeted review fixes require explicit prefix ownership before cleanup, write PASS only after secret/manifest gates, atomically write summaries, and require exactly one intended negative failure. Focused failure-path mutations passed, and final run `imp007_final5` passed the complete baseline/negative/catalog/object/cleanup/secret workflow on the fixed code.
- Remaining: none.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/spec.md` AC-001 | PASS | fast/acceptance: fixed run scope assertion found no excluded technology paths; final diff is limited to `.gitignore`, `scripts/run_acceptance.py`, and this task section. |
| `docs/spec.md` AC-003 | PASS | acceptance: final 128-node build passed; `baseline/route_binding.csv` maps P1→V1 and P2/P3/P4→V2 with promised timestamps, while interval/mapping tests passed in `run_results.json`. |
| `docs/spec.md` AC-004 | PASS | acceptance: `baseline/layer_counts.csv` records Bronze 28, typed 28, canonical 27; `duplicate_reconciliation.csv` records P3-E02 as 2 Bronze rows, 1 payload, 1 canonical row. |
| `docs/spec.md` AC-005 | PASS | acceptance: `p3_before.csv` and `p3_after.csv` preserve delivered/36h/on-time while visits/dwell/route ratio change `0/0h/1.0` → `2/3h/1.5`; P3 visits are B=2h and X=1h. |
| `docs/spec.md` AC-006 | PASS | acceptance: `package_facts.csv` records P1 as 48h, zero delay, on-time, B dwell 4h, route ratio 1.0, deviation 0%; final contract tests passed. |
| `docs/spec.md` AC-007 | PASS | acceptance: `package_facts.csv` records P2 as 48h, 12h delay, late, 16h completed dwell, route ratio 1.5, deviation 50%; hub aggregates record B/X/D=6/11/2h across V2 packages. |
| `docs/spec.md` AC-008 | PASS | acceptance: `package_facts.csv` and `p4_open_visit.csv` record one active P4, current `arrived_at_hub`, open D visit with null departure/dwell, null final metrics, and current route ratio 0.75. |
| `docs/spec.md` AC-009 | PASS | acceptance: baseline DQ tests passed; each isolated scenario exited 1 with exactly one result, exact intended unique ID, and `failures=1`. |
| `docs/spec.md` AC-010 | PASS | acceptance: route aggregates are V1 `1/0/100%/0h/0%` and V2 `2/1/50%/6h/50%`; completed hub dwell is V1/B=4h and V2/B=6h, X=11h, D=2h. |
| `docs/spec.md` AC-011 | PASS | acceptance: final build and CSV assertions record 28/27 Bronze/canonical events, 4 facts (3 completed/1 active), 7 visits (6 closed/1 open), and 2 independent S2 packages. |
| `docs/spec.md` AC-012 | PASS | acceptance: fixed run `imp007_final5` exited 0 in 238.86 seconds; 128 dbt results were 15 success/113 pass, Trino listed 68 isolated tables, Polaris returned `lakehouse`, RustFS listed 388 task object paths, cleanup left zero task objects/containers and preserved the volume, secret scan was clean, and the manifest hashed 466 non-summary evidence files. |

### Issues
#### IMP-007/B01
- State: RESOLVED
- Category: TEST
- Affects: mandatory fast-check and EVIDENCE_GATE
- Problem: the first pure-helper validation harness failed while dynamically importing the acceptance module, so its helper assertions did not execute.
- Evidence: Python exited 1 in `dataclasses` because the ad-hoc `importlib` harness did not register the module in `sys.modules`; the preceding AST, `--help`, invalid-run-id, and whitespace checks had passed.
- Unblock: register the temporary module before `exec_module`, rerun the helper assertions, and preserve the unchanged implementation if they pass.
- Resolution: the corrected harness registered the module, all helper assertions passed, and a mismatched staged P3 mutation raised the intended `AcceptanceError`; `git diff --check` also passed.

#### IMP-007/B02
- State: RESOLVED
- Category: ENVIRONMENT
- Affects: `docs/spec.md` AC-012 and mandatory acceptance EVIDENCE_GATE
- Problem: the first full workflow run reached a Compose-healthy Trino container but its immediate `SELECT 1` readiness probe exited 1, so no business assertion ran.
- Evidence: `docker compose up -d --wait` exited 0 in 45.471 seconds; `docker compose ps -a` recorded Trino healthy for only six seconds; the immediate query exited 1. The runner then executed `docker compose down`, left no project containers, preserved `iceberg-trino-dbt_rustfs-data`, and its secret scan found no credential value in evidence.
- Unblock: make query readiness a bounded retry that records each failed stdout/stderr before retrying, avoid schema cleanup until Trino has accepted a query, and rerun with a fresh isolated run ID.
- Resolution: the second run recorded attempt 1 as `Trino server is still initializing`, retried after two seconds, then saved the exact successful CSV rows `ready,1`; business assertions proceeded through the full baseline build.

#### IMP-007/B03
- State: RESOLVED
- Category: TEST
- Affects: `docs/spec.md` AC-010 and mandatory EVIDENCE_GATE
- Problem: the route-aggregate evidence assertion compares floating-point CSV text exactly and rejects a numerically valid result within the specification tolerance.
- Evidence: the final aggregate rows matched all expected counts/rates/delays, but Trino returned `50.000000000000014` instead of the string `50.0` for `R1-V2` average deviation; the runner stopped after 138.68 seconds and safely cleaned all task schemas/containers while preserving the volume.
- Unblock: parse aggregate numeric fields and compare them with the approved 0.01 percentage-point tolerance, retain exact identifiers/counts, then rerun the full workflow with a fresh run ID.
- Resolution: the tolerance-aware helper accepted the observed value, preserved exact version/count assertions, and rejected a `50.02` mutation outside the approved 0.01 percentage-point tolerance; `git diff --check` passed.

#### IMP-007/B04
- State: RESOLVED
- Category: ENVIRONMENT
- Affects: `docs/spec.md` AC-012 and mandatory acceptance EVIDENCE_GATE
- Problem: the local Polaris management-catalog evidence request used host proxy settings and received HTTP 403 after every baseline and negative assertion had passed.
- Evidence: the environment exposes HTTP/HTTPS proxy variables; the third run completed the 128-node build and saved all three exact intended DQ failures, then the localhost Polaris request returned `HTTP Error 403: Forbidden`. This matches the repository’s previously observed localhost proxy behavior. Cleanup removed all task schemas/containers and preserved the volume after 232.73 seconds.
- Unblock: use a proxy-disabled urllib opener for localhost Polaris token/catalog requests, preserve secret scanning, and rerun with a fresh isolated run ID.
- Resolution: run `imp007_final4` used a proxy-disabled opener, saved the expected `lakehouse` catalog/storage properties, passed object/catalog/secret gates, exited 0, and restored the initial environment.

#### IMP-007/B05
- State: RESOLVED
- Category: CODE
- Affects: mandatory safety boundary and acceptance cleanup gate
- Problem: after query readiness, a detected pre-existing run-prefix schema still triggers unconditional failure cleanup, which can drop the pre-existing schema with `CASCADE`.
- Evidence: the first fresh reviewer traced `assert_prefixes_absent()` raising after `query_ready=True`, followed by the `finally` branch calling `cleanup_task_data()` for every computed schema name.
- Unblock: track explicit ownership only after the collision check succeeds, gate failure cleanup on that ownership flag, use exact schema-name matching, and prove a collision remains intact after the runner refuses.
- Resolution: cleanup now requires `prefixes_owned=True`, set only after an exact `IN (...)` collision query passes. A synthetic collision propagated the refusal with zero cleanup calls; a failure after ownership produced exactly one cleanup call.

#### IMP-007/B06
- State: RESOLVED
- Category: CODE
- Affects: mandatory secret/evidence-manifest gates and no-false-PASS invariant
- Problem: the runner writes `acceptance_summary.json` as PASS before secret scanning and manifest creation, so a later finalization error can leave a false PASS on disk.
- Evidence: the first fresh reviewer traced PASS assignment/summary before `assert_no_secrets_in_evidence()` and `write_evidence_manifest()`; a secret finding or manifest write failure would return non-zero after the PASS summary was already saved.
- Unblock: make finalization transactional enough that PASS is written only after all final gates succeed; any final gate error must leave a FAIL summary and best-effort manifest, then validate both success and injected failure paths.
- Resolution: finalization now orders scan → manifest → atomic PASS summary. Injected secret-scan and first-manifest failures both returned errors, left `outcome=FAIL`, and created a best-effort manifest; the success-order assertion observed PASS only after both gates.

#### IMP-007/B07
- State: RESOLVED
- Category: REVIEW
- Affects: mandatory STATUS_RECORD and FRESH_READ_ONLY_REVIEW gates
- Problem: after the successful second reviewer call, `Progress/Remaining` still described that completed re-review as pending; correcting Progress is outside the narrow post-review finalization exception.
- Evidence: the second fresh reviewer returned `VERDICT: OK` with no findings, while the reviewed section still contained `Remaining: fresh read-only re-review only`.
- Unblock: set `Remaining` to `none`, validate the status/diff, and obtain one fresh targeted re-review of the corrected section.
- Resolution: `Remaining` is `none`; the unique-section/status assertion and `git diff --check` passed, and the third fresh targeted reviewer confirmed the corrected section with `VERDICT: OK`.

### Review
- Verdict: OK
- Calls: 3
- Fix iterations: 2
- Details: the first fresh reviewer returned `VERDICT: BLOCK` for B05/B06. After targeted code fixes and final acceptance, the second fresh reviewer returned `VERDICT: OK` with no findings. The third fresh targeted reviewer verified the B07 status-only correction and unchanged implementation diff, found no issues, and returned `VERDICT: OK`.

### Next action
After the user-authorized checkpoint commit, await separate authorization for push or transition to another task.

## TASK_ID: SE-AGENT-001

- Source: `docs/bootstrap-schema-evolution.md` §5.1, “SE-AGENT-001 — сохранить текущие инструкции и ресурсы”
- Status: REVIEW_READY
- Updated: 2026-10-29T22:59:30+03:00
- Baseline HEAD: 6d74963e098647c3191c039ffadc667cee020c9c

### Progress
- Implemented: confirmed that SE-AGENT-001 requires no project-code or agent-resource change; preserved `docs/spec.md`, prior `docs/status.md` task history, and the repository's existing resource layout. The only task diff is this required status section.
- Remaining: none.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/bootstrap-schema-evolution.md` §5.1 SE-AGENT-001, preserve current instructions and resources | PASS | fast: baseline HEAD remained `6d74963e098647c3191c039ffadc667cee020c9c`; `git diff --name-only` returned only `docs/status.md`, with no staged or untracked paths, so the approved specification, prior source files, and current resource files are unchanged. |
| `docs/bootstrap-schema-evolution.md` §5.1 SE-AGENT-001, do not add agent resources or duplicate state files | PASS | fast: repository assertions confirmed no `AGENTS.md`, `.pi/settings.json`, `.pi-lens.json`, tracked `.pi/` path, new handoff/status file, or untracked path; `docs/status.md` remains the sole tracked status file and the exact task section occurs once. `git diff --check` exited 0. |

### Issues
#### SE-AGENT-001/B01
- State: RESOLVED
- Category: REVIEW
- Affects: mandatory STATUS_RECORD and FRESH_READ_ONLY_REVIEW gates
- Problem: after the successful first reviewer call, `Progress/Remaining` still described that completed review as pending; correcting Progress is outside the narrow post-review finalization exception.
- Evidence: the first fresh reviewer returned `VERDICT OK` with no findings, while the reviewed section still contained `Remaining: independent fresh read-only review only`.
- Unblock: set `Remaining` to `none`, validate the status/diff, and obtain one fresh targeted re-review of the corrected section.
- Resolution: `Remaining` is `none`; `git diff --check` and the targeted status gate passed, and the second fresh read-only reviewer confirmed the corrected section, complete diff, unchanged AC evidence, and preserved prior sections with `VERDICT OK`.

### Review
- Verdict: OK
- Calls: 2
- Fix iterations: 1
- Details: the first fresh read-only reviewer inspected the complete diff, source criterion, status evidence, forbidden-resource paths, and preservation of prior sections and returned `VERDICT OK` with no findings. After the B01 status correction, the second fresh targeted reviewer verified the corrected section and full diff, found no BLOCKER, DEFERRED, or IMPROVEMENT, and returned `VERDICT OK`.

### Next action
User reviews the checkpoint and, if accepted, stages and commits `docs/status.md`; no push or transition to another task is authorized.

## TASK_ID: SE-ENV-001

- Source: `docs/bootstrap-schema-evolution.md` §5.2, “SE-ENV-001 — schema-evolution acceptance entry point”
- Status: REVIEW_READY
- Updated: 2026-10-29T23:07:59+03:00
- Baseline HEAD: 65798603483a5e5d56d419004358022b09c00de9

### Progress
- Implemented: added executable `scripts/run_schema_evolution_acceptance.py` as a subclass of the accepted core runner, with isolated baseline/evolution names, exact collision ownership gate, Compose lifecycle, task-scoped cleanup, inherited secret scan/evidence manifest/atomic summary, AC-013–AC-020 result slots, and an explicit non-success placeholder for the later SE-IMP workflow.
- Remaining: none.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/bootstrap-schema-evolution.md` §5.2 SE-ENV-001, runner entry point and lifecycle/evidence contract | PASS | fast: LSP diagnostics reported zero findings; `python3 -m py_compile scripts/run_acceptance.py scripts/run_schema_evolution_acceptance.py` exited 0; the new file is executable; core runner source/CLI remained unchanged; the subclass reuses accepted lifecycle, command capture, secret scan, manifest and atomic summary primitives while preventing a false success before SE-IMP-001. |
| `docs/bootstrap-schema-evolution.md` §5.2 SE-ENV-001, CLI/preflight refusal paths | PASS | fast: `--help` exposed `--run-id` and `--evidence-root`; invalid `INVALID-ID` exited 2 with the run-ID contract; a valid run with all four credentials unset exited 1 before creating evidence; a pre-existing evidence directory exited 1 with the collision refusal. |
| `docs/bootstrap-schema-evolution.md` §5.2 SE-ENV-001, ownership-safe failure cleanup | PASS | standard: an in-memory lifecycle harness proved a pre-existing exact evolution-schema collision performs zero cleanup and never enters the workflow; an injected failure after successful ownership performs exactly one cleanup. A cleanup harness asserted only `<run_id>_evolution` and the four `<run_id>_baseline_*` schemas plus `warehouse/<run_id>_` are targeted; an injected secret-scan failure left an atomic `outcome=FAIL` summary and manifest. |

### Issues
#### SE-ENV-001/B01
- State: RESOLVED
- Category: REVIEW
- Affects: mandatory STATUS_RECORD and FRESH_READ_ONLY_REVIEW gates
- Problem: after the successful first reviewer call, `Progress/Remaining` still described that completed review as pending; correcting Progress is outside the narrow post-review finalization exception.
- Evidence: the first fresh reviewer returned `VERDICT OK` with no findings, while the reviewed section still contained `Remaining: independent fresh read-only review only`.
- Unblock: set `Remaining` to `none`, validate the status/diff, and obtain one fresh targeted re-review of the corrected section.
- Resolution: `Remaining` is `none`; the status/diff gate passed, and the second fresh targeted reviewer found no issues and returned `VERDICT OK`.

### Review
- Verdict: OK
- Calls: 2
- Fix iterations: 1
- Details: the first fresh read-only reviewer inspected the complete tracked/untracked diff, implementation, source contracts, safety/evidence behavior and status preservation and returned `VERDICT OK`. After the B01 status correction, the second fresh targeted reviewer verified the full current diff and corrected section, found no BLOCKER, DEFERRED or IMPROVEMENT, and returned `VERDICT OK`.

### Next action
User reviews the checkpoint and, if accepted, stages and commits `scripts/run_schema_evolution_acceptance.py` and `docs/status.md`; no push or transition to another task is authorized.

## TASK_ID: SE-IMP-001

- Source: `docs/bootstrap-schema-evolution.md` §5.3, “SE-IMP-001 — pre/post core regression capture”; `docs/spec.md` AC-013 and AC-020
- Status: REVIEW_READY
- Updated: 2026-10-29T23:22:30+03:00
- Baseline HEAD: 69678d54758aa4b5e485255d09baeb2a0353a88d

### Progress
- Implemented: added pre/post core regression orchestration, deterministic schema/result capture, exact comparison, broad `EVO-P5` absence checks, and an explicit incomplete-slice gate that keeps AC-014–AC-020 from false PASS. Fast checks and the isolated runtime workflow passed their task assertions; cleanup restored the initially stopped Compose state and preserved the project volume.
- Remaining: none.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/spec.md` AC-013; `docs/bootstrap-schema-evolution.md` §5.3 SE-IMP-001 | PASS | acceptance: isolated run `seimp001_core` completed two full 128-result core builds; nine deterministic schema/result captures matched exactly pre/post, and ten package-bearing core relations each had zero `EVO-P5` rows in both phases. The runner recorded `AC-013=PASS` before the intentional incomplete-slice stop. |
| `docs/spec.md` AC-020, SE-IMP-001 contribution | PASS | fast/acceptance: LSP diagnostics and `py_compile` passed; comparator mutation/missing-key probes detected the changed contract. The incomplete runner exited 1 with the exact next-task diagnostic, left AC-014–AC-020 `NOT_RUN`, wrote a FAIL summary rather than a false slice PASS, completed clean secret scan/616-file manifest, removed task schemas/objects/containers, and preserved `iceberg-trino-dbt_rustfs-data`. |

### Issues
#### SE-IMP-001/B01
- State: RESOLVED
- Category: TEST
- Affects: mandatory FINAL_EVIDENCE_AND_DIFF_GATE for AC-013
- Problem: the post-run evidence wrapper compared quoted Trino CSV lines as raw text, so it rejected valid zero-count evidence after the runtime workflow had completed.
- Evidence: the runner exited 1 with the intended incomplete-slice diagnostic after 186 seconds; summary assertions confirmed `AC-013=PASS` and zero core mismatches, then the wrapper failed because a valid row was encoded as `"bronze.bronze_packages","0"` rather than ending in unquoted `,0`.
- Unblock: parse both `evo_p5_absence.csv` files with Python `csv`, re-run the final evidence assertions without repeating the accepted runtime, and confirm cleanup/environment restoration.
- Resolution: the corrected CSV parser confirmed ten zero-count rows in both phases; both 128-result builds, nine matched contracts, clean secret scan, 616-file manifest, zero task containers, and preservation of the original project volume were revalidated.

### Review
- Verdict: OK
- Calls: 1
- Fix iterations: 0
- Details: one fresh read-only reviewer inspected the complete two-file diff, task contracts, implementation, saved acceptance evidence, lifecycle/cleanup behavior, the SE-IMP-001 status section, and preservation of prior sections; it found no BLOCKER, DEFERRED, or IMPROVEMENT and returned `VERDICT OK`.

### Next action
User reviews the checkpoint and, if accepted, stages and commits `scripts/run_schema_evolution_acceptance.py` and `docs/status.md`; no push or transition to SE-IMP-002 is authorized.

## TASK_ID: SE-IMP-002

- Source: `docs/bootstrap-schema-evolution.md` §5.3, “SE-IMP-002 — S0 creation и evidence”; `docs/spec.md` AC-014 and AC-020
- Status: REVIEW_READY
- Updated: 2026-10-29T23:44:32+03:00
- Baseline HEAD: 44addd7d5263bb7d480569d19f25d1a3ad0d9847

### Progress
- Implemented: added the isolated evolution schema and six-column S0 CTAS, representation-independent exact row assertions, single-snapshot validation, `$files` and object mapping, streamed Parquet SHA-256 capture, metadata-log capture, and parsed Iceberg schema/field-ID evidence. Final isolated run `seimp002_s0b` passed the SE-IMP-002 assertions and preserved the intentional incomplete-slice gate for SE-IMP-003.
- Remaining: none.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/spec.md` AC-014; `docs/bootstrap-schema-evolution.md` §5.3 SE-IMP-002 | PASS | acceptance: isolated run `seimp002_s0b` created the six-column evolution table with exact P1–P4 rows, one generated S0 snapshot `1452054778057870415`, one Parquet file containing four records, five task objects, streamed SHA-256 file identity, one metadata-log entry, and parsed metadata JSON with schema ID 0, snapshot ID S0, last column ID 6 and field IDs 1–6. |
| `docs/spec.md` AC-020, SE-IMP-002 contribution | PASS | fast/acceptance: LSP diagnostics, `py_compile`, helper mutation probes and `git diff --check` passed. Run `seimp002_s0b` recorded AC-013/AC-014 PASS, intentionally left AC-015–AC-020 NOT_RUN with `continue with SE-IMP-003`, completed clean secret scan and a 632-file manifest, removed all task schemas/objects/containers/network, and preserved the three pre-existing named volumes. |

### Issues
#### SE-IMP-002/B01
- State: RESOLVED
- Category: TEST
- Affects: mandatory EVIDENCE_GATE for parsed Iceberg field-ID evidence
- Problem: the initial metadata mutation probe did not reject duplicate Iceberg field IDs, so the parser could accept an invalid identity map.
- Evidence: the pure-helper harness changed `delivery_status` field ID from 3 to the already used ID 2; `parse_s0_metadata` returned success and the wrapper exited 1 with `metadata mutation was not detected`.
- Unblock: require field IDs to be unique, rerun the positive and duplicate-ID/current-snapshot mutations, then continue runtime acceptance.
- Resolution: the parser now rejects reused field IDs; the positive six-field metadata sample passed, and duplicate-ID, wrong-current-snapshot and wrong-field-type mutations all raised `AcceptanceError`. `py_compile`, LSP diagnostics and `git diff --check` also passed.

#### SE-IMP-002/B02
- State: RESOLVED
- Category: TEST
- Affects: `docs/spec.md` AC-014 exact S0 row evidence
- Problem: the first runtime assertion compared Trino DOUBLE text to fixed decimal strings, while Trino 484 rendered the valid values in scientific notation.
- Evidence: run `seimp002_s0` reached S0 creation and returned the exact P1–P4 identifiers/status/count/boolean values, but `delivery_duration_hours` appeared as `4.8E1`, `4.8E1`, `3.6E1`, `NULL`; the runner exited 1 after 141 seconds at the row wrapper.
- Unblock: compare the DOUBLE values numerically or render them through an explicit stable decimal projection, then rerun the full isolated workflow with a fresh run ID.
- Resolution: the row assertion now parses non-null duration values numerically while preserving exact identifiers, statuses, counts, booleans and NULLs. A scientific-notation positive sample passed, a `49.0` mutation failed, and full run `seimp002_s0b` passed AC-014 before the intentional SE-IMP-003 stop.

### Review
- Verdict: OK
- Calls: 1
- Fix iterations: 0
- Details: one fresh read-only reviewer inspected the complete two-file diff, source contracts, S0 implementation, saved `seimp002_s0b` evidence, ownership/cleanup and no-false-PASS behavior, the SE-IMP-002 status section, and preservation of prior sections; it found no BLOCKER, DEFERRED, or IMPROVEMENT and returned `VERDICT: OK`.

### Next action
User reviews the checkpoint and, if accepted, stages and commits `scripts/run_schema_evolution_acceptance.py` and `docs/status.md`; no push or transition to SE-IMP-003 is authorized.

## TASK_ID: SE-IMP-003

- Source: `docs/bootstrap-schema-evolution.md` §5.3, “SE-IMP-003 — metadata-only DDL checkpoints”; `docs/spec.md` AC-015 and AC-020
- Status: REVIEW_READY
- Updated: 2026-10-30T00:08:59+03:00
- Baseline HEAD: 337f51d13619069710d270dc165c57be8980ab0f

### Progress
- Implemented: added the three ordered DDL operations, per-checkpoint schema/snapshot/file/object/metadata capture, field-ID and schema-ID assertions, nullable new-field validation, data-file digest comparison, and the next-slice incomplete gate. Final isolated run `seimp003_ddl2` passed AC-013–AC-015, preserved the single S0 snapshot and Parquet identity through schema IDs 1–3, completed core regression, and cleaned all task-owned runtime resources.
- Remaining: none.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/spec.md` AC-015; `docs/bootstrap-schema-evolution.md` §5.3 SE-IMP-003 | PASS | acceptance on final code: run `seimp003_ddl2` executed rename, INTEGER→BIGINT widening and nullable `delivery_priority` add-after in order. Schema IDs advanced 0→1→2→3 while the only data snapshot remained S0 `810038079541715347`; snapshot schema stayed 0. The same single-file identity (4 records, 1120 bytes, SHA-256 `2002cf3d707074934313dbe5a5f3dfe7012978e693a2683ce91b2530ade045a3`) persisted after every DDL. Field IDs 3 and 4 were preserved for rename/widen; the new nullable field received ID 7 and `last-column-id=7`. |
| `docs/spec.md` AC-020, SE-IMP-003 contribution | PASS | fast/acceptance: LSP diagnostics, `py_compile`, CLI, metadata/file mutation probes and `git diff --check` passed. Final run recorded AC-013/014/015 PASS, intentionally left AC-016–AC-020 NOT_RUN with `continue with SE-IMP-004`, matched all nine pre/post core contracts, completed a clean secret scan and 675-file manifest, removed all task schemas/objects/containers/network, and preserved the pre-existing project volume. |

### Issues
#### SE-IMP-003/B01
- State: RESOLVED
- Category: TEST
- Affects: `docs/spec.md` AC-015 and mandatory EVIDENCE_GATE
- Problem: the first runtime checkpoint incorrectly required `$metadata_log_entries.latest_schema_id` to equal the metadata JSON `current-schema-id` after a schema-only DDL.
- Evidence: run `seimp003_ddl` exited 1 after 190.45 seconds with `metadata log/schema JSON mismatch: 0 != 1`; the current metadata JSON correctly contained schema 1 after rename while the unchanged S0 snapshot still referenced schema 0. The runner removed all task schemas/objects/containers and preserved the three pre-existing volumes.
- Unblock: assert that the metadata-log row remains tied to S0 schema 0 while separately validating the current metadata JSON schema ID, then rerun with a fresh isolated run ID.
- Resolution: the assertion now requires the metadata-log snapshot schema to remain the original S0 schema while validating the current metadata JSON schema independently. The direct evidence probe confirmed snapshot schema 0/current schema 1 after rename, and fresh run `seimp003_ddl2` passed all three checkpoints with snapshot schema 0 and current schema IDs 1, 2 and 3.

#### SE-IMP-003/B02
- State: RESOLVED
- Category: REVIEW
- Affects: mandatory FRESH_READ_ONLY_REVIEW and STATUS_RECORD gates
- Problem: after the second reviewer returned `VERDICT OK`, finalization changed `Progress/Remaining` from pending re-review to `none`, which is outside the narrow post-review finalization fields.
- Evidence: the second reviewer reviewed the wording-corrected section while `Remaining` still named the pending re-review; the subsequent finalization changed that Progress field without a fresh review.
- Unblock: keep `Remaining: none` as the accurate pre-review implementation state, validate the status/diff, and obtain one fresh targeted re-review of the complete final section.
- Resolution: the third fresh targeted reviewer inspected the full current diff and complete pre-finalization section, explicitly confirmed `Status: IN_PROGRESS`, `Remaining: none`, AC evidence, B01/B02, review counters and unchanged prior sections, found no findings, and returned `VERDICT OK`.

### Review
- Verdict: OK
- Calls: 3
- Fix iterations: 2
- Details: the first fresh read-only reviewer returned `VERDICT OK` with two non-blocking status wording improvements. The second fresh targeted reviewer verified those corrections and returned `VERDICT OK`. After B02 recorded the out-of-exception Progress finalization, the third fresh targeted reviewer inspected the complete final pre-finalization section, found no BLOCKER, DEFERRED or IMPROVEMENT, and returned `VERDICT OK`.

### Next action
User reviews the checkpoint and, if accepted, stages and commits `scripts/run_schema_evolution_acceptance.py` and `docs/status.md`; no push or transition to SE-IMP-004 is authorized.

## TASK_ID: SE-IMP-004

- Source: `docs/bootstrap-schema-evolution.md` §5.3, “SE-IMP-004 — reader/writer compatibility и S1”; `docs/spec.md` AC-016, AC-017 and AC-020
- Status: REVIEW_READY
- Updated: 2026-10-30T00:27:58+03:00
- Baseline HEAD: 12bf88fc065fe085f382ee72236094ae2cbd893f

### Progress
- Implemented: added current-schema P1–P4 row/type assertions, full before/after invariant capture for the expected old-name writer failure, correct `EVO-P5` insert, direct S0→S1 snapshot-chain validation, retained-S0/new-file checks, metadata validation, and the next-slice incomplete gate. Fast checks and isolated run `seimp004_compat` passed the SE-IMP-004 assertions; cleanup restored the initially stopped Compose state and preserved the pre-existing project volume. After review, the old-name diagnostic gate was hardened and replayed against the saved failure plus unrelated-error mutations.
- Remaining: none.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/spec.md` AC-016; `docs/bootstrap-schema-evolution.md` §5.3 SE-IMP-004 | PASS | acceptance: run `seimp004_compat` read the evolved table through the explicit seven-column current schema and returned exact P1–P4 values; `delivery_priority` was `NULL`, statuses/counts were preserved, and `completed_visit_count` was `BIGINT`. The final metadata retained the expected field IDs and nullable priority field. |
| `docs/spec.md` AC-017; `docs/bootstrap-schema-evolution.md` §5.3 SE-IMP-004 | PASS | acceptance/targeted replay: the old-name INSERT exited 1 with `Insert column name does not exist in target table: delivery_status`; the final diagnostic helper accepted that saved output and rejected success plus two unrelated-error mutations. Complete before/after schema, rows, snapshots, metadata, objects and SHA-256 file identities had zero mismatches. The correct `EVO-P5` insert produced exact five-row output and direct S0 `683260960248810578` → S1 `1122032600352381225` parentage, preserving the four-record S0 file and adding exactly one new record. |
| `docs/spec.md` AC-020, SE-IMP-004 contribution | PASS | fast/acceptance: LSP diagnostics, `py_compile`, CLI, helper mutation probes and `git diff --check` passed. The isolated run recorded AC-013–AC-017 PASS, intentionally left AC-018–AC-020 NOT_RUN with `continue with SE-IMP-005`, matched all nine core contracts, completed a clean secret scan and 710-file manifest, removed all task schemas/objects/containers/network, and preserved the pre-existing project volume. |

### Issues
#### SE-IMP-004/B01
- State: RESOLVED
- Category: TEST
- Affects: mandatory FINAL_EVIDENCE_AND_DIFF_GATE
- Problem: the first post-acceptance evidence wrapper assumed the manifest root was a JSON list, so it stopped after validating the business evidence but before confirming the manifest count.
- Evidence: the wrapper raised `AssertionError`; direct inspection showed `evidence_manifest.json` is the valid object shape `{"files": [...]}` with 710 entries, matching the inherited runner contract.
- Unblock: assert the existing manifest object shape and file list, rerun the complete evidence wrapper without repeating acceptance, then record the confirmed result.
- Resolution: the corrected wrapper validated all AC-016/017 rows, snapshot/file/metadata invariants, old-name failure atomicity, core comparison, cleanup, clean secret scan and the exact 710-file manifest; it printed `acceptance_evidence=pass`.

### Review
- Verdict: OK
- Calls: 2
- Fix iterations: 1
- Details: the first fresh read-only reviewer inspected the complete diff and saved evidence, found no BLOCKER or DEFERRED and returned `VERDICT OK`; it suggested hardening the old-name diagnostic and narrowing the volume wording. After the targeted fix and evidence replay, the second fresh reviewer rechecked the complete post-fix diff, final status section and saved acceptance evidence, found no issues, confirmed the evidence remained applicable, and returned `VERDICT OK`.

### Next action
User reviews the checkpoint and, if accepted, stages and commits `scripts/run_schema_evolution_acceptance.py` and `docs/status.md`; no push or transition to SE-IMP-005 is authorized.

## TASK_ID: SE-IMP-005

- Source: `docs/bootstrap-schema-evolution.md` §5.3, “SE-IMP-005 — S0/S1 historical compatibility и narrowing”; `docs/spec.md` AC-018, AC-019 and AC-020
- Status: REVIEW_READY
- Updated: 2026-10-30T11:30:10+03:00
- Baseline HEAD: 5854963b58a5f97fd1268d7cc6c17f42394d1207

### Progress
- Implemented: revised AC-018 and the implementation plan for Trino 484 snapshot-schema semantics; added typed legacy S0/current S1 projections, post-capture CSV NULL normalization, exact S0/S1/current rows, `typeof` and `IS NULL` evidence, narrowing diagnostics for SQL/Iceberg type names, full atomic before/after invariants, and the SE-IMP-006 continuation gate. Final run `seimp005_typed` passed AC-013–AC-019, core comparison and cleanup evidence.
- Remaining: none.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/spec.md` AC-018; `docs/bootstrap-schema-evolution.md` §5.3 SE-IMP-005 | PASS | acceptance after reviewer fix: run `seimp005_typed` resolved generated S0 `1258327276937234185` through legacy schema 0 and S1 `4895020360701766093`/current through schema 3. All three projections reported exact types `VARCHAR×4, BIGINT, DOUBLE, BOOLEAN`; S0 had 4 exact rows, S1=current had 5, and separate `IS NULL` evidence proved true priority/duration/on-time NULL semantics. |
| `docs/spec.md` AC-019; `docs/bootstrap-schema-evolution.md` §5.3 SE-IMP-005 | PASS | acceptance after reviewer fix: Trino rejected `completed_visit_count` narrowing with non-zero `Cannot change column type ... long -> int`; complete before/after schema, S1 snapshot, five typed rows, metadata, objects and SHA-256 file identities were exactly equal, with `completed_visit_count` remaining `BIGINT`. |
| `docs/spec.md` AC-020, SE-IMP-005 contribution | PASS | fast/acceptance: LSP, `py_compile`, CLI, typed/NULL/diagnostic mutation probes and `git diff --check` passed. Run `seimp005_typed` recorded AC-013–AC-019 PASS, intentionally left AC-020 NOT_RUN with `continue with SE-IMP-006`, matched all nine core contracts, completed clean secret scan and a 742-file manifest, removed all task schemas/objects/containers/network, and preserved the pre-existing project volume. |

### Issues
#### SE-IMP-005/B01
- State: RESOLVED
- Category: ENVIRONMENT
- Affects: `docs/spec.md` AC-018, AC-019 and AC-020 acceptance evidence
- Problem: the runtime Compose preflight cannot render because the four required local training environment variables are absent from the current shell.
- Evidence: `docker compose --profile tools config --quiet` exited 1 and named only `RUSTFS_ACCESS_KEY`, `RUSTFS_SECRET_KEY`, `POLARIS_CLIENT_ID` and `POLARIS_CLIENT_SECRET`; no service was started.
- Unblock: supply task-local non-production values for those four variables and rerun Compose/port preflight before starting the isolated acceptance workflow.
- Resolution: with the documented local non-production training values exported only for the command, `docker compose --profile tools config --quiet` exited 0 and ports 8080/8181/9000/9001 were free.

#### SE-IMP-005/B02
- State: RESOLVED
- Category: SPEC
- Affects: `docs/spec.md` AC-018, AC-020 and approved OPEN-021 handling
- Problem: Trino 484 binds an S0 `FOR VERSION AS OF` query to S0 schema 0, so the required projection using current names `delivery_priority` and `current_status` cannot resolve; the approved AC expects current-schema projection across the old snapshot.
- Evidence: `evolution/historical/s0.csv.stderr.log` records `Column 'delivery_priority' cannot be resolved. Did you mean 'delivery_status' or 'delivery_duration_hours'?`; current metadata proves S0 uses schema 0 while S1/current use schema 3. The workflow exited 1 and wrote a FAIL summary.
- Unblock: the product/spec owner must return AC-018/OPEN-021 to DRAFT and choose a supported compatibility contract or approved stack change; implementation must not silently substitute a legacy-schema query or change pinned versions.
- Resolution: the user approved snapshot-schema-aware normalization without a stack change; `docs/spec.md` and the implementation plan now encode legacy S0 aliases/casts and current S1/current projections. Run `seimp005_revised2` recorded AC-018 PASS before continuing to AC-019.

#### SE-IMP-005/B04
- State: RESOLVED
- Category: TEST
- Affects: revised `docs/spec.md` AC-018 and acceptance EVIDENCE_GATE
- Problem: Trino CSV serializes `CAST(NULL AS VARCHAR)` as an empty field, while the shared expected-row helper uses the explicit evidence sentinel `NULL` produced by the S1/current projections.
- Evidence: run `seimp005_revised` passed the historical S0 query itself, then exited 1 after 245.97 seconds on row `['P1', 'R1-V1', '', 'delivered', '1', '4.8E1', 'true']`; cleanup restored the initially stopped environment.
- Unblock: normalize only the captured S0 `delivery_priority` empty CSV field to the evidence sentinel before exact comparison, retain the SQL-level NULL projection, add a mutation probe, and rerun with a fresh run ID.
- Resolution: the helper now normalizes only the S0 priority empty field in a copy, a non-null priority mutation is rejected, and run `seimp005_revised2` recorded AC-018 PASS with normalized S0=4 and S1=current=5.

#### SE-IMP-005/B05
- State: RESOLVED
- Category: TEST
- Affects: `docs/spec.md` AC-019 and mandatory EVIDENCE_GATE
- Problem: the narrowing operation failed correctly, but the diagnostic helper required SQL type words `BIGINT`/`INTEGER` while Trino reported Iceberg type names `long -> int`.
- Evidence: run `seimp005_revised2` recorded AC-018 PASS, then the DDL exited non-zero with `Failed to set column type: Cannot change column type: completed_visit_count: long -> int`; the helper rejected this relevant failure and the workflow cleaned task resources.
- Unblock: accept either the SQL type pair or the observed Iceberg type pair while still requiring the target column and non-zero exit, replay positive/unrelated mutations, and confirm the saved run reached no state-changing narrowing operation.
- Resolution: the helper now requires the target column, a type-change failure class and either `BIGINT/INTEGER` or `long -> int`; saved-output and unrelated-error mutation probes passed. Run `seimp005_final` completed the after-state capture with zero invariant mismatches and AC-019 PASS.

#### SE-IMP-005/B06
- State: RESOLVED
- Category: TEST
- Affects: revised `docs/spec.md` AC-018 and mandatory FRESH_READ_ONLY_REVIEW gate
- Problem: historical row queries cast typed values to `VARCHAR` and use a string `NULL` sentinel inside SQL for S1/current, so AC-018 can pass without proving the required `BIGINT/DOUBLE/BOOLEAN` result types or true SQL NULL priority semantics.
- Evidence: the first fresh reviewer traced `scripts/run_schema_evolution_acceptance.py` historical projections and `seimp005_final/commands.jsonl`; `comparison.json` records counts/equality but no expression types, and a literal priority value `'NULL'` would be indistinguishable from SQL NULL in the row assertion. It returned `VERDICT BLOCK`.
- Unblock: execute typed projections without serialization casts/COALESCE, normalize CSV null encoding only after capture, add `typeof(...)` evidence for the seven result columns and explicit `IS NULL` assertions for nullable fields, then rerun acceptance and fresh review.
- Resolution: historical SQL now preserves typed values and SQL NULLs; only captured CSV empties are normalized. Type and NULL mutation probes passed, and `seimp005_typed` produced exact `projection_types.json`/`null_semantics.json`, AC-018 PASS and applicable AC-019 evidence.

#### SE-IMP-005/B07
- State: RESOLVED
- Category: TEST
- Affects: mandatory FINAL_EVIDENCE_AND_DIFF_GATE after B06 fix
- Problem: the first post-fix evidence wrapper rejected any command containing the earlier compatibility-state `COALESCE` serialization, rather than scoping the prohibition to AC-018 historical projections.
- Evidence: all typed/NULL evidence assertions preceding it passed; diagnostics found `COALESCE` only in `capture_compatibility_state` commands used by AC-016/narrowing bundles, while the historical `FOR VERSION AS OF` commands use typed projections and separate `typeof`/`IS NULL` checks.
- Unblock: scope the assertion to historical snapshot commands/evidence paths, rerun the complete wrapper without repeating acceptance, and preserve the accepted B06 runtime evidence if it passes.
- Resolution: the corrected complete wrapper passed with exact typed rows, `typeof`/`IS NULL` evidence, zero narrowing/core mismatches, clean secret scan, 742 manifest files, empty task prefix, no project containers and preserved project volume.

#### SE-IMP-005/B03
- State: RESOLVED
- Category: TEST
- Affects: mandatory FINAL_EVIDENCE_AND_DIFF_GATE
- Problem: the first post-run evidence wrapper assumed `secret_scan.json` contains a `status` field and stopped before completing cleanup/manifest assertions.
- Evidence: the wrapper raised `KeyError: 'status'`; the inherited runner's actual secret-scan shape contains `findings` and `secret_values_written` instead.
- Unblock: assert the existing secret-scan schema, null-safe empty object listing, cleanup logs/environment and manifest list, then rerun the final evidence wrapper without repeating acceptance.
- Resolution: the corrected wrapper for the earlier blocked run `seimp005_hist` passed with 435 manifest files, empty secret findings, no task-prefix objects, exact five schema drops, no remaining project containers, and preservation of the initially present project volume. The later final run is recorded separately with 734 files.

### Review
- Verdict: OK
- Calls: 2
- Fix iterations: 1
- Details: the first fresh read-only reviewer returned `VERDICT BLOCK` for B06 and two status/plan improvements. After the targeted typed/NULL evidence fix, final acceptance and documentation corrections, the second fresh reviewer inspected the complete four-file diff and `seimp005_typed` evidence, found no BLOCKER, DEFERRED or IMPROVEMENT, and returned `VERDICT OK`.

### Next action
After this user-authorized checkpoint commit, await separate authorization for push or transition to SE-IMP-006.

## TASK_ID: SE-IMP-006

- Source: `docs/bootstrap-schema-evolution.md` §5.3, “SE-IMP-006 — end-to-end evidence и cleanup”; `docs/spec.md` AC-020
- Status: REVIEW_READY
- Updated: 2026-10-30T12:14:44+03:00
- Baseline HEAD: 55d680bcdfed2005e413a43a9366cc2e4e02332a

### Progress
- Implemented: added exact 21-table catalog registration evidence, Polaris catalog and complete task-prefix Iceberg object capture, final manifest coverage assertions, and an AC-020 finalization gate that marks PASS only after AC-013–AC-019, task cleanup, environment restoration, secret scan and manifest validation. After reviewer feedback, cleanup now queries the exact five task schemas after DROP and requires a header-only result. Fast checks and retained-schema mutation probes passed; isolated run `seimp006_final2` completed the full workflow and restored the environment.
- Remaining: none.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/spec.md` AC-020; `docs/bootstrap-schema-evolution.md` §5.3 SE-IMP-006 | PASS | fast/acceptance: LSP diagnostics, `py_compile`, CLI help, catalog/object/manifest/finalization and retained-schema mutation probes plus `git diff --check` passed. Run `seimp006_final2` exited 0 in 330.75 seconds with AC-013–AC-020 PASS, 153 recorded commands, exact 21 task tables including one evolution table, 122 task-prefix Iceberg objects, clean secret scan and a verified 748-file manifest. Post-drop evidence returned header-only `cleanup/remaining_schemas.csv`, an empty task object prefix, no project containers or bound project ports, and the preserved pre-existing project RustFS volume. |

### Issues
#### SE-IMP-006/B01
- State: RESOLVED
- Category: TEST
- Affects: `docs/spec.md` AC-020 and mandatory EVIDENCE_GATE
- Problem: cleanup can report success and AC-020 PASS without querying that all five task-owned schemas are absent after the DROP operations.
- Evidence: the first fresh reviewer traced `cleanup_task_data` and `seimp006_final/commands.jsonl`; after five DROP commands the workflow only lists the object prefix, and no `cleanup/remaining_schemas.csv` assertion exists. It returned `VERDICT: BLOCK`.
- Unblock: add an exact post-drop query for the five schema names, require a header-only result, include it in the manifest contract, run a retained-schema mutation probe and a fresh isolated acceptance run, then re-review.
- Resolution: cleanup now saves and asserts header-only `cleanup/remaining_schemas.csv`; the retained-schema lifecycle mutation is rejected, and final run `seimp006_final2` recorded the exact post-drop query with zero task schemas while AC-020 remained gated through the verified manifest.

### Review
- Verdict: OK
- Calls: 2
- Fix iterations: 1
- Details: the first fresh read-only reviewer returned `VERDICT: BLOCK` for B01. After the targeted cleanup assertion, mutation probe and fresh acceptance run, the second fresh reviewer inspected the complete corrected diff and `seimp006_final2` evidence, confirmed B01 resolution, found no BLOCKER or IMPROVEMENT, and returned `VERDICT: OK`. DEFERRED: the reviewer toolset could not independently execute Git/LSP/fast checks; the main-agent checks and saved runtime evidence cover those gates.

### Next action
User reviews the checkpoint and, if accepted, stages and commits `scripts/run_schema_evolution_acceptance.py` and `docs/status.md`; no push or transition to another slice is authorized.

## TASK_ID: PART-PROBE-001

- Source: `docs/bootstrap-partitioning-file-pruning.md` §4.8, “PART-PROBE-001 — writer topology и `$files` schema”; supporting contract `docs/spec.md` §11.2–§11.7
- Status: REVIEW_READY
- Updated: 2026-10-31T00:04:01+03:00
- Baseline HEAD: 784d203887374ed1ee98ea39623941977d100f95

### Progress
- Implemented: started the isolated pinned stack; proved query readiness and collision-free ownership; selected ten routes with exact bucket distribution 3/3/2/2; created balanced `U/D/R/DR` by one CTAS per table; verified exact rows, logical equality, tuple/file topology, `SHOW CREATE TABLE`, typed `$files` bounds and representative no-extra-file-exclusion checks; captured 271 Iceberg objects; removed the exact schema and residual task keys; restored the initially stopped environment with all three pre-existing volumes preserved; wrote a clean secret scan and 79-file evidence manifest.
- Remaining: none.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/bootstrap-partitioning-file-pruning.md` §4.8 PART-PROBE-001, exact balanced rows and partition topology | PASS | acceptance: four single-CTAS writes completed in 5.43/2.87/2.35/3.76 seconds; every layout has 256000 unique rows, 50 days, 10 routes and exact full-scan aggregate 256000/224000/160000/4800000. Bidirectional reconciliation against `U` returned zero differences; `$partitions`/`$files` proved `D=50/50`, `R=4/4`, `DR=200/200` non-empty tuples/files. |
| `docs/bootstrap-partitioning-file-pruning.md` §4.8 PART-PROBE-001, pinned Trino 484 `$files` schema and typed lower/upper bounds | PASS | acceptance: `DESCRIBE <table$files>` exposes `lower_bounds`/`upper_bounds` as typed rows with fields 1–8 matching the benchmark schema; direct field access such as `lower_bounds."2"` and `lower_bounds."4"` succeeded. Representative day 2025-03-30 and route `BENCH-R0002` selected one candidate file in each applicable tuple/control and every selected file's typed bounds included the target, so bounds excluded no additional file. |
| `docs/bootstrap-partitioning-file-pruning.md` §4.8 PART-PROBE-001, isolated cleanup and environment restoration | PASS | acceptance: before cleanup the exact prefix contained 271 Iceberg objects (5655939 bytes). `DROP SCHEMA ... CASCADE` removed the schema; after Polaris timed out deleting 212 residual task objects, an asserted exact-key subset manifest removed only those keys. Final prefix/schema checks are empty, `docker compose down` restored the initially stopped state in 5.44 seconds, all three pre-existing volumes remain, the secret scan is clean and the manifest covers 79 evidence files. |

### Issues
#### PART-PROBE-001/B01
- State: RESOLVED
- Category: TEST
- Affects: `docs/bootstrap-partitioning-file-pruning.md` §4.8 route mapping prerequisite and mandatory EVIDENCE_GATE
- Problem: the first route-mapping query used the documentation shorthand `system.bucket` without a session catalog, so Trino could not resolve the function and the probe tables were not created.
- Evidence: Trino query `20261030_204344_00002_ndr9b` exited 1 with `Session default catalog must be set to resolve a partial function name: system.bucket`; the exact schema collision check had passed and `CREATE SCHEMA` was not reached.
- Unblock: invoke the Iceberg connector function with the explicit catalog namespace, rerun the exact 3/3/2/2 mapping assertion, and only then establish schema ownership.
- Resolution: `lakehouse.system.bucket` returned the exact 3/3/2/2 distribution for ten routes; the assertion passed and `CREATE SCHEMA lakehouse.partprobe001_partition_benchmark` then succeeded.

#### PART-PROBE-001/B02
- State: RESOLVED
- Category: TEST
- Affects: candidate write protocol for the 200-tuple `DR` layout
- Problem: the attempted session override `lakehouse.max_partitions_per_writer = 250` is outside the pinned connector's allowed range, so it cannot be used to force one writer to hold all composite partitions.
- Evidence: Trino query `20261030_204537_00006_ndr9b` exited 1 with `max_partitions_per_writer must be between 1 and 100`; no table write was attempted by that query.
- Unblock: run the single-CTAS candidate with the default 100-partition limit and verify whether parallel writers distribute all 200 tuples successfully; if not, use bounded interleaved batches without changing data or partition specs.
- Resolution: the unchanged single CTAS at the pinned default completed in 3.76 seconds and produced exactly 200 non-empty composite tuples with one file per tuple and 256000 total rows; no batching or contract change was required.

#### PART-PROBE-001/B03
- State: RESOLVED
- Category: ENVIRONMENT
- Affects: `docs/bootstrap-partitioning-file-pruning.md` §4.8 cleanup and mandatory environment-restoration gate
- Problem: schema purge removed the catalog namespace but did not finish deleting all task-owned Iceberg objects, so the required empty prefix was not initially achieved.
- Evidence: pre-cleanup inventory contained 271 objects; the schema absence query was header-only, but immediate, 10-second and later retries each found 212 residual objects (205 Parquet, five Avro and two stats; 2117304 bytes). Polaris logs show concurrent cleanup tasks and repeated `Timeout waiting for connection from pool` failures in `S3FileIO.deleteBatch`.
- Unblock: verify every residual key is an exact-prefix subset of the captured task inventory, delete only those explicit keys through the task-owned RustFS credentials, then recheck the prefix before stopping Compose; do not delete the bucket, volumes or any other prefix.
- Resolution: all 212 residual keys were unique, matched the exact task prefix and were a subset of the captured 271-key inventory; one explicit `delete-objects` manifest removed them. The final listing is empty, Compose is stopped, ports are free and all three pre-existing volumes remain.

### Review
- Verdict: OK
- Calls: 1
- Fix iterations: 0
- Details: one fresh read-only reviewer inspected the complete append-only tracked diff, source contract, every required ignored evidence path, manifest/hash coverage, cleanup fallback and environment restoration. It found no BLOCKER, DEFERRED or IMPROVEMENT and returned `VERDICT OK`; status-only finalization is permitted.

### Next action
User reviews the checkpoint and, if accepted, stages and commits `docs/status.md`; no push or transition to PART-PROBE-002 is authorized.

## TASK_ID: PART-PROBE-002

- Source: `docs/bootstrap-partitioning-file-pruning.md` §4.8, “PART-PROBE-002 — plan/stats capture”; supporting contract `docs/spec.md` §11.3–§11.7
- Status: REVIEW_READY
- Updated: 2026-10-31T00:41:59+03:00
- Baseline HEAD: c3470bc8ab1a160833f4fa9e8b91018a473ede35

### Progress
- Implemented: started the isolated pinned stack; established ownership and the exact 3/3/2/2 route mapping; created balanced `U/D/R/DR`; captured exact results, distributed JSON, IO JSON and `EXPLAIN ANALYZE` for date/route/combined across all four layouts; matched IO estimates and runtime input rows to partition metadata; fixed a fail-closed parser/summary contract with mutation evidence and a bounded query-protocol fallback; removed the exact schema and residual object keys; restored the initially stopped environment.
- Remaining: none.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/bootstrap-partitioning-file-pruning.md` §4.8 PART-PROBE-002, one Iceberg scan and visible partition constraint | PASS | acceptance: all 12 query-layout captures contain exactly one task-schema `ScanProject`/`ScanFilterProject`; `EXPLAIN (TYPE IO, FORMAT JSON)` exposes the expected date/route query-column constraints and its output-row estimate exactly matches `$partitions` eligible records (date 256000/5120/256000/5120, route 256000/256000/51200/51200, combined 256000/5120/51200/1024 for U/D/R/DR). Trino 484 distributed descriptors visibly mark the day constraint but not the hidden bucket transform; this limitation is explicitly preserved rather than misreported. |
| `docs/bootstrap-partitioning-file-pruning.md` §4.8 PART-PROBE-002, parseable physical input and expected relative reduction | PASS | acceptance: every `EXPLAIN ANALYZE` scan yielded input rows, bytes, physical input and splits. Date physical input was U=977920B, D=11940B, DR=33070B; route U=977920B, R=377110B, DR=401650B; combined U=977920B, D=11940B, R=377110B, DR=8030B, with DR strictly below D and R. All layouts returned the exact 5120/4480/3200/96000, 25600/22400/16000/480000 and 512/448/320/9600 aggregates. |
| `docs/bootstrap-partitioning-file-pruning.md` §4.8 PART-PROBE-002, parser/summary decision and isolated cleanup | PASS | acceptance: `workload/parser_contract.json` fixes the Trino-484 composite summary schema (distributed scan cardinality + IO constraints/eligible estimate + runtime physical stats); the manifest-covered `replay_parser_mutations.py` reproduced seven positive/fail-closed cases with deterministic patches and captured actual errors, and `/v1/statement` final stats were validated only as a bounded runtime fallback. The run captured 271 objects, explicitly deleted 161 exact-prefix residual keys after catalog purge, left the schema/prefix empty, restored Compose stopped with ports free and the pre-existing volume preserved, produced a clean secret scan and a 171-file manifest including `probe_summary.json`. |

### Issues
#### PART-PROBE-002/B01
- State: RESOLVED
- Category: TEST
- Affects: `docs/bootstrap-partitioning-file-pruning.md` §4.8 plan/stats capture
- Problem: the first workload-capture wrapper omitted the task-local Compose interpolation environment, so the query did not execute.
- Evidence: `docker compose exec` exited 1 with only the four required missing-variable interpolation errors before invoking Trino; the running task stack remains healthy.
- Unblock: export the same tracked local training values for every Compose command and rerun the unchanged date capture.
- Resolution: rerunning the unchanged capture with the tracked task-local training environment produced all 12 result/distributed-plan/IO-plan/runtime evidence bundles successfully.

#### PART-PROBE-002/B02
- State: RESOLVED
- Category: TEST
- Affects: `docs/bootstrap-partitioning-file-pruning.md` §4.8 visible-constraint evidence and mandatory EVIDENCE_GATE
- Problem: the first parser required the distributed-plan scan descriptor to expose `constraint on [route_id]` for bucket partition pruning, but Trino 484 renders the route case as `ScanFilterProject` with a route predicate and no descriptor constraint marker.
- Evidence: `EXPLAIN (TYPE DISTRIBUTED, FORMAT JSON)` for `balanced_r WHERE route_id='BENCH-R0002'` contains exactly one owned Iceberg scan and `filterPredicate=(route_id = ...)`, but no `constraint on` suffix; the capture wrapper stopped before accepting ambiguous plan evidence.
- Unblock: add documented `EXPLAIN (TYPE IO, FORMAT JSON)` column-constraint capture, retain distributed scan cardinality and runtime physical-input evidence, and verify whether this combined summary is stable without claiming that the distributed descriptor exposes bucket transforms.
- Resolution: the final composite parser uses distributed JSON for exact scan cardinality, IO JSON for machine-readable query constraints and eligible-row estimates, and `EXPLAIN ANALYZE` for runtime physical input; all 12 summaries passed, while the absent bucket descriptor marker remains documented as a Trino-484 limitation.

#### PART-PROBE-002/B03
- State: RESOLVED
- Category: TEST
- Affects: supporting eligible-partition metadata assertion
- Problem: the first metadata query encoded the Iceberg metadata-table `$` as the literal text `\\u0024`, so Trino looked for a nonexistent table and no metadata assertion executed.
- Evidence: the query exited 1 with `Table ... balanced_u\\u0024partitions does not exist`; workload result/plan/runtime captures were already complete and remain unaffected.
- Unblock: quote the actual metadata table names with a literal `$`, rerun the 12-row eligible-record matrix and compare it to IO-plan estimates.
- Resolution: the corrected UNION-based metadata query used literal `$partitions` names, returned the exact 12-cell eligible-record matrix, and every IO-plan output-row estimate matched its metadata value.

#### PART-PROBE-002/B04
- State: RESOLVED
- Category: TEST
- Affects: parser negative/mutation evidence
- Problem: the first duplicate-scan mutation copied the output fragment, which contains no scan, so the parser correctly continued to see one scan and the mutation wrapper failed.
- Evidence: the wrapper stopped at `duplicate scan accepted`; inspection shows the duplicated fragment was the first output fragment rather than the source fragment containing `ScanFilterProject`.
- Unblock: duplicate the actual source fragment selected by scan-node traversal, then rerun all byte-unit, scan-cardinality, IO-constraint and missing-physical-input mutations.
- Resolution: the corrected mutation duplicated the source fragment containing the scan; duplicate distributed/runtime scans, duplicate IO input, missing IO constraint, missing physical input and unknown byte unit were all rejected, while B/kB/MB/GB positive cases passed.

#### PART-PROBE-002/B05
- State: RESOLVED
- Category: ENVIRONMENT
- Affects: isolated cleanup and environment-restoration gate
- Problem: `DROP SCHEMA ... CASCADE` removed the catalog schema but left task-owned Iceberg objects under the exact benchmark prefix.
- Evidence: the pre-cleanup inventory contained 271 objects; after the schema drop and wait, 161 captured task-prefix objects remained.
- Unblock: prove every residual key is unique, under the exact task prefix and a subset of the pre-cleanup inventory, then delete only those explicit keys and recheck schema/prefix/environment state.
- Resolution: all 161 residual keys satisfied the ownership assertions and were deleted by explicit manifest; final schema/prefix checks are empty, Compose is stopped, manifest-covered `cleanup/final_ports.txt` records all four project ports free, and the pre-existing project volume remains.

#### PART-PROBE-002/B06
- State: RESOLVED
- Category: TEST
- Affects: mandatory EVIDENCE_GATE and FRESH_READ_ONLY_REVIEW
- Problem: the first reviewer found that parser mutation PASS values were only a summary without a manifest-covered executable repro, deterministic mutation patches or captured actual errors.
- Evidence: reviewer call 1 returned `VERDICT BLOCK`; `workload/parser_mutations.json` contains only seven `PASS` strings and `commands.jsonl` contains only the 48 workload captures.
- Unblock: save and execute a standalone parser mutation replay with per-case mutation, expected/actual error and command result; include it and `probe_summary.json` in the rebuilt manifest, add a persisted port-restoration assertion or remove that claim, then obtain fresh re-review.
- Resolution: added and executed manifest-covered `workload/replay_parser_mutations.py`; `parser_mutations_detailed.json` records each source, deterministic patch, expected substring and actual error, the command exited 0, `probe_summary.json` is now hashed by the 171-file manifest, and final port evidence is persisted.

### Review
- Verdict: OK
- Calls: 2
- Fix iterations: 1
- Details: reviewer call 1 independently confirmed scan/result/metadata/runtime reduction/cleanup claims and returned `VERDICT BLOCK` for non-reproducible mutation evidence. After the targeted replay/manifest/port-evidence fix, reviewer call 2 inspected the complete corrected diff and ignored evidence, confirmed B06 resolution and all counters, found no BLOCKER, DEFERRED or IMPROVEMENT, and returned `VERDICT OK`.

### Next action
User reviews the checkpoint and, if accepted, stages and commits `docs/status.md`; no push or transition to PF-ENV-001 is authorized.

## TASK_ID: PF-ENV-001

- Source: `docs/bootstrap-partitioning-file-pruning.md` §5.2, “PF-ENV-001 — isolated acceptance entry point”
- Status: REVIEW_READY
- Updated: 2026-10-31T01:07:03+03:00
- Baseline HEAD: e527f1a149f2752bee2c09c2d072a0b190c44dbe

### Progress
- Implemented: added the executable isolated partitioning/file-pruning runner with AC-021–AC-027 placeholders, exact benchmark namespace/table identities, inherited lifecycle/evidence finalization, ownership-gated cleanup, and atomic summary output.
- Remaining: none.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/bootstrap-partitioning-file-pruning.md` §5.2 PF-ENV-001, runner entry point and lifecycle/evidence contract | PASS | fast/standard: LSP diagnostics reported zero findings; `py_compile` passed for the core, schema-evolution and new runners; the new executable runner exposes AC-021–AC-027 slots, exact eight-table identities, inherited command/evidence/secret/manifest lifecycle and atomic PASS/FAIL summary behavior. An injected final-gate failure wrote atomic `outcome=FAIL` evidence and a manifest with no temporary summary left behind. |
| `docs/bootstrap-partitioning-file-pruning.md` §5.2 PF-ENV-001, CLI/preflight refusal paths | PASS | fast: executable mode, `--help`, invalid run ID (exit 2), missing env (exit 1 before evidence creation), existing evidence-directory refusal (exit 1), shared-runner immutability and `git diff --check` all passed. |
| `docs/bootstrap-partitioning-file-pruning.md` §5.2 PF-ENV-001, ownership-safe failure cleanup | PASS | standard: an in-memory lifecycle harness proved an exact pre-existing schema collision performs zero cleanup, while an injected failure after ownership performs exactly one cleanup. The real cleanup method targets only `<run_id>_partition_benchmark`, verifies exact schema absence and checks only `warehouse/<run_id>_partition_benchmark/`. |

### Issues
#### PF-ENV-001/B01
- State: RESOLVED
- Category: TEST
- Affects: `docs/bootstrap-partitioning-file-pruning.md` §5.2 PF-ENV-001 lifecycle/evidence and ownership-safe cleanup checks
- Problem: the first combined standard harness exited at an assertion, so its lifecycle/cleanup/atomic-summary evidence was incomplete.
- Evidence: the Python harness exited 1 with `AssertionError` at line 128 after the fast checks had passed; no repository runtime service was started.
- Unblock: isolate the failing assertion, correct the test or implementation as warranted, then rerun the complete standard harness.
- Resolution: the failing assertion incorrectly expected AC slots to remain `NOT_RUN` after simulating a post-behavior final gate failure; the inherited contract correctly retains business AC `PASS` while the overall atomic summary is `FAIL`. The corrected complete harness passed lifecycle, exact cleanup scope, summary and manifest assertions.

#### PF-ENV-001/B02
- State: RESOLVED
- Category: REVIEW
- Affects: mandatory STATUS_RECORD and FRESH_READ_ONLY_REVIEW gates
- Problem: after the successful first reviewer call, `Progress/Remaining` still described that completed review as pending; correcting Progress was outside the narrow post-review finalization exception.
- Evidence: the first fresh reviewer returned `VERDICT OK` with no BLOCKER, while the reviewed section still contained `Remaining: independent fresh read-only review only`.
- Unblock: set `Remaining` to `none`, validate the status/diff, and obtain one fresh targeted re-review of the corrected section.
- Resolution: `Remaining` is `none`; the targeted status/diff gate and LSP diagnostics passed, and the second fresh reviewer confirmed the corrected section, complete diff, counters, evidence and unchanged prior sections with `VERDICT OK`.

### Review
- Verdict: OK
- Calls: 2
- Fix iterations: 1
- Details: the first fresh read-only reviewer inspected the complete tracked/untracked diff and returned `VERDICT OK` with two non-blocking DEFERRED notes. After the required `Progress/Remaining` correction, the second fresh targeted reviewer verified B02 resolution, the complete corrected diff, status counters/evidence and preservation of prior sections; it found no BLOCKER or IMPROVEMENT and returned `VERDICT OK`. DEFERRED: before a future successful behavior workflow, add a slice-specific final PASS gate and exact-inventory residual-object cleanup fallback.

### Next action
User reviews the checkpoint and, if accepted, stages and commits `scripts/run_partitioning_file_pruning_acceptance.py` and `docs/status.md`; no push or transition to PF-ENV-002 is authorized.

## TASK_ID: PF-ENV-002

- Source: `docs/bootstrap-partitioning-file-pruning.md` §5.2, “PF-ENV-002 — pure helper/parser tests”
- Status: REVIEW_READY
- Updated: 2026-10-31T01:33:42+03:00
- Baseline HEAD: bfa80234ec25d9f9288d7d2a2f3479c52a3c60a6

### Progress
- Implemented: added the pure route/group/aggregate/eligible-matrix, fail-closed distributed/IO/runtime parsers, bounds and 52-case final-manifest helpers plus a 20-test stdlib positive/mutation suite; runtime parsing now requires one total scan and rejects foreign-scan stats; replayed all 12 saved pinned-stack captures.
- Remaining: none.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/bootstrap-partitioning-file-pruning.md` §5.2 PF-ENV-002, stdlib pure helper/parser test module | PASS | fast after targeted fix: `py_compile` passed and `python3 -m unittest -v scripts.tests.test_partitioning_file_pruning_acceptance` passed all 20 tests. |
| `docs/bootstrap-partitioning-file-pruning.md` §5.2 PF-ENV-002, route/group/aggregate/eligible-matrix and bounds decisions | PASS | fast: exact 3/3/2/2 route roles, balanced/skewed group sizes, all aggregate/matrix rows, bounds decisions and wrong-bucket/count/bounds mutations passed; LSP diagnostics reported zero findings. |
| `docs/bootstrap-partitioning-file-pruning.md` §5.2 PF-ENV-002, byte parser, plan scan cardinality, manifest completeness and false-cleanup mutations | PASS | fast/standard after targeted fix: parser rejects an owned scan without stats followed by a foreign scan with stats, as well as unknown units, duplicate scans/inputs, missing constraints/physical input, missing cases, invalid/duplicate manifest entries and false cleanup. The 12 saved Trino-484 captures still parse and match IO/runtime eligible rows. |

### Issues
#### PF-ENV-002/B01
- State: RESOLVED
- Category: TEST
- Affects: `docs/bootstrap-partitioning-file-pruning.md` §5.2 PF-ENV-002 required wrong-bucket mutation and mandatory EVIDENCE_GATE
- Problem: the wrong-bucket test mutates a row that is already in bucket 3, so no bucket-count defect is introduced and the expected rejection does not occur.
- Evidence: the 19-test unittest run exited 1 only at `test_rejects_wrong_bucket_count_mutation` with `AcceptanceError not raised`; inspection shows `mutated[-2]["bucket_id"] = 3` preserves that row's original bucket.
- Unblock: mutate an actual bucket-2 row into bucket 3, rerun the complete suite, and confirm the exact bucket-count failure is detected.
- Resolution: the mutation now changes selected bucket-2 row index 6 to bucket 3; the complete final 20-test suite exited 0 and the exact bucket-count rejection passed.

#### PF-ENV-002/B02
- State: RESOLVED
- Category: TEST
- Affects: standard replay of pinned Trino-484 parser evidence and mandatory EVIDENCE_GATE
- Problem: the first saved-probe replay passed `date` directly to the helper whose approved balanced case name is `day`, so the wrapper stopped before completing all 12 parser assertions.
- Evidence: the replay exited 1 with `AcceptanceError: unknown eligible-record case: balanced/date`; route mapping and bounds checks had passed, and the parser had already read the first saved capture successfully.
- Unblock: map saved probe names `date/combined` to helper names `day/day_route`, rerun the unchanged 12-capture replay, and require IO/runtime eligible rows to match.
- Resolution: the corrected replay maps `date` to `day` and `combined` to `day_route`; it exited 0 after parsing 12 distributed/IO/runtime captures, with exact eligible-row matches plus route-mapping and bounds PASS.

#### PF-ENV-002/B03
- State: RESOLVED
- Category: CODE
- Affects: runtime plan parser fail-closed invariant, `docs/bootstrap-partitioning-file-pruning.md` §4.5/§5.2 parser contract, and mandatory FRESH_READ_ONLY_REVIEW gate
- Problem: `parse_explain_analyze` searches from the owned scan to the end of the plan, so an owned scan without stats can incorrectly consume physical-input statistics from a later foreign scan.
- Evidence: reviewer call 1 returned `VERDICT BLOCK` with a reproducible owned-scan-without-stats followed by foreign-scan-with-stats path; the current duplicate-plan mutation only proves duplicate owned-scan cardinality.
- Unblock: bound stats parsing to the owned scan fragment or reject subsequent scan ambiguity, add the exact foreign-scan mutation, rerun the complete suite and 12-capture replay, then obtain fresh re-review.
- Resolution: runtime parsing now requires exactly one total `ScanProject`/`ScanFilterProject`; a new mutation with one owned scan lacking stats followed by a foreign scan with stats is rejected. All 20 tests, LSP diagnostics, whitespace checks and the 12-capture replay passed.

### Review
- Verdict: OK
- Calls: 2
- Fix iterations: 1
- Details: reviewer call 1 returned `VERDICT BLOCK` only for PF-ENV-002/B03. After the targeted parser/mutation fix, reviewer call 2 re-read the complete tracked/untracked diff, source contracts, saved captures and status section; it confirmed B03 resolution, found no BLOCKER, DEFERRED or IMPROVEMENT, and returned `VERDICT OK`.

### Next action
User reviews the checkpoint and, if accepted, stages and commits `scripts/run_partitioning_file_pruning_acceptance.py`, `scripts/tests/test_partitioning_file_pruning_acceptance.py`, and `docs/status.md`; no push or transition to PF-ENV-003 is authorized.
