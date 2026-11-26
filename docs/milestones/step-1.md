# Milestone 1: Project skeleton & tooling

- PR: https://github.com/Husky1711/fastapi-user-management/pull/2
- Latest CI run (automatic report): https://github.com/Husky1711/fastapi-user-management/actions/runs/45882257652 (54 tests + 5 user scenarios passed, coverage 97.2 %; open "Summary" for every result)
- Verdict: **IN PROGRESS**. All sections ✅; gate checks 1–4 PASS; check 5 (independent review
  and scorecard) not run yet.

> Process note: the testing process was introduced partway through this step, so these
> scenario plans were written after the first version of the code, not before it. From step 2
> on, each section's plan is written first.

## Section log

| # | Section | Status | Scenarios (pass / total) | Notes |
| --- | --- | --- | --- | --- |
| 1.1 | Clean branch and tooling (`pyproject`, `Makefile`, `.env.example`, `.gitignore`) | ✅ | 4 / 4 | Old code removed from `v2`; stays on `main` |
| 1.2 | Settings and production safety | ✅ | 15 / 15 | |
| 1.3 | Logging and request middleware | ✅ | 16 / 16 | |
| 1.4 | Error format (RFC 9457) | ✅ | 8 / 8 | |
| 1.5 | Health probes and infrastructure clients | ✅ | 9 / 9 | |
| 1.6 | Docker, Compose, CI and automatic test report | ✅ | 9 / 9 | |
| | **Total** | **✅** | **61 / 61** | Automated tests + CI-scripted operator scenarios |

## Scenario plan and results

Result column: ✅ = passing in the CI run linked above. Test names are in parentheses.
C4 (authentication) and C5 (authorization) are N/A for the whole step: no endpoint in step 1
needs a user. They start in step 3.

### Section 1.1: Clean branch and tooling

| Id | Category | Scenario | Expected | Result |
| --- | --- | --- | --- | --- |
| 1.1-1 | C1 | Fresh clone installs and every quality gate runs (`uv sync`, ruff, mypy, pytest) | All succeed | ✅ (CI jobs Lint, Type check, Test) |
| 1.1-2 | C10 | `.env` with real secrets can't be committed | `.env` git-ignored; `.env.example` committed | ✅ (`.gitignore`) |
| 1.1-3 | C11 | A new developer follows the README quick start | `cp .env.example .env && make run` serves the app | ✅ (Compose job) |
| 1.1-4 | C12 | Nothing from the old code is imported or required | App and tests pass with no old files present | ✅ (CI) |
| — | C2, C3, C6–C9 | N/A: configuration files only, no runtime input | | |

### Section 1.2: Settings and production safety

| Id | Category | Scenario | Expected | Result |
| --- | --- | --- | --- | --- |
| 1.2-1 | C1 | Development defaults load | Accepted, docs enabled (`test_development_defaults_are_accepted`) | ✅ |
| 1.2-2 | C1 | Safe production settings | Accepted, docs disabled (`test_safe_production_settings_pass`) | ✅ |
| 1.2-3 | C6 | Production with the default JWT secret | Rejected (`test_production_rejects_default_jwt_secret`) | ✅ |
| 1.2-4 | C3 | Production with a secret shorter than 32 characters | Rejected with the exact reason (`test_production_rejects_short_jwt_secret`) | ✅ |
| 1.2-5 | C6 | Production with `DEBUG=true` | Rejected (`test_production_rejects_debug`) | ✅ |
| 1.2-6 | C6 | Production with default DB credentials | Rejected (`test_production_rejects_default_database_credentials`) | ✅ |
| 1.2-7 | C6 | Several problems at once | All reported together (`test_production_reports_every_problem_at_once`) | ✅ |
| 1.2-8 | C6 | `CORS *` with credentials, any environment | Rejected (`test_cors_wildcard_with_credentials_is_rejected_everywhere`) | ✅ |
| 1.2-9 | C3 | `CORS *` without credentials | Allowed (`test_cors_wildcard_without_credentials_is_allowed`) | ✅ |
| 1.2-10 | C2 | Nested values and JSON lists from env vars | Parsed correctly (`test_nested_settings_load_from_environment`) | ✅ |
| 1.2-11 | C6 | Settings printed or logged | Secret not visible (`test_secret_is_not_shown_in_repr`) | ✅ |
| 1.2-12 | C6 | Production set only through real env vars | Detected as unsafe (`test_t1_production_from_environment_variables_is_unsafe`) | ✅ |
| 1.2-13 | C2 | Unrelated `VERSION` env var (set by many CI systems) | App version unchanged (`test_t10_version_is_not_overridable_from_environment`) | ✅ |
| 1.2-14 | C11 | App started with unsafe production config | Refuses to start (`test_unsafe_production_settings_stop_startup`) | ✅ |
| 1.2-15 | C11 | Real container started with `ENVIRONMENT=production` and defaults | Exits non-zero with "Unsafe production configuration" (Compose job, operator step) | ✅ |
| — | C7–C10 | N/A: settings are read once at startup and are immutable (`frozen=True`) | | |

