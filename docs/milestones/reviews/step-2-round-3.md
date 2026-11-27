# Step 2: independent review, round 3 (verbatim)

### 5. Independent review: PASS

Reviewer: milestone-reviewer agent (`.claude/agents/milestone-reviewer.md`), 2026-11-27, commit 7de96e7

**Summary:** All eleven round 2 findings are fixed as the round 2 resolution table says, or carried to a named step: R2-03 is in ROADMAP step 3, line 131. CI run 45934502590 is green on 79f2cba, and 7de96e7 changes only the report's run link. The savepoint-based `transaction()` is a real improvement. It is tested with real commits over HTTP (2.1-01 to 2.1-03, 2.1-10) and for readability after a failure (2.1-12, 2.6-09). I found no Critical or High issue. What remains is test depth around the round 2 fixes. The new non-42P01 CLI branch has no test, which lowers `app/cli.py` coverage to 88 %. The nested-call and cancellation tests prove less than their scenario rows claim. Two round 2 missing scenarios were dropped without saying so.

| # | Finding | Severity | Evidence | Recommended fix |
| --- | --- | --- | --- | --- |
| R3-01 | The R2-10 fix has no test. The new branch that turns a non-42P01 `ProgrammingError` into the generic message is never run. This is the behaviour R2-10 asked for (no "run migrations" advice for, say, insufficient privilege). `_sqlstate`'s `return None` is not run either. `app/cli.py` coverage fell from 95 % (round 2) to 88 %. The report cites 2.6-13 as evidence, but 2.6-13 only tests the 42P01 path (`test_s2_6_13_database_without_the_schema_says_to_run_migrations`). | Medium | `app/cli.py:37,71-73`; job 140294495883 coverage: `app/cli.py 88% 35->33, 37, 72-73, 106, 110`; `docs/milestones/step-2.md:312` | Add a test that causes a different `ProgrammingError`, for example a role without `SELECT` on `users` (42501), or a unit test of `_sqlstate` and the branch with a stub error. Assert the generic message and that "run migrations" is absent. |
| R3-02 | The generic database-error message is now printed in two `except` branches. The second copy came in with the R2-10 fix. | Low | `app/cli.py:72` and the `except (OSError, DBAPIError)` branch at lines 82-84 | Handle only the 42P01 case specially, for example in `except ProgrammingError as e if ...` style with one shared handler, or a small `_db_error(err, error)` helper. |
| R3-03 | 2.1-13 doesn't check "the outer one still commits". `db.get(User, user.id) is user` is answered from the identity map without a query. Also, in the `db` fixture a commit is only a savepoint release. | Low | `tests/integration/test_s2_1_database.py:238-247`; `tests/conftest.py:53-66`; scenario row `step-2.md:82` | Expunge and re-query, or run the test on a real-engine session and read from a second connection. |
| R3-04 | 2.1-14 tests cancellation only on the `session.begin()` branch, with a bare `AsyncSession`. The HTTP shape is not tested: a dependency has read, the `begin_nested` branch runs, then the task is cancelled. That is the path a client disconnect actually takes. The test also uses `NullPool`, so it cannot show the connection going back to the pool. The row says "The request is cancelled". | Low | `tests/integration/test_s2_1_database.py:250-269`; `app/infra/database.py:59-62`; `step-2.md:83` | Read first, then cancel inside `transaction()` (savepoint branch). Use a pooled engine and assert `engine.pool.checkedout() == 0` after close. |
| R3-05 | Two round 2 missing scenarios were neither added nor listed under "Not added, with reason". This is the same pattern as R2-02. (a) 2.2 C10: `updated_at` versus `created_at` when the app clock is ahead (R2-06 was resolved in the docs only; 2.2-24's `updated > created` still depends on one host clock). (b) 2.3 C9: migration against an unresponsive host. The R2-08 `connect_args` change in `migrations/env.py` has no test. | Low | `step-2.md:315-321`; R2 "Missing scenarios" 2.2 and 2.3; `migrations/env.py:49-54` | Add them, or list them with a reason. For (b), a CI step that runs `alembic upgrade head` against 10.255.255.1 with a 0.5 s timeout and asserts it fails quickly is enough. |
| R3-06 | ARCHITECTURE §2 says objects the dependencies loaded ("the current user") stay readable after a failed unit of work, without condition. That holds only if the failed block did not change them. A rolled-back savepoint expires the objects changed inside it, and in async code the next attribute read raises `MissingGreenlet`. Step 3 lockout (raising `failed_login_count` on the user, then raising) is exactly that case. The docstring gets it right; ARCHITECTURE overstates it. | Low | `docs/ARCHITECTURE.md:52-56`; `app/infra/database.py:47-50`; 2.1-12 only reads an unchanged object | Add "unless changed in the failed block" to ARCHITECTURE. In step 3, add a scenario that changes the current user and then fails. |
| R3-07 | In the common HTTP case (a dependency has read), every unit of work now costs two extra round trips (`SAVEPOINT`, `RELEASE`). The trade-off is reasonable, but the design decision does not record it. | Low | `app/infra/database.py:59-61`; `step-2.md:29-36` | Note the cost in the design decision. Look at it again with the step 3 load numbers. |

**Report claims verified:**
- **CI run 45934502590:** `head_sha` 79f2cba, event `pull_request`, conclusion success. All four jobs succeeded: Test 140294495883, Docker Compose 140294495661, Lint 140294495966, Type check 140294496024. `git diff 79f2cba 7de96e7` touches only `docs/milestones/step-2.md` (one line). The branch run list has no red run after 99ae3c2, so nothing is missing from the failure log. The two red runs (45932585174, 45932943098) are F9 and F10.
- **Test job:** "291 passed, 6 skipped". That is 288 from round 2 plus the three new tests 2.1-12, 2.1-13 and 2.1-14. All 6 skips are e2e tests waiting for `E2E_BASE_URL` / `E2E_ALLOWED_ORIGIN`. Total coverage is 98.08 %. `app/infra/database.py`, `app/services/admin.py` and `app/core/security.py` are among the "34 files skipped due to complete coverage". `app/cli.py` is at 88 % (R3-01).
- **Gate check 1:** no longer types counts; it cites the run (R2-01 resolved).
- **Type check:** "Success: no issues found in 71 source files". **Lint:** "All checks passed!" and "114 files already formatted". I also ran `ruff check` and `ruff format --check` locally; both pass.
- **Migration CI step:** "left after downgrade: []". The new 2.3-07 assertion `grep -c 'Running upgrade' = 2` runs, and the log shows exactly one "-> 0001" / "0001 -> 0002" pair after the 2.3-07 echo. 2.3-08 was refused, and the database stayed at "0002 (head)".
- **Compose job:** printed `admin,member,owner`, "password authentication failed", and "Created platform admin o\*\*\*@example.com". The `argon2id` check returned `t`. The second run printed "already exists"; the new `hash_of` before/after comparison sits in the step under `set -e`, and the job passed.
- **Round 2 resolutions, each checked in code:**
  - R2-02: `begin_nested` in `transaction()`. 2.1-12 reads `caller.email` after `Conflict` and checks the org is gone. 2.6-09 now reads `gone.email` after a savepoint rollback triggered by an `IntegrityError`.
  - R2-04: the `session.info` marker, `NestedUnitOfWork`, cleared in `finally`. The inner raise happens before the `try`, so it does not clear the outer marker; this is correct.
  - R2-03: comment fixed; ROADMAP line 131 names R2-03.
  - R2-05: four cross-check rows added (`step-2.md:244-247`).
  - R2-06: ARCHITECTURE §4 states the clock split.
  - R2-07: downgrade comment at `0001_initial_schema.py:445-446`.
  - R2-08: `connect_args` and a PgBouncer note in `migrations/env.py`.
  - R2-09: `0.4 <` lower bound and "(TimeoutError)" asserted.
  - R2-10: SQLSTATE check (untested, R3-01).
  - R2-11: run links on F6, F9 and F10; CI assertions; docstring reworded; `WeakPassword.default_detail`. The ligature case `"ﬁ" * 65` was added in `tests/unit/test_s2_6_security.py`.
- **Carried items:** R1-08 + R2-03 and R1-18 (ROADMAP 131-132, step 3), R1-09 (246, step 8), R1-17 (269, step 9). The 5 carried + 24 fixed = 29 review findings in the totals line match.
- **Scenario totals:** the rows add up to 14 + 25 + 9 + 6 + 14 + 16 = 84, matching the section log and "72 + 9 + 3".
- **No regressions:** 2.1-01 to 2.1-04 and 2.1-10 (real engine and pool, HTTP shape) still pass with the savepoint branch, and 2.1-01 checks the real commit from a second connection.
- **Could not verify locally:** pytest and mypy (packages not installed). I relied on the CI logs above and did not open the JUnit artifact.

**Missing scenarios:**
- **2.1:**
  - C7/C9: cancellation in the savepoint branch, with the pooled connection returned (R3-04).
  - C10: an object changed inside a failed unit of work, then read (R3-06; can be step 3).
- **2.2 C10:** `updated_at` versus `created_at` with the app clock ahead of the database (R3-05a).
- **2.3 C9:** migration against an unresponsive host, which now has a timeout but no test (R3-05b).
- **2.6:**
  - C9: a non-42P01 `ProgrammingError` in `create-admin` gives the generic message (R3-01).
  - C7: two concurrent creates through the HTTP shape, where a dependency read first so the `IntegrityError` hits the savepoint branch. 2.6-14 covers only fresh sessions (`begin()` branch).

## Scorecard (by the independent reviewer)

| Area | Old code | After step 2 | Evidence |
| --- | --- | --- | --- |
| Folder structure & architecture | 6 | 9 | Layers match ARCHITECTURE §2/§3. One unit-of-work helper, now a savepoint with a reentrancy guard (`app/infra/database.py:42-67`), documented in ARCHITECTURE §2 and tested over HTTP (2.1-01, 2.1-10, 2.6-15). ARCHITECTURE overstates what stays readable (R3-06). |
| API design | 5 | 9 | No new endpoints. Rule errors are problem+json 422s and the conflict is a 409, each with a stable code (2.6-15). `PaginationParams` is bounded (2.5-09). `Page[T]` is not built yet. |
| Database schema | 5 | 9 | Named constraints, full FK indexes (2.2-20), triggers checked from the catalog (2.2-24), a CI round trip, a lock that is now asserted to run the migrations once (2.3-07), a guarded seed downgrade (2.3-08). The clock split and the `citext` assumption are documented, not tested (R3-05a). |
| Scalability & load balancing | 4 | 8 (carried to step 3) | Bounded pool and pool timeout (2.1-11); connect timeout in the app, the CLI and now migrations. Argon2 concurrency is unbounded and the connection sits idle in a transaction while hashing (R1-08, R2-03; ROADMAP step 3, line 131). A savepoint costs two round trips per write (R3-07). |
| DSA / algorithms | 4 | 9 | No N+1, shown with a query counter (2.5-10). Stable ordering with an id tiebreak (2.5-08). An index for every query pattern. |
| Code quality & correctness | 3 | 9 | R2-02 and R2-04 are fixed in the design rather than worked around (2.1-12, 2.1-13, 2.6-09). The race maps to exactly one `Conflict` (2.6-14). The R2-10 branch is untested (R3-01), and two new tests claim more than they show (R3-03, R3-04). |
| Duplication & reuse | 3 | 9 | One `EMAIL_MAX_LENGTH`; shared `_visible_to`, `_page`, factories and check helpers. One new duplicated error message in `app/cli.py` (R3-02). |
| Maintainability | 3 | 9 | Guards that catch drift (2.5-11, 2.2-24, 2.2-20, 2.3-03). CI now asserts what the report used to claim (2.3-07 count, 2.6-12 hash). The records are consistent with CI. Two R2 missing scenarios were silently dropped (R3-05). |
| Security | 2 | 9 | Tenant-scoped `permission_keys` with an attack test (2.5-07); Argon2id with RFC 9106 parameters and NFKC length checked both ways (2.6-04/05); hashed 32-byte tokens; passwords only on stdin and never in output (2.1-07, 2.3-06, 2.6-10, 2.6-13); the CLI no longer gives misleading advice on other SQL errors. IDN emails are carried to step 3. |
| **Overall** | **4** | **9** (8.9) | Average of the nine areas. No Critical or High findings. Scalability (8) is carried to step 3 (R1-08, R2-03). R3-01 should be fixed in this step, or carried with the step 3 CLI and auth work. |
