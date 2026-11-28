# Step 3: independent review, round 6 (verbatim)

### 5. Independent review: FAIL

Reviewer: milestone-reviewer agent (`.claude/agents/milestone-reviewer.md`), 2026-11-28, commit e3b0ebd

**Summary:** ADR-0012 fixes the round 5 oracle. Each re-entry takes its budget slot under the user lock with an atomic `UPDATE … RETURNING` before Argon2 runs. All four write paths re-check under the lock through one shared `lock_and_recheck`. A thief can no longer use the account lockout to block the owner. I found no concurrency hole in the reservation itself, and CI is green on both the code head and the docs head (544 passed, 6 skipped, 1 xfailed, 98.85 %). The verdict is still FAIL, for three reasons:
1. A right password does not always restore the budget. On `POST /me/sessions/{id}/revoke` a 404 rolls back the reset, so the ADR's invariant breaks in a realistic double-click flow.
2. The ADR's main defence against bypass, carrying the budget over a refresh rotation, has no test.
3. Three rows of the report still describe the replaced lockout design.

| # | Finding | Severity | Evidence | Recommended fix |
| --- | --- | --- | --- | --- |
| H1 | **A right password used up budget instead of restoring it when ending another device answered 404.** Step by step:<br>• `verify_current_password` reserves an attempt and commits it (auth.py:403, :421-435).<br>• In `end_session`, `lock_and_recheck` then resets `reauth_attempts` to 0 inside the write's `transaction` (auth.py:488-491).<br>• When `revoke_family` ends nothing, `NotFound` is raised inside that same block (me.py:59-66), and the savepoint rollback undoes the reset (database.py:65-71).<br>The attempt therefore stays used even though the password was correct. This is the 3.6-16 flow: ending the same device twice, which also happens with a double click, two tabs, or a stale device list. Consequences:<br>• Two such 404s plus one typo end the owner's session.<br>• Three such 404s leave a session that still works for `GET /me` but refuses every re-entry with `auth.invalid_token` (auth.py:431). The session is not ended, and the error is misleading.<br>This contradicts ADR-0012 §2 ("A right password restores the budget") and the report's 3.8-05 claim. No test checks `reauth_attempts` after a 404 (test_s3_6_me.py:315-327 checks status codes and audit only). | High | app/services/me.py:59-66; app/services/auth.py:488-491; app/infra/database.py:65-71; docs/adr/0012…:27-28; tests/integration/test_s3_6_me.py:315-327 | Decide whether the session exists before raising, without losing the reset. Either look up the target family first (and do the reset only after it succeeds), or turn `ended == 0` into a refusal raised after the commit, as the other refusals are. Extend 3.6-16 to assert `reauth_attempts == 0` after the 404. |
| H2 | **The budget surviving a refresh rotation (the obvious bypass) has no test.** `_rotate` passes `reauth_attempts=row.reauth_attempts` (auth.py:357-366), and ADR-0012 lists this as a consequence (:43-44). No test refreshes between wrong guesses. 3.8-03 refreshes only after the session has ended (test_s3_8_races.py:254), and 3.8-05 and 3.8-06 never refresh. If that keyword argument were deleted, every test would still pass, and a thief holding the refresh token would get unlimited guesses at 3 per rotation. CLAUDE.md: "Any change to auth, sessions or permissions needs tests for the attack case." | High | app/services/auth.py:357-366; docs/adr/0012…:43-44; tests/integration/test_s3_8_races.py:241-266, :302-322 | Add a 3.8 scenario: 2 wrong guesses, refresh, 1 wrong guess, so the session ends (`revoked_reason = reauth_failed`). Also assert `reauth_attempts` on the successor row. |
| H3 | **Report rows and carry notes still describe the replaced lockout design (false claims).**<br>• Row 3.6-17 says the wrong password is "counted toward the lockout", but the test asserts `failed_login_count == 0`.<br>• Row 3.8-10 says the "stolen access token guesses 5 times and the right password is refused (account locked)", but the Compose step does 3 guesses, the session ends and the owner logs in.<br>• "Carried out of step 3" still says "a stolen access token can lock the account through wrong guesses at `/me/password`". That is no longer possible.<br>• The 3.6-17 docstring contradicts its own assertion. | High | docs/milestones/step-3.md:194, :232, :488-491; tests/integration/test_s3_6_me.py:335 vs :358; .github/workflows/ci.yml:275-285 | Rewrite the three report passages and the docstring to match ADR-0012. The step 4 carry is now only the anonymous login lockout, as ROADMAP:169 already says. |
| M1 | **The budget can be used up without ending the session.**<br>• If `_reauth_failed` fails (DB error, or the task is cancelled during Argon2 on shutdown), the reserved attempt stays used and nothing revokes the family.<br>• Once `reauth_attempts == limit`, every later reservation returns `InvalidToken` (auth.py:431) but never revokes.<br>The result is fail-closed for guessing, but a thief in that state keeps working access and refresh tokens until the 12 h end. That contradicts "using it up ends the session" (ADR-0012 §2). No C9 scenario covers it. | Medium | app/services/auth.py:403-409, :421-435, :438-473 | When the reservation finds a live session with the budget used up, revoke it (`reauth_failed`) in the same locked transaction. Add a C9 test: the DB fails in `_reauth_failed`, then the next attempt ends the session. |
| M2 | **The security audit (gate 6) covers neither the round 4 re-auth routes nor the ADR-0012 design.** The section still reads "PASS (after fixes)" for an audit run before both changes. This step's security-relevant surface changed substantially after the audit. | Medium | docs/milestones/step-3.md:453-477 (no re-run recorded); commits 342e78f and 13f1503 come after F8 | Re-run the vendored skill on the final auth code (re-auth routes, budget, `lock_and_recheck`) and record the outcome before merge. |
| L1 | The 3.8 section says "Each id is one test function", but 3.8-14 is two functions. This repeats round 1 H2. | Low | step-3.md:218-219; tests/integration/test_s3_8_races.py:515, :535 | Rename one test to 3.8-15 (and update the totals), or make the two cases parameters of one test. |
| L2 | 3.8-06 accepts two outcomes, depending on whether the right guess got one of the 3 slots, so the strong assertions (all 401, password unchanged) run only in the "usual" case. | Low | tests/integration/test_s3_8_races.py:368-373 | Make it deterministic: gate the first three verifications, then release them. Or put the right guess last and hold the reservations. |
| L3 | The 3.8-14 "disabled" test claims "before any password check" but does not assert that `verify_password` was never called. | Low | tests/integration/test_s3_8_races.py:535-555 | Spy on `verify_password` and assert it was not called. |
| L4 | Compose 3.8-10 does not prove the session ended: a refusal caused by the exhausted budget (M1) would also return `auth.invalid_token`. | Low | .github/workflows/ci.yml:276-285 | After the guesses, also check that `/auth/refresh` with the stolen refresh token returns 401, or that the database has no active row. |
| L5 | The body of ADR-0011 still says wrong re-entries are "counted toward the lockout" and "refused while the account is locked". Only its status line points to ADR-0012. | Low | docs/adr/0011…:27-28, :38-44 | Add a one-line "superseded by 0012" note next to those paragraphs. |
| L6 | The ADR's claim "stealing more sessions needs more logins" overstates the protection. Client-side token theft (for example XSS) gets a fresh 3-guess budget each time the owner logs in, and no account-wide signal ever builds up from re-entry failures. | Low | docs/adr/0012…:38-40 | State it in the ADR. Consider an account-level audit alert on repeated `auth.session_ended_after_reauth_failures` (step 7 or 8). |