### Section 1.3: Logging and request middleware

| Id | Category | Scenario | Expected | Result |
| --- | --- | --- | --- | --- |
| 1.3-1 | C1 | Structured fields and request id in a log line (`test_structured_fields_and_request_id_are_included`) | Both present | ✅ |
| 1.3-2 | C3 | Logging outside any request (`test_request_id_is_omitted_outside_a_request`) | No request id key | ✅ |
| 1.3-3 | C1 | Exception logging (`test_exception_includes_traceback`) | Traceback included | ✅ |
| 1.3-4 | C1 | Every level works (`test_every_level_is_available`, 3 cases) | debug, warning, error | ✅ |
| 1.3-5 | C1 | Output is JSON on stdout; uvicorn's duplicate access log off (`test_configure_logging_writes_json_to_stdout`) | As described | ✅ |
| 1.3-6 | C1 | Request id generated when absent (`test_request_id_is_generated`) | 32-character id | ✅ |
| 1.3-7 | C1 | Valid incoming request id kept (`test_valid_incoming_request_id_is_kept`) | Same id | ✅ |
| 1.3-8 | C2, C6 | Malformed ids: space, 65 chars, `<script>` (`test_malformed_incoming_request_id_is_replaced`, 3 cases) | Replaced | ✅ |
| 1.3-9 | C2 | Lower-case header name (`test_t4_...`) | Honoured | ✅ |
| 1.3-10 | C7 | 25 concurrent requests with different ids (`test_t5_...`) | No id leaks between requests | ✅ |
| 1.3-11 | C6 | Request with `Authorization: Bearer <secret>` (`test_t3_...`) | One log line per request; secret not logged | ✅ |
| 1.3-12 | C1 | Security headers on every response (`test_security_headers`) | nosniff, DENY, no-referrer | ✅ |
| 1.3-13 | C6 | Content-Security-Policy (`test_t9_content_security_policy`) | Strict on API; docs exempt | ✅ |
| 1.3-14 | C1 | Production adds HSTS and hides docs (`test_production_adds_hsts_and_hides_docs`) | As described | ✅ |
| 1.3-15 | C6 | CORS only for configured origins, incl. preflight (`test_cors_allows_only_configured_origins`, `test_t2_...`) | Allowed vs not allowed | ✅ |
| 1.3-16 | C3 | Non-HTTP traffic (lifespan) passes through (`test_t8_...`) | Untouched | ✅ |
| — | C8 | `configure_logging` called repeatedly (once per app in tests) keeps one handler | Covered by every test creating an app | ✅ |
| — | C9, C10 | N/A: no external dependency or stored data | | |

### Section 1.4: Error format

