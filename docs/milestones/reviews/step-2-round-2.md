# Step 2: independent review, round 2 (verbatim)

### 5. Independent review: PASS

Reviewer: milestone-reviewer agent (`.claude/agents/milestone-reviewer.md`), 2026-11-27, commit 621b96c

**Summary:** All four round 1 High findings are fixed in the code and covered by tests that check what the report says they check. `transaction(session)` now continues a dependency's read transaction (2.1-01, 2.1-10, 2.6-15). The rule errors are 422 `AppError`s with stable codes. `permission_keys` is tenant-scoped, and a cross-org case was added. The cross-check row is corrected. CI run 45933396263 is green on 99ae3c2. I found no Critical or High issue, so the step passes. Several Medium issues remain: a stale test count in gate check 1; one scenario that round 1 named (touching loaded objects after a rollback) was neither added nor carried; a pool connection stays checked out, idle in a transaction, during Argon2 hashing; a nested `transaction()` call is not guarded; and the cross-check table has no row for the MySQL/sync-engine baseline.

| # | Finding | Severity | Evidence | Recommended fix |
| --- | --- | --- | --- | --- |
| R2-01 | Gate check 1 gives the wrong CI numbers. It says "271 tests … at 98 % coverage". The linked run reports **288 passed, 6 skipped, 98.55 %**. 271 was the round 1 count. | Medium | `docs/milestones/step-2.md:215`; job 140290951582 log: "288 passed, 6 skipped in 12.45s", "Total coverage: 98.55%" | Correct the number. Better, cite the run instead of typing counts by hand (CLAUDE.md: "never type test results by hand"). |
| R2-02 | One round 1 missing scenario was not handled. "2.1 C10: objects loaded before a failed service transaction are touched afterwards (F8)" was not added, and not marked N/A or carried. The step only documents the hazard. In step 3, `get_current_user` will load a `User`, any `AppError` raised inside `transaction()` expires it, and any later attribute read in async code raises `MissingGreenlet` (a 500). The "missing scenarios were added" list leaves this one out without saying so. | Medium | `app/infra/database.py:44-45`; `docs/ARCHITECTURE.md` §2 "Transactions"; `docs/milestones/step-2.md:288-290`; R1 missing scenarios, 2.1 C10 | Either add a test now (a dependency loads a row, the service raises `Conflict`, then the route or handler path reads nothing from it, or the object is refreshed), or carry it explicitly to step 3 in ROADMAP next to `get_current_user`. Also consider running the unit of work in a SAVEPOINT (`begin_nested`): rolling back a savepoint expires only the objects changed inside it. |
| R2-03 | In the HTTP shape this step introduces, the slow hash runs inside an open transaction. Once a dependency has read, the session holds a pool connection with a transaction open (idle in transaction) while `hash_password` (64 MiB, tens of ms) runs. The comment "before the transaction: it's slow" is only true for the CLI path. With a default pool of 5 + 5, login or signup throughput will be limited by connections × hash time, which compounds R1-08. | Medium (carry to step 3) | `app/services/admin.py:22`; `app/infra/database.py:47`; 2.6-15 shape (`tests/integration/test_s2_6_create_admin.py` `_admin_router`) | In step 3, end the dependency's read transaction before slow work, or hash before any DB read, and fix the comment now. Add this to the R1-08 roadmap item. |
| R2-04 | `transaction()` is documented as "not reentrant" but nothing enforces that. If a service calls another service that also uses `transaction()`, the inner call commits the outer call's partial work early, and a later failure in the outer call can no longer roll it back. That breaks atomicity silently. | Medium | `app/infra/database.py:36-53` (docstring lines 41-42) | Mark the session (`session.info`) on entry and raise if `transaction()` is entered again. Add a unit test. |
| R2-05 | The cross-check table is incomplete for the database scope. The old code ran **MySQL** (`mysql+pymysql` default URL, README "MySQL 8.0+") through a **synchronous** engine and `get_db` inside async FastAPI, with pool_size 10. The step changes the engine, the driver, sync to async, the session/commit pattern and the pool default, and none of these has a row. | Medium | `git show 209a9bd:config/settings.py:15,17`; `209a9bd:README.md:43,427`; `209a9bd:utils/database.py`; `docs/milestones/step-2.md:236-257` | Add rows for the database engine and driver, sync vs async sessions, the transaction ownership pattern (old routes committed ad hoc), and the pool size. |
| R2-06 | Timestamps come from two clocks, which contradicts ARCHITECTURE. `created_at` comes from the app clock, but later `updated_at` values come from the database's `clock_timestamp()`. If the app clock is ahead of the database (or a test injects a future clock), `updated_at < created_at`. ARCHITECTURE §4 still says all timestamps are "written in UTC from code". 2.2-24's `updated > created` only holds because CI's app and database share a host clock. | Low | `migrations/versions/0001_initial_schema.py:356-361`; `app/models/base.py` `Timestamps`; `docs/ARCHITECTURE.md:201`; `tests/integration/test_s2_2_schema.py` 2.2-24 | Update ARCHITECTURE §4 to state the split, or set `updated_at` from the app clock in the ORM and keep the trigger as a fallback. |
| R2-07 | The downgrade drops `citext` unconditionally, although the upgrade created it with `IF NOT EXISTS`. On a database where `citext` already existed (managed Postgres, a shared database), `downgrade base` removes an extension that the migration did not create, or fails if other objects use it. | Low | `migrations/versions/0001_initial_schema.py:417,445` | Document this, or drop the extension only if this migration created it. |
| R2-08 | `migrations/env.py` builds its engine without the new connect timeout. `alembic upgrade head` against an unresponsive host waits asyncpg's 60 s default, which is the problem R1-14 fixed for the app and the CLI. Also, `pg_advisory_lock` is session-level, so it breaks behind PgBouncer in transaction mode (not documented). | Low | `migrations/env.py:24-31,48` | Pass `connect_args={"timeout": settings.database.connect_timeout_seconds}`, and note the PgBouncer limitation. |
| R2-09 | The unresponsive-host test doesn't prove the timeout path. It asserts only `< 5 s`. If the CI network returns ICMP unreachable for 10.255.255.1, the test passes on a quick refusal and never exercises `connect_timeout_seconds`. | Low | `tests/integration/test_s2_6_create_admin.py:203-215` | Also assert the elapsed time is ≥ the timeout (0.5 s), or check that the error type is `TimeoutError`. |
| R2-10 | The CLI maps every `ProgrammingError` to "schema is missing; run migrations". `InsufficientPrivilegeError` and SQL errors in future changes would print misleading advice. | Low | `app/cli.py:60-66` | Match the undefined-table SQLSTATE (`42P01`) and treat other errors as generic database errors. |
| R2-11 | Record nits. F6, F9 and F10 say "Fixed" without the run that proved it, unlike F1–F5. Gate check 3 says the second 2.6-12 run "changes nothing", but that CI step checks only exit code 1 (the hash comparison exists only in 2.6-09). The 2.3-07 CI step does not assert "migrations run once"; only the log shows a single set of "Running upgrade" lines. The `transaction` docstring calls the dependency reads plus writes "one consistent transaction", which overstates READ COMMITTED. `WeakPassword` inherits the self-referential default detail "see `detail`". | Low | `docs/milestones/step-2.md:196,199,200,231`; `.github/workflows/ci.yml` 2.3-07 and 2.6-12 steps; `app/infra/database.py:41`; `app/core/security.py:22-25` | Add the run links. Assert the claims in CI (count "Running upgrade" lines; compare the hash before and after). Reword the docstring. Give `WeakPassword` its own default detail. |

