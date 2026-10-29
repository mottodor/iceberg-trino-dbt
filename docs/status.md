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
