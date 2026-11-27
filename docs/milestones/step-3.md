# Milestone 3: Authentication core

- PR: #5
- Latest CI run (automatic report): https://github.com/Husky1711/fastapi-user-management/actions/runs/46083134460
- Verdict: **GATE IN PROGRESS** (all sections ✅; review rounds 1–4 FAIL, fixes below, round 5 pending)

Scenario plans below were written **before** the code (process rule). Ids map to test names
`test_s3_<section>_<nn>_...`; *CI step* means a named step in the CI workflow.

## Section log

| # | Section | Status | Scenarios (pass / total) | Notes |
| --- | --- | --- | --- | --- |
| 3.1 | Token and password primitives: JWT, opaque tokens, bounded hashing, dummy verify | ✅ | 14 / 14 | CI run 46044586029 |
| 3.2 | Auth data: migration 0003, session and audit repositories | ✅ | 11 / 11 | CI run 46046371009; 3.2-10 in run 46056180851; 3.2-11 in run 46083134460 |
| 3.3 | Request dependencies: `client_info`, `get_current_user` | ✅ | 14 / 14 | CI run 46047567713 (3.3-09 also on the real stack in 3.6-12); 3.3-14 in run 46080870382 |
| 3.4 | Signup and login: lockout, rehash, session strategies | ✅ | 23 / 24 | CI run 46049595954; 3.4-17 in run 46051473324; 3.4-20/21 in run 46079219114; 3.4-22/23 in run 46080870382; 3.4-24 is a pinned known gap (step 6) |
| 3.5 | Refresh rotation, reuse detection, logout, logout-all | ✅ | 19 / 19 | CI run 46050265813; 3.5-13 in run 46051473324; 3.5-15 in run 46079219114; 3.5-16 in run 46080870382; 3.5-17..19 in run 46082036988 |
| 3.6 | `/me`: profile, sessions, revoke, revoke-others, change password | ✅ | 18 / 18 | CI run 46051473324; 3.6-14 in run 46079219114; 3.6-15/16 in run 46080870382; 3.6-17/18 in run 46083134460 |
| 3.7 | Carried from step 1: 499 on client disconnect, broader log redaction | ✅ | 9 / 9 | CI run 46052631869; 3.7-09 in run 46080870382 |
| 3.8 | Security audit fixes: per-user lock order, re-checks under the lock | ✅ | 12 / 12 | Failing first in run 46055289113; passing in 46055748820; extended after review round 1, run 46079219114; 3.8-12 in run 46080870382 |
| | **Total** | | **120 / 121** | 89 planned + 32 added during the step: 3.4-19 (step 2 carry-over); 3.2-10, 3.8-01..05 and 3.8-11 (security audit); 3.8-06..10 (review round 1); 3.4-20, 3.4-21, 3.5-15, 3.6-14 (review round 1); 3.3-14, 3.4-22..24, 3.5-16, 3.6-15, 3.6-16, 3.7-09, 3.8-12 (review round 2); 3.5-17..19 (review round 3); 3.2-11, 3.6-17, 3.6-18 (review round 4) |

**Totals:** 121 scenarios: 120 passing, 0 failing, 1 known gap pinned as a strict expected failure (3.4-24, closed in step 6). Failures found and fixed during the step: 12 (F1–F11, F13); 1 expected red run (F12).

## Design decisions for this step

- **`sid` is the session family.** A login starts a family; each refresh rotates to a new row
  in the same family. The access token's `sid` is the `family_id`, and `get_current_user`
  checks that the family still has an active row, so logout and revocation end access at the
  next request instead of when the access token expires (one indexed query per request).
- **Revocation has a reason** (`sessions.revoked_reason`: `rotated`, `logout`, `logout_all`,
  `revoked`, `replaced`, `password_changed`, `reuse_detected`). A presented refresh token
  whose row was `rotated` is reuse: the whole family is revoked and audited. Other revoked
  tokens are just invalid.
- **Signup's answer never reveals whether an email exists**: same status (202), body and work
  (a password hash) either way. It returns no tokens; the client logs in next. Across the
  flow it still can: signing up and then logging in with that password succeeds only if the
  email was free. That known gap is pinned by 3.4-24 (strict expected failure) and closed in
  step 6 (verified email before login); step 4's per-IP limits slow the probe meanwhile.
- **Lockout without enumeration**: a locked account gets the same 401 as a wrong password
  (and the same Argon2 work); the lock and every failure are audited.
- **Failed-login counting commits before the error is raised**, so the counter survives the
  401 and no object changed in a failed block is read afterwards (step 2 review R3-06).
- **No pool connection is held while hashing** (step 2 review R2-03): the user is read, the
  read transaction ends, the hash runs, then a fresh unit of work re-reads the user with a
  row lock and writes.
- **Argon2 runs on a dedicated, bounded thread pool** (`AUTH__PASSWORD_HASH_WORKERS`, default 4,
  so ≤ 4 × 64 MiB) instead of the shared default executor (step 2 review R1-08).
- **IDN email domains stay refused** for now: ADR-0009 (step 2 review R1-18).
- **Client IP comes from `request.client`**; uvicorn's proxy-header handling rewrites it only
  for proxies listed in `FORWARDED_ALLOW_IPS` (ARCHITECTURE §8). `client_info` never reads
  `X-Forwarded-For` itself.

## Scenario plan and results

### Section 3.1: Token and password primitives

| Id | Cat. | Scenario | Expected | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| 3.1-01 | C1 | Encode then decode an access token | Claims `sub`, `sid`, `iat`, `exp`, `iss`, `aud`, `jti`, `typ=access` round-trip | test | ✅ |
| 3.1-02 | C6 | Token signed with another key; `alg: none`; another HMAC algorithm than configured | Rejected | test | ✅ |
| 3.1-03 | C6 | Wrong `iss`, wrong `aud`, wrong `typ`, missing `sub`/`sid`/`exp`/`jti` | Rejected | test | ✅ |
| 3.1-04 | C3 | Expired by 1 s past the leeway; not yet valid (`iat` in the future beyond leeway) | Rejected; within leeway accepted | test | ✅ |
| 3.1-05 | C2 | Garbage, empty, truncated, non-ASCII token | Rejected with one error type, no exception leaks | test | ✅ |
| 3.1-06 | C1 | Opaque token | 256 bits of randomness, URL-safe; stored hash is SHA-256 (32 bytes); same token → same hash | test | ✅ |
| 3.1-07 | C6 | 10 000 generated tokens | All distinct | test | ✅ |
| 3.1-08 | C7 | 20 concurrent hashes with 4 workers | Never more than 4 at once; all verify | test | ✅ |
| 3.1-09 | C9 | Hash pool shut down and restarted (lifespan) | New pool works; old one is closed | test | ✅ |
| 3.1-10 | C6 | Dummy verify for an unknown user | Runs a real Argon2 verify (same cost as a real one) and returns False | test | ✅ |
| 3.1-11 | C2 | IDN domain email | Refused with `user.email_invalid` (ADR-0009) | test | ✅ |
| 3.1-12 | C10 | JWT and auth settings: issuer, audience, TTL bounds, session limits (5 min–90 days idle, up to 365 days absolute, ISO 8601 durations, review round 3); secret shorter than the HMAC output (32/48/64 bytes for HS256/384/512) | Invalid values refused; short secret is a production safety problem | test | ✅ |
| 3.1-13 | C8 | Decoding the same token twice | Same claims; nothing cached that could go stale | test | ✅ |
| 3.1-14 | C12 | Earlier tests still pass | CI green | CI run | ✅ |
| — | C4, C5 | Covered in 3.3 (the primitives are used by `get_current_user`) | | | |
| — | C11 | Covered by 3.4–3.6 end-to-end flows | | | |

