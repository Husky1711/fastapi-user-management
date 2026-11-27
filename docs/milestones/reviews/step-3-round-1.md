# Step 3: independent review, round 1 (verbatim)

### 5. Independent review: FAIL

Reviewer: milestone-reviewer agent (`.claude/agents/milestone-reviewer.md`), 2026-11-28, commit 1c09104

**Summary:** The authentication core is well built. The per-user lock order (user row first, then session rows) is applied on every path that writes sessions or credentials, and I found no cycle that could deadlock. The 3.8 race tests are real: they failed first with a genuine `DeadlockDetectedError` in run 46055289113. The step still fails, for four High findings. The report's totals are wrong. The scenario ids in section 3.8 do not match the test names. A service runs a SQL query itself, which CLAUDE.md forbids. The roadmap exit criterion (ASVS V2/V3) is never addressed. There are also Medium gaps: a re-check under the lock that no test exercises, and a status check that is missing under the lock.

**Lock-order and deadlock check (requested focus).** Every write path takes the user lock first:
- login: `_complete_login`, auth.py:154
- refresh: auth.py:299, then the session row `FOR UPDATE` at :300
- logout and logout-all: auth.py:362
- end one session and revoke-others: me.py:48 and :67
- password change: me.py:108

`count_failed_login` touches only the users row (one `UPDATE`). Every session `INSERT` (the FK check takes `FOR KEY SHARE` on users) and every audit `INSERT` with `actor_user_id` happens after the same transaction already holds the user lock. Signup only inserts a brand-new user. No path locks a session row and then waits on a user row. In READ COMMITTED, the bulk revoke runs after the lock is granted, so its new snapshot sees a successor row that a refresh just committed. Test 3.8-01 checks exactly this. I found no deadlock cycle. The residual issues are in the table below (L1, L2, L3).

