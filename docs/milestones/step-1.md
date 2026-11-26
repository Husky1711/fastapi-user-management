# Milestone 1: Project skeleton & tooling

- PR: https://github.com/Husky1711/fastapi-user-management/pull/2
- Latest CI run (automatic report): https://github.com/Husky1711/fastapi-user-management/actions/runs/45887647468
  (120 tests passed, 6 skipped in the Test job, which are the e2e tests that run in the Compose job; 6 user
  scenarios passed on the real stack; coverage 97.8 %; open "Summary" for every result)
- Verdict: **IN PROGRESS**. All sections ✅; gate checks 1–4 PASS; check 5 rounds 1 and 2 FAILED
  (`reviews/`), all their findings addressed or carried below; round 3 pending.

> Process note: the testing process was introduced partway through this step, so the first
> scenario plans were written after the first version of the code. The round 1 review found
> the gaps this caused; the plans below are the corrected ones. From step 2 on, each
> section's plan is written before its code.

## Section log

| # | Section | Status | Scenarios (pass / total) | Notes |
| --- | --- | --- | --- | --- |
| 1.1 | Clean branch and tooling | ✅ | 5 / 5 | Old code removed from `v2`; stays on `main` |
| 1.2 | Settings and safety checks for strict environments | ✅ | 23 / 23 | Staging now strict as well |
| 1.3 | Logging and request middleware | ✅ | 32 / 32 | |
| 1.4 | Error format (RFC 9457) | ✅ | 16 / 16 | Error boundary moved inside CORS |
| 1.5 | Health probes, readiness cache, infrastructure clients | ✅ | 19 / 19 | |
| 1.6 | Docker, Compose, CI and automatic test report | ✅ | 9 / 9 | |
| | **Total** | **✅** | **104 / 104** | |

## Scenario plan and results

- **Id** = scenario id. Automated tests carry it in their name: `test_s1_<section>_<nn>_...`.
- **Evidence**: *test* = pytest (unit / integration / e2e), visible in the CI run's automatic
  report; *CI step* = a named step in the Compose job of the same run.
- ✅ = passing in the CI run linked above.
- **C4 (authentication) and C5 (authorization) are N/A for the whole step**: no endpoint in
  step 1 needs a user. They start in step 3.

### Section 1.1: Clean branch and tooling

| Id | Cat. | Scenario | Expected | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| 1.1-01 | C1 | Fresh checkout installs; lint, type check and tests run | All succeed | CI jobs Lint, Type check, Test | ✅ |
| 1.1-02 | C6, C10 | `.env`, `.env.production`, `.env.staging`, `.env.local` can't be committed; `.env.example` is committed | Ignored / tracked | test `s1_1_02` (git check-ignore) | ✅ |
| 1.1-03 | C11 | New developer follows the README quick start: `cp .env.example .env`, then the stack (`make run` is `docker compose up --build`; CI runs it detached) with no other overrides | Stack starts healthy; ready 200 | CI step "1.1-03" | ✅ |
| 1.1-04 | C10 | No old code left on the branch | None present | test `s1_1_04` | ✅ |
| 1.1-05 | C12 | Every test still passes on every push | CI green | CI run | ✅ |
| — | C2, C3 | N/A: configuration files only; no runtime input | | | |
| — | C7, C8, C9 | N/A: static repository files; no concurrent use, repeat effect or dependency | | | |

### Section 1.2: Settings and safety checks for strict environments

