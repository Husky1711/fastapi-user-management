# Step 3: independent review, round 2 (verbatim)

### 5. Independent review: FAIL

Reviewer: milestone-reviewer agent (`.claude/agents/milestone-reviewer.md`), 2026-11-28, commit 763a29a

**Summary:** I checked every row of the round 1 resolution table against the code and CI, and all of them hold. The query now lives in `UserRepository.get_authenticated`. The totals recount to 106. The 3.8 ids map one-to-one to test functions. The status and lockout re-checks under the lock are real, and the new race tests exercise them. CI is green at both b626713 and the docs-only head. The step still fails on one High finding. The new ASVS table says "the exit criterion is met for everything this step owns", but it leaves out an L2 password-storage item (V2.4.5, a secret pepper on the password hash). It neither passes that item nor carries it to a later step. There are also four Medium gaps: token responses have no `Cache-Control: no-store`; log redaction leaks the rest of a multi-word or punctuated secret; and an account-enumeration probe and a step 7 re-test are said to be carried forward but are missing from the ROADMAP.

| # | Finding | Severity | Evidence | Recommended fix |
| --- | --- | --- | --- | --- |
| H1 | **False claim: ASVS exit criterion "met for everything this step owns".** The V2/V3 table lists V2.4.1 and V2.4.4 but leaves out **V2.4.5** (ASVS 4.0.3, L2: an extra KDF iteration with a secret salt, or "pepper", stored apart from the hashes). Hashing has no secret: `PasswordHasher.from_parameters(profiles.RFC_9106_LOW_MEMORY)` takes only the password. So the item neither passes nor has a named carry step. V2.2.2 sits in a shared row with 2.2.3, and its own status is never stated. | High | docs/milestones/step-3.md:315-344 (claim at :343-344); app/core/security.py:25, :105-106 | Add V2.4.5 to the table. Either implement a pepper (an HMAC key from settings, added through an ADR), or record a reasoned decision or carry with a named ROADMAP step. Give V2.2.2 its own status (N/A, no SMS/email authenticators). |
| M1 | Token and profile responses send no `Cache-Control: no-store`. RFC 6749 §5.1 requires it on token responses (MUST), and ASVS V8.2.1 asks for it on sensitive data. `/auth/login` and `/auth/refresh` return both tokens, and `/me` and `/me/sessions` return personal data, all without anti-caching headers. No ROADMAP step plans it. | Medium | `grep -ri "no-store\|cache-control" app/` finds nothing; app/api/v1/auth.py:48-80; app/api/v1/me.py:118-131 | Set `Cache-Control: no-store` (and `Pragma: no-cache`) on auth and `/me` responses, for example in the API router or middleware. Add a test per route. |
| M2 | Message redaction leaks most of a secret value that contains a space or `; & , } '`. `redact('body {"password": "correct horse battery staple"}')` gives `"password": "*** horse battery staple"` (checked locally). Passphrases with spaces are explicitly allowed (ASVS row V2.1.4). Every 3.7-05 case uses a single-token value, so the claim "Value redacted" is only partly true. No current code path logs such text, so this is defense in depth. | Medium | app/core/redaction.py:13-17 (value class `[^\s;&,'"}]+`); tests/integration/test_s3_7_logging.py:106-116 | When the value is quoted, redact up to the matching closing quote. Add 3.7-05 cases for a quoted multi-word value and for values containing `;`, `,` and `}`. |
| M3 | Two carried items have no ROADMAP entry. (a) The signup-then-login account probe (sign up with a password, then try to log in with it: success means the email was free). The report calls this "carried to steps 4 and 6", but ROADMAP steps 4 and 6 have no such item; step 6 only has generic "enumeration resistance" tests. Design decision "Signup never reveals whether an email exists" is true per response but not across the flow, and CLAUDE.md requires "generic message + rate limit". (b) "To step 7: hard-deleted user … re-tested once admin deletion exists" is not in ROADMAP step 7, which only plans soft delete. | Medium | step-3.md:36-37, :368-369, :386-387; docs/ROADMAP.md:159-215, :229 | Add explicit ROADMAP items: step 4 for per-IP limits on signup and login; step 6 to decide the `REQUIRE_VERIFIED_EMAIL` default, or send "account exists" mail instead of creating a second account. Add the step 7 re-test, or drop the claim. Reword design decision 3. |
| L1 | `Any` without a comment, which the CLAUDE.md Python style rule forbids. Rated Low because it has no effect on behaviour, the same treatment round 1 gave L1/L7. | Low | app/repositories/sessions.py:5, :113 | Add `# Any: rows are not read, only rowcount`. |
| L2 | The dummy Argon2 hash (about 64 MiB of CPU work) runs synchronously inside the async lifespan and the async CLI path. Shutdown, by contrast, is moved off the loop with `to_thread`. | Low | app/core/security.py:87-88; app/main.py:50; app/cli.py:71 | `await asyncio.to_thread(start_password_hashing, …)`. |
| L3 | `_ip_or_none` keeps IPv6 zone ids: `str(ip_address("fe80::1%eth0"))` gives `fe80::1%eth0`. PostgreSQL `inet` most likely rejects that, which would turn login and signup into a 500 for such clients. I did not run this against PostgreSQL. The `ValueError` branch is also uncovered (coverage: deps.py 95%, lines 66-67). | Low | app/core/deps.py:62-67; job 140774023273 coverage | Drop the scope id. Test both the non-IP and zone-id cases. |
| L4 | The failure log leaves out red run 46043074202 (3b7232d): all four jobs failed because `uv.lock` lacked PyJWT and a temporary lock job was used. This was deliberate, but CLAUDE.md says "never hide … a failure". | Low | `gh api …/runs/46043074202/jobs`: Lint, Type check, Test and Compose all failed | Add a row F12, or a note that this was an expected red run. |
| L5 | The `logout` and `logout-all` cases of 3.5-15 fail inside `get_current_user`, before `auth.logout` runs, so they repeat 3.3-10. A database failure inside the logout and password-change write paths is still untested (the 3.6 C9 N/A has the same flaw round 1 found in 3.5). | Low | tests/integration/test_s3_5_refresh_logout.py:255-277; app/core/deps.py:203; step-3.md:180 | Fail the database after authentication, for example by patching `SessionRepository.revoke_all` to raise `OperationalError`, for logout, logout-all and password change. |
| L6 | `is_unique_violation` substring-matches the constraint name in the message text, so any constraint whose name contains `uq_users_email` also matches. The re-raise branch in signup is never executed (auth.py:100 uncovered). | Low | app/infra/database.py:82-85; coverage `auth.py 99% 100` | Compare `error.orig.__cause__.constraint_name` (asyncpg), and cover the signup re-raise. |
| L7 | The docs name the switch `FEATURE_SIGNUP`, but the setting is `AUTH__SIGNUP_ENABLED`. With signup disabled, the route still appears in OpenAPI. | Low | docs/ROADMAP.md:137; docs/ARCHITECTURE.md:319; app/core/config.py `AuthSettings.signup_enabled`; app/api/v1/auth.py:33-40 | Align the docs. Leave the route out of the schema when it is disabled. |
| L8 | The 3.8-09 row claims "refusal audited without an actor; failure count skipped", but the test asserts only the status and code. | Low | tests/integration/test_s3_8_races.py:381-399 | Assert the `auth.login_refused` row with `actor_user_id IS NULL`. |
| L9 | Reuse detection has no grace period. A client that retries a refresh after a lost response, or two tabs refreshing at once, ends up with its family revoked and flagged as theft (3.5-05 asserts this). It is a deliberate choice, but client developers are not told. | Low | app/services/auth.py:318-332; test 3.5-05 | Document single-flight refresh for clients (README or API docs). |
| L10 | The secret field-name regex is unanchored, so it also blanks non-secret fields (`compass`, `bypass_cache`, `token_type`, `passive`; checked locally). | Low | app/core/redaction.py:48-52 | Match whole name segments (`(^\|_)password(_\|$)`, …). |
| L11 | The lock-wait helper still polls with `asyncio.sleep(0.01)` (`noqa`), against "No sleeping in tests". Round 1 accepted this as documented. | Low (carry) | tests/integration/test_s3_8_races.py:149-150 | Keep it, but record it as an accepted exception in the testing rules. |
| L12 | Logins with an unknown or malformed email leave no audit entry, so credential stuffing shows up only as access-log 401s. | Low (carry to step 7) | app/services/auth.py:115-117, :157-158 | Audit (or count) unknown-account failures with a masked email in step 7. |

