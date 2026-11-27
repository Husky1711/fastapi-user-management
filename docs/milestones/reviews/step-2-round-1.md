# Step 2: independent review, round 1 (verbatim)

### 5. Independent review: FAIL

Reviewer: milestone-reviewer agent (`.claude/agents/milestone-reviewer.md`), 2026-11-27, commit 175cee2

**Summary:** The schema work is strong. It has named constraints, a full index on every foreign key, role-scope triggers, `citext`, 32-byte `bytea` token hashes and a CI-proven upgrade/downgrade/upgrade round trip, and the CI numbers in the report are real (271 passed, 98 % coverage, run 45931167559 green). The step still fails, on four High findings. First, the transaction design the step introduces (`get_db` hands out a bare session and the service calls `session.begin()`) breaks as soon as any dependency reads through the same session. The author hit this in F7 and changed the test rather than the design. Second, the new service raises `ValueError` subclasses instead of `AppError`. Third, an org-owned lookup (`RoleRepository.permission_keys`) is deliberately left without tenant scoping. Fourth, the cross-check table states something false about the old code.

| # | Finding | Severity | Evidence | Recommended fix |
| --- | --- | --- | --- | --- |
| R1-01 | The per-request transaction contract breaks for its first real user. `get_db` yields a session with no transaction, and services call `async with session.begin()`. Any read before that call, such as `get_current_user` or `require_permission` in steps 3 and 5 (both use the same `DbSession` per ARCHITECTURE §2/§5), autobegins a transaction, so the service's `begin()` raises `InvalidRequestError: A transaction is already begun` and the request returns 500. The author hit exactly this (F7, "service test hit 'transaction already begun'") and changed the test ("commits its setup first") rather than the design. A related problem (F8): a rolled-back service transaction expires every object already loaded, such as the current user, and touching one afterwards in async code raises `MissingGreenlet`. That is only "noted for step 3". No scenario covers "dependency reads, then service writes". | High | `app/core/deps.py:10-19`; `app/services/admin.py:26-32`; `tests/integration/test_s2_6_create_admin.py:269-270`; step-2.md failure log F7, F8; roadmap item rewritten at `docs/ROADMAP.md:106` | Pick one contract that works with reading dependencies and test it. Options: a single `core` helper such as `transaction(session)` that commits or ends an autobegun read transaction before beginning, or joins it; or have `get_db` own `session.begin()` and commit explicitly before the response. Add a test with a dependency that reads and a service that then writes and fails. Document the rule in ARCHITECTURE §2. |
| R1-02 | The service raises non-`AppError` exceptions. `create_platform_admin` lets `InvalidEmail` / `WeakPassword` (`ValueError` subclasses) through as part of its contract. CLAUDE.md says services "raise `AppError` subclasses". When step 3 signup calls these rules over HTTP, they become unhandled 500s, not 422s with stable codes. | High | `app/services/admin.py:16-20`; `app/core/emails.py:16`; `app/core/security.py:20`; `app/cli.py:53` | Make both errors `AppError` subclasses (422, codes such as `user.email_invalid` / `user.password_weak`, safe detail), or translate them in the service. Keep the CLI mapping to exit code 2. |
| R1-03 | An org-owned query has no tenant scope. `RoleRepository.permission_keys(role_id)` returns the permissions of any role, including another organization's custom role, given only its id. CLAUDE.md: "Org-scoped queries always take `organization_id` as a required argument". The guard test exempts this method by hand. Step 5's roles API (role id from the URL) is the obvious caller that would leak across tenants. | High | `app/repositories/roles.py:37-41`; `tests/integration/test_s2_5_repositories.py:150-154` | Require `organization_id` as a keyword and join to `roles` with `organization_id = :org OR organization_id IS NULL`. Remove the exemption and add a cross-org case to 2.5-07. |
| R1-04 | The cross-check table contains a false claim. The row "`create_all()` at startup → Alembic" is wrong: the old code never creates tables. `git grep -n create_all 209a9bd` returns nothing; `utils/database.py` only builds the engine, and `main.py` only calls `engine.connect()`. | High | step-2.md gate §4, row "`create_all()` at startup"; `git show 209a9bd:utils/database.py`, `209a9bd:main.py:22,40` | Correct the row (old: no schema management at all; tables had to be created by hand). Re-check the other rows against the old source. |
| R1-05 | The expiry CHECK compares an app-clock value with a DB-clock value. `expires_at` comes from `clock.now()` in code, while `created_at` is the DB's `now()`. ARCHITECTURE §4 says timestamps are "written in UTC from code". With an injected or frozen clock (which CLAUDE.md requires in tests) or with app/DB clock skew, valid inserts fail `ck_*_expires_after_created`. | Medium | `app/models/base.py:72`; `app/models/user.py:69,95`; `app/models/organization.py:80`; `docs/ARCHITECTURE.md:193`; `tests/factories.py:137` | Set `created_at` from `app.core.clock.now()` in the model (keep the server default as a fallback), or change the CHECK and update ARCHITECTURE. Add a test with an injected clock. |
| R1-06 | Nothing stops two `alembic upgrade head` runs at once (several replicas or init containers at deploy). The C7 N/A ("single runner") is an assumption nothing enforces. | Medium | `migrations/env.py:19-27`; step-2.md §2.3 N/A row | Take `pg_advisory_xact_lock(<const>)` in `_run` before `run_migrations()`. Add a scenario that runs two upgrades at the same time on an empty DB. |
| R1-07 | Test 2.5-12 doesn't check what the report claims ("visible only after the caller's transaction commits"). It only proves the row is invisible before commit and after rollback; it never commits and checks the row becomes visible. | Medium | `tests/integration/test_s2_5_repositories.py:360-370` | Commit the writer and assert the reader sees the row. Clean up afterwards. |
| R1-08 | Argon2 concurrency has no bound. Each hash or verify takes 64 MiB and runs on the shared default executor with no semaphore. A burst of logins can use roughly `max_workers × 64 MiB` and starve every other `to_thread` user. | Medium (carry to step 3) | `app/core/security.py:14,42-54` | Use a settings-sized `asyncio.Semaphore` (or a dedicated executor) around hashing, plus a test. |
| R1-09 | Readiness says "ready" before the schema exists. In the Compose job the app is ready (200) before `alembic upgrade head` runs, so an un-migrated instance would take traffic and return 500. | Medium (carry to step 8) | `.github/workflows/ci.yml` step "2.3-05" runs after "1.1-03 … wait ready 200"; compose log lines 437-453 | Add a readiness check that the DB revision equals the code's head, or a documented migration job/init container. |
| R1-10 | `EMAIL_MAX_LENGTH = 254` is defined twice ("one way to do each thing"). | Low | `app/core/emails.py:9`; `app/models/user.py:13` | Keep one constant and import it. |
| R1-11 | `Any` is used without a comment. | Low | `app/models/base.py:59` | Add the reason, or type it as `dict[type, TypeEngine]`. |
| R1-12 | The old engine's `pool_recycle=3600` was dropped without a cross-check row. | Low | `git show 209a9bd:utils/database.py`; `app/infra/database.py:14-22` | Add a row: kept, dropped (with reason), or a new setting. |
| R1-13 | Record inconsistencies. The report header links run 45930672394, not the final run 45931167559. The failure log is out of order (F6–F8 before F1–F5). There is no passed / failed / fixed totals line. | Low | `docs/milestones/step-2.md:4,170-181` | Fix the link, the order and the totals. |
| R1-14 | The CLI has no connect timeout. A blackholed DB host makes `create-admin` hang for asyncpg's default 60 s. The test only uses a refused port. | Low | `app/infra/database.py:14-22`; `tests/db.py:82-86` | Set `connect_args={"timeout": …}` from settings. Add a non-routable-host case, or document the wait. |
| R1-15 | Weak assertions. 2.6-11 compares ORM objects from different sessions by identity, which only passes while the list is empty. 2.6-13 checks that the whole URL is absent rather than the password. | Low | `tests/integration/test_s2_6_create_admin.py:322-326,334` | Compare ids. Assert `UNREACHABLE_PASSWORD not in err`. |
| R1-16 | The tenant-scope guard test is a hand-written allowlist of two repositories. New repositories (invitations, sessions, audit) won't be checked automatically. | Low | `tests/integration/test_s2_5_repositories.py:150-154,340-350` | Discover `Repository.__subclasses__()` and require each one to declare its unscoped methods. |
| R1-17 | The docstring calls `audit_logs` "Append-only", but nothing enforces it (no trigger, no revoked UPDATE/DELETE). | Low (carry to step 9) | `app/models/audit.py:1` | Add a trigger or grants when the audit log is built, or soften the docstring. |
| R1-18 | IDN email domains are refused (`grace@exämple.com` is invalid), so real users with such addresses can't be created. This limit is documented, not hidden. | Low | `app/core/emails.py:13`; `tests/unit/test_s2_6_security.py:156` | Decide in step 3 (IDNA-encode or keep refusing) and record the choice in an ADR or README. |