**Report claims verified:**
- **CI run 45933396263:** `head_sha` 99ae3c2. All four jobs (Test, Docker Compose smoke test, Type check, Lint) succeeded. `git diff 99ae3c2 621b96c` changes only `docs/milestones/step-2.md` (one line).
- **Test job:** 288 passed, 6 skipped; all 6 skips are e2e tests waiting for `E2E_BASE_URL` / `E2E_ALLOWED_ORIGIN`, so no service test was skipped. Coverage is 98.55 %. `app/services`, `app/repositories`, `app/infra/database.py`, `app/core/security.py` and `app/core/emails.py` are fully covered (in the "34 files skipped due to complete coverage"). `app/cli.py` is at 95 %, missing only `main()` and `__main__`. The "271 tests" claim is false (R2-01).
- **Migration step in the log:** "left after downgrade: []". After the 2.3-07 echo there is exactly one "Running upgrade -> 0001" / "0001 -> 0002" pair, so the advisory lock serialised the two upgrades. 2.3-08 refused the downgrade and the database stayed at "0002 (head)". The repeated upgrade did no work.
- **Compose job:** 2.3-05 printed `admin,member,owner`. 2.3-06 printed "password authentication failed" and the password did not appear. 2.6-12 printed "Created platform admin o\*\*\*@example.com", the `argon2id` check returned `t`, and the second run printed "already exists" with exit 1.
- **Type check:** "Success: no issues found in 71 source files", with `migrations` in the mypy `files`. **Lint:** "All checks passed!" and 113 files formatted in CI. I also ran `ruff check` and `ruff format --check` locally; both pass.
- **Round 1 resolutions, each checked in code and tests:**
  - R1-01: `transaction()`, `assert session.in_transaction()` in the probe route, 2.1-10, 2.6-15, and the ARCHITECTURE §2 text.
  - R1-02: `InvalidEmail` and `WeakPassword` subclass `Unprocessable`; 2.6-15 asserts the 422 codes.
  - R1-03: keyword-only `organization_id` joined through `_visible_to`, and 2.5-07 asserts `leaked == frozenset()`.
  - R1-04: cross-check row corrected.
  - R1-05: `utc_now` and `_same_as_created_at`; 2.1-05 and 2.2-25 use a frozen clock.
  - R1-06: advisory lock in `migrations/env.py`.
  - R1-07: 2.5-12 commits and checks visibility, then cleans up.
  - R1-10: one `EMAIL_MAX_LENGTH`, imported by `app/models/user.py`.
  - R1-11: the `Any` has a reason comment.
  - R1-12: `pool_recycle` row added.
  - R1-13: header run link, failure-log order and totals line fixed.
  - R1-14: `connect_timeout_seconds` added, in `.env.example`, with a test.
  - R1-15: ids compared, and the password itself checked.
  - R1-16: `__subclasses__` discovery, and every repository declares `unscoped`.
  - R1-17: docstring corrected; carried to step 9 (ROADMAP line 269).
  - R1-08 and R1-18: carried to step 3 (ROADMAP lines 131-132).
  - R1-09: carried to step 8 (ROADMAP line 246).