**Report claims verified:**
- **CI.** Run 46079219114 (b626713) has all four jobs green. The Test job (140774023273) shows `483 passed, 6 skipped`; all six skips are step-1 e2e tests that need `E2E_BASE_URL`. Coverage is 98.55% overall, with auth.py at 99%, deps.py 95% and security.py 98%. me.py is not listed under `skip_covered = true`, so it is at 100%. The head run 46079523604 (763a29a, which differs from b626713 only in ARCHITECTURE, ROADMAP and step-3.md) is green. The Compose job includes the steps "3.3-09, 3.4-17, 3.5-13, 3.6-12" and "3.8-10", both green.
- **Totals.** The tables hold 14+10+13+21+15+14+8+11 = 106 ids. 89 planned plus 17 added (3.4-19, 3.2-10, 3.8-01..11, 3.4-20/21, 3.5-15, 3.6-14) is also 106. Every "test" id has a matching `test_s3_<sec>_<nn>_…` function. 3.1-12, 3.2-04, 3.4-03 and 3.4-09 each have two functions. The ids marked CI or Compose map to named CI steps.
- **Round 1 rows.**
  - H3: `get_authenticated` is at users.py:37-53, and the service no longer imports query builders.
  - H2: the 3.8 renumbering matches test_s3_8_races.py.
  - M1: 3.8-06 only passes because of the `can_log_in` lock check inside `_refusal_under_lock` (me.py:133).
  - M2: `can_log_in` includes status (auth.py:165-167), and 3.8-07 exercises it.
  - L1: every caller uses `lock_user` (auth.py:142, 300, 364; me.py:52, 71, 116).
  - L2: `with_for_update(key_share=True)` is at users.py:66.
  - L3: `record_failed_login` returns `None` and the audit entry has no actor.
  - L6: the action constants are at me.py:27-28.
  - L7: `SessionOut.of` exists.
  - L8: documented in ARCHITECTURE §2.
  - L9: the new regex is backed by the 3.7-06 "Basic information" case.
  - L10: the dummy hash is built at pool start.
  - M3/F10: run 46055530031 shows Type check failure.
  - M4: all five cross-check rows are present.
  - M5: listed at ROADMAP:169.
  - H4: the table exists, but see H1.
