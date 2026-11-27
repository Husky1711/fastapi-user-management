# Step 3: independent review, round 4 (verbatim)

### 5. Independent review: FAIL

Reviewer: milestone-reviewer agent (`.claude/agents/milestone-reviewer.md`), 2026-11-28, commit af8ddf9

**Summary:** Every row of the round 3 resolution table holds in the code, and the round 1 and round 2 rows have not regressed. Specifically: whitespace-collapsed password length, ISO 8601 session limits, no-store on errors, the clock-skew `created_at`, the strict `raises=AssertionError` xfail, the derived hidden path and the logged commit fallback are all present and green in CI (521 passed, 6 skipped, 1 xfailed, 98.63 %). The step still fails on governance, not code. ADR-0010 turns the round 3 ASVS gap into a permanent "Accepted" deviation: V3.3.4 is not met at L2, which is the only level that has it, and V3.3.2 ships with L1 defaults. VISION §5 defines 10/10 as "ASVS L2 V2/V3 pass", and CLAUDE.md lists changes to VISION scope as an owner decision. There is no owner approval on record. The ADR and `.env.example` also give the wrong L2 recipe ("PT30M **or** PT12H"), and no setting check stops an access token from outliving its refresh token.

| # | Finding | Severity | Evidence | Recommended fix |
| --- | --- | --- | --- | --- |
| H1 | **ADR-0010 permanently lowers the VISION quality bar without the owner.** VISION §5 (the measurable 10/10) says "OWASP ASVS L2 sections V2 (auth), V3 (sessions) … pass", and step 3's exit criterion says "ASVS V2/V3 items for these flows pass". ADR-0010 makes three choices: a deliberate, permanent V3.3.4 L2 deviation; V3.3.2 defaults at L1; and nothing carried to a later step (ROADMAP has no item for either). The project therefore can never meet VISION §5 as written. CLAUDE.md "Things to ask the owner about (don't guess)" lists "Anything that changes `docs/VISION.md` scope". The milestones README says a sub-9 area needs to be "explained and accepted by the owner". The ADR is marked "Accepted", but there is no owner sign-off: PR #5 has no comments, and VISION is not amended. A previous reviewer suggesting "record a reasoned deviation" is not owner acceptance. | High | docs/VISION.md:87; docs/ROADMAP.md:155; CLAUDE.md "Things to ask the owner about"; docs/milestones/README.md:154-155; docs/adr/0010-session-limits-and-ending-sessions.md:3, :20-31; docs/milestones/step-3.md:399, :401, :406-408; `gh api …/issues/5/comments` returns nothing | Choose one. (a) Get the owner's explicit approval, record it in the PR and the ADR, and add the exception to VISION §5 (or a pointer to the ADR). (b) Implement the opt-in the ADR already describes, `current_password` on `DELETE /me/sessions/{id}` and `revoke-others` behind a setting, and default it (and the session limits) to L2, or carry the default change to step 9 as a ROADMAP item with the owner's agreement. |
| M1 | **Wrong ASVS L2 recipe in the ADR, `.env.example` and config comment.** ASVS 4.0.3 V3.3.2 asks for re-authentication "periodically both when actively used or after an idle period". L2 therefore needs both limits: 12 h absolute and 30 min idle. The docs say "PT30M **or** PT12H". Setting only `AUTH__REFRESH_TTL=PT30M` leaves a 30-day absolute limit, which is not L2. Setting only `AUTH__SESSION_MAX_AGE=PT12H` fails validation against the 14-day default refresh TTL, so the app does not start. The step report's V3.3.2 row and 3.5-17 correctly use both values. | Medium | docs/adr/0010-…md:18-20; .env.example:83; app/core/config.py:97-98 | Say "both `AUTH__REFRESH_TTL=PT30M` and `AUTH__SESSION_MAX_AGE=PT12H`". |
| M2 | **No check ties the access-token lifetime to the refresh lifetime.** `JWT__ACCESS_TTL_SECONDS` goes up to 3600, and `AUTH__REFRESH_TTL` now goes down to 5 min. `get_authenticated` refuses an access token once its family's row expires, so with access 3600 s and refresh PT30M every session dies after 30 min even under active use. The client is told `expires_in=3600` and only refreshes at about 60 min, by which point the refresh token has also expired. Because this round lowered the minimum, a documented L2 setup combined with a longer access TTL is now an accepted configuration that logs every user out. | Medium | app/core/config.py:78, :109-117; app/repositories/users.py:40-45; app/services/auth.py:279-280 | Add a validator on `Settings`: `refresh_ttl` must exceed `access_ttl_seconds` with a margin. Add a 3.1-12 case. |
| L1 | ASVS table wording. V3.3.4 is "Pass at L1", but V3.3.4 has no L1 requirement (L2/L3 only), so it is simply not met. The V2.4.1/2.4.4 row pairs an item that is bcrypt-only (2.4.4, N/A for Argon2) and leaves out V2.4.2 (salt ≥ 32 bits). There are no N/A rows for V3.2.3 (client token storage) or V3.5.1 (OAuth revocation). | Low | docs/milestones/step-3.md:390, :401 | Mark V3.3.4 "Not met (L2/L3 only), ADR-0010". Replace 2.4.4 with 2.4.2, and add the two N/A rows. |
| L2 | Invisible padding still passes the length rule. `"a" + "​"*11` (zero-width space) and `"a" + "­"*11` give 12 characters after collapsing, and Cf characters are not refused. That is one visible character. The rule also strips the ends, but its message says "runs of spaces count as one". | Low | app/core/security.py:59-75 (checked locally with the same regex/NFKC logic) | Count length without category Cf (or also collapse them), and add a 2.6-04 case. Align the message with the strip. |
| L3 | The round-3 L7 fix is untested. The warning path in `_end_after_failure` is uncovered in CI ("database.py … 81-83"). | Low | app/infra/database.py:81-83; job 140782977310 coverage table | Add a unit test where both the savepoint block and the outer commit fail. Assert the warning (error type only) and the re-raise. |
| L4 | Attribution drift in the totals. Line 22 lists "3.8-01..11 (security audit)", but section 3.8 (line 212-213) and the round 1 resolution (line 334) say review round 1 added 3.8-06..10. The count of 29 is still right. | Low | docs/milestones/step-3.md:22, :212-213, :334 | Attribute 3.8-06..10 to review round 1 on line 22. |
| L5 | "Both tested at their boundaries" is overstated for the absolute limit. 3.5-17 checks it only at 12 h 05 (a 29-min step past 11 h 36), never at exactly 12 h or just before. It also never checks that the *access* token stops working at the L2 limits. | Low | tests/integration/test_s3_5_refresh_logout.py:299-321; ADR-0010:20-21 | Check refresh at 12 h − 1 s (200) and 12 h (401), and an access-token call after 30 min idle (401). |
| L6 | 3.5-18 simulates the failure by replacing `_add_refresh_token` before any INSERT. The real failure, the INSERT or flush failing (for example `uq_sessions_family_id_active` or a dropped connection at flush), is not exercised. The claim "writing the new refresh token fails" is approximated. | Low | tests/integration/test_s3_5_refresh_logout.py:324-334 | Patch the flush (or insert a conflicting active row) so the database statement itself fails. |