- **Scenario totals:** the rows add up to 11 + 25 + 9 + 6 + 14 + 16 = 81, which matches the section log. The 9 added rows are exactly the ones marked "(added)". I read every test cited for the new and changed scenarios (2.1-01 to 11, 2.2-23 to 25, 2.3, 2.5-05/07/08/11/12, 2.6-04 and 2.6-09 to 15) and each one asserts its claim, apart from R2-09.
- **Old code:** I checked against `git show 209a9bd`: `pool_recycle=3600`, `last_login`, `refresh_tokens` with `device_info` + `user_agent` + `ip_address String(45)`, a unique `organizations.name String(100)`, `phone_number` default, `organization_id` default 1, and no `create_all`. I also found the MySQL baseline, which is missing from the table (R2-05).
- **Could not verify locally:** pytest and mypy runs (packages are not installed). I relied on the CI logs above. I did not open the JUnit artifact.

**Missing scenarios:**
- **2.1:**
  - C10: an object loaded by a dependency is read after a failed unit of work (R2-02, from round 1).
  - C10: a nested `transaction()` call is refused (R2-04).
  - C7/C9: the client disconnects (task cancelled) during the unit of work; the rollback runs and the connection goes back to the pool.
  - C9: the request path against a blackholed database host (connect timeout through `get_db`, not only the CLI).