### Section 3.2: Auth data

| Id | Cat. | Scenario | Expected | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| 3.2-01 | C1 | Migration 0003 up, down, up | `users.last_login_at`, `sessions.revoked_reason` (+ CHECK), index on active rows per family; round trip clean | CI step + test | ✅ |
| 3.2-02 | C10 | Revoked row without a reason, or a reason without `revoked_at` | Rejected (CHECK) | test | ✅ |
| 3.2-03 | C1 | Session repository: add, get by token hash, active row of a family, active families of a user (paged) | Correct rows; revoked and expired excluded | test | ✅ |
| 3.2-04 | C1 | Revoke one family / all of a user's families / all but one, with a reason | Bulk `UPDATE`s; counts returned; already-revoked rows untouched | test | ✅ |
| 3.2-05 | C5, C6 | Revoking another user's family by id | Nothing changes (every method is scoped by `user_id`) | test | ✅ |
| 3.2-06 | C1 | Audit repository: add an entry | Row with action, actor, target, ip, request id, details | test | ✅ |
| 3.2-07 | C6 | Audit details | Never contain the password, token or full email (masked) | test | ✅ |
| 3.2-08 | C10 | Models vs migrated database (parity, names, triggers) | Still no difference (step 2 tests) | test | ✅ |
| 3.2-09 | C12 | Earlier tests still pass | CI green | CI run | ✅ |
| 3.2-10 | C10 | (added during build, F9) Backfill: two active legacy rows of one family with the same `created_at` | Exactly one stays active (ties broken by id); the unique index is created | CI step 3.2-01b | ✅ |
| 3.2-11 | C9 | (added, review round 4) The block fails and ending the outer transaction fails too | The block's own error surfaces; the second failure is logged once as a warning with its type only (no message, no secret) | test | ✅ |
| — | C2, C3, C7, C8, C9, C11 | Covered by 3.4–3.6 (the repositories are exercised through the flows) | | | |

### Section 3.3: Request dependencies

| Id | Cat. | Scenario | Expected | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| 3.3-01 | C1 | Valid bearer token for an active user and session | User loaded; the session id available to the route | test | ✅ |
| 3.3-02 | C4 | No `Authorization` header; wrong scheme; empty token | 401 `auth.not_authenticated`, `WWW-Authenticate: Bearer` | test | ✅ |
| 3.3-03 | C4 | Expired, forged or malformed token | 401 `auth.invalid_token`, same body for all | test | ✅ |
| 3.3-04 | C4 | Valid token, but its session was revoked or expired | 401 `auth.invalid_token` | test | ✅ |
| 3.3-05 | C4 | Valid token for a disabled, deleted or missing user | 401 `auth.invalid_token` | test | ✅ |
| 3.3-06 | C6 | Token whose `sid` belongs to another user | 401 | test | ✅ |
| 3.3-07 | C6 | Refresh token sent as a bearer token | 401 (wrong type) | test | ✅ |
| 3.3-08 | C1 | `client_info` | IP from `request.client`; user agent truncated to 256; missing values are `None` | test | ✅ |
| 3.3-09 | C6 | `X-Forwarded-For` from an untrusted client | Ignored | test + e2e | ✅ |
| 3.3-10 | C9 | Database down during the user lookup | Generic 500, no token in logs | test | ✅ |
| 3.3-11 | C1 | The lookup is one query (user + session check) | Query counter | test | ✅ |
| 3.3-12 | C6 | Token never logged | Not in access logs or error logs | test | ✅ |
| 3.3-13 | C12 | Earlier tests still pass | CI green | CI run | ✅ |
| 3.3-14 | C2 | (added, review round 2) Client host is IPv4, IPv6, IPv6 with a zone id, a name, empty or missing | Addresses recorded (zone id dropped: `inet` refuses it); names and blanks recorded as none | test | ✅ |
| — | C5 | N/A here: authorization (permissions) is step 5 | | | |
| — | C7, C8 | Covered by 3.5 (concurrent refresh / repeated logout) | | | |

### Section 3.4: Signup and login

| Id | Cat. | Scenario | Expected | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| 3.4-01 | C1 | Signup with a new email | 202; user created (not verified, not admin) | test | ✅ |
| 3.4-02 | C6 | Signup with an existing email (any case) | Same 202 and body; no change to the existing user | test | ✅ |
| 3.4-03 | C2, C3 | Signup with a weak password (incl. padded with spaces to 12: `"a"+11 spaces`, `"ab"+10 spaces+"c"`, cases added in review round 3), invalid email, extra fields, missing fields | 422 with stable codes; nothing created | test | ✅ |
| 3.4-04 | C1 | Signup disabled (`AUTH__SIGNUP_ENABLED=false`) | 404 (the route behaves as absent) | test | ✅ |
| 3.4-05 | C1 | Login with the right password | 200; access + refresh token, `token_type`, `expires_in` from settings; `last_login_at` set; counter reset (refresh lifetime 30 min by default since review round 4) | test | ✅ |
| 3.4-06 | C4 | Wrong password; unknown email; disabled or deleted user | Same 401 `auth.invalid_credentials` | test | ✅ |
| 3.4-07 | C6 | Timing: unknown email vs wrong password | Both run one Argon2 verify (spy count) | test | ✅ |
| 3.4-08 | C6 | 5 wrong passwords | Locked for 15 min; the right password is then refused with the same 401; audited | test | ✅ |
| 3.4-09 | C3 | 4 failures then success; lock expiry exactly at `locked_until` | Counter reset on success; login allowed once the lock has passed (injected clock) | test | ✅ |
| 3.4-10 | C7 | 10 concurrent wrong-password logins | Counter counts all 10 (row lock), lock applied once | test | ✅ |
| 3.4-11 | C1 | Login with a hash using old Argon2 parameters | Succeeds; hash upgraded | test | ✅ |
| 3.4-12 | C1 | Session strategy `allow_multiple` | Each login adds a family | test | ✅ |
| 3.4-13 | C1 | Session strategy `replace_all` | Earlier families revoked (`replaced`) | test | ✅ |
| 3.4-14 | C3 | Session strategy `limit_sessions` with limit 3, 4th login | Oldest family revoked; 3 remain | test | ✅ |
| 3.4-15 | C1 | Session strategy `replace_same_device` | Earlier family with the same user agent revoked; others kept | test | ✅ |
| 3.4-16 | C9 | Database down at login | Generic 500; password and email not logged | test | ✅ |
| 3.4-17 | C11 | User signs up, logs in, calls `/me` (real stack) | Works end to end | CI step (Compose) | ✅ |
| 3.4-18 | C12 | Earlier tests still pass | CI green | CI run | ✅ |
| 3.4-19 | C7 | Two concurrent signups with one email (different case) over HTTP | Both 202, same body; exactly one user (added: step 2 carry-over) | test | ✅ |
| 3.4-20 | C3 | (added, review round 1) Login with a 129-character password: over the 128 rule, under the 1024 input cap | Just a wrong password: 401 `auth.invalid_credentials`, counted toward lockout (never 422, which would reveal the rule applies) | test | ✅ |
| 3.4-21 | C3 | (added, review round 1) Signup `full_name` of 200 and 201 characters | 202 and stored; 422 and nothing stored | test | ✅ |
| 3.4-22 | C6 | (added, review round 2) Signup, login, refresh, `/me`, `/me/sessions` and logout answers, plus error answers (401 wrong password, 422, 401 without a token; added in review round 3) | `Cache-Control: no-store`, `Pragma: no-cache` (RFC 6749 §5.1) on every one: successes through the API router, errors through `problem_response` | test | ✅ |
| 3.4-23 | C1 | (added, review round 2) Signup switched off | Left out of the OpenAPI document; shown when on | test | ✅ |
| 3.4-24 | C6 | (added, review round 2) Sign up, then log in with that password | Known gap (strict xfail on `AssertionError` only; any other error fails the run): today the login succeeds only when the email was free. Pinned as a strict expected failure; it must start passing (login refused until the email is verified) in step 6 | test (strict xfail) | ⏳ step 6 |
| — | C5 | N/A: signup and login are public | | | |
| — | C8 | Covered by 3.4-02 (repeat signup) and 3.4-12 (repeat login) | | | |
| — | C10 | Covered by 3.4-03 (nothing created) and 3.4-10 (counter exact) | | | |

