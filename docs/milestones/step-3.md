# Milestone 3: Authentication core

- PR: #5
- Latest CI run (automatic report): https://github.com/Husky1711/fastapi-user-management/actions/runs/46053102591
- Verdict: **GATE IN PROGRESS** (all sections ✅)

Scenario plans below were written **before** the code (process rule). Ids map to test names
`test_s3_<section>_<nn>_...`; *CI step* means a named step in the CI workflow.

## Section log

| # | Section | Status | Scenarios (pass / total) | Notes |
| --- | --- | --- | --- | --- |
| 3.1 | Token and password primitives: JWT, opaque tokens, bounded hashing, dummy verify | ✅ | 14 / 14 | CI run 46044586029 |
| 3.2 | Auth data: migration 0003, session and audit repositories | ✅ | 9 / 9 | CI run 46046371009 |
| 3.3 | Request dependencies: `client_info`, `get_current_user` | ✅ | 13 / 13 | CI run 46047567713 (3.3-09 also on the real stack in 3.6-12) |
| 3.4 | Signup and login: lockout, rehash, session strategies | ✅ | 19 / 19 | CI run 46049595954; 3.4-17 in run 46051473324 |
| 3.5 | Refresh rotation, reuse detection, logout, logout-all | ✅ | 14 / 14 | CI run 46050265813; 3.5-13 in run 46051473324 |
| 3.6 | `/me`: profile, sessions, revoke, revoke-others, change password | ✅ | 13 / 13 | CI run 46051473324 |
| 3.7 | Carried from step 1: 499 on client disconnect, broader log redaction | ✅ | 8 / 8 | CI run 46052631869 |
| | **Total** | | **90 / 90** | 89 planned + 1 added (3.4-19) |

## Design decisions for this step

- **`sid` is the session family.** A login starts a family; each refresh rotates to a new row
  in the same family. The access token's `sid` is the `family_id`, and `get_current_user`
  checks that the family still has an active row, so logout and revocation end access at the
  next request instead of when the access token expires (one indexed query per request).
- **Revocation has a reason** (`sessions.revoked_reason`: `rotated`, `logout`, `logout_all`,
  `revoked`, `replaced`, `password_changed`, `reuse_detected`). A presented refresh token
  whose row was `rotated` is reuse: the whole family is revoked and audited. Other revoked
  tokens are just invalid.
- **Signup never reveals whether an email exists**: same status (202), body and work
  (a password hash) either way. It returns no tokens; the client logs in next.
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
| 3.1-12 | C10 | JWT settings: issuer, audience, TTL bounds; secret shorter than the HMAC output (32/48/64 bytes for HS256/384/512) | Invalid values refused; short secret is a production safety problem | test | ✅ |
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
| — | C5 | N/A here: authorization (permissions) is step 5 | | | |
| — | C7, C8 | Covered by 3.5 (concurrent refresh / repeated logout) | | | |

### Section 3.4: Signup and login