| # | Finding | Severity | Evidence | Recommended fix |
| --- | --- | --- | --- | --- |
| H1 | The totals are false. The section log says **90 / 90** ("89 planned + 1 added"), but the scenario tables hold 14+10+13+19+14+13+8+10 = **101** scenarios. 3.8 (10) and 3.2-10 (1) were never added to the total. The required passed / failed / fixed totals are missing, and 3.2-10 has no "(added during build)" note. | High | docs/milestones/step-3.md:22, :86, :196-207; CLAUDE.md "Records" | Recount to 101. Add passed / failed / fixed totals. Mark 3.2-10 and all of 3.8 as added after planning. |
| H2 | The 3.8 scenario ids do not match the test names. The plan has 3.8-01 to 3.8-08, but the tests are named `test_s3_8_01` to `_05` with different meanings: `test_s3_8_02` is plan 3.8-03/04, `test_s3_8_03` is plan 3.8-05, `test_s3_8_04` is 3.8-06/07, `test_s3_8_05` is 3.8-08. Following an id from the plan to the CI report lands on the wrong test. | High | tests/integration/test_s3_8_races.py:138, 173, 203, 223, 254 vs step-3.md:198-205; CLAUDE.md "Scenario ids in test names" | Rename the tests, or renumber the plan, so each id maps to its own test. |
| H3 | A service runs a query. `authenticate` builds and executes `select(User)…exists()` inside `app/services/auth.py`, which imports `select` and `exists`. CLAUDE.md: "Repositories hold queries." | High | app/services/auth.py:8, 71-83 | Move it to a repository method, e.g. `UserRepository.get_active_with_live_session(user_id, family_id, now)`. Keep the single query (test 3.3-11). |
| H4 | The roadmap exit criterion "ASVS V2/V3 items for these flows pass" is neither evidenced nor carried forward. The report never mentions ASVS. Known gaps: V2.1.7 (breached-password check) is absent, and V2.2.1 (anti-automation) is not built until step 4. | High | docs/ROADMAP.md:155; step-3.md has no ASVS mapping | Add a V2/V3 item table for these flows (pass, or carried forward to a named step with a reason). Do not tick the exit criterion until then. |
| M1 | The lockout re-check *after* hashing in a password change is never run by any test. me.py:124 is uncovered in run 46056180851 (coverage line `me.py … 98% 124`). The audit table claims "Refused while locked, before and after hashing" and cites 3.8-05, which only tests the *before* check (me.py:98). | Medium | step-3.md:290; coverage in job 140699114005; me.py:123-124 | Add a race test: pause a password change after `hash_password`, lock the account with failed logins, release, then expect 401 with the password unchanged. |
| M2 | `_refusal_under_lock` re-checks deletion, the lock, the hash and the live session, but not `status`. A user disabled between `authenticate` and the write can still change the password. ARCHITECTURE §2 says what was checked earlier "is checked again under that lock". | Medium | app/services/me.py:123; ARCHITECTURE.md:66-67 | Also refuse when `user.status != ACTIVE`. Add a test. |
| M3 | The failure log is incomplete. Run 46055530031 (fix commit ad0cb93) failed **Type check**, fixed by a63cc96 "patch hashing by import path (mypy)". Run 46055289113 also failed Type check, not only tests. Neither appears in F8. | Medium | `gh api …/runs/46055530031/jobs` (Type check: failure); step-3.md:221 | Add a failure-log row with cause and fix. |
| M4 | The cross-check table is incomplete for the step's scope. Missing old items: `GET /auth/sessions/info`, the server-side auto-refresh service and middleware, `GET /users/{user_id}`, `/auth/health` in the auth router, and the per-route rate-limit dependency on login and refresh. | Medium | `git show 209a9bd:routes/login.py` (lines 302, 528, 598, 519); `services/auto_refresh_service.py`, `utils/auto_refresh_middleware.py`, `utils/rate_limit_dependency.py` | Add a row for each, with a decision and a reason (dropped, moved to step 4 or 7, …). |
| M5 | None of the new endpoints has a rate-limit policy, which the Definition of Done requires. A stolen access token can also lock the owner out of login through wrong guesses at `/me/password` (me.py:101-103). The step-4 deferral is acknowledged but not marked as a DoD exception. | Medium (carry to step 4) | app/api/v1/auth.py:3; CLAUDE.md DoD; step-3.md:294 | Record it explicitly as carried to step 4: login, refresh, signup and password limits, plus lockout-DoS protection. |
| L1 | Two ways to take the per-user lock: `auth.lock_user` (`include_deleted=True`) and a direct `UserRepository.get_for_update` (`include_deleted=False`) in login. | Low | auth.py:154, 345-347; ARCHITECTURE.md:63 | Use one entry point; let the caller check `deleted_at`. |
| L2 | The lock is `FOR UPDATE`, which also blocks other transactions' FK inserts that reference the user (sessions, audit, and future memberships). `FOR NO KEY UPDATE` is enough, since no flow changes `users.id`. | Low | app/repositories/users.py:45 | `with_for_update(key_share=True)`. |
| L3 | A user hard-deleted between the read and the write leads to 500s: `record_failed_login` calls `.one()` on a zero-row `UPDATE`, and `auth.login_refused` inserts an audit row whose `actor_user_id` violates the FK. There is no hard-delete path yet. | Low (carry to step 7) | users.py:75; auth.py:155-156 | Handle `None`; test it once admin deletion exists. |
| L4 | `_wait_until_blocked_on_a_lock` counts *any* lock waiter in the database, not the revoking connection, so it gives false positives under parallel tests. It also polls with a 10 ms sleep, against the "no sleeping" rule (noqa'd). | Low | tests/integration/test_s3_8_races.py:116-126 | Filter by the revoking backend's PID (`pg_backend_pid()` via the request), or by `query LIKE '%FROM users%FOR UPDATE%'`. |
| L5 | 3.8-09 is tagged C11 (real user flow) but re-runs integration tests. It is not a real-stack journey. | Low | step-3.md:206 | Retag it as C12, or add a Compose step. |
| L6 | Wrong guesses at the current password during a password change are audited as `auth.login_failed`, and the "refused while locked" pre-check is not audited at all. | Low | me.py:98-103; auth.py:199-205 | Pass the action name through; audit the refusal. |
| L7 | The session list maps fields and computes `current` in the router by hand instead of using an `*Out` schema with `from_attributes`. | Low | app/api/v1/me.py:30-42 | Move it to a schema constructor or the service. |
| L8 | `core/deps.py` imports `app.services.auth` while services import `app.core.*`: a package-level cycle between core and services. | Low | app/core/deps.py:15 | Accept it with a note in ARCHITECTURE, or move `deps` under `api/`. |
| L9 | The redaction regex `\b(Bearer\|Basic)\s+…` rewrites ordinary prose such as "Basic information" to "Basic ***". | Low | app/core/redaction.py (`_AUTH_SCHEME`) | Anchor it to `Authorization:` or require token-like length. |
| L10 | The first unknown-email login does an extra Argon2 hash to build `_dummy_hash`, a one-off timing difference. | Low | app/core/security.py `verify_dummy_password` | Build the dummy hash at lifespan start. |

**Report claims verified:**
- CI run 46056180851: every job green at 5dddb23. Test job 140699114005 shows 465 passed and 6 skipped (all 6 are step-1 e2e tests that need `E2E_BASE_URL`), total coverage 98.54%, auth.py 99%, me.py 98%.
- Head 1c09104 differs from 5dddb23 only in docs (ARCHITECTURE, ROADMAP, step-3.md). Its own run, 46056476341, is green.
- "Failing first" for 3.8: run 46055289113 Test job shows 3.8-01 failing, with `DeadlockDetectedError` in `/me/password` → `revoke_all` (matches F8b). Run 46055748820 is green.
- F9: run 46055991972 failed at f292c6f; CI step 3.2-01b exists in ci.yml; the tie-break `(created_at, id)` is in the migration.
- I read every test cited in sections 3.3, 3.4, 3.5, 3.6 and 3.8 that bears on races, lockout and isolation. Each asserts what is claimed, except the "after hashing" half of the lockout claim (M1).
- Lock order: verified by reading every write path (see "Lock-order and deadlock check" above).
- Ruff is clean locally. I did not run mypy locally; CI's Type check is green.
- Not verifiable: the per-section run ids for sections 3.1 to 3.7 (spot-checked only); the security-audit run itself (its output is kept outside the repository by design).

**Missing scenarios:**
- 3.8 C7: refresh in flight against `DELETE /me/sessions/{id}` and against `revoke-others` (same lock, untested); account locked while a password change is hashing (M1); user disabled while a password change is hashing (M2); two concurrent logins under `limit_sessions` and `replace_all` (does the session count hold?).
- 3.5 C9: database down during refresh and logout. The N/A "same service path as 3.4-16" is not true: refresh is a different path.
- 3.6 C1/C4: `DELETE /me/sessions/{current sid}`, i.e. ending your own current session (the access token must stop working).
- 3.4 C3: login with a password over the 128-character rule but under the 1024 input cap (it is still hashed). Signup with `full_name` at 200 and 201 characters.
- 3.4/3.5 C10: user hard-deleted between the read and the lock (L3; carry to step 7).
- 3.8 C11: no real-stack journey for any of the race fixes.

## Scorecard (by the independent reviewer)

| Area | Old code | After step 3 | Evidence |
| --- | --- | --- | --- |
| Folder structure & architecture | 6 | 8 | Layers are otherwise clean, but a service executes SQL (H3, auth.py:71-83) and core and services import each other (L8). |
| API design | 5 | 9 | Every route has a `response_model`, problem+json codes, 202 enumeration-safe signup and `Page[T]` (api/v1/auth.py, me.py). Rate-limit headers are step 4. |
| Database schema | 5 | 9 | Migration 0003: CHECKs for reason and family start, a partial unique index on active rows per family, a tie-safe backfill, and up/down tested in CI step 3.2-01/01b. |
| Scalability & load balancing | 4 | 9 | Bounded Argon2 pool (security.py, test 3.1-08); `end_read` before hashing; per-user serialization only. The 8 carried from step 2 is resolved. |
| DSA / algorithms | 4 | 9 | One-query authentication (3.3-11), bulk revocation `UPDATE`s, an atomic lockout counter (3.4-10), deadlock-free lock order (3.8-01). |
| Code quality & correctness | 3 | 8 | Small, well-named functions, but the status re-check under the lock is missing (M2), a branch is untested (M1), and the hard-delete edge returns 500 (L3). |
| Duplication & reuse | 3 | 9 | Shared `transaction`, `is_unique_violation`, `count_failed_login` and `redact_fields`. Minor: two lock entry points (L1). |
| Maintainability | 3 | 8 | Strong CI (migration and Compose journeys), but the report totals are false (H1), the ids are mismatched (H2) and the failure log has gaps (M3). |
| Security | 2 | 8 | Thorough attack-case tests (alg none, reuse, lockout, races, enumeration), but the ASVS exit criterion is unaddressed (H4), the status re-check is missing (M2), and there is no rate limiting yet (M5, carry to step 4). |
| **Overall** | **4** | **8.6** | Average of the nine areas (77 / 9). FAIL until H1 to H4 are fixed. |