### Section 3.5: Refresh, reuse detection, logout

| Id | Cat. | Scenario | Expected | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| 3.5-01 | C1 | Refresh with the current refresh token | New pair; old row `rotated`; same family; `sid` unchanged | test | ✅ |
| 3.5-02 | C6 | Refresh with an already-rotated token (stolen copy) | 401; whole family revoked (`reuse_detected`); audited; the legitimate holder's newer token stops working | test | ✅ |
| 3.5-03 | C4 | Refresh with an unknown, expired or logged-out token | 401 `auth.invalid_token`; no family revoked | test | ✅ |
| 3.5-04 | C2 | Refresh with a missing / empty / oversized token | 422 or 401, never 500 | test | ✅ |
| 3.5-05 | C7 | Two concurrent refreshes with the same token | Exactly one succeeds; the other is treated as reuse (family revoked) | test | ✅ |
| 3.5-06 | C3 | Refresh exactly at expiry (injected clock) | Refused at `expires_at`; accepted 1 s before | test | ✅ |
| 3.5-07 | C3 | Refresh keeps a session alive, but not forever | Each rotation gets a fresh TTL, capped at `AUTH__SESSION_MAX_AGE` from the family's first login; past the cap, 401 | test | ✅ |
| 3.5-08 | C1 | Logout | Current family revoked (`logout`); access token stops working immediately | test | ✅ |
| 3.5-09 | C8 | Logout twice | Second call 401 (token's session gone), nothing else changes | test | ✅ |
| 3.5-10 | C1 | Logout-all | Every family of the user revoked (`logout_all`); other users untouched | test | ✅ |
| 3.5-11 | C4 | Logout without a token | 401 | test | ✅ |
| 3.5-12 | C10 | Refresh after the user was disabled | 401; no new session | test | ✅ |
| 3.5-13 | C11 | Real stack: login, refresh twice, replay the first refresh token, everything revoked | As stated | CI step (Compose) | ✅ |
| 3.5-14 | C12 | Earlier tests still pass | CI green | CI run | ✅ |
| — | C5 | N/A: a user acts only on their own sessions (3.2-05 covers cross-user) | | | |
| 3.5-15 | C9 | (added, review round 1) Database down at refresh | Generic 500; the token not in logs or body | test | ✅ |
| 3.5-16 | C9 | (added, review round 2) The database fails inside the logout / logout-all write (after authentication) | Generic 500; nothing changed (the session still works); token not logged | test | ✅ |
| 3.5-17 | C3 | (added, review round 3; defaults and exact boundaries in round 4) The default limits are ASVS level 2: 30 min idle and 12 h absolute | Refreshing every 29 min keeps a session alive; at 12 h − 1 s a refresh works, at 12 h it is refused and that session's access token stops working; 30 min − 1 s idle refresh works, exactly 30 min is refused | test | ✅ |
| 3.5-18 | C9, C10 | (added, review round 3; real INSERT failure in round 4) The database refuses the new refresh row (a CHECK fails at flush) after the old row was marked `rotated` | 500; the mark is rolled back with it, so a retry with the same token succeeds (not reuse) | test | ✅ |
| 3.5-19 | C7 | (added, review round 3) The refreshing node's clock is 2 s behind the login node's | 200, not a 500 from the `family_started_first` CHECK (the new row is never older than its family) | test | ✅ |

### Section 3.6: `/me`

| Id | Cat. | Scenario | Expected | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| 3.6-01 | C1 | `GET /me` | Own profile (`id`, `email`, `full_name`, `email_verified`, `created_at`); no hash, no counters | test | ✅ |
| 3.6-02 | C1 | `GET /me/sessions` | Own active sessions, paged, current one marked; no token hashes | test | ✅ |
| 3.6-03 | C1 | `POST /me/sessions/{id}/revoke` for another device (with the current password; `DELETE` until review round 4) | 204; that family revoked (`revoked`) | test | ✅ |
| 3.6-04 | C5, C6 | Revoke another user's session id; unknown id; malformed id | 404 (not 403); 404; 422 | test | ✅ |
| 3.6-05 | C1 | `POST /me/sessions/revoke-others` | Every other family revoked; the current one keeps working | test | ✅ |
| 3.6-06 | C1 | `POST /me/password` with the right current password | 204; new hash; other sessions revoked (`password_changed`); current kept | test | ✅ |
| 3.6-07 | C4 | Change password with a wrong current password | 401-style refusal (`auth.invalid_credentials`), counts toward lockout | test | ✅ |
| 3.6-08 | C2, C3 | New password weak (incl. padded with spaces, review round 3), same as the old one, or missing | 422 with stable codes | test | ✅ |
| 3.6-09 | C4 | Every `/me` route without a token | 401 | test | ✅ |
| 3.6-10 | C8 | Revoke-others twice | Second call revokes nothing, still 204 | test | ✅ |
| 3.6-11 | C3 | Sessions list with 0, 1 and limit+1 sessions | Correct pages | test | ✅ |
| 3.6-12 | C11 | Real stack: change password, old password refused, new accepted | As stated | CI step (Compose) | ✅ |
| 3.6-13 | C12 | Earlier tests still pass | CI green | CI run | ✅ |
| 3.6-14 | C1, C4 | (added, review round 1) Ending your own current session by id | 204; that access token and its refresh token stop working at once; the other device stays | test | ✅ |
| — | C7 | Covered by 3.5-05 (session races) | | | |
| 3.6-15 | C9, C10 | (added, review round 2) The database fails inside the password-change write | Generic 500; the whole change rolled back: old password and other devices still work | test | ✅ |
| 3.6-16 | C8 | (added, review round 2) Ending the same session twice | 204, then 404 `session.not_found`; one audit entry | test | ✅ |
| 3.6-17 | C4, C6, C11 | (added, review round 4) Ending another device, revoke-others and logout-all with a stolen access token: no password, wrong password, right password | 422 `auth.current_password_required`; 401 `auth.invalid_credentials` (counted toward the lockout, audited `auth.reauth_failed`; the other device still works); 204 and the other device is signed out. Logout-all also on the real stack (3.8-10) | test, 3 variants; CI step (Compose) | ✅ |
| 3.6-18 | C1 | (added, review round 4) Ending this session by id; and with `AUTH__REAUTH_TO_END_SESSIONS=false`, ending another device, revoke-others and logout-all | All 204 without a password | test | ✅ |

### Section 3.7: Carried from step 1

| Id | Cat. | Scenario | Expected | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| 3.7-01 | C9 | Client disconnects while a JSON-body route reads its body | Logged with status 499, not 400; no error response attempted | test | ✅ |
| 3.7-02 | C1 | Normal JSON request | Unchanged (200/422 as before) | test | ✅ |
| 3.7-03 | C6 | Log fields named like secrets (`password`, `token`, `secret`, `authorization`, `api_key`, …), any case | Value replaced by `[REDACTED]` | test | ✅ |
| 3.7-04 | C6 | Secret values that aren't strings (numbers, lists, nested dicts) | Redacted | test | ✅ |
| 3.7-05 | C6 | `key: value`, `key=value` and `Authorization: Bearer …` inside messages, incl. prefixed keys (`new_password`), quoted multi-word values and values with `;`, `,`, `}`, `&` or an escaped quote (cases added in review round 2) | Whole value redacted | test | ✅ |
| 3.7-06 | C2 | Messages that only mention the words ("password reset sent") | Not mangled | test | ✅ |
| 3.7-07 | C1 | Login and refresh logs | Never contain the password or a token (whole flow) | test | ✅ |
| 3.7-08 | C12 | Earlier tests still pass | CI green | CI run | ✅ |
| 3.7-09 | C2 | (added, review round 2) Field names that only contain a secret word (`compass`, `bypass_cache`, `token_type`, `passive`, `keyboard`) | Kept (names are matched by whole words) | test | ✅ |
| — | C3, C4, C5, C7, C8, C10, C11 | N/A: logging behaviour, no auth, state or flow of its own | | | |

### Section 3.8: Security audit fixes (added after gate check 6 found the candidates)

The audit (gate check 6) proposed four candidates; the first tests here were pushed **before**
the fix and failed (run 46055289113), then passed with it (run 46055748820). Review round 1
added 3.8-06 to 3.8-10 and the extra variants of 3.8-01 (run 46079219114). Each id is one test
function `test_s3_8_<nn>_...`; variants are its parameters.

| Id | Cat. | Scenario | Expected | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| 3.8-01 | C7, C6, C9 | A refresh is mid-rotation (user row locked) while the owner runs logout-all, a password change, ends that session by id, or revoke-others | The revocation waits for the rotation (test waits until PostgreSQL shows it blocked behind the user lock), then also ends the new token: refresh and access with it are 401. No deadlock, no 500, no 404. Only the owner's device survives (none after logout-all) | test (real pool), 4 variants | ✅ |
| 3.8-02 | C7, C6, C10 | A login verified the old password; the password changes before it finishes. Variant: an old-parameter hash that a login would upgrade | Login refused (401, `auth.login_refused` audited); old password refused, new one works; the upgrade never overwrites the new password | test, 2 variants | ✅ |
| 3.8-03 | C4, C6 | Stolen access token: 5 wrong current passwords lock the account; then the right one | 401 `auth.invalid_credentials`; password unchanged; guesses during the lock not counted; audited as `auth.password_change_failed` ×5, `auth.account_locked`, `auth.password_change_refused`; the owner's session untouched | test | ✅ |
| 3.8-04 | C7, C4 | A stolen token's password change has verified and is hashing; the owner changes the password, or runs logout-all, first | Stale change refused (`auth.invalid_credentials` / `auth.invalid_token`), audited `auth.password_change_refused`; the owner's password stands | test, 2 variants | ✅ |
| 3.8-05 | C1, C8 | Password change after a wrong guess | Succeeds; failure counter reset to 0 | test | ✅ |
| 3.8-06 | C7, C6 | (review M1) The account gets locked by failed logins while a password change is hashing | Change refused under the lock (the after-hashing check); password unchanged; refusal audited | test | ✅ |
| 3.8-07 | C7, C4 | (review M2) The account is disabled while a password change is hashing | Change refused (status re-checked under the lock); password unchanged | test | ✅ |
| 3.8-08 | C7, C10 | Six concurrent logins under `replace_all` and under `limit_sessions` (limit 2) | All 200; exactly 1 / 2 active sessions remain (count-then-insert serialized by the user lock) | test (real pool), 2 variants | ✅ |
| 3.8-09 | C9, C10 | The user row is removed while a login (right or wrong password) is verifying | 401 `auth.invalid_credentials`, never 500; right password: one `auth.login_refused` with no actor; wrong password: nothing audited (no row to count) | test, 2 variants | ✅ |
| 3.8-10 | C11 | Real stack: logout-all without the password is 422, with it 204, and it ends a session refreshed with a stolen token (no active row left in the database); then a stolen access token guesses 5 times and the right password is refused (account locked) | As stated | CI step (Compose) | ✅ |
| 3.8-11 | C12 | Earlier tests still pass (incl. refresh race 3.5-05, password change 3.6-06, lockout 3.4-08/10) | CI green | CI run | ✅ |
| 3.8-12 | C7 | (added, review round 2; `limit_sessions` variant review round 3) A login under `replace_all`, or `limit_sessions` with a limit of 1, while a refresh is mid-rotation | The login waits for the rotation, then ends the successor too: only the new login's session remains | test (real pool) | ✅ |
| — | C2, C3, C5 | N/A: no new input, boundary or permission; routes and schemas unchanged (input caps are 3.4-20/21) | | | |

## Failure log

| # | Found by | What failed | Cause | Fix | Status |
| --- | --- | --- | --- | --- | --- |
| F1 | CI test (runs 46043542631, 46044092198) | Test collection failed: PyJWT `InsecureKeyLengthWarning` (as an error) for an HS512 token signed with a 40-byte key | Real gap: the production safety check allowed HS384/HS512 with a 32-byte secret, below RFC 7518 §3.2 (key ≥ hash size) | Minimum secret length now follows the algorithm (32/48/64 bytes); test key is 64 bytes; boundary test added to 3.1-12; the step 1 test 1.2-04 expects the new message (run 46044092198 caught it) | Fixed (run 46044586029) |
| F2 | CI test (run 46045405514) | 3.2-04 failed: `SADeprecationWarning` for `Result.tuples()` (warnings are errors) | SQLAlchemy 2.1 deprecates it; rows unpack directly | Rows unpacked directly (and a lint fix, run 46045889238) | Fixed (run 46046371009) |
| F3 | CI test (run 46047067623) | 3.3-04 `[expired]` violated `ck_sessions_family_started_first` | Test computed `created_at` and `family_started_at` from two `clock.now()` calls microseconds apart | One shared value | Fixed (run 46047567713) |
| F4 | CI test (run 46048430388) | Signup answered 202 but stored nothing; every login after it failed (11 tests) | Two bugs: (1) the unit of work orders inserts by `relationship()` only, so the audit row (foreign key to the new user) was inserted first and refused; (2) `except IntegrityError` treated *every* integrity error as "email taken" and hid (1). The step 2 admin service had the same broad catch | User flushed before its audit row (rule written in `audit.record`); only `uq_users_email` means taken (`is_unique_violation`, shared, tested), anything else is re-raised; the admin service also releases its connection before hashing (R2-03) | Fixed (run 46049028389) |
| F5 | CI test (run 46049028389) | Step 2 test 2.6-09 regressed: reading a loaded object after a failed unit of work raised `MissingGreenlet` | Ending the read transaction first (`end_read`, R2-03) made the next unit of work a fresh transaction; its failure rolled back the whole transaction and expired every loaded object (re-opening R2-02) | `transaction()` always runs the block in a SAVEPOINT; on failure it rolls back the savepoint and commits the empty outer transaction, so nothing loaded earlier is expired | Fixed (run 46049595954) |
| F6 | CI test (run 46050943060) | `GET /me/sessions` answered 500 (6 tests); the Compose check still passed because the error body's `ip` was `null`, which is "not the spoofed address" | asyncpg returns `inet` as `ipaddress` objects, not `str` (the model said `str`); test 3.2-06 missed it by reading back the cached object; the Compose check asserted only a negative | `IPAddress` column type returns `str`; 3.2-06 re-reads from the database; the Compose check also requires a real address | Fixed (run 46051473324) |
| F7 | CI test (run 46052147559) | Step 1 test 1.5-20 expected `token=***` for `token = abc123`; 3.7-02 got a 500 | (1) Deliberate change: the broader redaction keeps the original spacing (`token = ***`), still fully redacted; (2) the test ran the app without its lifespan, so `get_db` had no session factory | (1) Expectation updated with a comment; (2) the test starts the lifespan | Fixed (run 46052631869) |
| F8 | Security audit (gate check 6), tests first (run 46055289113) | Four confirmed race and lockout flaws, plus a deadlock found by the new test: (a) a refresh in flight survived logout-all / password change; (b) refresh racing a password change deadlocked (500); (c) a login that verified the old password got a session after a password change, and with a due rehash put the old password back; (d) a stolen access token could keep guessing the current password past the lockout; (e) a stale password change committed after the owner's own change or logout-all | Checks made before slow hashing or outside a shared lock were not repeated at the write, and refresh locked the session row before the user row (READ COMMITTED bulk revoke can't see a successor committed after its snapshot; reversed lock order deadlocked) | Per-user lock order (user row first) in refresh, logout, logout-all, session revocation, login and password change; under the lock login and password change compare the verified hash, password change requires an unlocked account and a live caller session and resets the failure counter; ARCHITECTURE §2 rule | Fixed (run 46055748820) |
| F9 | Security audit coverage critic, CI check first (run 46055991972) | Migration 0003 aborted (`could not create unique index`) when two active legacy rows of one family had the same `created_at` | "Keep the newest" compared `created_at` only, so ties both stayed active | Ties broken by `(created_at, id)`; CI step 3.2-01b (migration not yet merged, so edited in place) | Fixed (run 46056180851) |
| F10 | CI type check (runs 46055289113, 46055530031) | `mypy --strict` failed on the 3.8 tests: `Module "app.services.auth" does not explicitly export attribute "verify_password"` (and the same for `me.hash_password`) | The tests patched the services' imported names through module attributes, which the strict "no implicit re-export" rule refuses | Patched by import path (`monkeypatch.setattr("app.services.auth.verify_password", ...)`) wrapping the real `security` functions | Fixed (run 46055748820) |
| F11 | CI test (run 46077451738 hung 13 min, cancelled; run 46078967397 failed) | 3.8-01 never saw the revocation wait, and on that failure the test hung | (1) The new wait filter matched the statement text, which didn't hold (column order; PostgreSQL also truncates `query` at 1024 bytes); (2) on any failure the paused refresh was never released, kept the user lock, and the cleanup waited forever | (1) Waiter found by its blocker's lock on `users` (`pg_locks`, `pg_blocking_pids`), no text; (2) `paused_request` always releases and collects the paused request; (3) every CI job now has `timeout-minutes: 20` | Fixed (run 46079219114) |
| F12 | CI, all jobs (run 46043074202, at 3b7232d) | Lint, type check, tests and Compose all failed: `uv sync --locked` refused | Expected: PyJWT was added to `pyproject.toml` before `uv.lock` could be regenerated (the sandbox has no network); a temporary CI job produced the lockfile, checked by sha256 | Lockfile committed next | Expected red run, resolved in the next run |
| F13 | CI test (run 46080669546) | 3.4-19 errored (fixture `race_email` not found); 3.4-23 failed (disabled signup still in the OpenAPI document) | (1) Rewriting 3.4-03 deleted the fixture that sat between the two tests; (2) setting `include_in_schema` on the route after inclusion didn't reach the generated document | (1) Fixture restored; (2) the schema generator leaves switched-off paths out | Fixed (run 46080870382) |