**Report claims verified:**
- **CI.**
  - Run 46084765029 (822fc1c): Lint, Type check, Test and Compose all succeeded. Test job 140791640003: `544 passed, 6 skipped, 1 xfailed`, total coverage 98.85 %. `auth.py` is at 99 % (only branch 318->320 missed); `me.py`, `sessions.py` and `deps.py` are not listed, so 100 %.
  - Docs-only head e3b0ebd, run 46084911836: all four jobs succeeded with the same counts.
  - Branch red runs since round 5: 46084419736 and 46084572013, both recorded as F14 with a plausible cause (the interleaved savepoints are consistent with how `transaction()` nests). 13f1503 was green on its first run (46084208552).
- **Totals.** Section counts 14+11+14+24+19+20+9+14 = 125. Added ids: 1+7+5+4+9+3+3+4 = 36, and 89 + 36 = 125. "124 passing + 1 strict xfail" matches CI.
- **Ids vs test names.** Every "test" id has a `test_s3_<sec>_<nn>_` function. Ids without one are the C12 and CI/Compose rows. Duplicate function ids exist (1_12, 2_04, 4_03, 4_09, 8_14); only 8_14 contradicts an explicit claim (L1).
- **Round 5 rows.**
  - H1: reservation before Argon2 (auth.py:403-435, sessions.py:105-122) and `lock_and_recheck` in logout, `end_session`, `end_other_sessions` and `change_password`; tests 3.8-06, 3.8-13 and 3.8-14 exist and assert as described (with L2 and L3).
  - M1: 3.6-20 asserts a locked login together with a 204 revoke-others; ROADMAP:169 reworded.
  - L1: 3.8-05 asserts `[2]`.
  - L2: `if not password` (auth.py:400); 3.6-19 has five cases and asserts attempts `{0}`.
  - L3: `auth.reauth_refused` is asserted in 3.8-13 and 3.8-14.
  - L4: links are correct.
  - L5: `not_after` in `issue_access_token`; 3.5-17 asserts `expires_in == 1`.
