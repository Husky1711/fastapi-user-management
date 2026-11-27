# Step 3: independent review, round 3 (verbatim)

### 5. Independent review: FAIL

Reviewer: milestone-reviewer agent (`.claude/agents/milestone-reviewer.md`), 2026-11-28, commit 5270ef5

**Summary:** I checked every row of both resolution tables (round 1 and round 2) against the code, the tests and CI, and they all hold. The code is in good shape: the lock order is consistent, the re-checks under the lock are real, the no-store dependency exists, the quoted-value redaction works, constraint matching is exact, and CI is green at 12dd5dc and at the docs-only head 5270ef5. The step still fails for the same reason as round 2: the ASVS level 2 table claims "Pass" for items the code does not meet. V3.3.2 (re-authentication after 12 hours, or after 30 minutes idle, at L2) cannot be met even by configuration, because the shortest settings allowed are 1-day refresh and 1-day max age. V2.1.1 (at least 12 characters *after multiple spaces are combined*) is not enforced: `"a" + 11 spaces` passes the password rules. The closing sentence "the exit criterion is met for every item this step owns" is therefore false again.

| # | Finding | Severity | Evidence | Recommended fix |
| --- | --- | --- | --- | --- |
| H1 | **False ASVS claim: V3.3.2 "Pass" at level 2.** ASVS 4.0.3 V3.3.2 at L2 requires re-authentication after 12 hours, or after 30 minutes of inactivity. The defaults are 14 days idle (refresh TTL) and 30 days absolute. The settings can't go below 1 day for either (`ge=1` on whole days), so no configuration complies. V3.3.4 is also marked "Pass", but at L2 it requires users to log out other sessions "having re-entered login credentials". `DELETE /me/sessions/{id}` and `POST /me/sessions/revoke-others` need only the access token. | High | docs/milestones/step-3.md:376, :378, :383-384; app/core/config.py:91, :93; app/services/me.py:42-84 | Either support the L2 limits (an idle timeout and a max age set in minutes or hours, with tests at the boundaries), or mark V3.3.2 as L1-only/deviation, with a reason and a named ROADMAP step. For V3.3.4, require the current password for revoke-others/end-session, or record a reasoned deviation. Then correct the closing sentence. |
| H2 | **False ASVS claim and weak-password gap: V2.1.1 "Pass".** ASVS says 12 characters "after multiple spaces are combined". `check_password_rules` refuses only passwords that are entirely spaces. `"a"` followed by 11 spaces (2 characters once the spaces are combined) is accepted at signup and at password change. No test covers padding. | High | app/core/security.py:57-71; tests/unit/test_s2_6_security.py:86-98 (only the all-spaces case); docs/milestones/step-3.md:356 | Count length after collapsing runs of whitespace (and strip ends for the length check only). Add C3 cases for 3.4-03 and 3.6-08 (`"a"+" "*11`, `"ab"+" "*10+"c"`). |
| M1 | The no-store claim is broader than what was built. The report, the ASVS V8.2.1 row and the README say "every `/api/v1` answer" carries `Cache-Control: no-store`. The `no_store` dependency only sets headers on the dependency `Response`, which error responses built by the exception handlers (401, 404, 422, 500) never receive. 3.4-22 checks only successful answers (`assert answer.is_success`). Error bodies hold no secrets, so the risk is low, but the claim is not true as written. | Medium | app/core/deps.py:74-78; app/api/v1/__init__.py:19-21; tests/integration/test_s3_4_signup_login.py:529-532; step-3.md:140, :369; README.md "Notes for API clients" | Reword to "every successful answer", or add the headers in `problem_response` too, and test a 401 and a 422. |
| L1 | Stale carried item. Redaction of prefixed keys (`new_password=`) is said to be carried to step 8, but round-2 M2 already implemented and tested it (3.7-05 case `new_password='a;b,c}d&e'`). | Low | step-3.md:410, :428; docs/ROADMAP.md:255; app/core/redaction.py:13-19 | Drop the prefixed-key part from the step 8 ROADMAP item and from the report's carry notes. |
| L2 | Totals double-count F12. The sentence says "Failures found and fixed during the step: 13 (F1–F13), plus one expected red run (F12)". F12 is one of the 13 rows, so the true figure is 12 fixed plus 1 expected. | Low | step-3.md:24, :244 | Say "12 fixed (F1–F11, F13) and 1 expected red run (F12)". |
| L3 | The strict xfail on 3.4-24 has no `raises=`, so any error inside the test also counts as the expected failure (for example a 500 at signup or an assertion in `_registered`). | Low | tests/integration/test_s3_4_signup_login.py:545-557 | `xfail(strict=True, raises=AssertionError)`, and assert the current behaviour (login 200) in a companion test. |
| L4 | The CHECK `family_started_at <= created_at` compares the first login's clock with the clock of whichever instance does the refresh (`created_at` comes from the app clock at flush). Behind a load balancer, a refresh issued within the clock skew of a login on another node violates it and returns a 500. Rare, but it ties data integrity to wall clocks across nodes. | Low | migrations/versions/0003_auth_sessions.py (ck_sessions_family_started_first); app/services/auth.py:256-271; app/models/base.py:84-88 | Write `created_at=now` explicitly in `_add_refresh_token`, or allow `family_started_at <= created_at + leeway`. |
| L5 | `.env.example` adds `JWT__ISSUER` and `JWT__AUDIENCE` with no comment, against the Definition of Done ("safe default and a comment"). | Low | .env.example:68-69 | Add one-line comments. |
| L6 | The hidden OpenAPI path is a hard-coded string that repeats the router prefix and route path. If either changes, the path silently stops being hidden; only 3.4-23 would catch it. | Low | app/main.py:136-139 | Derive the path from the route (`url_path_for`/route name), or mark the route with `include_in_schema` before it is included. |
| L7 | `_end_after_failure` catches every `Exception` from the commit and falls back to rollback without logging. The original error is re-raised, but a failing commit after a failure leaves no trace. | Low | app/infra/database.py:73-79 | Log at warning level (redacted) before the rollback. |
| L8 | The cross-check table has no row for the old `GET /auth/sessions` list (`list[SessionInfo]`) or the old `session_info` in token responses. | Low | `git show 209a9bd:routes/login.py` lines 455, and `schemas/login.py` `TokenResponse.session_info`; step-3.md:273-295 | Add two rows (replaced by `GET /me/sessions`; dropped). |