## Gate

### 1. Automated: PASS
In the run linked at the top (counts and coverage are in its automatic report): lint,
`mypy --strict`, the migration checks (now including the 0003 backfill), every test against
real PostgreSQL 16 and Redis 7 above the 90 % coverage gate, and the Compose job (all earlier
checks plus the auth journey: signup, login with a spoofed `X-Forwarded-For`, refresh replay,
password change, no password or token in the container logs).

### 2. Tester: PASS
Every section covers C1–C12 or gives an N/A reason. Attack cases tested, not only happy
paths: forged / `none` / wrong-algorithm / wrong-audience tokens (3.1-02, 3.1-03), a refresh
token used as an access token (3.3-07), another user's `sid` (3.3-06), enumeration by signup,
login and timing (3.4-02, 3.4-06, 3.4-07), lockout under concurrency and lock extension
(3.4-09, 3.4-10), refresh replay and racing (3.5-02, 3.5-05), session max age (3.5-07),
another user's session id (3.6-04), secrets and emails in logs and audit (3.2-07, 3.3-12,
3.7-03..07).

### 3. User: PASS
Compose step "3.3-09, 3.4-17, 3.5-13, 3.6-12": a person signs up, logs in, sees their
profile and devices (with their real address, not a spoofed one), refreshes, has a stolen
refresh token replayed (everything revoked), logs in again and changes the password (old
refused, new accepted).