**Report claims verified:**
- **CI run 45931167559:** on head 175cee2, all four jobs succeeded. The Test job shows "271 passed, 6 skipped" (all six are e2e skips, for missing `E2E_BASE_URL` / `E2E_ALLOWED_ORIGIN`) and "Total coverage: 98.49%". The Type check job shows `mypy`: "Success: no issues found in 71 source files", and `pyproject` includes `migrations`.
- **Migration round trip:** the log shows "left after downgrade: []", a second upgrade with no "Running upgrade" line, and `0002 (head)`.
- **Compose job:** 2.3-05 prints `admin,member,owner`. 2.3-06 output contains "password authentication failed" and the password does not appear. 2.6-12 prints "Created platform admin o***@example.com", and the second run prints "already exists" with exit 1.
- **Ruff:** `ruff check` and `ruff format --check` pass locally.
- **Tests behind the scenario ids:** I read every cited test body for 2.1–2.6. All exist and assert their scenario, except 2.5-12 (R1-07) and the weak assertions in R1-15.
- **Scenario totals:** row counts match the section log (9 + 22 + 7 + 6 + 14 + 14 = 72).
- **Old-code facts:** I checked against `git show 209a9bd:` and confirmed unsalted SHA-256 (`utils/jwt_config.py:16`), the fake phone default, `organization_id` default 1, free-text role, no `ON DELETE`, and `utcnow` use. The `create_all` claim is false (R1-04).
- **Roadmap:** all nine boxes are ticked. The first item's wording was changed to fit the R1-01 design.
- **Could not verify locally:** test and mypy runs, since packages are not installed. I relied on the CI logs above. I did not open the JUnit artifact itself, only the log summary.

