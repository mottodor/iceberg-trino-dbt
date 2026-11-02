# Task status

## Current project state

- Reconciled: **2026-11-02**, through Time travel implementation commit `1bf0c5a` and the documentation checkpoint containing this update.
- **Four slices are implemented, tested and committed. All 42 recorded tasks are DONE**, including TT-DOC-001 in this documentation checkpoint.
- Full-project completion is not claimed: maintenance, verification of incremental-predicate coverage and full learning-outcome traceability (AC-002) remain open.

| Completed slice | Recorded tasks | Final acceptance | Completion commit |
|---|---|---|---|
| Core lakehouse | PROBE-001–003, BOOT-ENV-001–003, IMP-001–007 (13) | `imp007_final5`: PASS, 2026-10-29; AC-001 and AC-003–AC-012 | `82b89ab` |
| Schema evolution | SE-AGENT-001, SE-ENV-001, SE-IMP-001–006 (8) | `seimp006_final2`: PASS, 2026-10-30; AC-013–AC-020 | `25ff57e` |
| Partitioning / file pruning | PART-PROBE-001–002, PF-ENV-001–002, PF-IMP-001–006 (10) | `pfimp006_final`: PASS, 2026-11-01; AC-021–AC-027 | `88fc7db` |
| Time travel / rollback | TT-AGENT-001, TT-ENV-001–002, TT-PROBE-001, TT-IMP-001–006, TT-DOC-001 (11) | `tt_imp006_final`: PASS, 2026-11-02; AC-028–AC-033 | `1bf0c5a`; documentation follows in this checkpoint |

### Evidence and verification

- Final summaries are retained under `artifacts/acceptance/<run-id>/acceptance_summary.json`. These local, Git-ignored directories are not supplied by a fresh clone.
- All four summaries record outcome PASS, error null and PASS for every criterion assigned to the slice. Environment/probe/staged CHECKPOINT runs are not full-slice PASS.
- The final TT runner independently executes the full staged workflow from a fresh CLI invocation; saved behavior replay, complete manifest checks, secret scan, isolation, task-data cleanup and environment restoration all pass.
- Unit discovery on 2026-11-02: **104/104 PASS** (54 partitioning and 50 Time travel tests). Each full TT baseline build passes **128/128 nodes**, 15 models and 113 tests.
- Protected fixtures/models, old runners/tests, Compose, infrastructure, dependency files and approved spec are unchanged. Prior completed-slice acceptance remains applicable; no shared-path change required a full rerun of those workflows.
- The local `.env` workflow is documented in README. Values remain local and are excluded from evidence; existing volumes are preserved.

### Remaining scope and next action