### 4. Cross-check vs old code (`main` @ `209a9bd`): PASS

| Old | New | Decision | Reason |
| --- | --- | --- | --- |
| Passwords: unsalted SHA-256 (`utils/jwt_config.py`) | Argon2id (RFC 9106) on a bounded pool; dummy verify for unknown emails; rehash on login | Fixed | Old hashes crackable; timing revealed accounts |
| Access token carried `role` and `organization_id`; `/users` trusted them | Token holds only `sub`, `sid`, `iat`, `exp`, `iss`, `aud`, `jti`, `typ`; user and live session re-read per request | Fixed | A demoted or removed user kept power until expiry |
| `expires_in=300` hard-coded while settings said otherwise | From `JWT__ACCESS_TTL_SECONDS` | Fixed | Clients refreshed on the wrong schedule |
| Refresh JWT and a stored refresh token (two mechanisms) | One opaque 256-bit refresh token, stored as SHA-256 | Simplified | The refresh JWT was never needed |
| Rotation revoked the old token; replaying it was just "invalid" | Families; a replayed rotated token revokes the family, audited | Added | A stolen refresh token went unnoticed |
| `revoke-others` passed session id `0`, so it also ended the current session | Keeps the current family (`sid`) | Fixed | Users signed themselves out |
| Logout needed the refresh token; the access token stayed valid until expiry | Logout with the access token; access ends at once (family check) | Improved | "Logged out" tokens kept working for minutes |
| `DELETE /sessions/{id}` by integer id | `POST /me/sessions/{id}/revoke` by family UUID, scoped to the user; others' ids are 404; another device needs the current password | Improved | Guessable ids |
| Session strategy chosen by the client per request (`login-with-session-control`) | Server setting `AUTH__SESSION_STRATEGY` | Fixed | Clients could pick the weakest policy |
| `login_attempts` / `locked_until` never used | Lockout (5 / 15 min), atomic counter, lock not extended by more failures, audited | Added | No brute-force protection (rate limits: step 4) |
| Signup answered "Email already exists" / "Username already exists" | Same 202 either way | Fixed | Account enumeration |
| Signup and login logged full emails (`auth_logger.signup_attempt(email=…)`) | Emails masked in every log line and audit entry | Fixed | Personal data in logs |
| `/debug-login`, `/debug-refresh` | Not recreated | Removed | Test-only routes in production |
| Many routes repeated the token check (`HTTPBearer` + `verify_token`) | One `get_current_user` | Fixed | One place to get it right |
| `request.client.host` stored as the IP | `client_info`; proxies trusted only via `FORWARDED_ALLOW_IPS` | Improved | Spoofable or wrong behind a proxy |
| Role-based `GET /users` inside the auth router | Not in step 3 (admin endpoints: step 7) | Moved | Belongs to administration |
| `GET /users/{user_id}` in the auth router | Not in step 3: admin user lookup is step 7, members of an organization step 5 | Moved | Not authentication; needs permissions |
| `GET /auth/sessions` (`list[SessionInfo]`) and `GET /auth/sessions/info` | `GET /me/sessions` (paged, current one marked) | Replaced | One way to list sessions |
| `session_info` inside token responses (`TokenResponse.session_info`) | Not returned: the token response holds only tokens and lifetimes; `GET /me/sessions` describes sessions | Dropped | One shape per answer; session details aren't needed to use a token |
| Server-side auto-refresh service and middleware (`auto_refresh_service.py`, `auto_refresh_middleware.py`) | Not recreated: clients refresh explicitly with the refresh token | Dropped | Silently renewing on the server hides token theft from reuse detection and keeps stolen access alive |
| `/auth/health` in the auth router | `/health/live` and `/health/ready` (step 1) | Replaced | Health is not an auth concern |
| Per-route rate-limit dependency on login and refresh (`rate_limit_dependency.py`) | Not in step 3; GCRA limits are step 4 | Moved (carried, see below) | The old limiter was incorrect (see step 4 fixes); lockout covers brute force meanwhile |