- **Failure log against red runs.** Every failed or cancelled run on the branch maps to F1–F11 except 46043074202 (L4). F11: run 46077451738 has Test cancelled and run 46078967397 has Test failed (CancelledError).
- **Tests read.** I read the bodies of 3.8-01..09, 3.4-07, 3.4-10, 3.4-20, 3.4-21, 3.5-05, 3.5-15, 3.6-14, 3.7-05 and 3.7-06. They assert what the report claims, except 3.8-09's audit claim (L8) and 3.5-15's logout cases (L5).
- **Lock order.** I re-read every write path; none takes a session row before the user row. `count_failed_login` touches only `users`.
- **Other checks.** `ruff check app tests` is clean locally.
- **Could not verify.** I could not open the JUnit artifact (the artifact storage host is blocked by the proxy), so per-test results come from the pass and fail summary only. I also could not verify the security-audit run itself (its output is kept outside the repository).

**Missing scenarios:**
- 3.3 C2: the client host is a non-IP name, or an IPv6 address with a zone id (L3).
- 3.4/3.5 C6: `Cache-Control: no-store` on login and refresh responses (M1); the signup-then-login enumeration probe, at least documented as a known gap with a test pinned to the step that fixes it (M3).
- 3.5 C7: a refresh racing a login under `replace_all` or `limit_sessions`, where the strategy revokes the family being refreshed.
- 3.5 C9 and 3.6 C9: the database fails after authentication, inside the logout, logout-all and password-change writes (L5).
- 3.6 C8: `DELETE /me/sessions/{id}` twice (expect 404 the second time, with no extra audit entry).
- 3.7 C6: quoted multi-word secret values, and values containing `;`, `,`, `}` or `&` (M2).
- 3.8 C10: 3.8-09 should assert the refusal audit entry with no actor (L8).

## Scorecard (by the independent reviewer)

| Area | Old code | After step 3 | Evidence |
| --- | --- | --- | --- |
| Folder structure & architecture | 6 | 9 | Queries are only in repositories (users.py:37-53, sessions.py). Routers call one service each (api/v1/auth.py, me.py). The core→services link is documented as the single exception (ARCHITECTURE §2). |
| API design | 5 | 9 | Every route has a `response_model`, problem+json codes, an enumeration-safe 202 signup and `Page[T]`. Missing: no-store headers (M1), disabled signup still in OpenAPI (L7), rate-limit headers (step 4). |
| Database schema | 5 | 9 | Migration 0003 adds reason and family CHECKs, a partial unique active-row index and a tie-safe backfill, tested in CI steps 3.2-01 and 3.2-01b, with a downgrade. |
| Scalability & load balancing | 4 | 9 | Bounded Argon2 pool (security.py:81-123, 3.1-08); `end_read` before hashing; locks are per user only (`FOR NO KEY UPDATE`). |
| DSA / algorithms | 4 | 9 | One-query authentication (3.3-11), bulk revocation `UPDATE`s, an atomic lockout counter (3.4-10), a deadlock-free lock order (3.8-01). |
| Code quality & correctness | 3 | 9 | Re-checks under the lock are complete and tested (3.8-02, 04, 06, 07, 09). Small gaps remain: L2, L3, L6. |
| Duplication & reuse | 3 | 9 | One `lock_user`, `can_log_in`, `count_failed_login`, `transaction`, `redact_fields` and `SessionOut.of`. |
| Maintainability | 3 | 9 | Records now match the code and CI (106 ids, test names, F1–F11). One red run is not logged (L4), and two carried items are not in the ROADMAP (M3). |
| Security | 2 | 8 | Strong attack-case coverage (alg none, reuse, lockout, races, enumeration, isolation). Held back by H1 (V2.4.5 unaddressed), M1 (no no-store), M2 (partial redaction) and M3 (enumeration probe not tracked). Rate limits are carried to step 4. |
| **Overall** | **4** | **8.9** | Average of the nine areas (80 / 9). FAIL until H1 is fixed. Under the merge rule, Security needs M1–M3 fixed or carried to named ROADMAP steps before it can reach 9. |