| Id | Cat. | Scenario | Expected | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| 1.2-01 | C1 | Development defaults | Accepted; docs on | test `s1_2_01` | ✅ |
| 1.2-02 | C1 | Safe staging and production settings | Accepted; docs off | test `s1_2_02` (×2) | ✅ |
| 1.2-03 | C6 | Default JWT secret in staging / production | Rejected | test `s1_2_03` (×2) | ✅ |
| 1.2-04 | C3 | JWT secret of 31 / 32 / 33 characters | 31 rejected; 32 and 33 accepted | test `s1_2_04` (×3) | ✅ |
| 1.2-05 | C6 | `DEBUG=true` in a strict environment | Rejected | test `s1_2_05` | ✅ |
| 1.2-06 | C6 | Default DB credentials in a strict environment | Rejected | test `s1_2_06` | ✅ |
| 1.2-07 | C6 | Several problems at once | All reported together | test `s1_2_07` | ✅ |
| 1.2-08 | C3 | Development and test with unsafe values | Allowed (checks apply only to strict environments) | test `s1_2_08` (×2) | ✅ |
| 1.2-09 | C6 | `CORS *` with credentials | Rejected in every environment | test `s1_2_09` | ✅ |
| 1.2-10 | C3 | Edge of the CORS rule: `*` with credentials off | Allowed | test `s1_2_10` | ✅ |
| 1.2-11 | C2 | Nested values and JSON lists from env vars | Parsed | test `s1_2_11` | ✅ |
| 1.2-12 | C2, C6 | Invalid env values: `ENVIRONMENT=prod`, pool 0 / 101 / "five", `LOG__LEVEL=verbose`, malformed CORS JSON, `JWT__ALGORITHM=none` / `RS256`, timeout 0, unknown nested key | Startup stops with a validation error | test `s1_2_12` (×10) | ✅ |
| 1.2-13 | C3 | Pool size at its limits 1 and 100 | Accepted | test `s1_2_13` (×2) | ✅ |
| 1.2-14 | C6 | Settings printed or dumped | Secret not visible | test `s1_2_14` | ✅ |
| 1.2-15 | C6 | Production set only through real env vars | Detected as unsafe | test `s1_2_15` | ✅ |
| 1.2-16 | C2 | Unrelated `VERSION` env var (set by many CI systems) | App and API-schema version unchanged | tests `s1_2_16` (×2) | ✅ |
| 1.2-17 | C6 | JWT algorithm limited to HMAC | HS512 accepted (none / RS256 rejected in 1.2-12) | test `s1_2_17` | ✅ |
| 1.2-18 | C6, C10 | Changing settings after the safety check (nested field, top level, origin list) | Refused | test `s1_2_18` | ✅ |
| 1.2-19 | C11 | App built with unsafe staging / production settings | Refuses to start | test `s1_2_19` (×2) | ✅ |
| 1.2-20 | C11 | Real container started as production with the default JWT secret and the default DB credentials | Exits non-zero, naming both problems | CI step "1.2-20" (greps both messages) | ✅ |
| 1.2-21 | C11 | Real container started as production with safe settings (strong secret, dedicated DB role) | Ready 200; HSTS sent; `/docs` and `/openapi.json` 404 | CI step "1.2-21" | ✅ |
| 1.2-22 | C8 | Settings requested repeatedly | Loaded once, same object | test `s1_2_22` | ✅ |
| 1.2-23 | C12 | Earlier tests still pass | CI green | CI run | ✅ |
| — | C7 | N/A: loaded once at startup before any request, then immutable (1.2-18); no shared mutable state | | | |
| — | C9 | N/A: loading reads only env vars and a local file; no network dependency | | | |

### Section 1.3: Logging and request middleware