### 5. Independent review

- Round 1 (commit 1c09104): **FAIL**, 8.6/10, four High findings. Verbatim:
  [reviews/step-3-round-1.md](reviews/step-3-round-1.md). Resolution below.
- Round 2 (commit 763a29a): **FAIL**, 8.9/10, one High finding. Verbatim:
  [reviews/step-3-round-2.md](reviews/step-3-round-2.md). Resolution below.
- Round 3 (commit 5270ef5): **FAIL**, 8.9/10, two High findings. Verbatim:
  [reviews/step-3-round-3.md](reviews/step-3-round-3.md). Resolution below.
- Round 4 (commit af8ddf9): **FAIL**, 8.9/10, one High finding. Verbatim:
  [reviews/step-3-round-4.md](reviews/step-3-round-4.md). Resolution below.
- Round 5: pending.

**Round 1 resolution**

| # | Resolution |
| --- | --- |
| H1 | Totals recounted to 106 (89 planned + 17 added, each marked), with passed / failing / fixed totals |
| H2 | 3.8 renumbered: one id per test function, variants as parameters |
| H3 | Query moved to `UserRepository.get_authenticated` (still one query, 3.3-11) |
| H4 | ASVS V2/V3 table added below; items not met are carried to a named step |
| M1 | 3.8-06: locked while hashing; `me.py` now 100 % covered |
| M2 | Status re-checked under the lock (`can_log_in`); 3.8-07 |
| M3 | F10 added |
| M4 | Five cross-check rows added |
| M5 | Recorded as a Definition-of-Done exception carried to step 4 (below) |
| L1 | One entry point, `auth.lock_user`; callers check status and deletion (`can_log_in`) |
| L2 | `FOR NO KEY UPDATE` (`with_for_update(key_share=True)`) |
| L3 | Removed user: failure count skipped, refusal audited without an actor, 401 not 500; 3.8-09 (no hard-delete path yet; step 7 re-tests it) |
| L4 | Waiter matched by its blocker's lock on `users`; still a 10 ms poll of PostgreSQL state (no event exists), bounded and documented |
| L5 | 3.8-10 is now a real-stack Compose journey; C12 is 3.8-11 |
| L6 | `auth.password_change_failed` and `auth.password_change_refused` (also for the locked pre-check) |
| L7 | `SessionOut.of(row, current_family=...)` |
| L8 | Kept, documented in ARCHITECTURE §2: `core/deps.py` is the FastAPI glue and the one place that calls `auth.authenticate` |
| L9 | Outside an `Authorization:` header, the scheme word is masked only before a credential-like value (digit/symbol or 16+ chars); 3.7-05/06 cases added |
| L10 | Dummy hash made when the hashing pool starts |
| Missing scenarios | Added: 3.8-01 variants (end session, revoke-others), 3.8-06, 3.8-07, 3.8-08, 3.8-09, 3.8-10, 3.5-15, 3.6-14, 3.4-20, 3.4-21. Hard delete through an API: step 7 |

**Round 2 resolution**