- Define and execute maintenance: small-files diagnostics/remediation, compaction, snapshot expiration and the specified scope of orphan-file cleanup.
- Complete competency mapping, determine any missing incremental-predicate exercise and close AC-002 after the full scope is covered.
- Use [the completion roadmap](bootstrap-time-travel.md#9-порядок-завершения-проекта) for sequencing. Time travel has no unfinished implementation task.

### Task-history conventions

`Status` and `Completion` below are reconciled with committed history as of the date above; obsolete pending-commit instructions have been replaced with actual completion commits. The original `Updated` timestamps, `Baseline HEAD`, Progress, AC evidence, Issues, and Review entries describe their historical checkpoints and are preserved, including intermediate continuation gates, resolved issues, and review counters. A task marked DONE means its bounded work was completed and committed, not that its intermediate run covered the entire project. Non-blocking historical review suggestions are not silently treated as implemented.

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

### Completion
PROBE-001 is complete and committed as `0fe79f1`.

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

### Completion
PROBE-002 is complete and committed as `af47c52`.

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

### Completion
PROBE-003 is complete and committed as `527f473`.

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

### Completion
BOOT-ENV-001 is complete and committed as `540fc19`.

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

### Completion
BOOT-ENV-002 is complete and committed as `f1e121a`.

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

### Completion
BOOT-ENV-003 is complete and committed as `7f86432`.

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

### Completion
IMP-001 is complete and committed as `5da246f`.

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

### Completion
IMP-002 is complete and committed as `5e80c08`.

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

### Completion
IMP-003 is complete and committed as `a09dd66`.

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

### Completion
IMP-004 is complete and committed as `ab4cbf0`.

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

### Completion
IMP-005 is complete and committed as `345be2c`.

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

### Completion
IMP-006 is complete and committed as `64b2ecc`.

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

### Completion
IMP-007 is complete and committed as `82b89ab`. The core acceptance workflow is complete.

## TASK_ID: SE-AGENT-001

- Source: `docs/bootstrap-schema-evolution.md` §5.1, “SE-AGENT-001 — сохранить текущие инструкции и ресурсы”
- Status: DONE
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

### Completion
SE-AGENT-001 is complete and committed as `6579860`.

## TASK_ID: SE-ENV-001

- Source: `docs/bootstrap-schema-evolution.md` §5.2, “SE-ENV-001 — schema-evolution acceptance entry point”
- Status: DONE
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

### Completion
SE-ENV-001 is complete and committed as `69678d5`.

## TASK_ID: SE-IMP-001

- Source: `docs/bootstrap-schema-evolution.md` §5.3, “SE-IMP-001 — pre/post core regression capture”; `docs/spec.md` AC-013 and AC-020
- Status: DONE
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

### Completion
SE-IMP-001 is complete and committed as `44addd7`.

## TASK_ID: SE-IMP-002

- Source: `docs/bootstrap-schema-evolution.md` §5.3, “SE-IMP-002 — S0 creation и evidence”; `docs/spec.md` AC-014 and AC-020
- Status: DONE
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

### Completion
SE-IMP-002 is complete and committed as `337f51d`.

## TASK_ID: SE-IMP-003

- Source: `docs/bootstrap-schema-evolution.md` §5.3, “SE-IMP-003 — metadata-only DDL checkpoints”; `docs/spec.md` AC-015 and AC-020
- Status: DONE
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

### Completion
SE-IMP-003 is complete and committed as `12bf88f`.

## TASK_ID: SE-IMP-004

- Source: `docs/bootstrap-schema-evolution.md` §5.3, “SE-IMP-004 — reader/writer compatibility и S1”; `docs/spec.md` AC-016, AC-017 and AC-020
- Status: DONE
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

### Completion
SE-IMP-004 is complete and committed as `5854963`.

## TASK_ID: SE-IMP-005

- Source: `docs/bootstrap-schema-evolution.md` §5.3, “SE-IMP-005 — S0/S1 historical compatibility и narrowing”; `docs/spec.md` AC-018, AC-019 and AC-020
- Status: DONE
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

### Completion
SE-IMP-005 is complete and committed as `55d680b`.

## TASK_ID: SE-IMP-006

- Source: `docs/bootstrap-schema-evolution.md` §5.3, “SE-IMP-006 — end-to-end evidence и cleanup”; `docs/spec.md` AC-020
- Status: DONE
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

### Completion
SE-IMP-006 is complete and committed as `25ff57e`. The schema evolution slice is complete.

## TASK_ID: PART-PROBE-001

- Source: `docs/bootstrap-partitioning-file-pruning.md` §4.8, “PART-PROBE-001 — writer topology и `$files` schema”; supporting contract `docs/spec.md` §11.2–§11.7
- Status: DONE
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

### Completion
PART-PROBE-001 is complete and committed as `c3470bc`.

## TASK_ID: PART-PROBE-002

- Source: `docs/bootstrap-partitioning-file-pruning.md` §4.8, “PART-PROBE-002 — plan/stats capture”; supporting contract `docs/spec.md` §11.3–§11.7
- Status: DONE
- Updated: 2026-10-31T19:27:19+03:00
- Baseline HEAD: 3f411d60361717a512cd9ef359ac8aa906a314bf

### Progress
- Implemented: revalidated the committed PART-PROBE-002 result without changing project code. The source contract and pinned stack configuration are unchanged since commit `e527f1a`; all 171 manifest entries match size/SHA-256, all 12 saved captures satisfy the exact result/scan/constraint/eligible-row/runtime contracts, the seven-case fail-closed parser replay passes, and current cleanup state remains stopped with ports free and the project volume preserved.
- Remaining: none.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/bootstrap-partitioning-file-pruning.md` §4.8 PART-PROBE-002, one Iceberg scan and visible partition constraint | PASS | standard revalidation: source diff from task commit `e527f1a` is empty for the specification, plan, Compose/infra and shared runner paths. The 171-file manifest hash check passed; all 12 summaries retain exactly one owned distributed/runtime scan, one IO input, expected date/route query-column constraints and IO estimates equal to `$partitions` eligible records. |
| `docs/bootstrap-partitioning-file-pruning.md` §4.8 PART-PROBE-002, parseable physical input and expected relative reduction | PASS | standard revalidation: all 12 summaries retain positive physical input/splits and runtime input rows equal to eligible metadata. Exact aggregates match for every layout; D/DR reduce date input, R/DR reduce route input, all partitioned layouts reduce combined input versus U, and combined DR remains below D and R. |
| `docs/bootstrap-partitioning-file-pruning.md` §4.8 PART-PROBE-002, parser/summary decision and isolated cleanup | PASS | fast/standard revalidation: `python3 workload/replay_parser_mutations.py` exited 0 with seven detected positive/fail-closed cases in 59 ms. The complete evidence assertion exited 0 in 252 ms, verifying 171 hashes, parser contract/fallback, 271 pre-cleanup and 161 exact-key residual objects, empty final schema/prefix, clean secret scan and saved environment restoration. Current Docker state has no project containers, ports 8080/8181/9000/9001 are free, and `iceberg-trino-dbt_rustfs-data` is preserved. |

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
- Calls: 1
- Fix iterations: 0
- Details: one fresh read-only reviewer inspected the complete status-only diff, source AC, all 12 saved summaries, parser contract/replay, 171-file manifest, cleanup/secret evidence and neighboring status boundaries. It independently confirmed the scan/constraint/result/runtime claims, the documented Trino-484 bucket-descriptor limitation, evidence applicability without a costly rerun, current-attempt counters and preservation of other task sections; no BLOCKER, DEFERRED or IMPROVEMENT was found, and it returned `VERDICT: OK`.

### Completion
PART-PROBE-002 is complete and committed as `e527f1a`. Evidence revalidation is committed as `87d695d`.

## TASK_ID: PF-ENV-001

- Source: `docs/bootstrap-partitioning-file-pruning.md` §5.2, “PF-ENV-001 — isolated acceptance entry point”
- Status: DONE
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

### Completion
PF-ENV-001 is complete and committed as `bfa8023`.

## TASK_ID: PF-ENV-002

- Source: `docs/bootstrap-partitioning-file-pruning.md` §5.2, “PF-ENV-002 — pure helper/parser tests”
- Status: DONE
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

### Completion
PF-ENV-002 is complete and committed as `02f4d66`.

## TASK_ID: PF-IMP-001

- Source: `docs/bootstrap-partitioning-file-pruning.md` §5.3, “PF-IMP-001 — route mapping и deterministic generators”; `docs/spec.md` §11.2–§11.4 and AC-022
- Status: DONE
- Updated: 2026-10-31T11:54:47+03:00
- Baseline HEAD: 02f4d6634c49ada534c071b3b16c0c7b96e80111

### Progress
- Implemented: added the explicit-catalog bucket route query, exact route-mapping parser, deterministic balanced/skewed CTAS builders, schema/group/formula assertions, runner integration through the AC-022 checkpoint, and positive/mutation coverage. Fast checks pass; isolated run `pfimp001_gen` proved the exact mapping, both 256000-row datasets and all schema/group/state formulas, then stopped at the intentional PF-IMP-002 continuation gate and restored the initially stopped environment.
- Remaining: none.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/spec.md` AC-022; `docs/bootstrap-partitioning-file-pruning.md` §5.3 PF-IMP-001 | PASS | fast/standard/acceptance: `py_compile`, LSP diagnostics and 23 unit tests passed; actual-evidence group/state mutations were rejected. Isolated run `pfimp001_gen` selected exact bucket counts 3/3/2/2 with hot routes `BENCH-R0004`/`BENCH-R0001`, created exact eight-column balanced/skewed controls with 256000 unique rows each, 50 days, 10 routes, 500 exact groups and full aggregates 256000/224000/160000/4800000; all NULL/SLA/timestamp/state violations were zero. The expected continuation exit 1 retained `AC-022=PASS`, cleanup left a header-only schema listing and empty object prefix, stopped Compose, preserved the pre-existing volume, and produced a clean 34-file manifest. |

### Issues
#### PF-IMP-001/B01
- State: RESOLVED
- Category: ENVIRONMENT
- Affects: `docs/spec.md` AC-022 acceptance evidence
- Problem: Compose cannot render because the four required local training credential variables are absent from the current shell and no `.env` file exists.
- Evidence: `docker compose --profile tools config --quiet` exited 1 naming only `RUSTFS_ACCESS_KEY`, `RUSTFS_SECRET_KEY`, `POLARIS_CLIENT_ID` and `POLARIS_CLIENT_SECRET`; all four project ports are free and no service started.
- Unblock: export the documented `.env.example` non-production training values only for the preflight/acceptance command and rerun Compose config before starting the isolated workflow.
- Resolution: with those task-local non-production values exported only for the command, Compose config exited 0; ports 8080/8181/9000/9001 are free and the fresh evidence path is absent.

#### PF-IMP-001/B02
- State: RESOLVED
- Category: TEST
- Affects: mandatory fast static generator boundary check
- Problem: the first ad-hoc static harness imported the script as a package without adding `scripts/` to `PYTHONPATH`, so the helper assertions did not execute.
- Evidence: Python exited 1 with `ModuleNotFoundError: No module named 'run_acceptance'`; the normal unittest invocation had already imported the same module and passed 23 tests.
- Unblock: rerun the static boundary harness with `PYTHONPATH=scripts` and require all no-sorting/no-maintenance assertions to pass.
- Resolution: the corrected harness exited 0 and confirmed both generated CTAS statements contain no `ORDER BY`, `sorted_by`, optimize, expiration or orphan-maintenance operation.

#### PF-IMP-001/B03
- State: RESOLVED
- Category: TEST
- Affects: mandatory FINAL_EVIDENCE_AND_DIFF_GATE for AC-022
- Problem: the first post-run wrapper expected a nonexistent `final_compose_state` field in the inherited environment evidence and stopped before secret/manifest assertions.
- Evidence: all business evidence preceding that access was valid; `cleanup/environment.json` actually records `final_project_containers`, initial/final volumes and `preexisting_volumes_preserved`.
- Unblock: assert the inherited environment/secret evidence shapes and rerun the complete wrapper without repeating acceptance.
- Resolution: the corrected wrapper passed all mapping, schema, 1000 group, aggregate/formula, cleanup, secret and 34-file manifest assertions; no project containers remain, all four ports are free and the three pre-existing named volumes remain.

### Review
- Verdict: OK
- Calls: 1
- Fix iterations: 0
- Details: one fresh read-only reviewer inspected the complete three-file diff, AC-022 source contract, SQL generators/assertions/tests, saved `pfimp001_gen` mapping/group/schema/contract/cleanup/secret/manifest evidence and the PF-IMP-001 status section; it found no BLOCKER and returned `VERDICT OK`. DEFERRED: before the final-slice manifest gate is enabled, replace the pre-existing generic `generation/group_counts.csv` requirement with the two dataset-specific paths or create the aggregate path. IMPROVEMENT: future evidence can persist the standalone mutation/port/global-volume probes rather than relying on the main-agent command record; this does not affect AC-022.

### Completion
PF-IMP-001 is complete and committed as `42df7c6`.

## TASK_ID: PF-IMP-002

- Source: `docs/bootstrap-partitioning-file-pruning.md` §5.3, “PF-IMP-002 — eight layouts, reconciliation и topology gate”; `docs/spec.md` §11.2, §11.6, AC-023 and AC-026
- Status: DONE
- Updated: 2026-10-31T19:02:15+03:00
- Baseline HEAD: 42df7c62c562f7a931f1a1827dee0ac25e6091bc

### Progress
- Implemented: added unsorted D/R/DR CTAS layouts from each validated U control, exact eight-table/schema/partition-spec/aggregate/full-row reconciliation assertions, `$partitions`/`$files` topology and typed representative-bounds gates, exact-inventory residual-object cleanup, and fail-closed mutation tests. Isolated run `pfimp002_layouts` passed the PF-IMP-002 behavior gates, reached the intentional PF-IMP-003 continuation stop, and restored the initially stopped environment.
- Remaining: none.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/spec.md` AC-023; `docs/bootstrap-partitioning-file-pruning.md` §5.3 PF-IMP-002 | PASS | acceptance: run `pfimp002_layouts` registered exactly eight tables. Both datasets had four identical 256000-row layouts with exact aggregate `256000/224000/160000/4800000`, zero bidirectional full-row differences, partition specs U/D/R/DR, tuple counts 1/50/4/200, at least one Parquet file per tuple and complete `$files` record totals. The runner recorded `AC-023=PASS` before the intentional PF-IMP-003 stop. |
| `docs/spec.md` AC-026, PF-IMP-002 contribution | PASS | fast/acceptance: 28 unit tests include partition/spec/count/reconciliation/file/bounds/cleanup mutations; LSP, `py_compile` and whitespace checks passed. For balanced and skewed, representative day `2025-03-30` plus route `BENCH-R0002` selected one file in every applicable U/D/R/DR tuple/control and every selected file's typed route/time bounds retained the target. No sorting or maintenance operation appears in generated SQL/commands. |

### Issues
#### PF-IMP-002/B01
- State: RESOLVED
- Category: TEST
- Affects: mandatory fast test suite and future final evidence-manifest gate
- Problem: replacing the obsolete single `generation/group_counts.csv` requirement with the two dataset-specific evidence paths increased the exact required manifest count, but the existing unit assertion still expects the old count.
- Evidence: `python3 -m unittest -v scripts.tests.test_partitioning_file_pruning_acceptance` ran 23 tests and failed only `test_manifest_covers_all_52_query_layout_cases`: expected 427 paths, actual 428.
- Unblock: update the pure manifest expectation and add PF-IMP-002 layout/topology/cleanup mutation coverage, then rerun the complete suite.
- Resolution: the manifest expectation now covers 428 required paths; five new layout/topology/file/bounds/cleanup tests include row, partition, format, reconciliation, bounds and ownership mutations. The complete 28-test suite exited 0; `py_compile`, LSP diagnostics and `git diff --check` also passed.

#### PF-IMP-002/B02
- State: RESOLVED
- Category: TEST
- Affects: mandatory FINAL_EVIDENCE_AND_DIFF_GATE
- Problem: the first post-run evidence wrapper imposed an uncontracted minimum of 100 manifest entries and stopped after validating the business/layout/cleanup evidence but before completing its hash/required-path assertions.
- Evidence: the wrapper raised `AssertionError` at `len(entries) >= 100`; direct inspection shows a valid 98-file manifest containing all required PF-IMP-002 evidence, with every listed size and SHA-256 matching.
- Unblock: remove the arbitrary count threshold, require the exact task evidence paths and valid hashes instead, then rerun the complete post-run wrapper.
- Resolution: the corrected wrapper validated all 98 manifest entries by size/SHA-256 and required every generation/layout/contract/reconciliation/topology/file/bounds/cleanup path. It also confirmed 71 commands, clean secret scan, header-only remaining-schema evidence, empty final prefix, 479 exact inventoried residual keys deleted, no project containers/ports, and preserved pre-existing volumes.

### Review
- Verdict: OK
- Calls: 1
- Fix iterations: 0
- Details: one fresh read-only reviewer inspected the complete three-file diff, source AC, code/tests/status, all eight layout/spec/contract/reconciliation/topology/bounds evidence sets, the 71-command journal, 98-file manifest, exact-inventory deletion of 479 residual keys and final environment restoration. It found no BLOCKER, DEFERRED or IMPROVEMENT and returned `VERDICT: OK`.

### Completion
PF-IMP-002 is complete and committed as `3f411d6`.

## TASK_ID: PF-IMP-003

- Source: `docs/bootstrap-partitioning-file-pruning.md` §5.3, “PF-IMP-003 — balanced workload”; `docs/spec.md` §11.3, §11.5 and AC-024; runtime permissions boundary in the plan §7
- Status: DONE
- Updated: 2026-10-31T19:54:37+03:00
- Baseline HEAD: 87d695db3c0b84e70b41ea54bac27716243b286f

### Progress
- Implemented: added balanced raw-column SQL for four cases across four layouts, exact candidate tuple/file reconciliation with per-case bounds isolation, result/plan/runtime capture and fail-closed comparison gates. All 33 unit tests, compilation, CLI, LSP diagnostics and 12 saved Trino-484 parser replays passed. Isolated run `pfimp003_balanced` confirmed all sixteen AC-024 cells and actual-evidence mutations, then reached the intentional PF-IMP-004 continuation gate. The corrected final wrapper validated all 263 manifest hashes, cleanup and environment restoration; only the two readiness retries were non-zero among 169 journaled commands. Initial diff was the main agent's prior task status append, not unrelated work.
- Remaining: none within PF-IMP-003; PF-IMP-004–006 and completed slices remain out of scope.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/spec.md` AC-024; `docs/bootstrap-partitioning-file-pruning.md` §5.3 PF-IMP-003 | PASS | acceptance: `python3 scripts/run_partitioning_file_pruning_acceptance.py --run-id pfimp003_balanced` (task-local training environment) recorded AC-022/023/024 PASS; exit 1 is the intended PF-IMP-004 stop, not overall slice acceptance. `artifacts/acceptance/pfimp003_balanced/workload/balanced/` contains all 16 SQL/result/partition/file/distributed/IO/runtime/summary bundles and `comparison.json`. Exact four-metric results match §11.5; U/D/R/DR eligible rows are day 256000/5120/256000/5120, route 256000/256000/51200/51200, combined 256000/5120/51200/1024, full scan 256000 each. Matching layouts reduce physical input: combined bytes 977880/12260/378880/8410; DR's 1024 records are strictly below D/R. Full scan retains all tuples/files and 256000 runtime input rows per layout. Standard replay revalidated every raw bundle, rejected actual-result/input-row/no-reduction mutations, and verified 263 hashes, clean secret scan, empty schema/prefix, 479 exact inventoried residual keys deleted, stopped services/free ports and three preserved project/probe volumes. Fast: 33 unit tests, compilation/CLI/whitespace PASS; active LSP found zero diagnostics. |

### Issues
#### PF-IMP-003/B01
- State: RESOLVED
- Category: PERMISSION
- Affects: PRECHECK, EVIDENCE_GATE and `docs/spec.md` AC-024
- Problem: required runtime actions are not explicitly authorized under the approved plan's separate-permission boundary.
- Evidence: `docs/bootstrap-partitioning-file-pruning.md` §6 step 3 and §7 require separate permission for Docker, ports, task-owned writes and cleanup; the current invocation is PF-IMP-003 only. Read-only `docker compose ps --all` exited 1 during interpolation because the four required local environment variables are unset; no runtime assertion ran and no service was started. Direct Docker label inspection subsequently exited 0 and found no project containers.
- Unblock: user explicitly authorizes the pinned Compose stack on ports 8080/8181/9000/9001, task-local non-production environment values, unique benchmark schema/object-prefix writes and exact task-owned cleanup, with initial service-state restoration and all pre-existing volumes preserved. No image/version/dependency changes or volume deletion are requested.
- Resolution: the current user request explicitly states “PF-IMP-003 разрешаю docker runtime-действия”, answering the bounded runtime-permission request; PRECHECK re-established initial_stopped and the distinguishable status-only baseline. No versions, dependencies or volume deletion are authorized.

#### PF-IMP-003/B02
- State: RESOLVED
- Category: TEST
- Affects: FINAL_EVIDENCE_AND_DIFF_GATE
- Problem: the first post-run wrapper incorrectly requires every journaled command to return zero, rejecting the inherited bounded query-readiness retries before completing its final environment assertions.
- Evidence: acceptance `pfimp003_balanced` recorded AC-022/023/024 PASS and stopped at the intended PF-IMP-004 continuation gate (exit 1, measured 339.897 seconds). Raw sixteen-case replay, actual aggregate/runtime/physical-input mutations, cleanup/secret checks and all 263 manifest hashes passed before the wrapper assertion. Journal inspection found 169 commands, with only two non-zero `SELECT 1 AS ready` attempts before successful readiness; business commands succeeded.
- Unblock: verify the two readiness diagnostics, require subsequent successful readiness and all behavior/cleanup commands to succeed, then rerun the corrected evidence wrapper without repeating acceptance.
- Resolution: both saved readiness errors are exactly “Trino server is still initializing”; the corrected wrapper required readiness exits [1,1,0] with final CSV ready=1 and all other 166 commands successful. It exited 0 after replaying sixteen raw evidence bundles, three actual-evidence mutations, all 263 hashes, final cleanup/ports/volumes and immutable-path checks; no acceptance rerun was needed.

### Review
- Verdict: OK
- Calls: 1
- Fix iterations: 0
- Details: one fresh read-only built-in reviewer (read/grep/find/ls/watchdog_diff/contact_supervisor, no bash/write/edit) inspected the complete three-file diff, all sixteen summaries and raw SQL/results/runtime captures, representative complete raw bundles, comparison/topology/manifest/cleanup/readiness/secret evidence and this status section with prior-section preservation. It returned VERDICT OK within PF-IMP-003/AC-024, with zero BLOCKER, DEFERRED or IMPROVEMENT; it did not independently execute hash/unittest/LSP assertions. Post-review Git scope/whitespace and stopped-environment/volume checks remained consistent.

### Completion
PF-IMP-003 is complete and committed as `651e070`.

## TASK_ID: PF-IMP-004

- Source: `docs/bootstrap-partitioning-file-pruning.md` §5.3, “PF-IMP-004 — skewed workload”; `docs/spec.md` §11.3, §11.5 and AC-025; runtime permissions boundary in the plan §7
- Status: DONE
- Updated: 2026-10-31T22:13:11+03:00
- Baseline HEAD: 651e070f69c2e1ea0e641f9f19b2f2a245781256

### Progress
- Implemented: added exact skewed predicates/queries, partition and file candidate reconciliation, nine-case scan comparison gates, runner integration through the AC-025 checkpoint, and positive/mutation coverage. After fixing the runtime-shaped CSV result-type defect, all 37 tests and LSP checks passed; isolated run `pfimp004_skewed_fix1` proved all 36 skewed query/layout cells, exact aggregates/eligible records, physical-input reductions, hot/cold and peak/off-peak density contrasts, co-bucket rows, and full-scan behavior, then reached the intentional PF-IMP-005 continuation gate. Evidence hashes, mutations, cleanup and environment restoration passed.
- Remaining: none within PF-IMP-004; PF-IMP-005–006 remain out of scope.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/spec.md` AC-025; `docs/bootstrap-partitioning-file-pruning.md` §5.3 PF-IMP-004 | PASS | acceptance: `pfimp004_skewed_fix1` ran 501.81 seconds and recorded `AC-025=PASS` before the intentional PF-IMP-005 stop. All nine exact aggregates matched §11.5; U/D/R/DR eligible rows included peak 256000/20480/256000/20480, off-peak 256000/1280/256000/1280, hot route 256000/256000/115200/115200, cold route 256000/256000/12800/12800 and combined DR 9216/576/1024/64. Matching layouts reduced physical input; denser cases read more than paired sparse cases; bucket candidates exceeded route results. Standard replay accepted all 36 raw bundles, rejected five actual-evidence mutations, verified 622 manifest hashes and 384 commands, clean secrets, empty schema/prefix, stopped services/free ports and the preserved project volume. Fast: compilation, CLI, static boundary, 37 tests, whitespace and active LSP diagnostics passed. |

### Issues
#### PF-IMP-004/B01
- State: RESOLVED
- Category: CODE
- Affects: `docs/spec.md` AC-025 and mandatory EVIDENCE_GATE
- Problem: the skewed co-bucket assertion compares parsed integer metadata with an unparsed CSV aggregate string, so the final comparison crashes after all runtime captures.
- Evidence: `python3 scripts/run_partitioning_file_pruning_acceptance.py --run-id pfimp004_skewed` exited 1 after 508.65 seconds with `TypeError: '<=' not supported between instances of 'int' and 'str'` in `assert_skewed_comparison`; `acceptance_summary.json` records outcome FAIL and 384 commands.
- Unblock: parse the aggregate field before comparison, add a runtime-shaped string-value regression test, rerun affected fast checks, then repeat acceptance under a fresh run ID.
- Resolution: the comparison now parses `package_count` before the co-bucket assertion; the runtime-shaped string-value regression passed in the full 37-test suite, and fresh acceptance `pfimp004_skewed_fix1` completed the final comparison with `AC-025=PASS`. The standard wrapper replayed all evidence and mutation checks successfully.

#### PF-IMP-004/B02
- State: RESOLVED
- Category: REVIEW
- Affects: mandatory STATUS_RECORD and FRESH_READ_ONLY_REVIEW gates
- Problem: after reviewer call 1 returned OK, `Progress/Remaining` still describes that completed review and final gates as pending; correcting Progress is outside the narrow post-review service-finalization exception.
- Evidence: reviewer call 1 returned `VERDICT OK` with no findings, while the reviewed section still says `Remaining: independent fresh read-only review and final status/diff gates only`.
- Unblock: correct `Progress/Remaining`, validate status/diff, then obtain one fresh targeted re-review of the corrected complete diff.
- Resolution: `Progress/Remaining` now states no remaining PF-IMP-004 work; the unique-section assertion and `git diff --check` passed, and fresh reviewer call 2 confirmed the corrected complete diff with `VERDICT OK` and no findings.

### Review
- Verdict: OK
- Calls: 2
- Fix iterations: 1
- Details: reviewer call 1 inspected the complete diff, source AC and saved runtime evidence and returned `VERDICT OK` with no findings. After the targeted stale-Remaining correction, reviewer call 2 re-read the complete diff and corrected status section, found no BLOCKER, DEFERRED or IMPROVEMENT, and returned `VERDICT OK`.

### Completion
PF-IMP-004 is complete and committed as `f8b8da1`.

## TASK_ID: PF-IMP-005

- Source: `docs/bootstrap-partitioning-file-pruning.md` §5.3, “PF-IMP-005 — causal evidence matrix”; `docs/spec.md` §11.6 and AC-026
- Status: DONE
- Updated: 2026-10-31T22:55:49+03:00
- Baseline HEAD: f8b8da17269b590b9ffd33e897b601c4da08a0d1

### Progress
- Implemented: added the 52-cell raw causal-evidence gate, canonical SQL/exact IO-domain checks, plan/snapshot/summary consistency, layout-inventory binding, full-scan controls, ambiguous-stat rejection and AC-026 checkpoint. Fresh run `pfimp005_causal` confirmed AC-026 before the intentional PF-IMP-006 stop (515.681 seconds); final raw replay/hash/cleanup checks passed. After review B04, reproduced the accepted NONE mutation, required explicit `constraint.none is False` and added regression coverage for true/null/zero/string/missing values without changing summaries. Final 43 tests passed in 1.438 seconds, active LSP and compilation/whitespace passed; post-fix 52-cell replay, eight actual NONE mutations, 623 unchanged hashes and full environment/boundary checks passed in 0.519 seconds. Initial stopped state and pre-existing volume are preserved.
- Remaining: none within PF-IMP-005; PF-IMP-006 catalog/object evidence and overall slice finalization remain out of scope.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/spec.md` AC-026; `docs/bootstrap-partitioning-file-pruning.md` §5.3 PF-IMP-005 | PASS | acceptance: `python3 scripts/run_partitioning_file_pruning_acceptance.py --run-id pfimp005_causal` (command-local training env) exited 1 in 515.681 seconds at the expected PF-IMP-006 continuation gate, with AC-022–AC-026 PASS and AC-021/027 NOT_RUN; this is not overall slice PASS. `workload/causal_matrix.json` revalidates all 13×4 SQL/result/partition/file/distributed/IO/analyze/summary bundles. Full scans retain 256000 input records and all 1/50/4/200 tuples/files per dataset, zero filtering, no constraints and `pruning=false`; physical bytes are not equated to file sizes or wall-clock thresholds. Standard final replay matched the saved matrix, rejected five read-only actual-evidence mutations (SQL, aggregate, missing files, missing/ambiguous stats), verified 623 size/SHA-256 entries and 384 commands (only expected initialization retry [1,0] non-zero), clean secrets, absent schema/prefix, stopped project/free ports and preserved volume. Post-fix final-state replay (0.519 seconds) revalidated all 52 bundles with explicit non-NONE domains, matched the unchanged saved matrix, rejected the reviewer mutation in all eight actual full scans and rechecked 623 hashes, commands, cleanup/environment and immutable boundary. No SQL/data/runtime/summary-format changed in the fix, so the saved pinned-stack runtime remains applicable without another costly acceptance. Fast: compilation, CLI, final 43 positive/mutation tests, active LSP and whitespace pass. |

### Issues
#### PF-IMP-005/B01
- State: RESOLVED
- Category: CODE
- Affects: mandatory fast/LSP gate
- Problem: initial snapshot-match expression does not narrow optional regex matches for the type checker.
- Evidence: post-edit active LSP reports two `Object of type None is not subscriptable` errors in the causal snapshot comparison.
- Unblock: explicitly narrow both matches and rerun active diagnostics plus tests.
- Resolution: explicit planned/runtime regex matches are narrowed before indexing; active LSP reports zero diagnostics for both changed Python paths and all 42 tests pass.

#### PF-IMP-005/B02
- State: RESOLVED
- Category: TEST
- Affects: mandatory FINAL_EVIDENCE_AND_DIFF_GATE
- Problem: post-run wrapper requires `runtime/object_paths.json`, which belongs to PF-IMP-006, instead of excluding all three future catalog/object paths at this checkpoint.
- Evidence: wrapper exited 1 after successful matrix replay and 623 manifest hashes; required-path difference is exactly `runtime/catalog_tables.csv`, `runtime/object_paths.json`, `runtime/polaris_catalog.json`. Runtime summary retains the intended PF-IMP-006 continuation failure.
- Unblock: scope the wrapper to PF-IMP-005 evidence, retaining all 52 raw bundles, cleanup, command/secret/hash/environment checks; rerun without repeating unchanged acceptance.
- Resolution: corrected final wrapper exited 0, requiring exactly the three future paths absent while validating all 52 bundles, five actual-evidence mutations, all 623 hashes, cleanup and environment. Acceptance was not repeated; evidence/code were unchanged.

#### PF-IMP-005/B03
- State: RESOLVED
- Category: TEST
- Affects: mandatory FINAL_EVIDENCE_AND_DIFF_GATE
- Problem: corrected post-run wrapper treats the journal's rendered command string as an argv list while identifying the permitted readiness retry.
- Evidence: wrapper exited 1 at the retry assertion; `commands.jsonl` stores `command` as a string ending in `--execute SELECT 1 AS ready`, with readiness exits [1,0] and all other commands at exit 0.
- Unblock: match the actual rendered command suffix, verify the saved initialization diagnostic and complete the same post-run checks.
- Resolution: corrected final wrapper matched the rendered suffix, required readiness exits [1,0], asserted the first saved diagnostic is `Trino server is still initializing` and final CSV ready=1, and required all other commands exit 0; the complete wrapper passed in 0.437 seconds.

#### PF-IMP-005/B04
- State: RESOLVED
- Category: CODE
- Affects: `docs/spec.md` AC-026 full-scan negative control and fail-closed causal gate
- Problem: causal gate ignores raw IO `constraint.none`, so matching raw/decoded plans with `none=true` can still be classified as unpruned full scan.
- Evidence: fresh read-only reviewer call 1 returned VERDICT BLOCK; tracing `parse_io_plan` shows `none` is omitted from summaries while the new gate compares only column domains. Actual saved full-scan IO plans have `none=false`, so the finding does not invalidate runtime data itself.
- Unblock: require raw IO `constraint.none is False`, add matching raw/decoded NONE mutations, rerun fast/standard and full final raw replay against unchanged acceptance evidence, then fresh re-review.
- Resolution: supervisor reproduced the original mutation's false PASS read-only, then added the explicit false check. All 43 unit tests pass, including coordinated raw/decoded mutations with summaries untouched; active LSP is clean. Final standard replay rejects NONE=true for all eight actual full scans while accepting the unchanged 52-cell evidence and matching its saved matrix; all 623 hashes, command/cleanup/environment/boundary checks pass. The fix strengthens only evidence validation and leaves query/data/runtime and summary format unchanged, so acceptance was not repeated.

### Review
- Verdict: OK
- Calls: 2
- Fix iterations: 1
- Details: call 1 returned VERDICT BLOCK for B04 only. After one targeted fix and all affected checks, fresh built-in reviewer call 2 (read/grep/find/ls/watchdog_diff/contact_supervisor, no bash/write/edit) inspected the complete corrected three-file diff, source AC, status and runtime evidence; it confirmed B04 resolution and returned VERDICT OK with no BLOCKER, DEFERRED or IMPROVEMENT. It did not independently execute tests, LSP, hash or port checks. Post-review hashes confirm no files changed during review; final scope/whitespace/status-preservation and stopped-environment/volume checks passed.

### Completion
PF-IMP-005 is complete and committed as `0d3324a`.

## TASK_ID: PF-IMP-006

- Source: `docs/bootstrap-partitioning-file-pruning.md` §5.3 PF-IMP-006; `docs/spec.md` §11.7 AC-021–AC-027; current user authorization for Docker runtime actions
- Status: DONE
- Updated: 2026-11-01T00:34:37+03:00
- Baseline HEAD: 0d3324a36088e3020923ee14bf81340052f95ae4

### Progress
- Implemented: exact Trino/Polaris eight-table registration and per-layout RustFS data/metadata/manifests binding, immutable file/runtime boundary captures, orphan-prefix collision guard and fail-closed finalization after cleanup/restoration/secret scan/actual manifest hashes. Fresh full acceptance `pfimp006_final` exited 0 in 578.243 seconds with AC-021–AC-027 PASS. Final raw replay passed all generation/layout/52-cell/catalog/object/isolation/cleanup checks, 640 hashes, 404 command records and four actual-evidence mutations in 0.267 seconds. Final 54 tests passed in 2.533 seconds; compilation/CLI/whitespace pass, active LSP has zero findings with one file unconfirmed on clean recheck/timeout. Initial_stopped is restored, ports are free and all 12 initial global volumes are preserved. No expensive failed acceptance or acceptance rerun occurred.
- Remaining: none within PF-IMP-006. Only the isolated runner, its tests and this status section changed; shared/completed-slice code, stack and dependencies are unchanged.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/spec.md` AC-021 | PASS | acceptance: `python3 scripts/run_partitioning_file_pruning_acceptance.py --run-id pfimp006_final` with command-local training environment exited 0 in 578.243 seconds. `preflight/immutable_before.json` equals `runtime/immutable_after.json` (67 protected file hashes and HEAD); final replay matched current files. `runtime/boundary_before/` and `boundary_after/` have identical non-task schema/table listings and object key/size/ETag maps; `runtime/isolation.json` confirms unchanged. Diff contains only the three allowed paths, prior status sections are byte-preserved, and command review found no writes outside the exact benchmark schema/prefix or forbidden maintenance. No shared-path change, so completed-slice full regression is not required. |
| `docs/spec.md` AC-022 | PASS | acceptance and final standard replay: both eight-column datasets have 256000 unique rows, 50 days, ten bucket-aware routes, exact 500 day/route groups each and state/SLA/nullability assertions. `generation/` contains mapping, schemas, group counts and contract CSVs; full aggregates are 256000/224000/160000/4800000. |
| `docs/spec.md` AC-023 | PASS | acceptance and final replay: exact eight-table listing, U/D/R/DR specs, 256000 rows per layout, zero bidirectional full-row differences, nonempty tuple counts 1/50/4/200 and complete file inventories. `layouts/` and both actual Trino/Polaris runtime listings agree. |
| `docs/spec.md` AC-024 | PASS | acceptance and final 52-cell raw replay: all sixteen balanced SQL/result/partition/file/distributed/IO/analyze/summary bundles and `workload/balanced/comparison.json` pass exact aggregates, eligible-row matrix and physical-input reductions/combined strict subsets. |
| `docs/spec.md` AC-025 | PASS | acceptance and final raw replay: all thirty-six skewed bundles and `workload/skewed/comparison.json` pass nine exact aggregates, eligible records 20480/1280, 115200/12800 and DR 9216/576/1024/64; physical-input/density and co-bucket assertions pass. |
| `docs/spec.md` AC-026 | PASS | acceptance and final replay match `workload/causal_matrix.json` for all 52 raw bundles, including inventory/bounds binding and eight unpruned full scans. No wall-clock threshold defines PASS. Final 54 positive/mutation tests pass; compilation/CLI and active LSP have no findings (one LSP clean recheck remains unconfirmed). |
| `docs/spec.md` AC-027 | PASS | acceptance: runtime Trino and Polaris REST listings contain exactly eight registrations; `runtime/end_to_end.json` binds 542 RustFS objects, including all 510 Parquet data files with exact Iceberg path/size and metadata JSON/Avro for every table. Cleanup confirms header-only schema listing and empty exact prefix; 480 inventoried residual keys were deleted in one bounded batch. Environment is stopped again, four ports free, all 12 original global volumes preserved. Secret scan is clean; manifest covers all 546 required paths and 640 actual files with valid sizes/SHA-256. Final standard replay (0.267 seconds) rejected four read-only actual-evidence mutations and verified all 404 commands: only expected readiness exits [1,0], all other commands exit 0. |

### Issues
#### PF-IMP-006/B01
- State: RESOLVED
- Category: TEST
- Affects: mandatory fast/LSP gate before acceptance
- Problem: the new negative catalog test contains an unclosed outer list.
- Evidence: active post-edit LSP reports unclosed brackets at test line 1325; no runtime assertion has run.
- Unblock: close the list, rerun active diagnostics and the complete unittest suite.
- Resolution: bracket corrected; compilation and all final 54 tests pass. Active diagnostics report zero findings (one file clean and one push-only clean recheck unconfirmed); the syntax assertion is independently confirmed by successful compilation and suite execution.

#### PF-IMP-006/B02
- State: RESOLVED
- Category: TEST
- Affects: mandatory FINAL_EVIDENCE_AND_DIFF_GATE
- Problem: the post-run replay wrapper expects a readiness CSV under an incorrect path and stops before its final live environment checks.
- Evidence: full acceptance `pfimp006_final` exited 0 in 578.243 seconds with AC-021–AC-027 PASS; raw generation/layout/52-cell/catalog/object/isolation/secret/640-hash checks passed before `FileNotFoundError: preflight/query_ready.csv`. Journal shows readiness exits [1,0] and 404 total commands.
- Unblock: inspect the inherited readiness evidence path, correct only the wrapper and complete final raw/environment checks without repeating unchanged acceptance.
- Resolution: corrected wrapper reads `runtime/trino_ready.csv`, checks the expected initialization diagnostic and readiness exits [1,0], then passes complete raw/640-hash/404-command/four-mutation/ports/containers/all-12-volume assertions in 0.267 seconds. Runtime code and evidence were unchanged; acceptance was not repeated.

### Review
- Verdict: OK
- Calls: 1
- Fix iterations: 0
- Details: one fresh builtin read-only reviewer (read/grep/find/ls/watchdog_diff/contact_supervisor, no bash/write/edit; effective configuration checked) inspected the complete three-file diff, source contracts, this section, runtime boundaries, catalog/object evidence, layouts, causal matrix and representative raw bundles, cleanup, manifest, secret scan and command journal. VERDICT OK, no BLOCKER/DEFERRED/IMPROVEMENT. Exhaustive test/hash/replay and live port/global-volume checks were supervisor evidence, not independently executed by reviewer. Post-review hashes of all three files match the pre-review snapshot; only permitted status/verdict/time/next-action finalization follows.

### Completion
PF-IMP-006 is complete and committed as `88fc7db`. The partitioning/file-pruning slice is complete; final acceptance `pfimp006_final` records AC-021–AC-027 PASS.

## TASK_ID: TT-AGENT-001

- Source: [Time travel bootstrap plan](bootstrap-time-travel.md) §5, row “TT-AGENT-001 — работа агента”; [approved specification](spec.md) §12 (TT-1, DEC-034–DEC-040, AC-028–AC-033).
- Status: DONE
- Updated: 2026-11-01T17:35:41+03:00
- Baseline HEAD: ca04d3915ac875f10cd7ab31ce10e62a03006a86

### Progress
- Implemented: retained the spec/plan navigation links and registered only TT-AGENT-001 in the existing status file. The current Time travel contract is approved TT-1 in spec §12; the bootstrap plan supplies task boundaries. Earlier “next slice not selected” statements above are historical and do not override these sources. Navigation, uniqueness, append-only scope and three in-memory negative mutations passed. No new agent resources, instructions, journals, dependencies or global settings were created/changed. No Docker, SQL, builds or acceptance commands were invoked; service/volume state was not inspected or managed.
- Remaining: none within TT-AGENT-001. TT-ENV/TT-IMP/TT-DOC work, runtime acceptance, branches/tags, maintenance and full AC-002 coverage are outside this task.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/bootstrap-time-travel.md` §5 TT-AGENT-001, retain spec/plan links and use existing status file | PASS | fast: inline `python3` navigation/scope assertion exited 0 (0.019 seconds): both relative links resolve within the repository; the exact task heading occurs once and no other task was appended. In-memory duplicate-heading and broken-link mutations were rejected. |
| `docs/bootstrap-time-travel.md` §5 TT-AGENT-001, no new global instructions/duplicate journals; preserve old entries | PASS | fast: the same assertion compared every original byte with `git show ca04d3915ac875f10cd7ab31ce10e62a03006a86:docs/status.md` (original SHA-256 `4db0ccb79fdecbd9fdfa0178dc94ade1fff5729d4b6759ccd628c8de9c48b2e2`); prior-history mutation rejected. `git diff --name-only` reports only `docs/status.md`; staged/untracked lists are empty; spec/plan hashes match PRECHECK; `git diff --check` exited 0. No global settings commands were used. Active LSP probe for this Markdown path returned clean=1, zero diagnostics; the earlier post-write silent-server warning was not treated as clean evidence. |
| `docs/spec.md` §12.9 AC-028 | NOT_RUN | Full exercise isolation is outside this agent-navigation task; no runtime actions are planned. |
| `docs/spec.md` §12.9 AC-029 | NOT_RUN | Historical queries belong to later TT implementation tasks, not TT-AGENT-001. |
| `docs/spec.md` §12.9 AC-030 | NOT_RUN | Rollback belongs to later TT implementation tasks, not TT-AGENT-001. |
| `docs/spec.md` §12.9 AC-031 | NOT_RUN | Negative SQL operations belong to later TT implementation tasks, not TT-AGENT-001. |
| `docs/spec.md` §12.9 AC-032 | NOT_RUN | Staged source builds belong to later TT implementation tasks, not TT-AGENT-001. |
| `docs/spec.md` §12.9 AC-033 | NOT_RUN | End-to-end evidence, runtime cleanup and lifecycle acceptance belong to later TT tasks. |

### Issues
none

### Review
- Verdict: OK
- Calls: 1
- Fix iterations: 0
- Details: one fresh builtin read-only reviewer (read, grep, find, ls, watchdog_diff, contact_supervisor; no bash/write/edit; effective capabilities inspected) reviewed the complete 35-line append-only diff, spec/plan task boundaries, this section, prior-section preservation and AC evidence. VERDICT OK; no BLOCKER, DEFERRED or IMPROVEMENT. Python assertions, hashes, LSP and Git checks were supervisor evidence, not independently executed by the reviewer. Post-review SHA-256 matched the pre-review file; only permitted status/time/review/next-action finalization follows.

### Next action
Completed and committed as `44eaef7`. TT-1 full acceptance is recorded under TT-IMP-006; remaining project scope is maintenance and AC-002 coverage.

### Completion
TT-AGENT-001 completed and committed as `44eaef7`.

## TASK_ID: TT-ENV-001

- Source: [Time travel bootstrap plan](bootstrap-time-travel.md) §5, row “TT-ENV-001 — среда и проверки”; [approved specification](spec.md) §12.5 step 1, §12.7–12.8.
- Status: DONE
- Updated: 2026-11-01T18:15:44+03:00
- Baseline HEAD: 44eaef767158db2566e5cbc4e836dbc9bbaded2e

### Progress
- Implemented: new TT environment-only runner and simulated Docker lifecycle/ownership suite. Borrowed healthy default stack receives no stop/down/rm; own run-specific project pins container and full network IDs immediately after attempted up, including partial failure. Cleanup refuses identity drift and removes only pinned IDs, never volumes. Exact five-schema/object allowlist, catalog identity and local S3 storage contract are checked before verified_absent. No fixture/model/table writes are implemented. Live environment initial_stopped → initial_stopped; three pre-existing project/probe RustFS volumes remain present. No real lifecycle mutations, credentials or downloads performed.
- Remaining: none within TT-ENV-001. Final targeted suite 28/28 and complete discovery 82/82 pass; active LSP two Python files clean; final AST/CLI/whitespace/immutable/scope gates pass. Authenticated live checkpoint was not run (no local credential set); simulated results are not live integration evidence. Full TT acceptance/evidence, staged data, snapshots/rollback and runtime object cleanup remain later tasks.

### AC evidence
| AC / ссылка на источник | Result | Проверка / evidence / причина |
|---|---|---|
| `docs/bootstrap-time-travel.md` §5 TT-ENV-001, reuse healthy stack or manage only own startup | PASS | standard (simulated engine, not live integration): `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/tests -p 'test_time_travel_acceptance.py' -v` exited 0, 28/28 in 0.055 seconds. Borrowed success/collision issue no lifecycle mutations; own startup pins Compose/project path and instance IDs, with no pulls/builds/recreate. Complete discovery `... discover -s scripts/tests -q` exited 0, 82/82 in 2.666 seconds. |
| `docs/bootstrap-time-travel.md` §5 TT-ENV-001, allowlist before first write | PASS | standard: final 28-test suite verifies exact schemas/locations, prefix boundaries, schema/object collisions and malformed/truncated lists. Catalog fixture now matches pinned response; missing/foreign catalog name/type, S3 type/endpoints/region/path-style/allowed locations rejected before any SQL/object listing. B08 regression reproduced before fix and now passes. No table writes in ENV-001. |
| `docs/bootstrap-time-travel.md` §5 TT-ENV-001, safe refusal / lifecycle restoration | PASS | standard: final 28-test suite includes same-label container-ID and same-name network-ID replacements; both refuse all cleanup mutation. Successful/partial startup persists ownership evidence; cleanup targets pinned full IDs only, never volumes. Also validates stopped/partial refusal, stop failure, evidence/resource collision, malformed inventory, symlink/path refusal and replay protection. fast: final AST/CLI/scope assertion exit 0 (0.287 seconds); explicit full-acceptance refusal exit 2, no evidence; LSP clean=2, zero diagnostics; whitespace/immutable/history preservation pass. |
| `docs/spec.md` §12.9 AC-028 | NOT_RUN | Full exercise isolation belongs to later TT tasks. Task-scoped byte comparisons to HEAD pass for dbt/, docker/, infra/, Compose, old runners/tests, spec and plan. Existing status history is byte-identical to baseline; only this task section appended. |
| `docs/spec.md` §12.9 AC-029 | NOT_RUN | Historical queries are outside TT-ENV-001. |
| `docs/spec.md` §12.9 AC-030 | NOT_RUN | Rollback is outside TT-ENV-001. |
| `docs/spec.md` §12.9 AC-031 | NOT_RUN | Negative snapshot SQL operations are outside TT-ENV-001. |
| `docs/spec.md` §12.9 AC-032 | NOT_RUN | Staged source builds are outside TT-ENV-001. |
| `docs/spec.md` §12.9 AC-033 | NOT_RUN | Full evidence/cleanup acceptance belongs to later TT tasks; no full-slice PASS intended. |

### Issues
#### TT-ENV-001/B01
- State: RESOLVED
- Category: CODE
- Affects: TT-ENV-001 safe refusal / EVIDENCE_GATE
- Problem: container inventory JSON parsing lacks an explicit malformed-input error boundary.
- Evidence: post-write pi-lens blocker at scripts/run_time_travel_acceptance.py:185; json.loads can raise directly on malformed Docker output.
- Unblock: primary agent adds fail-closed decoding and a malformed-inventory negative test.
- Resolution: targeted 23-test suite exited 0; malformed JSON, array and null inventory cases all rejected as AcceptanceError. Active LSP probe: two Python paths clean.

#### TT-ENV-001/B02
- State: RESOLVED
- Category: CODE
- Affects: TT-ENV-001 allowlist preflight
- Problem: initial checks assumed a wrapped catalog response and an explicit IsTruncated flag for empty storage listings, unlike retained pinned-stack evidence.
- Evidence: pfimp006_final/runtime/polaris_catalog.json has top-level properties; seimp005_typed/cleanup/remaining_objects.json omits IsTruncated/Contents/KeyCount for an empty prefix. Initial implementation rejects both shapes.
- Unblock: primary agent validates the observed response forms without accepting malformed or truncated listings; add positive and mutation tests.
- Resolution: targeted 23-test suite exited 0; flat catalog properties and both empty-list forms accepted; missing/wrong Prefix, occupied/truncated listings and foreign catalog base rejected.

#### TT-ENV-001/B03
- State: RESOLVED
- Category: TEST
- Affects: task-scoped fast diagnostics
- Problem: two query_csv test doubles do not preserve the method's named parameter signature.
- Evidence: active LSP probe reports two Pyright reportAttributeAccessIssue errors at test_time_travel_acceptance.py:276,285; runner itself is clean.
- Unblock: primary agent corrects test-double signatures and reruns diagnostics/tests.
- Resolution: active LSP probe reports clean=2, zero diagnostics after named-parameter fixes; targeted suite subsequently passes.

#### TT-ENV-001/B04
- State: RESOLVED
- Category: TEST
- Affects: task-scoped lifecycle standard tests
- Problem: fake Docker parses label filters at the first equals sign, treating existing containers as absent.
- Evidence: targeted unittest run exited 1; 23 tests, 8 failures and 3 errors (0.040 seconds). Inspection shows label=com.docker.compose.project=NAME decoded as com.docker.compose.project=NAME rather than NAME, so lifecycle assertions cannot exercise the intended states.
- Unblock: primary agent fixes the simulator to parse the final equals sign and reruns the affected suite; no real Docker lifecycle was invoked.
- Resolution: corrected fake label decoding; targeted suite exited 0 (23/23, 0.051 seconds), then full discovery exited 0 (77/77, 2.516 seconds), including real command-shape assertions against the simulated engine.

#### TT-ENV-001/B05
- State: RESOLVED
- Category: CODE
- Affects: TT-ENV-001 safe refusal on repeated run
- Problem: calling run twice on the same instance retains evidence_reserved=True and overwrites its successful checkpoint after the second preflight refuses the occupied directory.
- Evidence: test_same_instance_cannot_overwrite_its_successful_checkpoint failed (exit 1, 0.005 seconds); byte comparison detects environment_checkpoint.json replaced with failure evidence.
- Unblock: primary agent makes run instances single-use before entering any finalization path, then reruns the replay assertion and affected suite.
- Resolution: single-use guard precedes all finalization; replay test preserves checkpoint bytes and command count. Final targeted suite passed 24/24 (0.050 seconds); full discovery passed 78/78 (2.338 seconds), exit 0.

#### TT-ENV-001/B06
- State: RESOLVED
- Category: TEST
- Affects: task-scoped standard suite
- Problem: external-path/symlink test reuses its runner instance for two scenarios after run instances became single-use.
- Evidence: targeted run exited 1 (24 tests, one failure, 0.043 seconds); full discovery also exited 1 (78 tests, one failure, 2.610 seconds). Expected canonical-path error is replaced by correct single-use refusal on the second scenario.
- Unblock: primary agent uses a fresh runner for the second scenario, preserving both path-refusal assertions; rerun targeted before full discovery.
- Resolution: fresh runner used for symlink scenario; final targeted 24/24 passed first, then full discovery 78/78 passed; both path checks retain expected canonical-path refusal and no Docker commands.

#### TT-ENV-001/B07
- State: RESOLVED
- Category: CODE
- Affects: TT-ENV-001 ownership/lifecycle safety
- Problem: cleanup trusts current labels/hash rather than pinned startup container IDs and network identity, so replacement resources can be treated as owned.
- Evidence: first fresh reviewer BLOCK; start_stack does not save IDs, while stop_stack deletes current inventory. Mutation changing only a container ID preserves all validation fields and reaches stop/rm. Network deletion similarly uses name, not pinned ID.
- Unblock: primary agent pins container and network IDs after attempted up (including partial failure), refuses drift before cleanup, and adds ID-only replacement mutations.
- Resolution: pre-fix `... -k replacement_container -v` reproduced failure (exit 1, 0.004 seconds). After pinning startup ownership in finally, container-ID and network-ID replacement tests reject before any stop/rm; partial up saves two IDs and cleanup succeeds. Targeted 28/28 and complete 82/82 pass, exit 0; Docker network CLI confirms --no-trunc support.

#### TT-ENV-001/B08
- State: RESOLVED
- Category: CODE
- Affects: TT-ENV-001 verified schema/object allowlist
- Problem: catalog base location is checked without validating the storage backend used by that catalog.
- Evidence: first fresh reviewer BLOCK; missing/foreign storageConfigInfo is accepted by assert_allowlist_absent, while object listing always uses local RustFS. Existing catalog bootstrap does not correct storage of a pre-existing catalog.
- Unblock: primary agent checks catalog identity/S3 endpoints/path style/allowed locations against local warehouse and adds missing/foreign storage mutation tests.
- Resolution: pre-fix `... -k catalog_storage -v` reproduced missing/foreign-storage acceptance (exit 1, 0.003 seconds). Pinned-response fixture and per-field missing/foreign mutations now reject before SQL/storage queries; positive real-form response remains accepted. Final 28/28 and 82/82 suites pass, exit 0.

### Review
- Verdict: OK
- Calls: 2
- Fix iterations: 1
- Details: first fresh builtin reviewer found B07/B08; after their reproduced fixes, a second fresh read-only reviewer inspected the complete two new Python files, full status addition and source/helper contracts. VERDICT OK for TT-ENV-001 only; no issues found. Both findings confirmed resolved. Toolset read, grep, find, ls, watchdog_diff, contact_supervisor; no bash/write/edit. Tests are supervisor evidence, not independently executed by reviewer. All three file hashes matched before/after each review; only permitted status/time/review/next-action finalization follows. No live or full-slice acceptance claimed.

### Next action
Completed and committed as `75bbdcb`. TT-1 full acceptance is recorded under TT-IMP-006; remaining project scope is maintenance and AC-002 coverage.

### Live completion on 2026-11-02

- Authenticated `tt_env_live_004 --check-environment`: ENVIRONMENT_READY; exact five-prefix allowlist verified, own containers/network removed, all pre-existing volumes preserved. AC-028–AC-033 remain NOT_RUN.
- Live runs exposed two defects absent from the simulator: Docker setup containers omit State.Health; healthy HTTP does not guarantee Trino SQL readiness. Safe map lookup and bounded retries only for the initializing diagnostic fix both. Added a regression that retries initialization but rejects connection errors immediately.
- `tt_env_live_002` failed before ownership persistence; exact startup IDs from its command journal were validated and recorded in cleanup/recovered_ownership.json before removing only those resources. `tt_env_live_003` cleaned itself after SQL initialization failure. Failed evidence is retained.
- Current Codex verification: full unit discovery 83 tests; live checkpoint. Earlier pi review applies to the original checkpoint; these live fixes were verified directly, without claiming a new pi reviewer invocation.


### Completion
TT-ENV-001 completed and committed as `75bbdcb`.

## TASK_ID: TT-ENV-002

- Source: [Time travel bootstrap](bootstrap-time-travel.md) §5–6; [spec](spec.md) §12.
- Status: DONE
- Updated: 2026-11-02T15:31:29+03:00
- Baseline HEAD: 75bbdcb1d2e2eb2225088048eb2af3e8cae214d3

### Progress
- Implemented: Implemented TT-specific evidence manifest with complete hash verification, catalog metadata pointers, full historical object content checksums, protected-path/runtime boundaries, exact-location cleanup and non-blanket AC gates. Inherited dbt commands are pinned to the same project and never pull images.
- Remaining: none within this stage; final AC-028–AC-033 acceptance is recorded separately under TT-IMP-006.

### AC evidence
Unit discovery: 88/88 PASS. Live tt_env002_live2: CHECKPOINT, AC-028 PASS, remaining AC NOT_RUN; all five task prefixes empty, pre-existing volumes preserved and environment restored. Initial live failure on virtual system.iceberg_tables reproduced and fixed with a targeted boundary regression. Manifest mutations and simulated cleanup failure cannot produce overall PASS.

### Review
- Codex direct source/diff verification and recorded tests; no pi reviewer invocation is claimed. User authorized sequential execution and commits on 2026-11-02.

### Next action
Completed and committed as `39f806c`. TT-1 full acceptance is recorded under TT-IMP-006; remaining project scope is maintenance and AC-002 coverage.

### Completion
TT-ENV-002 completed and committed as `39f806c`.

## TASK_ID: TT-PROBE-001

- Source: [Time travel bootstrap](bootstrap-time-travel.md) §5–6; [spec](spec.md) §12.
- Status: DONE
- Updated: 2026-11-02T15:34:31+03:00
- Baseline HEAD: 39f806ccf32e84863bb8eea15e691fe994e521d5

### Progress
- Implemented: Implemented and executed bounded single-table compatibility probe: three parent-linked snapshots, rollback to the second, preserved historical reads and unchanged data/delete file SHA-256 identities.
- Remaining: none within this stage; final AC-028–AC-033 acceptance is recorded separately under TT-IMP-006.

### AC evidence
Unit discovery 90/90 PASS, including mutation tests for snapshots, parents, schema/table identity, history, content hashes and catalog pointer. Live tt_probe001_live: CHECKPOINT; probe/comparison.json records 37.858 seconds within the 120-second budget. Exact task schemas/objects removed; environment restored; volumes preserved. This probe does not close the staged P1–P4 AC.

### Review
- Codex direct source/diff verification and recorded tests; no pi reviewer invocation is claimed. User authorized sequential execution and commits on 2026-11-02.

### Next action
Completed and committed as `6988d7e`. TT-1 full acceptance is recorded under TT-IMP-006; remaining project scope is maintenance and AC-002 coverage.

### Completion
TT-PROBE-001 completed and committed as `6988d7e`.

## TASK_ID: TT-IMP-001

- Source: [Time travel bootstrap](bootstrap-time-travel.md) §5–6; [spec](spec.md) §12.
- Status: DONE
- Updated: 2026-11-02T15:40:04+03:00
- Baseline HEAD: 6988d7e3a05f11efe8abee7d9f8f0ccc34bb575d

### Progress
- Implemented: Implemented immutable fixture batch_1 source build, independent typed P1-P4 oracle, eight-column Iceberg v2 learning table and H0 snapshot. Typed JSON arrays preserve SQL NULL; catalog metadata is checked against stored metadata JSON and content SHA-256 inventories.
- Remaining: none within this stage; final AC-028–AC-033 acceptance is recorded separately under TT-IMP-006.

### AC evidence
Unit discovery 93/93 PASS. Live tt_staged_dev002 reached STAGE_PASS stage_h0: all 15 unchanged dbt models executed; staged Gold and educational rows match independent H0; h0/comparison.json and states/H0/bundle.json retained. Prior tt_staged_dev001 exposed ROW-to-JSON field-name semantics; array serialization fixes the reproduced invalid-shape failure, and that failed run cleaned itself. Stateful development run continues under task ownership; final cleanup/end-to-end acceptance belongs to TT-IMP-006.

### Review
- Codex direct source/diff verification and recorded tests; no pi reviewer invocation is claimed. User authorized sequential execution and commits on 2026-11-02.

### Next action
Completed and committed as `e107c5f`. TT-1 full acceptance is recorded under TT-IMP-006; remaining project scope is maintenance and AC-002 coverage.

### Completion
TT-IMP-001 completed and committed as `e107c5f`.

## TASK_ID: TT-IMP-002

- Source: [Time travel bootstrap](bootstrap-time-travel.md) §5–6; [spec](spec.md) §12.
- Status: DONE
- Updated: 2026-11-02T15:41:58+03:00
- Baseline HEAD: e107c5fb12285e8b196d3ef5a9b8be050d11ce64

### Progress
- Implemented: Implemented batch_2 source build, one MERGE updating only the three P3 late-event metrics, and one UPDATE injecting duration 36 -> 360 in the educational table. Captured exactly H0 -> H1 -> Hbad, unchanged table UUID/schema and correct source Gold during the fault.
- Remaining: none within this stage; final AC-028–AC-033 acceptance is recorded separately under TT-IMP-006.

### AC evidence
Unit discovery 95/95 PASS, including rejection of swapped H0/H1/Hbad oracles and oracle mutation isolation. Live tt_staged_dev002 reached STAGE_PASS stage_states; batch_2 dbt build passed 128/128 nodes. states/comparison.json binds three runtime IDs and parents; source/after_fault.json remains exact H1. Cleanup and overall acceptance remain TT-IMP-006 gates.

### Review
- Codex direct source/diff verification and recorded tests; no pi reviewer invocation is claimed. User authorized sequential execution and commits on 2026-11-02.

### Next action
Completed and committed as `52fa272`. TT-1 full acceptance is recorded under TT-IMP-006; remaining project scope is maintenance and AC-002 coverage.

### Completion
TT-IMP-002 completed and committed as `52fa272`.

## TASK_ID: TT-IMP-003

- Source: [Time travel bootstrap](bootstrap-time-travel.md) §5–6; [spec](spec.md) §12.
- Status: DONE
- Updated: 2026-11-02T15:43:24+03:00
- Baseline HEAD: 52fa272001b12bfaf631c4fd3f2b3d79cb9f8fbf

### Progress
- Implemented: Implemented three snapshot-ID reads, five UTC timestamp boundary reads with preserved milliseconds, late P3 event_at/received_at evidence, exact historical/current comparisons and full table/catalog/object invariance around reads.
- Remaining: none within this stage; final AC-028–AC-033 acceptance is recorded separately under TT-IMP-006.

### AC evidence
Unit discovery 97/97 PASS, including ambiguous/insufficiently separated times and commit/history mismatch rejection. Live tt_staged_dev002 history/comparison.json records all eight successful reads; timestamp queries at each commit and one interior millisecond return H0/H1/Hbad as specified. Before/after bundles including all five task object inventories are identical; AC-029 PASS.

### Review
- Codex direct source/diff verification and recorded tests; no pi reviewer invocation is claimed. User authorized sequential execution and commits on 2026-11-02.

### Next action
Completed and committed as `e304708`. TT-1 full acceptance is recorded under TT-IMP-006; remaining project scope is maintenance and AC-002 coverage.

### Completion
TT-IMP-003 completed and committed as `e304708`.

## TASK_ID: TT-IMP-004

- Source: [Time travel bootstrap](bootstrap-time-travel.md) §5–6; [spec](spec.md) §12.
- Status: DONE
- Updated: 2026-11-02T15:47:02+03:00
- Baseline HEAD: e30470871870d4be50156ea12b004c7e4143258f

### Progress
- Implemented: Implemented three atomic negative operations: unavailable positive BIGINT snapshot read, t0 minus one millisecond read and rollback to the absent ID. Each checks a semantic unavailable-version diagnostic and its own complete before/after table, catalog, object and checksum bundle.
- Remaining: none within this stage; final AC-028–AC-033 acceptance is recorded separately under TT-IMP-006.

### AC evidence
Unit discovery 100/100 PASS; negative tests reject successful operations, wrong IDs, network/auth/startup/syntax failures. Live tt_staged_dev002 reached STAGE_PASS stage_negative: all three operations returned nonzero with the expected semantic diagnostic and zero state changes. negative/comparison.json records missing ID 9223372036854775807 and the exact early UTC timestamp; AC-031 PASS.

### Review
- Codex direct source/diff verification and recorded tests; no pi reviewer invocation is claimed. User authorized sequential execution and commits on 2026-11-02.

### Next action
Completed and committed as `2b921b6`. TT-1 full acceptance is recorded under TT-IMP-006; remaining project scope is maintenance and AC-002 coverage.

### Completion
TT-IMP-004 completed and committed as `2b921b6`.

## TASK_ID: TT-IMP-005

- Source: [Time travel bootstrap](bootstrap-time-travel.md) §5–6; [spec](spec.md) §12.
- Status: DONE
- Updated: 2026-11-02T15:48:13+03:00
- Baseline HEAD: 2b921b634f8a621f33e5f27cf98981746bec63a9

### Progress
- Implemented: Implemented rollback to actual H1, exact restored-current comparison, all three historical reads after rollback, metadata/history and ancestry assertions, preserved schema/table identity and full historical data/delete file path/size/SHA-256 invariants.
- Remaining: none within this stage; final AC-028–AC-033 acceptance is recorded separately under TT-IMP-006.

### AC evidence
Unit discovery 100/100 PASS; rollback mutations include resized/new delete files, changed content/schema/history/pointers and invalid rollback times. Live tt_staged_dev002 reached STAGE_PASS stage_rollback: current P3 duration=36, visits/dwell/ratio=2/3/1.5, Hbad readable; exactly three data snapshots and H0 -> H1 -> Hbad -> H1 history. rollback/comparison.json and before/after bundles retained; AC-030 PASS.

### Review
- Codex direct source/diff verification and recorded tests; no pi reviewer invocation is claimed. User authorized sequential execution and commits on 2026-11-02.

### Next action
Completed and committed as `53a139a`. TT-1 full acceptance is recorded under TT-IMP-006; remaining project scope is maintenance and AC-002 coverage.

### Completion
TT-IMP-005 completed and committed as `53a139a`.

## TASK_ID: TT-IMP-006

- Source: [Time travel bootstrap](bootstrap-time-travel.md) §5–6; [spec](spec.md) §12.
- Status: DONE
- Updated: 2026-11-02T16:00:41+03:00
- Baseline HEAD: 53a139aacc02096b69a0326f13de094179d2b5b4

### Progress
- Implemented: Completed standalone default CLI workflow, final source regression, exact catalog/storage evidence, ownership-aware cleanup, implementation/protected-file fingerprints, saved-behavior replay and full mandatory evidence gating. Added --probe alongside the preserved --check-environment mode; tightened cleanup against post-preflight schema collisions.
- Remaining: none; AC-028–AC-033 final acceptance is PASS.

### AC evidence
Fresh CLI python3 scripts/run_time_travel_acceptance.py --run-id tt_imp006_final exited 0: outcome PASS, error null, AC-028–AC-033 all PASS, 267 commands in 518.621 seconds. Exactly three nonzero commands are the semantic negative operations. Both full dbt builds pass 128/128 nodes; source remains H1 and educational history survives the final rebuild. All five task schemas/prefixes empty; own containers/network absent; pre-existing volumes preserved. Saved-behavior replay and complete 973-file SHA-256 manifest verification pass; 161 mandatory behavior paths present, secret scan clean and all 62 protected files unchanged. Implementation/test fingerprints match final code. Unit discovery 104/104 PASS, including whole-evidence mutations, nested manifests and schema-ownership races. Independent post-run Docker checks confirm no final-project containers/networks remain.

### Review
- Codex direct source/diff verification and recorded tests; no pi reviewer invocation is claimed. User authorized sequential execution and commits on 2026-11-02.

### Next action
Completed and committed as `1bf0c5a`. TT-1 full acceptance is recorded under TT-IMP-006; remaining project scope is maintenance and AC-002 coverage.

### Completion
TT-IMP-006 completed and committed as `1bf0c5a`.


## TASK_ID: TT-DOC-001

- Source: [Time travel bootstrap](bootstrap-time-travel.md) §5–6; [spec](spec.md) §12.
- Status: DONE
- Updated: 2026-11-02T16:01:25+03:00
- Baseline HEAD: 1bf0c5af95ce4a8fa86cfa73177022e007933689

### Progress
- Implemented: Documented completed TT-1 workflow, current CLI modes, P3 state transitions, saved evidence, cleanup behavior and remaining project scope. Reconciled all historical TT records with their actual per-stage commits; README and current status now report four completed slices.
- Remaining: none; AC-028–AC-033 final acceptance is PASS.

### AC evidence
Documentation matches tt_imp006_final PASS and implementation commit 1bf0c5a. Recorded 104 unit tests, 128 nodes per full dbt build, AC-028–AC-033, live environment/probe distinctions and excluded branches/tags/post-rollback timestamp semantics. Relative links, task uniqueness/counts, unchanged core/SE/PF task history and git diff whitespace are checked in the final documentation gate.

### Review
- Codex direct source/diff verification and recorded tests; no pi reviewer invocation is claimed. User authorized sequential execution and commits on 2026-11-02.

### Next action
Commit this documentation checkpoint. TT-1 is complete; maintenance and AC-002 remain in the project roadmap.

## TASK_ID: MA-SPEC-001

- Source: [Completion roadmap](bootstrap-time-travel.md) §9; [specification](spec.md) §13–14.
- Status: DONE
- Updated: 2026-11-02T16:59:56+03:00
- Baseline HEAD: c568502a5903e842a37741fa7bd4f8966b7f82cf

### Progress
- Implemented: Defined isolated maintenance contract, deterministic 2048-row/16-commit workload, compaction threshold, two retained snapshots, orphan age/location checks and session-only retention overrides. Added AC-034–AC-040 without changing earlier contracts.
- Remaining: none within this stage.

### AC evidence
Primary pinned Trino 484 documentation confirms optimize, expiration retain_last, orphan cleanup and session equivalents of retention minima. Specification source sections 1–12 are preserved byte-for-byte; no runtime writes or global config changes. Numerical thresholds and expected sets are fixed before implementation.

### Review
Direct source/diff review and recorded checks; no independent pi reviewer invocation is claimed. The user authorized completion of all project tasks and per-stage commits.

### Next action
Commit this completed stage and continue the project completion roadmap.

## TASK_ID: MA-BOOT-001

- Source: [Completion roadmap](bootstrap-time-travel.md) §9; [specification](spec.md) §13–14.
- Status: DONE
- Updated: 2026-11-02T17:01:20+03:00
- Baseline HEAD: 08de2d7e9fde555a05d3fac2985fcc1bcd345a28

### Progress
- Implemented: Created maintenance bootstrap with nine sequential tasks, file scope, runtime boundaries, unit/live/final gates and fresh CLI acceptance plan.
- Remaining: none within this stage.

### AC evidence
All AC-034–AC-040 map to observable assertions; paths and CLI are identified as implemented or proposed. Session-only retention and data ownership constraints follow spec §13. Documentation link/scope/whitespace checks pass.

### Review
Direct source/diff review and recorded checks; no independent pi reviewer invocation is claimed. The user authorized completion of all project tasks and per-stage commits.

### Next action
Commit this completed stage and continue the project completion roadmap.

## TASK_ID: COV-001

- Source: [Completion roadmap](bootstrap-time-travel.md) §9; [specification](spec.md) §13–14.
- Status: DONE
- Updated: 2026-11-02T17:01:23+03:00
- Baseline HEAD: fffa42343e9f73d907c12528ace9f381f1a895e2

### Progress
- Implemented: Audited all 14 source competencies and created the traceability matrix. Eleven are supported by retained core/SE/PF/TT reports; incremental predicates, small-files diagnostics and maintenance have explicit remaining tasks.
- Remaining: none within this stage.

### AC evidence
docs/learning-outcomes.md contains exactly 14 mapped competencies and identifies three open learning outcomes. Core Kimball/SCD2/DQ/late-event evidence and existing acceptance PASS are reused without claiming AC-002 completion.

### Review
Direct source/diff review and recorded checks; no independent pi reviewer invocation is claimed. The user authorized completion of all project tasks and per-stage commits.

### Next action
Commit this completed stage and continue the project completion roadmap.

## TASK_ID: MA-ENV-001

- Source: [Completion roadmap](bootstrap-time-travel.md) §9; [specification](spec.md) §13–14.
- Status: DONE
- Updated: 2026-11-02T17:05:28+03:00
- Baseline HEAD: 3354297452203e33dd53d7125803eba0325e29fe

### Progress
- Implemented: Implemented reusable single-schema exercise adapter over the unchanged TT lifecycle: exact allowlist, authoritative metadata/storage snapshots, raw content hashes, ownership-aware cleanup and explicit per-criterion final gates. Added no-blanket-PASS and cleanup-failure regressions.
- Remaining: none within this stage.

### AC evidence
Full unit discovery 108/108 PASS. Live ma_env001_live environment CHECKPOINT: AC-034 PASS, remaining criteria NOT_RUN, no data writes, owned containers/network removed and pre-existing volumes preserved. The adapter normalizes cleanup evidence to its exact single prefix; final standalone runs verify frozen implementation and complete evidence.

### Review
Direct source/diff review and recorded checks; no independent pi reviewer invocation is claimed. The user authorized completion of all project tasks and per-stage commits.

### Next action
Commit this completed stage and continue the project completion roadmap.

## TASK_ID: MA-IMP-001

- Source: [Completion roadmap](bootstrap-time-travel.md) §9; [specification](spec.md) §13–14.
- Status: DONE
- Updated: 2026-11-02T17:13:53+03:00
- Baseline HEAD: 274b587bdc7bfea7dfac230c949674c6305cb924

### Progress
- Implemented: Implemented independent typed maintenance oracle, real 16-commit/2048-row small-files workload, exact schema/grain checks, file size distribution, control signature and distributed/analyze plans. Catalog/S3 metadata comparison normalizes only unordered statistics arrays.
- Remaining: none within this stage.

### AC evidence
Unit discovery 112/112 PASS. Live ma_staged_dev003: STAGE_PASS stage_fixture, 16 data snapshots, 16 current data files of 889–999 bytes, all 2048 rows match the independent oracle; AC-035 PASS. Prior runs preserved failures and restored their owned environment. Diagnostic copies prove only statistics entry order differs; mutation tests reject changed statistics content and changed history order.

### Review
Direct source/diff review and recorded checks; no independent pi reviewer invocation is claimed. The user authorized completion of all project tasks and per-stage commits.

### Next action
Commit this completed stage and continue the project completion roadmap.

## TASK_ID: MA-IMP-002

- Source: [Completion roadmap](bootstrap-time-travel.md) §9; [specification](spec.md) §13–14.
- Status: DONE
- Updated: 2026-11-02T17:16:32+03:00
- Baseline HEAD: 98a6d8715a7265f2edb1f5bc70358f71e621a21d

### Progress
- Implemented: Implemented compaction with exact row/table/schema/history invariants, old-snapshot reads, preserved historical data hashes, control checks and before/after distributed/analyze plans. Added raw snapshot replay binding catalog/S3 metadata, content hashes and typed rows.
- Remaining: none within this stage.

### AC evidence
Unit discovery 115/115 PASS. Live ma_staged_dev003 STAGE_PASS stage_compaction: current files reduced 16 -> 1 (14392 -> 9531 bytes), all 2048 rows and prior snapshot readable, historical data files and control unchanged; AC-036 PASS. Independent replay verifies fragmented/before-compaction/compacted raw snapshots.

### Review
Direct source/diff review and recorded checks; no independent pi reviewer invocation is claimed. The user authorized completion of all project tasks and per-stage commits.

### Next action
Commit this completed stage and continue the project completion roadmap.

## TASK_ID: MA-IMP-003

- Source: [Completion roadmap](bootstrap-time-travel.md) §9; [specification](spec.md) §13–14.
- Status: DONE
- Updated: 2026-11-02T17:26:44+03:00
- Baseline HEAD: 2c5d2dbb6f163a099ca08a4efa216467fd8ffe1b

### Progress
- Implemented: Implemented default-retention atomic rejection, session-only expiration override, retained historical/current reads, expired-ID error checks and retained data/delete SHA-256 safety. Added an identical-row retention anchor so compaction deletion records can expire and physical obsolete data is actually reclaimed; recorded the live-driven sequence clarification in spec/bootstrap.
- Remaining: none within this stage.

### AC evidence
Unit discovery 118/118 PASS. Live ma_staged_dev004 STAGE_PASS stage_expiration: exactly two retained snapshots, 2048 historical rows and 2176 current rows, all 16 obsolete small files physically removed, retained files/control unchanged, expired read semantic failure without mutation. Ordinary session defaults remain 7.00d. Prior ma_staged_dev003 demonstrated conservative GC while the deletion snapshot is retained; no reclamation assertion was suppressed.

### Review
Direct source/diff review and recorded checks; no independent pi reviewer invocation is claimed. The user authorized completion of all project tasks and per-stage commits.

### Next action
Commit this completed stage and continue the project completion roadmap.

## TASK_ID: MA-IMP-004

- Source: [Completion roadmap](bootstrap-time-travel.md) §9; [specification](spec.md) §13–14.
- Status: DONE
- Updated: 2026-11-02T17:32:42+03:00
- Baseline HEAD: 3039c961c8c65c0a950f67b63d3cb842708a2c98

### Progress
- Implemented: Implemented default orphan-retention rejection, real storage-age checks, old/young/outside markers and session-only orphan cleanup. All table/schema/history/current/control and referenced content remain unchanged; defaults are checked from ordinary sessions.
- Remaining: none within this stage.

### AC evidence
Unit discovery 120/120 PASS. Live ma_staged_dev004 STAGE_PASS stage_orphan: old marker age 27.511 seconds removed, young marker age 3.511 seconds preserved under the 10-second threshold, outside-table marker and all other content hashes preserved. Both negative retention operations are atomic; defaults remain 7.00d. AC-038 and AC-039 PASS.

### Review
Direct source/diff review and recorded checks; no independent pi reviewer invocation is claimed. The user authorized completion of all project tasks and per-stage commits.

### Next action
Commit this completed stage and continue the project completion roadmap.

## TASK_ID: MA-IMP-005

- Source: [Completion roadmap](bootstrap-time-travel.md) §9; [specification](spec.md) §13–14.
- Status: DONE
- Updated: 2026-11-02T17:44:46+03:00
- Baseline HEAD: 58ac93c582b28b8ae4337e75b982793b1a81a4de

### Progress
- Implemented: Completed standalone maintenance CLI, full saved-snapshot/behavior replay, mandatory evidence list, exact catalog registrations, control proof, manifest/secret scan and single-schema cleanup/restoration gates. Old core/SE/PF/TT implementations remain unchanged.
- Remaining: none within this stage.

### AC evidence
Fresh ma_imp005_final CLI exits 0: AC-034–AC-040 all PASS, error null, 233 commands; 16 small files compacted to one, two retained states of 2048/2176 rows, 16 obsolete files removed, age/location-bounded orphan deletion verified. Ordinary retention stays 7.00d, owned schema/object prefix empty, own containers/network removed and volumes preserved. Unit discovery 120/120 PASS; independent raw snapshot/behavior/manifest replay and frozen implementation hashes pass.

### Review
Direct source/diff review and recorded checks; no independent pi reviewer invocation is claimed. The user authorized completion of all project tasks and per-stage commits.

### Next action
Commit this completed stage and continue the project completion roadmap.

## TASK_ID: MA-DOC-001

- Source: [Completion roadmap](bootstrap-time-travel.md) §9; [specification](spec.md) §13–14.
- Status: DONE
- Updated: 2026-11-02T17:44:49+03:00
- Baseline HEAD: 8cb10ad9a1e1bc31163414cb5b2c929f220b55e8

### Progress
- Implemented: Documented maintenance CLI, distributions, compaction, retention anchor/expiration, orphan ages and evidence/cleanup. Closed small-files and maintenance competency rows; incremental coverage remains open.
- Remaining: none within this stage.

### AC evidence
README statements match ma_imp005_final PASS; 120 unit tests and session-only retention behavior are recorded without claiming project completion. Documentation links/whitespace and existing task history are checked; no completed implementation files changed.

### Review
Direct source/diff review and recorded checks; no independent pi reviewer invocation is claimed. The user authorized completion of all project tasks and per-stage commits.

### Next action
Commit this completed stage and continue the project completion roadmap.

## TASK_ID: INC-SPEC-001

- Source: [Completion roadmap](bootstrap-time-travel.md) §9; [specification](spec.md) §13–14.
- Status: DONE
- Updated: 2026-11-02T17:46:16+03:00
- Baseline HEAD: ff517197cb9cef9dabc8bdb077606b779e315174

### Progress
- Implemented: Specified independent dbt incremental project, seven-event typed oracle, received_at lookback, safe source/target predicates and exact missing-event/duplicate counterexamples. Added AC-041–AC-045 without changing root dbt models/config or earlier specification sections.
- Remaining: none within this stage.

### AC evidence
Fixture expectations fixed before runtime: initial 5 rows, final/replay/full-refresh 7 rows (sum 215), narrow-source 6 missing E5, narrow-target 9 with duplicate E1/E2. Primary pinned adapter source confirms incremental_predicates participates in actual MERGE. No production/window SLA or core materialization change is introduced.

### Review
Direct source/diff review and recorded checks; no independent pi reviewer invocation is claimed. The user authorized completion of all project tasks and per-stage commits.

### Next action
Commit this completed stage and continue the project completion roadmap.

## TASK_ID: INC-IMP-001

- Source: [Completion roadmap](bootstrap-time-travel.md) §9; [specification](spec.md) §13–14.
- Status: DONE
- Updated: 2026-11-02T17:57:29+03:00
- Baseline HEAD: 394eddaf90d92c630140f65cfb4bcbeb29de7bb2

### Progress
- Implemented: Implemented standalone four-model dbt project with safe received_at incremental MERGE, full-reference model and exact narrow-source/narrow-target counterexamples. Added immutable fixture, positive dbt tests, replay/full-refresh checks, actual executed/compiled SQL, IO/ANALYZE plans and complete isolated evidence/cleanup.
- Remaining: none within this stage.

### AC evidence
Fresh inc_imp001_final2 CLI exits 0: AC-041–AC-045 all PASS, error null, 128 commands, 327 evidence files and 82 mandatory paths verified. Initial 5 and final/replay/full-refresh 7 typed rows match independent oracle/full rebuild; sum=215. Counterexamples reproduce missing E5 and duplicate E1/E2 (9 rows, 7 IDs). Actual source scan reads 11 raw rows; target has 7 and predicates select 6. All six dbt steps and positive tests pass; saved snapshot/behavior/manifest replay and implementation hashes pass. Unit discovery 126/126 PASS. Prior final run correctly rejected the expected timestamp(3) type: pinned Iceberg maps TIMESTAMPTZ to timestamp(6); the storage mapping was corrected and timestamp values remain exact. Owned schema/data/containers/network are cleaned and volumes preserved.

### Review
Direct source/diff review and recorded checks; no independent pi reviewer invocation is claimed. The user authorized completion of all project tasks and per-stage commits.

### Next action
Commit this completed stage and continue the project completion roadmap.
