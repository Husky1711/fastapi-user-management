# Step 3: independent review, round 5 (verbatim)

### 5. Independent review: FAIL

Reviewer: milestone-reviewer agent (`.claude/agents/milestone-reviewer.md`), 2026-11-28, commit 08dca94

**Summary:** Every row of the round 4 resolution table holds in the code, tests and CI. The defaults are now ASVS L2 (30 min idle and 12 h absolute, re-auth on), there is a validator tying the refresh lifetime to the access lifetime, and the head run 46083386910 is green with 530 passed, 6 skipped, 1 xfailed and 98.81 % coverage. The governance problem from round 4 is therefore gone. But the new re-authentication code brings back the class of bug the security audit fixed in F8(d). `verify_current_password` checks the lockout only before Argon2 runs. The three session-ending routes then write without re-checking anything under the user lock. A burst of parallel guesses with a stolen access token therefore gets past the 5-try lockout, and the right guess answers 204: a password oracle. This also breaks the ARCHITECTURE §2 rule the step itself introduced. A second, documented consequence has a carried fix that cannot close it: an attacker can now lock the owner out of logout-all and revoke-others.

| # | Finding | Severity | Evidence | Recommended fix |
| --- | --- | --- | --- | --- |
| H1 | **Parallel guessing gets past the lockout on the re-auth routes, and the correct guess is confirmed (password oracle).** `verify_current_password` checks `is_locked(current.user)` against the row the dependency loaded at the start of the request. It then calls `end_read`, runs Argon2, and returns. `logout(everywhere=True)`, `end_session` (another device) and `end_other_sessions` throw away the returned hash. They then take `lock_user` and revoke without re-checking `can_log_in`, the verified hash or the caller's live family. Every request in a burst that passed its dependency before the 5th failure was committed gets verified: the burst waits on the hash pool and holds no connection. Wrong guesses answer 401. The right guess answers **204** even though the account is now locked. With a stolen 15-minute access token, an attacker gets hundreds to thousands of guesses per lock window instead of 5. After the lock expires they log in with the password they learned. `change_password` (`_refusal_under_lock`, 3.8-06) and login (`_complete_login`, 3.8-02/09) both re-check under the lock, so the new paths regress F8(d). The same gap allows a stale request to finish. Example: an attacker who knows the old password starts logout-all. The owner changes the password while the attacker's Argon2 runs. The attacker's logout-all still revokes the owner's new session, even though the attacker's own family was revoked meanwhile. This breaks ARCHITECTURE §2: "Anything checked before `end_read` and slow hashing (the verified password hash, a live session, the account's status and lockout) is checked again under that lock before the write". The docstring says the hash is returned "for a re-check under the user lock", but three of the four callers never do that re-check. No test covers concurrency (C7) for re-auth. | High | app/services/auth.py:364-390, :377-378, :405-414; app/services/me.py:54-62, :83-94 (contrast me.py:132-141, :144-157); docs/ARCHITECTURE.md:66-68; tests/integration/test_s3_8_races.py:323-338 (exists only for password change) | Move `_refusal_under_lock` into `services/auth` as one shared check. Inside the `transaction` of all three session-ending flows (when re-auth ran), refuse with 401 and audit `auth.reauth_refused` if any of these fails: user missing, `not can_log_in`, `password_hash != verified`, or the caller's family not live. Add a 3.8 test per route: pause `verify_password` after it verifies, lock the account with 5 wrong logins (or change the password), release, then expect 401 and the other sessions still live. |
| M1 | **An attacker can use the lockout to take away the owner's remedy, and the carried fix doesn't cover it.** Before this round, an owner whose account was locked by a token thief could still run logout-all. Now logout-all, revoke-others and ending another device are refused while the account is locked, and so are login and password change. A thief holding a refresh token makes 5 wrong re-auths, refreshes every <30 min and re-locks every 15 min. The owner then cannot end the thief's session for up to the 12 h absolute limit. ADR-0011 says the default limits "keep their access short (… a refresh token 30 minutes idle)". That understates it: a thief who refreshes stays in for 12 h. The ROADMAP step 4 item lists limits only for `/me/password` and `/auth/refresh`, and proposes "per-IP/per-email limits before the counter". 5 tries per 15 min never trips a per-IP limit, and the three new password-checking routes are not named. | Medium | docs/adr/0011-asvs-level-2-session-defaults.md:38-44; docs/ROADMAP.md:169; app/services/auth.py:382-385 | Prefer a session-scoped consequence: N failed re-auths end the *calling* session, which kills the thief, instead of (or before) counting toward the account lock. Otherwise reword the step 4 item to name logout-all, revoke-others and `…/revoke`, and the mechanism that actually stops a 5-per-15-min attack. Correct the ADR consequence. |
| L1 | A successful re-auth on the session-ending routes doesn't reset `failed_login_count`, while login (`_mark_login`) and password change (`_replace_password`) do. After 4 thief guesses and the owner's successful logout-all, one more wrong guess locks the account. | Low | app/services/auth.py:386-390 vs :176, me.py:164 | Reset the counter under the lock once the re-check (H1) passes. |
| L2 | `ReauthIn.current_password` has no `min_length`. An empty string `""` is verified and counted as a failed attempt instead of returning 422 `auth.current_password_required`. The C2 cases for the new body are not tested: extra field, `null`, `""`, over 1024 characters. | Low | app/schemas/auth.py:45-54; tests/integration/test_s3_6_me.py:325-355 | Treat `""` as missing (`min_length=1`, or map it to `CurrentPasswordRequired`). Add 3.6-17 C2 variants. |
| L3 | The locked-account refusal on the session-ending routes is untested, although ADR-0011 lists it as a consequence ("a lock also blocks ending other sessions"). The branch is covered only through password change (3.8-03). | Low | tests (no `auth.reauth_refused` anywhere); ADR-0011:38-41 | Add a 3.6-17 variant: account locked, right password, expect 401 and `auth.reauth_refused` audited. |
| L4 | The report records point at the wrong run. The "Latest CI run" link and the 3.6-18 evidence point to 46083134460. In that run 3.6-18 had no revoke-others case, and `me.py` branch 83->87 was uncovered (99 %). The head run 46083386910, where 3.6-18 has four calls and `me.py` is at 100 %, is not cited. | Low | docs/milestones/step-3.md:4, :19; job 140786497114 coverage (`me.py 99% 83->87`) vs job 140787301576 | Cite 46083386910 as the latest run and as the evidence for 3.6-18. |
| L5 | `expires_in` is always `JWT__ACCESS_TTL_SECONDS`, even when the family's absolute end comes sooner. Near 12 h, a client is told 900 s but gets 401 earlier. This is not a security problem: the family check enforces the limit. | Low | app/services/auth.py:280-285 | Cap `access_expires_in` (and the token's `exp`) at `family_started_at + session_max_age`. |