| Id | Cat. | Scenario | Expected | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| 1.3-01 | C1 | Structured fields and request id in a log line | Present | test `s1_3_01` | ✅ |
| 1.3-02 | C3 | Logging outside any request | No request id key | test `s1_3_02` | ✅ |
| 1.3-03 | C1 | Exception logging | Traceback included | test `s1_3_03` | ✅ |
| 1.3-04 | C1 | Every level | debug, warning, error | test `s1_3_04` (×3) | ✅ |
| 1.3-05 | C1 | JSON on stdout; uvicorn duplicate access log off | As described | test `s1_3_05` | ✅ |
| 1.3-06 | C8 | Logging configured twice | Exactly one app handler; other handlers kept | test `s1_3_06` | ✅ |
| 1.3-07 | C6 | Fields named `message`, `level`, `request_id`, `timestamp` | Can't overwrite; stored as `field_*`; no crash | test `s1_3_07` | ✅ |
| 1.3-08 | C1 | No incoming request id | 32-char id generated | test `s1_3_08` | ✅ |
| 1.3-09 | C1 | Valid incoming request id | Kept | test `s1_3_09` | ✅ |
| 1.3-10 | C2, C6 | Empty, spaces, 65 chars, `<script>`, `a/b` | Replaced | test `s1_3_10` (×5) | ✅ |
| 1.3-11 | C3 | Request id of exactly 1 and 64 chars | Kept | test `s1_3_11` (×2) | ✅ |
| 1.3-12 | C2 | Lower-case header name | Honoured | test `s1_3_12` | ✅ |
| 1.3-13 | C2 | Two `X-Request-ID` headers | First one used | test `s1_3_13` | ✅ |
| 1.3-14 | C2 | Non-ASCII header bytes | Replaced with an ASCII id | test `s1_3_14` | ✅ |
| 1.3-15 | C7 | 25 concurrent requests with different ids (error path); smoke test, see 1.3-30 | No id leaks between requests | test `s1_3_15` | ✅ |
| 1.3-16 | C6 | Secrets in `Authorization` and query string; very long user agent | One access line per request; no secrets; user agent logged, cut at 256 chars | tests `s1_3_16` (×2) | ✅ |
| 1.3-17 | C1 | Security headers on success | nosniff, DENY, no-referrer, CSP; no HSTS outside strict envs | test `s1_3_17` | ✅ |
| 1.3-18 | C6 | Security headers on 404 and 500 | Present | test `s1_3_18` | ✅ |
| 1.3-19 | C6 | Docs page | Exempt from the API CSP | test `s1_3_19` | ✅ |
| 1.3-20 | C6 | Staging and production | HSTS sent; docs and schema 404 | test `s1_3_20` (×2) | ✅ |
| 1.3-21 | C6 | CORS for allowed vs other origin | Allowed one only; `X-Request-ID` exposed | test `s1_3_21` | ✅ |
| 1.3-22 | C6 | CORS preflight | Request id and security headers present | test `s1_3_22` | ✅ |
| 1.3-23 | C3 | Non-HTTP traffic (lifespan) | Passed through untouched | test `s1_3_23` | ✅ |
| 1.3-24 | C9 | Request cancelled (e.g. server shutdown) | Logged as 499, not 500; cancellation propagates | test `s1_3_24` | ✅ |
| 1.3-25 | C11 | Client traces its own request id on the real server | Same id back | e2e `s1_3_25` | ✅ |
| 1.3-26 | C11 | Real server's security headers | Present, incl. CSP | e2e `s1_3_26` | ✅ |
| 1.3-27 | C1 | Clock | Timezone-aware UTC | test `s1_3_27` | ✅ |
| 1.3-28 | C12 | Earlier tests still pass | CI green | CI run | ✅ |
| 1.3-29 | C9 | Client disconnects while the app reads its request body | Nothing sent; logged as 499; no ERROR log | test `s1_3_29` | ✅ |
| 1.3-30 | C7 | Request id context after a request, same task | Reset to none (a missing reset would leak ids between requests) | test `s1_3_30` | ✅ |
| 1.3-31 | C9, C6 | A layer outside the error boundary fails | Clean 500 problem JSON with request id; internal text hidden; logged once | test `s1_3_31` | ✅ |
| 1.3-32 | C9 | Error after streaming started | Logged exactly once (no duplicate from the outer layer) | test `s1_3_32` | ✅ |
| — | C10 | N/A: logging and middleware store no data | | | |

### Section 1.4: Error format (RFC 9457)