- **2.2 C10:** `updated_at` versus `created_at` when the app clock is ahead of the database clock (R2-06).
- **2.3:**
  - C9: migration against an unresponsive host, which has no timeout (R2-08).
  - C10: downgrade on a database where `citext` already existed (R2-07).
  - C7: assert in CI that the concurrent upgrade ran the migrations exactly once.
- **2.6:**
  - C3: a password that NFKC normalisation lengthens across the 128 limit (for example ligatures such as "ﬁ"), and one it shortens below 12; only the NFD-shortening case is tested.
  - C9: a slow hash that holds a pool connection while a dependency's transaction is open (R2-03, step 3).

## Scorecard (by the independent reviewer)

| Area | Old code | After step 2 | Evidence |
| --- | --- | --- | --- |
| Folder structure & architecture | 6 | 9 | Layers match ARCHITECTURE §2/§3. Transaction ownership is now one helper (`app/infra/database.py:36`), documented and tested with a reading dependency (2.1-10, 2.6-15). Reentrancy is not guarded (R2-04). |
| API design | 5 | 9 | No new endpoints. Rule errors are problem+json 422s with stable codes (`user.email_invalid`, `user.password_weak`; 2.6-15). `PaginationParams` is bounded (2.5-09); `Page[T]` is not built yet. |
| Database schema | 5 | 9 | Named constraints, full FK indexes (2.2-20), role-scope and `updated_at` triggers verified from the catalog (2.2-24), a CI round trip, a migration lock (2.3-07) and a guarded seed downgrade (2.3-08). Held back by mixed clocks (R2-06) and the unconditional `citext` drop (R2-07). Readiness is carried to step 8. |
| Scalability & load balancing | 4 | 8 (carried to step 3) | Bounded pool with a pool timeout (2.1-11), a connect timeout, and hashing off the loop (2.6-06). Argon2 concurrency is unbounded (R1-08), and the hash runs while a request's connection is idle in a transaction (R2-03). Both belong to step 3's auth work. |
| DSA / algorithms | 4 | 9 | No N+1, shown with a query counter (2.5-10 `[2, 2]`). Stable ordering with an id tiebreak (2.5-08). An index for every query pattern. |
| Code quality & correctness | 3 | 9 | R1-01 and R1-02 are fixed with real-shape tests. Short, typed functions; the concurrent-create race maps to exactly one `Conflict` (2.6-14). The expired-object hazard is only documented (R2-02). |
| Duplication & reuse | 3 | 9 | One `EMAIL_MAX_LENGTH`, shared `_visible_to`, `_page`, check helpers and factories. The migration's copy of the permissions is justified, and 2.4-03 keeps it in step with the code. |
| Maintainability | 3 | 9 | Guards that catch drift on their own: repository discovery (2.5-11), trigger catalog (2.2-24), FK index check (2.2-20), name parity (2.3-03). A detailed failure log. Record errors remain (R2-01, R2-05, R2-11). |
| Security | 2 | 9 | Tenant-scoped `permission_keys` with an attack test (2.5-07), Argon2id RFC 9106, 32-byte hashed tokens with a CHECK, passwords only on stdin, no secrets in output (2.1-07, 2.3-06, 2.6-10, 2.6-13). IDN email handling is carried to step 3. |
| **Overall** | **4** | **9** (8.9) | Average of the nine areas. No Critical or High findings. Scalability (8) is carried to step 3 with R1-08 and R2-03; the Medium findings R2-01, R2-02, R2-04 and R2-05 should be fixed in this step or recorded as carried. |