**Report claims verified:**

- **CI.**
  - Head run 46083386910 (08dca94): Lint, Type check, Test and Compose all succeeded. Test job 140787301576 reports `530 passed, 6 skipped, 1 xfailed`, total coverage 98.81 %. `auth.py` is at 99 % (only branch 310->312); `me.py` and `deps.py` are not listed, so 100 %. The only XFAIL is 3.4-24 with the step 6 reason.
  - Run 46083134460 (342e78f) is green with the same counts and 98.76 %. `me.py` 83->87 (revoke-others with re-auth off) is uncovered there; the head commit's 3.6-18 change closes it.
  - Compose: the 3.8-10/3.6-17 step reflects the new journey (422 without the password, 204 with it, no active row left, then 5 guesses and a refused right password).
- **Totals.**
  - Table ids: 14+11+14+24+19+18+9+12 = 121, with no duplicate ids.
  - Added: 1+7+5+4+9+3+3 = 32, and 89 + 32 = 121.
  - 120 passing + 1 strict xfail matches CI.
  - "12 fixed (F1–F11, F13), 1 expected red (F12)" is correct.
- **Ids vs test names.** Every id marked "test" has a `test_s3_<sec>_<nn>_` function. The ids without one are the C12 rows (1-14, 2-09, 3-13, 4-18, 5-14, 6-13, 7-08, 8-11), the CI/Compose ids (2-10, 4-17, 5-13, 6-12, 8-10) and 2-08 (step 2 tests).
- **Failure log.** The branch has 16 failed or cancelled runs, all cited in F1–F13. None is newer than 46080669546.
- **Round 4 rows.**
  - H1: config.py defaults PT30M/PT12H/`reauth_to_end_sessions=True`; ADR-0011 supersedes 0010 (status updated); route changed to `POST …/revoke`. Tested by 3.6-17 (three variants), 3.6-18, 3.5-17, and the Compose run.
  - M1: `.env.example` and config comment say "both".
  - M2: `_refresh_outlives_access`; 3.1-12 900/901/3600 cases.
  - L1: V3.3.4, V2.4.1/2.4.2, V3.2.3 and V3.5.1 rows present.
  - L2: `_counted_length` excludes Cf; 2.6-04 has ZWSP, soft-hyphen and mixed cases.
  - L3: 3.2-11 asserts one warning, the error type only, and that the secret is absent.
  - L4: line 22.
  - L5: 3.5-17 checks 12 h − 1 s → 200, 12 h → 401, access at 12 h → 401, 30 min − 1 s → 200, 30 min → 401.
  - L6: 3.5-18 breaks the CHECK at flush.