**Report claims verified:**

- **CI.**
  - Run 46082036988 (74959b9): Lint, Type check, Test and Compose all succeeded. Test job 140782977310 reports `521 passed, 6 skipped, 1 xfailed`, total coverage 98.63 %, auth.py 99 % (only branch 305->307). me.py and deps.py are 100 % (not listed under skip_covered). The 6 skips are the step 1 e2e tests that need `E2E_BASE_URL`. The XFAIL line is exactly 3.4-24 with the step 6 reason.
  - Head run 46082271882 (af8ddf9, docs-only: ROADMAP and step-3.md, checked with `git show --stat`) is green with the same 521/6/1 and 98.63 %. Compose job 140782977342 ran both `api=` journey steps successfully.
- **Totals.**
  - Table ids: 14+10+14+24+19+16+9+12 = 118.
  - Added: 1+12+4+9+3 = 29, so 89 planned + 29 = 118.
  - 117 passing + 1 strict xfail matches CI.
  - "12 fixed (F1–F11, F13), 1 expected red (F12)" is correct.
- **Ids vs test names.** Every "test" id has a matching `test_s3_<sec>_<nn>_` function. 3.1-12 now has 3 functions; 3.2-04 and 3.4-09 have 2; 3.4-03 has 3. The ids without a function are the C12 rows, the CI/Compose ids (3.2-01b, 3.4-17, 3.5-13, 3.6-12, 3.8-10, all present in the workflow) and 3.2-08 (step 2 tests).
- **Failure log.** No new red runs since round 3. The 16 failed or cancelled runs on the branch still map to F1–F13. The newest red run is 46080669546 (F13).
- **Round 3 rows, each checked in code and tests.**
  - H1: config.py:90-117 durations; 3.5-17 and 3.1-12 cases; ADR present (see H1/M1 above).
  - H2: security.py:59-70; 2.6-04 padded cases, 3.4-03 two cases, 3.6-08 one case.
  - M1: errors.py:97-123 `NO_STORE_HEADERS` in `problem_response`; 3.4-22 asserts 401/422/401.
  - L1: ROADMAP:255 has no prefixed-key item.
  - L2: step-3.md:24.
  - L3: test file `raises=AssertionError` plus `pytest.fail`.
  - L4: auth.py:265-267; 3.5-19.
  - L5: .env.example:68-71.
  - L6: main.py:138 `app.url_path_for("signup")`.
  - L7: database.py:81-83 (untested, L3 above).
  - L8: step-3.md:295-296.