| Id | Cat. | Scenario | Expected | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| 1.4-01 | C1 | `AppError` raised by code | Problem JSON with code, detail, request id | test `s1_4_01` | ✅ |
| 1.4-02 | C1 | Defaults and custom headers | 409, header kept | test `s1_4_02` | ✅ |
| 1.4-03 | C2, C6 | Missing field in a body that contains a password | Field error; password never echoed | test `s1_4_03` | ✅ |
| 1.4-04 | C2, C6 | Malformed JSON body | 422 `json_invalid`; body not echoed | test `s1_4_04` | ✅ |
| 1.4-05 | C2 | Query parameter 0 / 101 / "abc" | 422 pointing at `["query","limit"]` | test `s1_4_05` (×3) | ✅ |
| 1.4-06 | C2 | Unknown route | 404 `http.not_found` | test `s1_4_06` | ✅ |
| 1.4-07 | C2 | Wrong method | 405 `http.method_not_allowed` | test `s1_4_07` | ✅ |
| 1.4-08 | C6, C9 | Unhandled exception with a secret in its message | Generic 500 with request id; secret not leaked | test `s1_4_08` | ✅ |
| 1.4-09 | C6 | `HTTPException` with an internal dict detail | Standard text; detail hidden | test `s1_4_09` | ✅ |
| 1.4-10 | C3 | Non-standard status code 499 | Problem JSON, code `http.499`, generic title | test `s1_4_10` | ✅ |
| 1.4-11 | C9 | Error after streaming started | Surfaces; not disguised as a clean 500 | test `s1_4_11` | ✅ |
| 1.4-12 | C6 | 500 for a browser on an allowed origin | CORS header present; request id readable | test `s1_4_12` | ✅ |
| 1.4-13 | C11 | Client calls a wrong URL on the real server | 404 problem JSON with request id | e2e `s1_4_13` | ✅ |
| 1.4-14 | C11 | Browser app on an allowed origin reads an error on the real server | CORS header and exposed `X-Request-ID` | e2e `s1_4_14` | ✅ |
| 1.4-15 | C12 | Earlier tests still pass | CI green | CI run | ✅ |
| 1.4-16 | C2, C6 | Validation error on a 500-char client-chosen key with a secret-like value | Key cut to 64 chars in the field path; value never echoed | test `s1_4_16` | ✅ |
| — | C7 | Covered by 1.3-15 and 1.3-30: concurrent requests on the 404 error path each get their own request id, and the id is reset after each request | | | |
| — | C8 | N/A: error handling holds no state; the same input always gives the same output | | | |
| — | C10 | N/A: no data stored | | | |

### Section 1.5: Health probes, readiness cache, infrastructure clients

| Id | Cat. | Scenario | Expected | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| 1.5-01 | C1 | Liveness | 200 `alive` | test `s1_5_01` | ✅ |
| 1.5-02 | C1 | Readiness, all checks pass | 200 `ready` | test `s1_5_02` | ✅ |
| 1.5-03 | C9, C6 | A check fails with a DSN in its error; then recovers | 503 `error`; DSN not in the body; log line has error type and redacted message, no traceback, no secret; ready again after the cache window | tests `s1_5_03` (×3) | ✅ |
| 1.5-04 | C9, C3 | A check never finishes | Cut off at the limit; 503 `timeout` (no sleeping: waits on an unset event) | tests `s1_5_04` (×2) | ✅ |
| 1.5-05 | C7 | Checks run in parallel | Two checks that each wait for the other both succeed (impossible if run in sequence) | test `s1_5_05` | ✅ |
| 1.5-06 | C7 | 20 concurrent probes (unit); 30 concurrent requests (integration) | One check run (single flight); all answer 200 | tests `s1_5_06` (×2) | ✅ |
| 1.5-07 | C8, C3 | Repeated probes | Cached result at 0.999 s; refreshed at exactly 1.000 s; cache 0 = always fresh | tests `s1_5_07` (×2) | ✅ |
| 1.5-08 | C1 | API docs list the health routes | Present | test + e2e `s1_5_08` | ✅ |
| 1.5-09 | C1 | Lifespan | Builds database and Redis checks; closes engine and Redis on shutdown | test `s1_5_09` | ✅ |
| 1.5-10 | C8 | Lifespan started a second time | Checks rebound to the new engine and client | test `s1_5_10` | ✅ |
| 1.5-11 | C1 | Readiness against real PostgreSQL and Redis | 200, both `ok` | test `s1_5_11` (services) | ✅ |
| 1.5-12 | C11 | Operator probes the running stack | `alive`, `ready` | e2e `s1_5_12` | ✅ |
| 1.5-13 | C9, C11 | Redis stopped, then restarted | 503 while down, live still 200; back to 200 | CI step "1.5-13" | ✅ |
| 1.5-14 | C9, C11 | PostgreSQL stopped, then restarted | 503 while down, live still 200; back to 200 | CI step "1.5-14" | ✅ |
| 1.5-15 | C12 | Earlier tests still pass | CI green | CI run | ✅ |
| 1.5-16 | C3 | No checks at all (lifespan not started, or an empty set) | Not ready (fails closed) | tests `s1_5_16` (×2) | ✅ |
| 1.5-17 | C7 | 30 concurrent probes over HTTP with a counting check | The check runs once; all 200 | test `s1_5_17` | ✅ |
| 1.5-18 | C9, C11 | App started while PostgreSQL is down | Starts; live 200, ready 503; ready 200 once the DB is back | CI step "1.5-18" | ✅ |
| 1.5-19 | C6, C11 | Readiness failure logs on the real stack | No credentials, no traceback | CI step "1.5-19" | ✅ |
| — | C2 | N/A: probes take no input; wrong method on a probe is covered by 1.4-07 | | | |
| — | C10 | N/A: probes neither read nor write application data | | | |