| # | Resolution |
| --- | --- |
| H1 | V2.4.5 added: carried to step 9 with the reason (rotation and loss); V2.2.2 has its own N/A row; closing sentence lists all five carried items |
| M1 | `no_store` dependency on the `/api/v1` router; 3.4-22 checks every route kind; ASVS V8.2.1 row |
| M2 | Quoted values redacted to their closing quote (escapes handled); prefixed keys (`new_password`); 3.7-05 cases |
| M3 | ROADMAP step 4: per-IP limits on signup and login against the signup-then-login probe; step 6: login refused until verified (or "account exists" mail) so 3.4-24 passes; step 7: hard-delete re-test (3.8-09) and audit of unknown-email failures. Design decision reworded |
| L1 | Comment on the `Any` |
| L2 | Hashing pool (and dummy hash) started with `asyncio.to_thread` in the lifespan and the CLI |
| L3 | Zone id dropped; 3.3-14 covers names and blanks (deps.py `ValueError` branch now run) |
| L4 | F12 (expected red run) |
| L5 | 3.5-15 is refresh only; 3.5-16 and 3.6-15 fail the database inside the writes |
| L6 | SQLSTATE 23505 plus exact `constraint_name` from the driver; unit cases (a longer name, wrong SQLSTATE) and a real CHECK violation through signup (re-raise branch run) |
| L7 | Docs say `AUTH__SIGNUP_ENABLED`; a switched-off signup is left out of OpenAPI (3.4-23) |
| L8 | 3.8-09 asserts the audit rows |
| L9 | README: refresh is single-flight per session; a retried or parallel refresh with the same token ends the session |
| L10 | Names split into words; last word or last pair decides; 3.7-03 and 3.7-09 cases |
| L11 | Recorded as an accepted exception in `docs/milestones/README.md` (testing rules) |
| L12 | Carried to step 7 (ROADMAP) |
| Missing scenarios | 3.3-14, 3.4-22..24, 3.5-16, 3.6-15, 3.6-16, 3.7-05/09 cases, 3.8-09 assertion, 3.8-12 |

**Round 3 resolution**

| # | Resolution |
| --- | --- |
| H1 | Session limits are ISO 8601 durations (`AUTH__REFRESH_TTL`, `AUTH__SESSION_MAX_AGE`, 5 min–90 days / up to 365 days); level 2 values tested at the boundaries (3.5-17). Defaults kept at level 1 and the V3.3.4 deviation decided in ADR-0010; ASVS rows and closing sentence say exactly that |
| H2 | Length counted after runs of whitespace are combined and the ends stripped (ASVS wording); padded cases in 2.6-04, 3.4-03, 3.6-08 |
| M1 | `problem_response` adds the same headers (shared `NO_STORE_HEADERS`); 3.4-22 checks two 401s and a 422 |
| L1 | Prefixed-key redaction removed from the step 8 ROADMAP item and the carry notes |
| L2 | "12 fixed (F1–F11, F13), 1 expected red run (F12)" |
| L3 | `xfail(strict=True, raises=AssertionError)`; a signup that isn't 202 calls `pytest.fail` (a real failure) |
| L4 | `created_at = max(now, family_started_at)` for every refresh row; 3.5-19 |
| L5 | One-line comments for `JWT__ISSUER` and `JWT__AUDIENCE` |
| L6 | Hidden path from `app.url_path_for("signup")` |
| L7 | A failing commit after a failed unit of work is logged (warning, error type only) before the rollback |
| L8 | Two cross-check rows (`GET /auth/sessions`, `session_info`) |
| Missing scenarios | Padded passwords; level 2 limits (3.5-17); V3.3.4 recorded as a deviation; no-store on errors; refresh vs `limit_sessions` login (3.8-12 variant); failed rotation rolls back (3.5-18); clock skew (3.5-19) |

**Round 4 resolution**

| # | Resolution |
| --- | --- |
| H1 | Option (b), no change to VISION scope: ADR-0011 supersedes ADR-0010. Defaults are level 2 (30 min idle and 12 h absolute; re-auth to end other sessions on); products may opt down by settings. Ending one other session moved from `DELETE` to `POST /me/sessions/{id}/revoke` (a body on `DELETE` has no defined meaning, RFC 9110). Tests 3.5-17, 3.6-17, 3.6-18, 3.8-10 |
| M1 | ADR-0011, `.env.example` and the config comment say level 2 needs **both** limits |
| M2 | `Settings` refuses `AUTH__REFRESH_TTL` below twice `JWT__ACCESS_TTL_SECONDS`; 3.1-12 |
| L1 | V3.3.4 row rewritten (now passes by default); V2.4.2 replaces 2.4.4; N/A rows for V3.2.3 and V3.5.1 |
| L2 | Format characters (Cf: zero-width space, soft hyphen) not counted; message says so; 2.6-04 cases |
| L3 | 3.2-11 |
| L4 | Totals row attributes 3.8-06..10 to review round 1 |
| L5 | 3.5-17: refresh at 12 h − 1 s (200) and 12 h (401), access token at 12 h (401), idle at 30 min − 1 s (200) and 30 min (401) |
| L6 | 3.5-18 makes the database refuse the INSERT itself (CHECK at flush) |
| Missing scenarios | All six added (3.1-12, 3.5-17, 2.6-04, 3.5-18, 3.2-11, 3.6-17/18). Consequence recorded in ADR-0011: re-auth is refused while the account is locked (no password oracle), so a lock also blocks ending other sessions; step 4's limits keep the lockout from being used against the owner |

### ASVS 4.0.3 (roadmap exit criterion), level 2, for these flows