- **Rounds 1–4 spot check.** Lock order is intact: every new path calls `lock_user` before touching session rows. `no_store`, `is_unique_violation` and the strict xfail are intact.
- **Migration 0003.** It adds `reauth_attempts` (NOT NULL, default 0, CHECK ≥ 0) and the `reauth_failed` reason, and its downgrade drops them. Model parity holds through the step 2 tests, which pass in CI.
- **Settings.** `.env.example` documents `AUTH__REAUTH_MAX_FAILURES` (bounds 1–10, unit-tested in 3.1-12).
- **ASVS table.** Consistent with 4.0.3 level 2 for V2.1, V2.4, V3.2, V3.3 and V3.7.1. V3.3.4 is "Pass (defaults)" and is now true under parallel requests, apart from H1 and M1, which are consistency defects rather than bypasses. The carried items (V2.1.7, V2.2.1, V2.2.3, V2.4.5, V2.5) each have a ROADMAP line. V2.3.1 and V2.10.1–3 are not listed; minor, as in earlier rounds.
- **Cross-check table.** Unchanged and complete for the 15 routes in the old `routes/login.py` at 209a9bd. The old code had no password-change route.
- **Lint.** `ruff check` and `ruff format --check` are clean locally.
- **Could not verify.**
  - Per-run presence of individual tests (for example "3.6-19/20 in run 46084208552"): the CI log isn't verbose.
  - The security-audit output, which is outside the repository.
  - I did not run the test suite locally.

**Missing scenarios:**
- 3.8 C6/C7: guesses, refresh, more guesses: the budget carries over the rotation (H2). A refresh racing a reservation (both under the user lock; untested).
- 3.6 C8/C10: ending another device twice, or an unknown id, with the right password leaves `reauth_attempts` at 0 (H1).
- 3.8 C9: the DB fails in `_reauth_failed` after a wrong guess; the next attempt finds the budget used up, and the session should end (M1).
- 3.8 C10: a session whose budget was used up without ending (by any path) is ended at the next reservation (M1).
- 3.6 C11: the owner's real flow of two typos plus a double-clicked "end device", which should not sign the owner out (H1).

## Scorecard (by the independent reviewer)

| Area | Old code | After step 3 | Evidence |
| --- | --- | --- | --- |
| Folder structure & architecture | 6 | 9 | Budget queries live only in `SessionRepository` (sessions.py:105-134); services own the transactions; ARCHITECTURE §2 and §6 updated for `lock_and_recheck` and ADR-0012. |
| API design | 5 | 9 | Stable codes, `current_password_required` for `""`/`null`/missing (3.6-19), `expires_in` capped (3.5-17). Minor: a budget used up without ending the session answers `auth.invalid_token` while the token still works (M1). |
| Database schema | 5 | 9 | 0003 adds `reauth_attempts` with a CHECK ≥ 0 and the `reauth_failed` reason; the reservation is served by the partial unique active index; downgrade complete. |
| Scalability & load balancing | 4 | 9 | No connection held during Argon2 (the reservation commits first, auth.py:406); bounded hash pool; per-user `FOR NO KEY UPDATE`. |
| DSA / algorithms | 4 | 9 | Atomic conditional `UPDATE … RETURNING` reservation bounds parallel verifications to the budget (3.8-06); bulk revocations; deadlock-free lock order (3.8-01, 3.8-12). |
| Code quality & correctness | 3 | 8 | Shared re-check is clean, but the `NotFound` rollback undoes the budget reset (H1, me.py:59-66), and a used-up budget does not always end the session (M1). |
| Duplication & reuse | 3 | 9 | One `verify_current_password` and one `lock_and_recheck` for all four re-entry writes; `_audit_outcome` shared in me.py. |
| Maintainability | 3 | 8 | Totals and failure log match CI; but report rows 3.6-17 and 3.8-10, the carry note and the ADR-0011 body describe the replaced design (H3, L5); duplicate 3.8-14 id (L1). |
| Security | 2 | 8 | Burst oracle closed and lockout no longer usable against the owner (3.8-06, 3.6-20); but the rotation carry, the main bypass defence, is untested (H2); exhaustion paths that don't end the session (M1); audit not re-run on the new design (M2). |
| **Overall** | **4** | **8.7** | Average of the nine areas (78 / 9). FAIL until H1–H3 are fixed and tested. |