**Report claims verified:**
- **CI.**
  - Run 46080870382 (12dd5dc): Lint, Type check, Test and Compose all succeeded.
  - Test job 140779285696: `507 passed, 6 skipped, 1 xfailed`. The XFAIL line is exactly `test_s3_4_24_...` with the step 6 reason. Total coverage is 98.67%; auth.py 99% (only branch 302->304), and me.py and deps.py are absent from the `skip_covered` list, so 100%.
  - Head run 46081147312 (5270ef5, docs-only: README, ARCHITECTURE, ROADMAP, milestones README, step-3.md; checked with `git diff --stat 12dd5dc 5270ef5`) is green with the same 507/6/1 result.
  - Both Compose `api=` journey steps (3.3-09/3.4-17/3.5-13/3.6-12 and 3.8-10) ran inside the successful Compose job 140779285634.
- **Totals.**
  - Tables: 14+10+14+24+16+16+9+12 = 115 ids.
  - Plan: 89 planned + 17 added (round 1 list) + 9 added (round 2 list: 3.3-14, 3.4-22..24, 3.5-16, 3.6-15, 3.6-16, 3.7-09, 3.8-12) = 115.
  - 114 passing + 1 strict xfail matches CI.
- **Ids vs test names.** Every id with "test" evidence has a `test_s3_<sec>_<nn>_` function. The ids without one are the C12 regression rows, the CI/Compose ids (3.2-10 step 3.2-01b, 3.4-17, 3.5-13, 3.6-12, 3.8-10) and 3.2-08 (step 2 parity tests). 3.1-12, 3.2-04 and 3.4-09 have two functions each; 3.4-03 has three.
- **Failure log against red runs.** All 16 failed or cancelled runs on the branch map to F1–F13: 46043074202→F12; 46043542631/46044092198→F1; 46045405514/46045889238→F2; 46047067623→F3; 46048430388→F4; 46049028389→F5; 46050943060→F6; 46052147559→F7; 46055289113→F8/F10; 46055530031→F10; 46055991972→F9; 46077451738/46078967397→F11; 46080669546→F13 (Test job 140778637797 failed, the other jobs green).
- **Round 1 rows.** I re-checked H3, L1, L2, L6, L7 and L10 in the code, and they still hold (users.py:37-69, auth.py:346-349, me.py:27-28, schemas/me.py `SessionOut.of`, security.py `start_password_hashing`).
- **Round 2 rows, all verified in code and tests.**
  - H1: V2.4.5 row is present, ROADMAP step 9 has the item, and V2.2.2 has its own row.
  - M1: `no_store` exists, but see finding M1.
  - M2: regex at redaction.py:13-19 plus the 3.7-05 cases.
  - M3: ROADMAP steps 4, 6 and 7 have the items.
  - L1: comment at sessions.py:113.
  - L2: `asyncio.to_thread` at main.py:51 and cli.py:71.
  - L3: deps.py:62-71 and 3.3-14.
  - L4: F12 row.
  - L5: 3.5-16 patches `revoke_family`/`revoke_all` after authentication; 3.6-15 checks that the dirty hash is discarded by the failure path.
  - L6: database.py:85-91 uses `sqlstate`/`constraint_name`, with unit cases and a real CHECK violation in `test_s3_4_03_any_other_integrity_error_at_signup_is_raised`.
  - L7: docs say `AUTH__SIGNUP_ENABLED`; 3.4-23 passes.
  - L8: 3.8-09 asserts `actor_user_id` `[None]` or `[]`.
  - L9: README.
  - L10: `is_secret_field` plus 3.7-09.
  - L11: milestones README "Accepted exceptions".
  - L12: ROADMAP step 7.