| Item | Requirement (short) | Status | Evidence |
| --- | --- | --- | --- |
| V2.1.1 / 2.1.2 | Passwords ≥ 12 characters after runs of spaces are combined (invisible format characters not counted, review round 4); at least 64 allowed (128 here) | Pass | `check_password_rules` collapses whitespace before counting (review round 3); 2.6-04, 3.4-03, 3.6-08 padded cases |
| V2.1.3 | No truncation | Pass | Whole password hashed (Argon2 has no 72-byte limit); 3.4-20 |
| V2.1.4 | Any printable Unicode, incl. spaces and emoji | Pass | NFKC; only control characters refused (`security.py`) |
| V2.1.5 / 2.1.6 | Users can change their password; needs current and new | Pass | `POST /me/password`; 3.6-06, 3.6-07 |
| V2.1.7 | Check against breached passwords | **Carried to step 9** | Needs a local breached-password list or k-anonymity service (new dependency; owner decision) |
| V2.1.8, 2.1.11, 2.1.12 | Strength meter, paste, show password | N/A | Client UI concerns; the API accepts any allowed password |
| V2.1.9 / 2.1.10 | No composition rules; no forced rotation | Pass | Length-only rules; no expiry |
| V2.2.1 | Anti-automation against credential stuffing and brute force | **Partial; rate limits carried to step 4** | Lockout 3.4-08/10, also on password change 3.8-03; per-IP/email limits are step 4 |
| V2.2.2 | Weak authenticators (SMS, email OTP) not used as a primary factor | N/A | Passwords only; no SMS or email authenticators exist |
| V2.2.3 | Notify after a credential change | **Carried to step 6** (email) | Password-change audit entry exists now |
| V2.2.4–2.2.7, V2.7, V2.8 | MFA, phishing resistance, OTP | Out of scope | VISION backlog (version 2) |
| V2.4.1 / 2.4.2 | Salted, approved, memory-hard hash with tuned cost; salt of at least 32 bits | Pass | Argon2id, RFC 9106 low-memory profile, 128-bit random salt per hash; rehash on login 3.4-11 (V2.4.4 is bcrypt-only: N/A) |
| V2.4.5 | An extra iteration with a secret salt ("pepper") kept apart from the hashes | **Carried to step 9** (decision) | Not done in step 3, on purpose: a pepper without key versioning can never be rotated, and losing it makes every password unrecoverable. Step 9 adds it with a key id in the stored hash, rotation through rehash-on-login, and an ADR |
| V8.2.1 | Anti-caching headers on sensitive responses | Pass | `Cache-Control: no-store` on every `/api/v1` answer, errors included (3.4-22) |
| V2.5.1 / 2.5.6 | Recovery never sends the password; secure reset | **Carried to step 6** | Reset is step 6 |
| V2.5.2 / 2.5.4 | No secret questions; no default or shared accounts | Pass | None exist; `create-admin` requires a password (step 2) |
| V2.10.4 | Secrets not in source | Pass | JWT secret from settings, safety check per algorithm (3.1-12) |
| V3.1.1 | Tokens never in URLs | Pass | Header and JSON body only |
| V3.2.1 / 3.2.2 / 3.2.4 | New session per login; ≥ 64 bits; approved generator | Pass | New family per login; 256-bit `token_urlsafe`; 3.1-06/07 |
| V3.2.3 | Tokens stored safely in the browser | N/A | Client concern; the API returns tokens only in response bodies, never cookies or URLs |
| V3.3.1 | Logout invalidates the session | Pass | 3.5-08, 3.5-10, 3.6-14 |
| V3.3.2 | Re-authentication when actively used and after an idle period (L2: 12 h and 30 min idle) | Pass (defaults) | `AUTH__SESSION_MAX_AGE=PT12H` and `AUTH__REFRESH_TTL=PT30M` by default, refresh outlives access (validated); boundaries in 3.5-17, validator in 3.1-12 (ADR-0011). Longer values are a product's opt-down to L1 |
| V3.3.3 | Option to end all other sessions after a password change | Pass (automatic) | 3.6-06, 3.8-04 |
| V3.3.4 | Users can see their sessions and, after re-entering credentials, end any or all | Pass (defaults) | Listing 3.6-02; ending another device, revoke-others and logout-all need the current password, missing 422 / wrong 401 counted (3.6-17, 3.8-10); ending this session needs none (3.6-18). `AUTH__REAUTH_TO_END_SESSIONS=false` is a product's opt-down (ADR-0011) |
| V3.4.x | Cookie attributes | N/A | Bearer tokens, no cookies |
| V3.5.1 | Users can revoke OAuth tokens given to linked apps | N/A | No OAuth authorization server or linked apps |
| V3.5.2 / 3.5.3 | Session tokens not static keys; signed and tamper-checked stateless tokens | Pass | Rotation; HS* with algorithm pinned, all claims required (3.1-02/03) |
| V3.7.1 | Re-authentication before sensitive changes | Pass | Current password required for password change |

Every level 2 item this step owns passes with the default settings (ADR-0011; ADR-0010's
level 1 defaults and V3.3.4 deviation are superseded). A product can opt down to level 1
for V3.3.2 and V3.3.4 through settings. The five items the step doesn't own (V2.1.7, V2.2.1
rate limits, V2.2.3, V2.4.5, V2.5) each have a named step in the ROADMAP.

### 6. Security audit: PASS (after fixes)

Vendored `security-audit` skill, full audit mode, profile `quick` scoped to the step 3 auth
code (signup, login, refresh, logout, `/me`, tokens, dependencies, logging and audit,
migration 0003, CLI), 12 agent calls: 4 reconnaissance, 3 hunters, 1 coverage critic,
4 independent verifiers. Output kept outside the repository. No target code ran inside the
audit, so all four candidates came back *needs validation*; each was then validated here
with a failing test and fixed (F8). The critic's four uncovered units were handled after the
run: migration backfill (defect found and fixed, F9); logout / logout-all (now under the
per-user lock, 3.8-01); `create-admin` (local operator command, reviewed: no new exposure
since step 2); login refusal parity (same status, code and body for every refusal, one
Argon2 verify each, 3.4-06/07).

| Finding | Severity (my assessment) | Fix | Test |
| --- | --- | --- | --- |
| Refresh in flight survives logout-all / password change; refresh vs password change deadlock | High | Per-user lock order | 3.8-01, 3.8-10 |
| Login racing a password change keeps a session, can restore the old password | High | Verified hash re-checked under the lock; rehash only if unchanged | 3.8-02 |
| Password change ignores the lockout (guessing with a stolen access token) | High | Refused while locked, before and after hashing | 3.8-03, 3.8-06, 3.8-10 |
| Stale password change undoes the owner's remedy | Medium | Hash, session, status and lock re-checked under the lock | 3.8-04, 3.8-07 |
| Migration 0003 aborts on tied timestamps | Low (availability of the upgrade) | Tie broken by id | 3.2-10 |

Open hardening notes, not vulnerabilities, carried forward: rate limits on login, refresh
and password change, and lockout used to block an owner (step 4); signup-then-login and small
timing differences as an account probe (steps 4 and 6); `hide_parameters` on the engine
(step 8, observability). Redaction of prefixed keys was done in review round 2 (3.7-05).

## Carried forward

- From step 1: R3-03 (499 on disconnect) and R5-03 (redaction) — section 3.7.
- From step 2: R1-08 + R2-03 (bounded hashing, no idle connection) — design decisions above,
  3.1-08, 3.4; R1-18 (IDN) — ADR-0009, 3.1-11; `last_login_at` — 3.2-01, 3.4-05; R3-06 and the
  HTTP signup race — 3.4-10, 3.4-02.

**Carried out of step 3**

- **Definition-of-Done exception (review M5), to step 4:** the step 3 endpoints have no
  rate-limit policy yet. Step 4 adds limits on signup, login, refresh and password change,
  and protection against lockout used to keep an owner out (a stolen access token can lock
  the account through wrong guesses at `/me/password`). ROADMAP step 4 lists both.
- To step 6: ASVS V2.2.3 (notify after credential change), V2.5 (password reset).
- To step 7: a hard-deleted user between read and lock (review L3) is handled (3.8-09) but
  re-tested once admin deletion exists.
- To step 8: engine `hide_parameters=True` (audit hardening note).
- To step 9: ASVS V2.1.7 (breached-password check) and V2.4.5 (versioned pepper, with an ADR).
- To steps 4 and 6: the signup-then-login account probe (3.4-24, strict expected failure).
- To step 7: audit (or count) failed logins for unknown emails, with a masked email.