| Id | Category | Scenario | Expected | Result |
| --- | --- | --- | --- | --- |
| 1.4-1 | C1 | `AppError` raised by code (`test_app_error_becomes_problem_json`) | `application/problem+json` with code, detail, request id | ✅ |
| 1.4-2 | C1 | Defaults and custom headers (`test_app_error_defaults_and_headers`) | 409 + header kept | ✅ |
| 1.4-3 | C2, C6 | Invalid body containing a password (`test_validation_error_lists_fields_without_echoing_input`) | Field errors; password never echoed | ✅ |
| 1.4-4 | C2 | Unknown route (`test_unknown_route_is_problem_json`) | 404 `http.not_found` | ✅ |
| 1.4-5 | C2 | Wrong HTTP method (`test_wrong_method_is_problem_json`) | 405 `http.method_not_allowed` | ✅ |
| 1.4-6 | C6, C9 | Unhandled exception whose message holds a secret (`test_unhandled_exception_is_generic_500`) | Generic 500 with request id; secret not leaked | ✅ |
| 1.4-7 | C6 | `HTTPException` with an internal dict detail (`test_t7_...`) | Standard text; internal detail hidden | ✅ |
| 1.4-8 | C9 | Exception after a streaming response started (`test_t6_...`) | Surfaces instead of a fake clean 500 | ✅ |
| — | C7, C8, C10 | N/A: error handling holds no state | | |

### Section 1.5: Health probes and infrastructure clients

| Id | Category | Scenario | Expected | Result |
| --- | --- | --- | --- | --- |
| 1.5-1 | C1 | Liveness (`test_liveness`) | 200 `alive` | ✅ |
| 1.5-2 | C1 | Readiness with all checks passing (`test_readiness_when_all_checks_pass`) | 200 `ready` | ✅ |
| 1.5-3 | C9, C6 | A check fails with a DSN in the error (`test_readiness_fails_without_leaking_error_details`) | 503; DSN not in body | ✅ |
| 1.5-4 | C9, C3 | A check hangs beyond the time limit (`test_readiness_times_out_slow_checks`) | 503 `timeout` | ✅ |
| 1.5-5 | C1 | Readiness against real PostgreSQL and Redis through the real lifespan (`test_readiness_against_real_services`) | 200; both `ok` | ✅ |
| 1.5-6 | C11 | Operator probes the running stack (`test_u1_...`) | `alive`, `ready` | ✅ |
| 1.5-7 | C9, C11 | Redis stopped, then restarted (Compose job operator step) | 503, then back to 200 | ✅ |
| 1.5-8 | C1 | API docs list the health routes (`test_docs_are_served_outside_production`, `test_u2_...`) | Present | ✅ |
| 1.5-9 | C8 | Probes called repeatedly by load balancers | Stateless; every e2e and Compose call returns the same result | ✅ |
| — | C7 | Checks within one probe run concurrently (`asyncio.gather`) | Covered by 1.5-2 to 1.5-4 | ✅ |
| — | C10 | N/A: probes read nothing and write nothing | | |

### Section 1.6: Docker, Compose, CI and automatic test report

| Id | Category | Scenario | Expected | Result |
| --- | --- | --- | --- | --- |
| 1.6-1 | C1 | Image builds and the stack starts healthy (`docker compose up --wait`) | All services healthy | ✅ |
| 1.6-2 | C6 | Container runs as a non-root user | `USER app` (uid 10001) | ✅ (`Dockerfile`) |
| 1.6-3 | C11 | Client gets problem JSON on a wrong URL (`test_u3_...`) | 404 problem JSON with request id | ✅ |
| 1.6-4 | C11 | Client request id round trip (`test_u4_...`) | Same id back | ✅ |
| 1.6-5 | C11 | Security headers from the real server (`test_u5_...`) | Present | ✅ |
| 1.6-6 | C1 | Test report reads passed, failed, error and skipped tests (`test_reads_every_outcome`) | Correct outcomes and messages | ✅ |
| 1.6-7 | C2 | Report escapes pipes so tables stay intact (`test_render_shows_totals_failures_and_all_tests`) | Escaped | ✅ |
| 1.6-8 | C3 | Report with no failures; missing file; bad usage (`test_render_without_failures_...`, `test_main_handles_...`) | Handled | ✅ |
| 1.6-9 | C12 | Every earlier test passes on every push | CI green | ✅ |
| — | C7, C8, C10 | N/A: build and CI configuration | | |