| Id | Cat. | Scenario | Expected | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| 3.4-01 | C1 | Signup with a new email | 202; user created (not verified, not admin) | test | ✅ |
| 3.4-02 | C6 | Signup with an existing email (any case) | Same 202 and body; no change to the existing user | test | ✅ |
| 3.4-03 | C2 | Signup with a weak password, invalid email, extra fields, missing fields | 422 with stable codes; nothing created | test | ✅ |
| 3.4-04 | C1 | Signup disabled (`AUTH__SIGNUP_ENABLED=false`) | 404 (the route behaves as absent) | test | ✅ |
| 3.4-05 | C1 | Login with the right password | 200; access + refresh token, `token_type`, `expires_in` from settings; `last_login_at` set; counter reset | test | ✅ |
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
| 3.5-07 | C3 | Refresh keeps a session alive, but not forever | Each rotation gets a fresh TTL, capped at `AUTH__SESSION_MAX_AGE_DAYS` from the family's first login; past the cap, 401 | test | ✅ |
| 3.5-08 | C1 | Logout | Current family revoked (`logout`); access token stops working immediately | test | ✅ |
| 3.5-09 | C8 | Logout twice | Second call 401 (token's session gone), nothing else changes | test | ✅ |
| 3.5-10 | C1 | Logout-all | Every family of the user revoked (`logout_all`); other users untouched | test | ✅ |
| 3.5-11 | C4 | Logout without a token | 401 | test | ✅ |
| 3.5-12 | C10 | Refresh after the user was disabled | 401; no new session | test | ✅ |
| 3.5-13 | C11 | Real stack: login, refresh twice, replay the first refresh token, everything revoked | As stated | CI step (Compose) | ✅ |
| 3.5-14 | C12 | Earlier tests still pass | CI green | CI run | ✅ |
| — | C5 | N/A: a user acts only on their own sessions (3.2-05 covers cross-user) | | | |
| — | C9 | Covered by 3.4-16 (same service path) | | | |

### Section 3.6: `/me`

| Id | Cat. | Scenario | Expected | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| 3.6-01 | C1 | `GET /me` | Own profile (`id`, `email`, `full_name`, `email_verified`, `created_at`); no hash, no counters | test | ✅ |
| 3.6-02 | C1 | `GET /me/sessions` | Own active sessions, paged, current one marked; no token hashes | test | ✅ |
| 3.6-03 | C1 | `DELETE /me/sessions/{id}` | 204; that family revoked (`revoked`) | test | ✅ |
| 3.6-04 | C5, C6 | Delete another user's session id; unknown id; malformed id | 404 (not 403); 404; 422 | test | ✅ |
| 3.6-05 | C1 | `POST /me/sessions/revoke-others` | Every other family revoked; the current one keeps working | test | ✅ |
| 3.6-06 | C1 | `POST /me/password` with the right current password | 204; new hash; other sessions revoked (`password_changed`); current kept | test | ✅ |
| 3.6-07 | C4 | Change password with a wrong current password | 401-style refusal (`auth.invalid_credentials`), counts toward lockout | test | ✅ |
| 3.6-08 | C2 | New password weak, same as the old one, or missing | 422 with stable codes | test | ✅ |
| 3.6-09 | C4 | Every `/me` route without a token | 401 | test | ✅ |
| 3.6-10 | C8 | Revoke-others twice | Second call revokes nothing, still 204 | test | ✅ |
| 3.6-11 | C3 | Sessions list with 0, 1 and limit+1 sessions | Correct pages | test | ✅ |
| 3.6-12 | C11 | Real stack: change password, old password refused, new accepted | As stated | CI step (Compose) | ✅ |
| 3.6-13 | C12 | Earlier tests still pass | CI green | CI run | ✅ |
| — | C7 | Covered by 3.5-05 (session races) | | | |
| — | C9, C10 | Covered by 3.4-16 and the unit-of-work tests of step 2 | | | |

### Section 3.7: Carried from step 1

| Id | Cat. | Scenario | Expected | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| 3.7-01 | C9 | Client disconnects while a JSON-body route reads its body | Logged with status 499, not 400; no error response attempted | test | ✅ |
| 3.7-02 | C1 | Normal JSON request | Unchanged (200/422 as before) | test | ✅ |
| 3.7-03 | C6 | Log fields named like secrets (`password`, `token`, `secret`, `authorization`, `api_key`, …), any case | Value replaced by `[REDACTED]` | test | ✅ |
| 3.7-04 | C6 | Secret values that aren't strings (numbers, lists, nested dicts) | Redacted | test | ✅ |
| 3.7-05 | C6 | `key: value`, `key=value` and `Authorization: Bearer …` inside messages | Value redacted | test | ✅ |
| 3.7-06 | C2 | Messages that only mention the words ("password reset sent") | Not mangled | test | ✅ |
| 3.7-07 | C1 | Login and refresh logs | Never contain the password or a token (whole flow) | test | ✅ |
| 3.7-08 | C12 | Earlier tests still pass | CI green | CI run | ✅ |
| — | C3, C4, C5, C7, C8, C10, C11 | N/A: logging behaviour, no auth, state or flow of its own | | | |

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
| `DELETE /sessions/{id}` by integer id | By family UUID, scoped to the user; others' ids are 404 | Improved | Guessable ids |
| Session strategy chosen by the client per request (`login-with-session-control`) | Server setting `AUTH__SESSION_STRATEGY` | Fixed | Clients could pick the weakest policy |
| `login_attempts` / `locked_until` never used | Lockout (5 / 15 min), atomic counter, lock not extended by more failures, audited | Added | No brute-force protection (rate limits: step 4) |
| Signup answered "Email already exists" / "Username already exists" | Same 202 either way | Fixed | Account enumeration |
| Signup and login logged full emails (`auth_logger.signup_attempt(email=…)`) | Emails masked in every log line and audit entry | Fixed | Personal data in logs |
| `/debug-login`, `/debug-refresh` | Not recreated | Removed | Test-only routes in production |
| Many routes repeated the token check (`HTTPBearer` + `verify_token`) | One `get_current_user` | Fixed | One place to get it right |
| `request.client.host` stored as the IP | `client_info`; proxies trusted only via `FORWARDED_ALLOW_IPS` | Improved | Spoofable or wrong behind a proxy |
| Role-based `GET /users` inside the auth router | Not in step 3 (admin endpoints: step 7) | Moved | Belongs to administration |

### 5. Independent review

Pending.

### 6. Security audit

Pending.

## Carried forward

- From step 1: R3-03 (499 on disconnect) and R5-03 (redaction) — section 3.7.
- From step 2: R1-08 + R2-03 (bounded hashing, no idle connection) — design decisions above,
  3.1-08, 3.4; R1-18 (IDN) — ADR-0009, 3.1-11; `last_login_at` — 3.2-01, 3.4-05; R3-06 and the
  HTTP signup race — 3.4-10, 3.4-02.