### Section 1.6: Docker, Compose, CI and automatic test report

| Id | Cat. | Scenario | Expected | Evidence | Result |
| --- | --- | --- | --- | --- | --- |
| 1.6-01 | C1 | Image builds; stack starts healthy | All services healthy | CI step "1.1-3" (`compose up --wait`) | ✅ |
| 1.6-02 | C6 | Container user | Non-root (uid 10001 in the run) | CI step "1.6-02" | ✅ |
| 1.6-03 | C6 | Image contents | No tests, docs, `.env` or `.git` | CI step "1.6-03" | ✅ |
| 1.6-04 | C1 | Report reads passed, failed, error, skipped | Correct outcomes and messages | test `s1_6_04` | ✅ |
| 1.6-05 | C2 | Report with `|` in a message | Escaped; tables stay intact | test `s1_6_05` | ✅ |
| 1.6-06 | C3 | Report with no failures; missing results file; bad usage | Handled | tests `s1_6_06` (×2) | ✅ |
| 1.6-07 | C9 | Tests fail or produce no file | Report and artifacts still published (`if: always()`); missing file handled (1.6-06) | `ci.yml` + test `s1_6_06` | ✅ |
| 1.6-08 | C12 | Earlier tests still pass | CI green | CI run | ✅ |
| 1.6-09 | C1 | A setting edited in `.env` | Reaches the app container (CORS origin added to `.env`, then used by e2e 1.4-14) | CI step "1.6-09" | ✅ |
| — | C7, C8 | N/A: each CI run starts from a clean machine; no shared state between runs | | | |
| — | C10 | N/A: no application data | | | |
| — | C11 | Covered by 1.1-03 (README quick start on the real stack) | | | |

## Failure log

Every failure found while building, testing and reviewing this step.