- **Round 1 and 2 rows (spot-checked for regressions).** `to_thread` at main.py:50/65 and cli.py:71/86; `is_unique_violation` by SQLSTATE and constraint name; lock order unchanged in auth.py and me.py; README single-flight and no-store notes; ROADMAP carries for steps 4, 6, 7, 8 and 9 present.
- **ASVS table vs 4.0.3 wording.** V2.1.1, 2.1.2, 2.1.3, 2.1.6, 3.3.1, 3.3.3 and 8.2.1 are consistent. V3.3.2 (L2 requires both limits) and V3.3.4 (L2/L3 only) are discussed in H1, M1 and L1. V2.4.x is L1.
- **Cross-check table.** It covers every old `routes/login.py` route (lines 29-684), the `session_info` field and the auto-refresh services. Dropping `username` is recorded in step 2.
- **Lint.** `ruff check` and `ruff format --check` are clean locally.
- **Could not verify.** I could not run the tests locally (I relied on CI logs) or see the security-audit output, which is kept outside the repository.

**Missing scenarios:**

- 3.1 C10: an access TTL longer than (or equal to) the refresh TTL is refused at startup (M2).
- 3.5 C3: absolute limit at exactly 12 h and at 12 h − 1 s under the L2 settings. Access token refused after 30 min idle and at 12 h, not only refresh (L5).
- 3.4 C3 / 3.6 C3: passwords padded with zero-width or soft-hyphen characters (L2).
- 3.5 C9/C10: the session INSERT itself fails during rotation (unique-index or connection failure at flush) and the `rotated` mark is rolled back (L6).
- Infra C9: the outer commit fails after a failed unit of work; warning logged with error type only, original error re-raised (L3).
- 3.6 C6: if option (b) of H1 is chosen, ending another session or revoke-others with a wrong or missing current password, and with a stolen access token.

## Scorecard (by the independent reviewer)

| Area | Old code | After step 3 | Evidence |
| --- | --- | --- | --- |
| Folder structure & architecture | 6 | 9 | Queries only in repositories (users.py:37-101, sessions.py); one service call per route (api/v1/auth.py, me.py); infra→core only (database.py:16). |
| API design | 5 | 9 | `response_model` everywhere; problem+json with stable codes; no-store now on errors too (errors.py:97-123, 3.4-22); `Page[T]`; disabled signup hidden by route name (main.py:138). |
| Database schema | 5 | 9 | Migration 0003 CHECKs, partial unique active index, tie-safe backfill, downgrade (CI 3.2-01/3.2-01b); clock-skew CHECK hazard closed (auth.py:265-267, 3.5-19). |
| Scalability & load balancing | 4 | 9 | Bounded Argon2 pool (3.1-08); `end_read` before hashing; per-user `FOR NO KEY UPDATE` only; cross-node clock skew tolerated (3.5-19). |
| DSA / algorithms | 4 | 9 | Atomic lockout UPDATE (users.py:71-101, 3.4-10); bulk revocation UPDATEs; deadlock-free lock order (3.8-01, 3.8-12 both strategies). |
| Code quality & correctness | 3 | 9 | Re-checks under the lock complete (3.8-02..09); failed rotation rolls back (3.5-18). The missing access/refresh TTL check (M2) is the remaining correctness gap. |
| Duplication & reuse | 3 | 9 | One `lock_user`, `can_log_in`, `count_failed_login`, `transaction`, shared `NO_STORE_HEADERS` used by both success and error paths. |
| Maintainability | 3 | 9 | Records match CI (118 ids, 521/6/1, F1–F13 against every red run); small drift: wrong "or" in the ADR and `.env.example` (M1), attribution (L4), untested L7 path (L3). |
| Security | 2 | 8 | Strong attack coverage (alg none, reuse, lockout races, enumeration, padding). The step's ASVS L2 items are not all met: the V3.3.4 deviation and L1 defaults lack owner acceptance (H1). |
| **Overall** | **4** | **8.9** | Average of the nine areas (80 / 9). FAIL until H1 is resolved (owner acceptance recorded and VISION reconciled, or V3.3.4 re-auth implemented with L2 defaults or carried with owner agreement). |