## Failure log

Every failure found while building and testing this step, including small ones.

| # | Found by | What failed | Cause | Fix | Status |
| --- | --- | --- | --- | --- | --- |
| F1 | CI: type check | `problem_response()` rejected the headers of an `HTTPException` | Parameter typed `dict`; Starlette passes a `Mapping` | Parameter widened to `Mapping[str, str]` | Fixed |
| F2 | CI: tests | Log line missing `request_id` when formatted after the request ended | Request id read at format time, not when the line was logged | Captured when the log call is made | Fixed |
| F3 | Author while testing | Creating an app removed every other log handler (tests couldn't capture logs; other handlers would be lost) | `configure_logging()` replaced all root handlers | Replaces only its own handler | Fixed |
| F4 | CI: type check | Test passed a dict detail to Starlette's `HTTPException` (typed as text only) | Wrong class for the scenario | Test uses FastAPI's `HTTPException`, which allows structured details | Fixed |
| F5 | Lint | `timeout` parameter on async functions; HTTP-style error names; long lines | Lint rules | Used `asyncio.timeout`; names kept (rule disabled with a reason); lines wrapped | Fixed |
| F6 | Gate check 4 (vs old code) | No Content-Security-Policy header; the old code had one | Missed when rewriting | Strict CSP on API responses, docs exempt (1.3-13) | Fixed |
| F7 | Gate check 5 (author's critical pass) | A generic `VERSION` env var could change the reported version | Version was a setting | Version comes from code only (1.2-13) | Fixed |
| F8 | Process | Scenario plans written after the code | Testing process introduced mid-step | Plans come first from step 2 on | Process fixed |

**Totals for this step:** 61 scenarios, 61 passing. 8 failures found, 8 fixed, 0 open.

## Gate

### 1. Automated: PASS
Lint, `mypy --strict`, unit and integration tests against real PostgreSQL 16 and Redis 7 with
coverage ≥ 90 %, and the Docker Compose job with user and operator scenarios: all green in the
linked run. Totals and every test result are in the run's automatic report.

### 2. Tester: PASS
All six sections cover every checklist category or mark it N/A with a reason (tables above).

### 3. User: PASS
Scenarios 1.5-6, 1.5-7, 1.6-3 to 1.6-5 and 1.2-15 run against the real stack in CI.

### 4. Cross-check vs old code (`main` @ `209a9bd`): PASS

| Old | New | Decision | Reason |
| --- | --- | --- | --- |
| `config/settings.py`: known default JWT secret and DB password, no production checks | Nested, frozen settings; production refuses unsafe values | Improved | Old app ran in production with public default secrets |
| `Settings.is_production()` reads a missing attribute | `Settings.is_production` property, tested | Fixed | Crashed with `AttributeError` |
| Settings for sessions, rate limits, lockout | Not yet present | Moved | Added with their features in steps 3–4, so no setting exists without code using it |
| `app.host/port/reload`, `workers=4` hard-coded | uvicorn CLI / orchestrator | Dropped | Process settings belong to the runtime |
| `config_manager.py` copies `config/env_*.txt` (files don't exist) | `.env.example` + `.env` | Replaced | The old script could never work |
| `requirement.txt` missing `pydantic-settings`; unused `passlib`, `bcrypt`, `PyJWT`, `requests` | `pyproject.toml` with only what is used | Fixed | Fresh install crashed |
| 4 log modules writing rotating files under `logs/` | One JSON logger to stdout | Improved | Containers lose local files |
| Correlation id generated in each route | Request id set once; in every log line, error body and response header | Improved | Was duplicated and missing from errors |
| 5 stacked `BaseHTTPMiddleware` layers + a logging middleware | One pure ASGI middleware | Improved | Less overhead; one log line per request |
| Headers: `nosniff`, `DENY`, `strict-origin-when-cross-origin`, `Permissions-Policy`, `X-XSS-Protection`, CSP `default-src 'self'` | `nosniff`, `DENY`, `no-referrer`, CSP `default-src 'none'; frame-ancestors 'none'`, HSTS in production | Improved | Stricter, API-appropriate. `X-XSS-Protection` is deprecated and can introduce XSS; `Permissions-Policy` has no effect on JSON |
| HSTS only if `enable_https_redirect` | HSTS whenever environment is production | Improved | TLS ends at the load balancer |
| CORS `*` with credentials by default | Allow-list; `*` + credentials rejected | Fixed | Any website could make credentialed calls |
| Errors `{"detail", "status_code"}`; validation errors echo input | RFC 9457 with stable `code` and `request_id`; input never echoed | Improved | Old format leaked submitted passwords |
| 7 health/info endpoints incl. duplicates, `/hello`, `/` | `/health/live`, `/health/ready` | Consolidated | `/health/detailed` returned raw exception text; `/` exposed environment info |
| Readiness pinged DB then Redis, no timeout | Parallel checks with a timeout | Improved | One hung dependency stalled the probe |
| Sync engine, pool 10 + 20, `pool_recycle=3600` | Async engine, pool 5 + 5, `pool_pre_ping` | Improved | Non-blocking; smaller default pool |
| Sync Redis singleton, `PING` before every request | Async client from lifespan, closed on shutdown | Improved | No blocking calls, no per-request ping |
| `@app.on_event` hooks alongside `lifespan` | `lifespan` only | Fixed | Deprecated API removed |
| Docs disabled in production | Same | Kept | Correct in the old code |
| `.env` not git-ignored | Ignored; `.env.example` committed | Fixed | Risk of committing secrets |

### 5. Independent review: NOT RUN

Needs a reviewer who didn't write this code: the owner, another developer, or a fresh AI
reviewer session given only the PR, `CLAUDE.md`, `docs/milestones/README.md` and this report.
The reviewer records findings here and fills in the scorecard.

The author's critical pass before handover (input for the reviewer, not a substitute):

| # | Finding | Severity | Resolution |
| --- | --- | --- | --- |
| A1 | No Content-Security-Policy | Medium | Fixed (F6) |
| A2 | Generic `VERSION` env var could override the app version | Low | Fixed (F7) |
| A3 | `uv.lock` not committed; builds not fully reproducible | Medium | Carried forward (owner, needs internet) |
| A4 | Base images and GitHub Actions pinned by tag, not digest / SHA | Low | Carried to step 9 |
| A5 | Unhandled-exception logs include the exception message | Low | Accepted: logs are internal |
| A6 | `/health/ready` is public and names the failing dependency | Low | Accepted: standard probe behaviour, no details |
| A7 | Compose exposes Postgres and Redis on the host with default credentials | Low | Accepted for local development only |
| A8 | An exception after streaming started is logged twice (middleware and uvicorn) | Low | Accepted; rare |

## Scorecard (to be filled by the independent reviewer)

| Area | Old code | After step 1 | Evidence |
| --- | --- | --- | --- |
| Folder structure & architecture | 6 | | |
| API design | 5 | | |
| Database schema | 5 | not built yet | |
| Scalability & load balancing | 4 | | |
| DSA / algorithms | 4 | | |
| Code quality & correctness | 3 | | |
| Duplication & reuse | 3 | | |
| Maintainability | 3 | | |
| Security | 2 | | |

## Carried forward

- Commit `uv.lock`, then switch CI and Docker to `uv sync --locked` (owner action, needs internet).
- Pin images by digest and actions by SHA (step 9).
- Independent review and scorecard before this PR is merged.