| # | Found by | What failed | Cause | Fix | Status |
| --- | --- | --- | --- | --- | --- |
| F1 | CI: type check | `problem_response()` rejected an `HTTPException`'s headers | Typed `dict`; Starlette passes a `Mapping` | Widened to `Mapping[str, str]` | Fixed |
| F2 | CI: tests | Log line missing `request_id` when formatted after the request | Read at format time | Captured when logged | Fixed |
| F3 | Author while testing | Creating an app removed all other log handlers | Replaced every root handler | Replaces only its own (regression test 1.3-06) | Fixed |
| F4 | CI: type check | Dict detail passed to Starlette's `HTTPException` | Wrong class | FastAPI's `HTTPException` | Fixed |
| F5 | Lint | `timeout` parameter on async functions; long lines; HTTP-style error names | Lint rules | `asyncio.timeout`; wrapped lines; rule N818 disabled with a reason | Fixed (one rule waived) |
| F6 | Gate check 4 | No Content-Security-Policy (the old code had one) | Missed in the rewrite | Strict CSP on API responses (1.3-17/18) | Fixed |
| F7 | Author's critical pass | `VERSION` env var could change the version | Version was a setting | Code-only version (1.2-16) | Fixed |
| F8 | Process | Scenario plans written after the code | Process introduced mid-step | Plans first from step 2 on | Process change |
| F9 | CI: type check | Raw header bytes passed in a `str`-keyed mapping | httpx typing | `bytes` keys (1.3-14) | Fixed |
| R1-01 | Review round 1 (High) | Categories missing without N/A reasons | Incomplete plans | Every section lists C1–C12 or a reason | Fixed |
| R1-02 | Review round 1 (High) | Rows claimed coverage their tests didn't prove | Weak tests | Real tests: 1.2-04, 1.3-06, 1.5-05/06/07 | Fixed |
| R1-03 | Review round 1 (High) | Tests not named by scenario id | Rule not followed | All tests renamed `test_s1_<section>_<nn>_...` | Fixed |
| R1-04 | Review round 1 (High) | `Any` without a reason | Rule not followed | Removed from `app/`; commented where kept in test helpers | Fixed |
| R1-05 | Review round 1 | Rows marked CI-verified that no CI step checked | Inspection presented as CI | CI steps 1.1-3, 1.6-02, 1.6-03; test 1.1-02 | Fixed |
| R1-06 | Review round 1 | Nested settings were mutable after the safety check | Only top level frozen | All sections frozen, origins a tuple (1.2-18) | Fixed |
| R1-07 | Review round 1 | Staging had no safety checks and served docs | Production-only check | Staging is strict; docs only in development/test (1.2-02/03, 1.3-20) | Fixed |
| R1-08 | Review round 1 | `JWT__ALGORITHM` accepted any string, incl. `none` | Unconstrained | HMAC-only `Literal` (1.2-12, 1.2-17); kept because step 3 uses it | Fixed |
| R1-09 | Review round 1 | Browsers couldn't read 500s (no CORS header) | 500s produced outside CORS | Error boundary moved inside CORS (1.4-12) | Fixed |
| R1-10 | Review round 1 | Readiness unthrottled; floods could exhaust the DB pool | No policy | 1 s cache, single flight, policy documented in `app/services/health.py` (1.5-06/07) | Fixed |
| R1-11 | Review round 1 | Cross-check table incomplete, one row wrong | Missed old middleware details | Rows corrected and added (gate check 4) | Fixed |
| R1-12 | Review round 1 | Coverage blind to code after SQLAlchemy awaits | No greenlet tracing | `concurrency = ["greenlet", "thread"]` | Fixed |
| R1-13 | Review round 1 | `.env.production` could be committed | Narrow ignore rule | `.env.*` ignored except `.env.example` (1.1-02) | Fixed |
| R1-14 | Review round 1 | Non-standard status codes crashed the error handler | `HTTPStatus()` raised | Generic fallback (1.4-10) | Fixed |
| R1-15 | Review round 1 | Log fields could overwrite reserved keys | No guard | Stored as `field_*` (1.3-07) | Fixed |
| R1-16 | Review round 1 | Health checks bound to the first lifespan's resources | Built once | Rebuilt on every start (1.5-10) | Fixed |
| R1-17 | Review round 1 | Test setup copy-pasted | No helpers | `app_with`, `client_for`, `strict_settings`, `check_ok` in `tests/helpers.py` | Fixed |
| R1-18 | Review round 1 | Architecture layout out of date | Docs drift | `docs/ARCHITECTURE.md` §3 updated | Fixed |
| R1-19 | Review round 1 | Builds not reproducible | No `uv.lock`; tag pinning | Owner to commit `uv.lock`; pinning in step 9 | Carried forward |
| R1-20 | Review round 1 | Timeout test relied on a real sleep | Timing-based | Never-finishing check waits on an unset event (1.5-04) | Fixed |
| R2-01 | Review round 2 (High) | Three claims beyond their evidence: (a) 1.2-20 never showed the default-secret refusal; (b) `is_production` called "tested" but never run; (c) "app starts with DB down" never exercised | Evidence not re-checked after changes | (a) CI runs real defaults and greps both messages; (b) unused `is_production` deleted, row corrected; (c) CI step 1.5-18 | Fixed |
| R2-02 | Review round 2 | Readiness failures logged full tracebacks, possibly with connection strings | `log.exception` | Error type plus redacted, capped message; no traceback (1.5-03, 1.5-19) | Fixed |
| R2-03 | Review round 2 | Compose ignored `.env`; quick start ran with CI overrides | No `env_file` | `env_file: .env` (optional); quick start runs with no overrides; 1.6-09 proves `.env` reaches the app | Fixed |
| R2-04 | Review round 2 | "Client disconnect" scenario tested a different event | Cancellation ≠ disconnect | 1.3-24 renamed; real `ClientDisconnect` → 499, no error log (1.3-29) | Fixed |
| R2-05 | Review round 2 | 1.5-10 had no test of its own | Combined test | Split into `test_s1_5_10_...` | Fixed |
| R2-06 | Review round 2 | Readiness with no checks said "ready" | Fail-open default | No checks = not ready (1.5-16) | Fixed |
| R2-07 | Review round 2 | Request-id isolation test couldn't fail | Each task has its own context | Same-task reset test (1.3-30) | Fixed |
| R2-08 | Review round 2 | Last-resort 500 untested; errors after streaming logged twice | Missing test; both layers logged | Tests 1.3-31, 1.3-32; outer layer no longer logs re-raised errors | Fixed |
| R2-09 | Review round 2 | Health schemas outside `app/schemas/`; router read app state directly; duplicate doc line | Placement | `app/schemas/health.py`; `get_readiness_probe` dependency; `response_model` honoured; doc fixed | Fixed |
| R2-10 | Review round 2 | Strict checks don't catch weak secrets or password-less DB/Redis URLs | Narrow checks | Added to step 9 in the roadmap | Carried forward |
| R2-11 | Review round 2 | Small test duplication | Leftovers | `ALLOWED_ORIGIN`, crash route, ASGI fakes moved to `tests/helpers.py` | Fixed |
| R2-12 | Review round 2 | Builds not reproducible | Same as R1-19 | Same as R1-19 | Carried forward |
| F10 | CI: tests | New log test assumed a record without traceback has `exc_info is None` (it is `False`) | Wrong assumption | Assert falsy | Fixed |
| F11 | CI: tests | The "no secret in logs" check read pytest's plain log text, which leaves out structured fields, so it could never fail | Test checked the wrong output | Checks the JSON lines exactly as written in production (1.5-03) | Fixed |