- **Rounds 1–3 spot check.** Lock order is unchanged: every new path takes `lock_user` before touching sessions. `no_store`, `is_unique_violation`, the `to_thread` start and the strict xfail are all intact.
- **ASVS table vs 4.0.3.** V3.3.2 (L2 "12 hours or 30 minutes of inactivity", both enforced) and V3.3.4 (re-entered credentials) now pass by default. V2.1.1 matches "after multiple spaces are combined". Carried items have ROADMAP lines: V2.1.7 and V2.4.5 to step 9 (:276-277), V2.2.1 to step 4 (:169-170), V2.2.3 and V2.5 to step 6 (:212, :216). V3.3.4's re-auth can be defeated per H1, so the "Pass (defaults)" rows are true only for sequential requests.
- **Cross-check table.** Covers every route in the old `routes/login.py` (15 routes).
- **Lint.** `ruff check` and `ruff format --check` are clean locally.
- **Could not verify.** I did not run tests locally (CI logs only). The security-audit output is outside the repository.

**Missing scenarios:**

- 3.6/3.8 C7: re-auth verified, then the account is locked, disabled, has its password changed or its caller session revoked before the write (logout-all, revoke-others, end another device). A parallel burst of guesses with one correct guess (H1).
- 3.6 C6: a locked account re-authenticating on a session-ending route (L3). Repeated thief lockouts blocking the owner's remedy (M1, to be pinned or fixed).
- 3.6 C2/C3: `ReauthIn` with an extra field, `null`, `""`, or a value over 1024 characters (L2).
- 3.6 C10: the failure counter after a successful re-auth (L1).
- 3.5 C3: `expires_in` for a session refreshed within 15 minutes of its 12 h end (L5).

## Scorecard (by the independent reviewer)

| Area | Old code | After step 3 | Evidence |
| --- | --- | --- | --- |
| Folder structure & architecture | 6 | 9 | Queries only in repositories (users.py, sessions.py). One service call per route, including the new `…/revoke` (api/v1/me.py:35-58). Shared re-auth lives in `services/auth`. |
| API design | 5 | 9 | Body-less `DELETE` replaced by `POST …/revoke` (RFC 9110 reason, ADR-0011). Stable `auth.current_password_required`. no-store and problem+json throughout. Minor: `expires_in` not capped (L5). |
| Database schema | 5 | 9 | Migration 0003 CHECKs, partial unique active index, tie-safe backfill and downgrade (CI 3.2-01/01b). A real CHECK failure at flush rolls back (3.5-18). |
| Scalability & load balancing | 4 | 9 | Bounded Argon2 pool and `end_read` before hashing in the new re-auth too (auth.py:386). Per-user `FOR NO KEY UPDATE`. Clock-skew safe (3.5-19). |
| DSA / algorithms | 4 | 9 | Atomic lockout UPDATE (users.py:71-101). Bulk revocations. Deadlock-free lock order (3.8-01 with four re-auth variants, 3.8-12). |
| Code quality & correctness | 3 | 8 | The re-check under the lock is missing on three new write paths, and the docstring promises it (H1, auth.py:377-378). Successful re-auth doesn't reset the counter (L1). |
| Duplication & reuse | 3 | 9 | `verify_current_password` replaced the copy in `change_password` (me.py:119-128). One `lock_user`, `transaction` and `NO_STORE_HEADERS`. `_refusal_under_lock` should be shared (H1). |
| Maintainability | 3 | 9 | 121 ids, 530/6/1 and F1–F13 all match CI. ADR-0011 is clear and supersedes 0010 properly. Minor run-link drift (L4). |
| Security | 2 | 7 | Strong attack coverage (alg none, reuse, lockout races, enumeration, padding, L2 limits). But parallel guessing on the new re-auth routes gets past the lockout and acts as an oracle (H1), and the lockout can block the owner's remedy with only a weak carry (M1). |
| **Overall** | **4** | **8.7** | Average of the nine areas (78 / 9). FAIL until H1 is fixed and tested. |