**Missing scenarios:**
- **2.1:**
  - C7/C10: a dependency reads, then the service opens its transaction (the real `get_current_user` flow).
  - C10: objects loaded before a failed service transaction are touched afterwards (F8).
  - C9: database slow or blackholed (timeout, not refused); pool exhausted (`pool_timeout`).
- **2.2:**
  - C3: invalid `inet` for `sessions.ip`; role key length 50/51; slug 63/64; organization name 200/201.
  - C10: the `updated_at` trigger is exercised only on `users`, not on the other five tables. Also missing: a check that every `Timestamps` model has a trigger, so a new table without one is caught.
- **2.3:**
  - C7: two concurrent upgrades.
  - C10: `downgrade` of 0002 is refused while a membership uses a system role (the migration comment claims this; nothing tests it).
- **2.5:**
  - C10: a row becomes visible after commit.
  - C3: `limit = 100` with more than 100 rows; `offset = MAX_OFFSET` accepted.
  - C5/C6: a role id from another org passed to `permission_keys`.
- **2.6:**
  - C7: two concurrent `create_platform_admin` calls through the service, giving exactly one `Conflict`. 2.2-21 only covers raw inserts.
  - C9: database reachable but not migrated (exit 1, clear message).
  - C2: password with control or NUL characters; trailing spaces from stdin (only `\r\n` is stripped).

## Scorecard (by the independent reviewer)

| Area | Old code | After step 2 | Evidence |
| --- | --- | --- | --- |
| Folder structure & architecture | 6 | 8 | Layers and folders match ARCHITECTURE §3, but the transaction ownership design fails with reading dependencies (R1-01), and the service raises non-`AppError` errors (R1-02). |
| API design | 5 | 9 | No new endpoints in step 2 (the step 1 score stands). `PaginationParams` is bounded (`app/core/pagination.py`); `Page[T]` is not built yet. |
| Database schema | 5 | 8 | Constraints, full FK indexes (2.2-20), triggers, round trip in CI. Held back by the app-vs-DB clock CHECK (R1-05), no migration lock (R1-06) and readiness that ignores the revision (R1-09). |
| Scalability & load balancing | 4 | 8 | Async engine with a bounded pool; hashing runs off the event loop (2.6-06), but its concurrency is unbounded (R1-08). |
| DSA / algorithms | 4 | 9 | No N+1, proved with a query counter (2.5-10: `[2, 2]`); stable ordering; an index for every repository query. |
| Code quality & correctness | 3 | 8 | Clean, short and typed, but the transaction footgun (R1-01, F7/F8) and the error type contract (R1-02) are correctness gaps. |
| Duplication & reuse | 3 | 8 | Shared check helpers and factories, but `EMAIL_MAX_LENGTH` is duplicated (R1-10). The migration's copy of the permissions is justified. |
| Maintainability | 3 | 8 | CI round trip, mypy over migrations, a good failure log. Held back by the false cross-check row (R1-04), record inconsistencies (R1-13) and a hand-maintained guard allowlist (R1-16). |
| Security | 2 | 8 | Argon2id with RFC 9106 parameters, 32-byte hashed tokens, no secret leaks (2.1-07, 2.3-06, 2.6-10, 2.6-13), but `permission_keys` has no tenant scope (R1-03). |
| **Overall** | **4** | **8** (8.2) | Average of the nine areas. The four High findings block the gate. |