- **Tests read.** I read the bodies of 3.3-14, 3.4-22, 3.4-23, 3.4-24, 3.5-15, 3.5-16, 3.6-14, 3.6-15, 3.6-16, 3.7-03, 3.7-05, 3.7-06, 3.7-09, 3.8-09 and 3.8-12. They assert what the rows claim, except the "every answer" wording of 3.4-22 (M1).
- **Carried items in ROADMAP.** Present:
  - step 4: rate limits, plus the owner-lockout and signup-probe items;
  - step 6: V2.2.3 and closing the probe;
  - step 7: 3.8-09 re-test and unknown-email audit;
  - step 8: `hide_parameters`;
  - step 9: V2.1.7 and V2.4.5.

  The step 8 redaction item is stale (L1).
- **Lint.** `ruff check app tests` is clean locally.
- **Could not verify.** I could not run `check_password_rules` locally because the sandbox venv lacks PyJWT, so H2 rests on reading security.py:57-71: the padded password has length 12, `.strip()` is non-empty, and it has no Cc characters, so it is accepted. I also could not see the security-audit run itself (its output is kept outside the repository) or the JUnit artifact.

**Missing scenarios:**
- 3.4 C3 / 3.6 C3: passwords padded with spaces to reach 12 characters (`"a"+" "*11`); runs of internal spaces (H2).
- 3.5 / 3.6 C3: idle and absolute session limits at L2 values (H1); none can be configured today.
- 3.6 C4 / C6: ending other sessions without re-entering credentials (V3.3.4): either a test for re-auth or a recorded deviation.
- 3.3 / 3.4 C6: `Cache-Control: no-store` on error answers (401 from login, 422) (M1).
- 3.5 C7: a refresh racing a login under `limit_sessions` (3.8-12 covers `replace_all` only).
- 3.5 C9 / C10: a failure after a flushed write during rotation (for example the new session insert failing at commit), proving the old row's `rotated` mark is rolled back too.
- 3.5 C7 (deployment): refresh on an instance whose clock is behind the login instance (L4).

## Scorecard (by the independent reviewer)

| Area | Old code | After step 3 | Evidence |
| --- | --- | --- | --- |
| Folder structure & architecture | 6 | 9 | Queries only in repositories (users.py:37-101, sessions.py); each route calls one service (api/v1/auth.py, me.py); the one core→services link is documented (ARCHITECTURE §2). |
| API design | 5 | 9 | `response_model`, problem+json codes, enumeration-safe 202 signup, `Page[T]`, no-store on successes, disabled signup hidden (3.4-23). No-store is missing on errors (M1); rate-limit headers come in step 4. |
| Database schema | 5 | 9 | Migration 0003: reason CHECKs, partial unique active-row index, tie-safe backfill (CI 3.2-01/3.2-01b) and a downgrade. The cross-node clock CHECK is a Low (L4). |
| Scalability & load balancing | 4 | 9 | Bounded Argon2 pool (security.py:81-123, 3.1-08); `end_read` before hashing; per-user `FOR NO KEY UPDATE` locks only; one-query auth (3.3-11). |
| DSA / algorithms | 4 | 9 | Atomic lockout counter in one UPDATE (users.py:71-101, 3.4-10); bulk revocation UPDATEs; deadlock-free lock order (3.8-01, 3.8-12). |
| Code quality & correctness | 3 | 9 | Re-checks under the lock are complete and tested (3.8-02/04/06/07/09/12); exact constraint matching (database.py:85-91); populate_existing on locked re-reads. |
| Duplication & reuse | 3 | 9 | One `lock_user`, `can_log_in`, `count_failed_login`, `transaction`, `redact_fields` and `SessionOut.of`; shared race helpers (`Gate`, `paused_request`). |
| Maintainability | 3 | 9 | Records match CI (115 ids, 507/6/1, F1–F13 against every red run). Small drift: stale step 8 carry (L1), F12 double count (L2). |
| Security | 2 | 8 | Strong attack-case coverage (alg none, reuse, lockout under races, enumeration, isolation, redaction). Held back by H2 (space-padded passwords accepted), H1 (L2 session timeouts impossible; V3.3.4 without re-auth) and M1. |
| **Overall** | **4** | **8.9** | Average of the nine areas (80 / 9). FAIL until H1 and H2 are fixed or honestly re-scoped in the ASVS table with named ROADMAP steps. |