**Totals:** 104 scenarios, 104 passing. 43 failures found: 38 fixed, 1 fixed with a documented
rule waiver (F5), 1 process change (F8), 3 carried forward (R1-19 = R2-12 lockfile, R2-10 to step 9).

## Gate

### 1. Automated: PASS
Lint, `mypy --strict` (39 files), 120 tests against real PostgreSQL 16 and Redis 7 with 97.8 %
coverage, and the Compose job (README quick start, `.env` reaching the app, 6 user scenarios,
non-root and image checks, Redis and PostgreSQL outages, app started with the DB down, log
hygiene, safe and unsafe production containers): all green in the linked run.

### 2. Tester: PASS
Every section covers each category C1–C12 or gives an N/A reason (tables above). Every row
names its evidence.

### 3. User: PASS
Real-stack scenarios: 1.1-03, 1.2-20, 1.2-21, 1.3-25, 1.3-26, 1.4-13, 1.4-14, 1.5-08, 1.5-12,
1.5-13, 1.5-14, 1.5-18, 1.5-19, 1.6-02, 1.6-03, 1.6-09.

### 4. Cross-check vs old code (`main` @ `209a9bd`): PASS

| Old | New | Decision | Reason |
| --- | --- | --- | --- |
| `config/settings.py`: known default JWT secret and DB password, no safety checks | Frozen settings; staging and production refuse unsafe values | Improved | Old app ran with public default secrets |
| `Settings.is_production()` reads a missing attribute | `is_strict` property (tests 1.2-02, 1.2-03, 1.2-08); no unused `is_production` | Fixed | Crashed with `AttributeError` |
| Settings for sessions, rate limits, lockout | Not yet present | Moved | Added with their features in steps 3–4 |
| `app.host/port/reload`, `workers=4` hard-coded | uvicorn CLI / orchestrator | Dropped | Process settings belong to the runtime |
| `config_manager.py` copies `config/env_*.txt` (files don't exist) | `.env.example` + `.env` | Replaced | The old script could never work |
| `requirement.txt` missing `pydantic-settings`; unused `passlib`, `bcrypt`, `PyJWT`, `requests` | `pyproject.toml` with only what is used | Fixed | Fresh install crashed |
| Redis `password` and `retry_on_timeout` settings | Password inside `REDIS__URL` (`redis://:pw@host`); connect / socket timeouts set in the client | Replaced | One URL is the standard form; retries belong to the client |
| 4 log modules writing rotating files under `logs/` | One JSON logger to stdout | Improved | Containers lose local files |
| Correlation id generated in each route | Request id set once; in every log line, error body and response header | Improved | Was duplicated and missing from errors |
| 3 `BaseHTTPMiddleware` classes + one `@app.middleware("http")` (an `AutoRefreshMiddleware` existed but was never added) | 2 pure ASGI middlewares (request context; error boundary) + CORS | Improved | Less overhead; one access-log line per request |
| `user_agent` in request logs | Kept, truncated to 256 characters | Kept | Useful for support; bounded size |
| `SecurityLoggingMiddleware`: warnings for responses ≥ 400 and "suspicious" paths | Every request logged with its status, so ≥ 400 is filterable; path heuristics dropped | Replaced / dropped | Status-based alerting belongs in log tooling; path pattern matching is a WAF job (step 9 review) |
| `X-Process-Time` response header | Duration in the access log; metrics in step 8 | Dropped | Timing data is for operators, not clients |
| `HTTPSRedirectMiddleware` when enabled | Not in the app; HSTS in strict environments | Dropped | TLS ends at the load balancer, which does the redirect |
| Headers: `nosniff`, `DENY`, `strict-origin-when-cross-origin`, `Permissions-Policy`, `X-XSS-Protection`, CSP `default-src 'self'` | `nosniff`, `DENY`, `no-referrer`, CSP `default-src 'none'; frame-ancestors 'none'` on every response incl. errors, HSTS in strict environments | Improved | Stricter. `X-XSS-Protection` is deprecated and can introduce XSS; `Permissions-Policy` has no effect on JSON |
| HSTS only if `enable_https_redirect` | HSTS in staging and production | Improved | TLS ends at the load balancer |
| CORS `*` with credentials by default | Allow-list; `*` + credentials rejected | Fixed | Any website could make credentialed calls |
| Errors `{"detail", "status_code"}`; validation errors echo input | RFC 9457 with stable `code` and `request_id`; input never echoed; readable by browsers on allowed origins | Improved | Old format leaked submitted passwords |
| 7 health/info endpoints incl. duplicates, `/hello`, `/` | `/health/live`, `/health/ready` | Consolidated | `/health/detailed` returned raw exception text; `/` exposed environment info |
| Startup failed hard if the DB was unreachable | App starts; `/health/ready` returns 503 until the DB is reachable (1.5-18) | Changed | Orchestrators route traffic by readiness; a crash loop hides the cause and slows recovery |
| Readiness pinged DB then Redis, no timeout, no cache | Parallel checks with a time limit; 1 s single-flight cache | Improved | One hung dependency stalled the probe; probe floods could exhaust the pool |
| Sync engine, pool 10 + 20, `pool_recycle=3600` | Async engine, pool 5 + 5, `pool_pre_ping` | Improved | Non-blocking; smaller default pool |
| Sync Redis singleton, `PING` before every request | Async client from lifespan, closed on shutdown | Improved | No blocking calls, no per-request ping |
| `@app.on_event` hooks alongside `lifespan` | `lifespan` only | Fixed | Deprecated API removed |
| Docs disabled in production | Docs only in development and test | Improved | Staging is internet-facing too |
| `.env` not git-ignored | `.env` and `.env.*` ignored; `.env.example` committed | Fixed | Risk of committing secrets |

### 5. Independent review

| Round | Commit | Verdict | Record |
| --- | --- | --- | --- |
| 1 | `919dbc7` | **FAIL**: 4 High, 9 Medium, 7 Low | [`reviews/step-1-round-1.md`](reviews/step-1-round-1.md); every finding addressed (R1-01 to R1-20) |
| 2 | `180a554` | **FAIL**: 1 High, 3 Medium, 8 Low; 18 of 20 round-1 findings confirmed resolved | [`reviews/step-1-round-2.md`](reviews/step-1-round-2.md); every finding addressed (R2-01 to R2-12) |
| 3 | pending | | |

## Scorecard (independent reviewer)

| Area | Old code | Round 1 | Round 2 | Round 3 |
| --- | --- | --- | --- | --- |
| Folder structure & architecture | 6 | 8 | 8 | |
| API design | 5 | 7 | 7 | |
| Database schema | 5 | not built yet | not built yet | |
| Scalability & load balancing | 4 | 7 | 8 | |
| DSA / algorithms | 4 | not built yet | not built yet | |
| Code quality & correctness | 3 | 7 | 8 | |
| Duplication & reuse | 3 | 8 | 8 | |
| Maintainability | 3 | 7 | 7 | |
| Security | 2 | 6 | 7 | |
| **Overall** | **4** | **7** | **8** | |

Evidence for each score is in the review records.

## Carried forward

- Commit `uv.lock`, then switch CI and Docker to `uv sync --locked` (owner action, needs internet).
- Pin images by digest and actions by SHA (step 9).
