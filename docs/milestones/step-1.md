# Milestone 1: Project skeleton & tooling — gate report

- PR: https://github.com/Husky1711/fastapi-user-management/pull/2
- CI run: https://github.com/Husky1711/fastapi-user-management/actions/runs/45880785156 (all four jobs green)
- Verdict: **PENDING**. Checks 1–4 PASS; check 5 (independent review) has not been run yet.

> Process note: the gate was introduced partway through this milestone, so the tester plan
> (check 2) was written after the first version of the code, not before it. From milestone 2
> on, the plan is written first.

## 1. Automated — PASS

| Job | Result |
| --- | --- |
| Lint (`ruff check`, `ruff format --check`) | Pass: all checks passed, 47 files formatted |
| Type check (`mypy --strict`, 31 source files) | Pass: no issues |
| Tests (real PostgreSQL 16 + Redis 7 services) | Pass: 50 passed, 5 skipped (the e2e tests, which run in the Compose job); coverage **97.2 %** (gate: 90 %) |
| Docker Compose smoke test | Pass: stack builds, starts healthy, `/health/ready` = 200 |

## 2. Tester — PASS

Edge cases and attacks, each an automated test (`tests/integration/test_gate_step1.py`
unless noted).

| # | Scenario | Expected | Result |
| --- | --- | --- | --- |
| T1 | Production configured through real env vars with the default JWT secret | Detected as unsafe | Pass |
| T2 | CORS preflight from an allowed origin | 200 + CORS headers + request id + security headers | Pass |
| T3 | Request carrying `Authorization: Bearer <secret>` | Exactly one log line with method, path, status, duration, request id; secret not logged | Pass |
| T4 | Lower-case `x-request-id` header | Honoured | Pass |
| T5 | 25 concurrent requests with different request ids | Each response and error body carries its own id (no leakage between requests) | Pass |
| T6 | Exception after a streaming response has started | Not disguised as a clean 500; surfaces to the server | Pass |
| T7 | `HTTPException` with a structured (dict) detail | Problem JSON with standard text; internal detail not shown | Pass |
| T8 | Non-HTTP traffic (lifespan) through the middleware | Passed through untouched | Pass |
| T9 | Content-Security-Policy | `default-src 'none'; frame-ancestors 'none'` on API responses; docs page exempt | Pass |
| T10 | Unrelated `VERSION` env var set | App version unchanged | Pass |
| — | Validation error on a body containing a password | Field errors listed; the password is never echoed (`test_errors_and_middleware.py`) | Pass |
| — | Unhandled exception whose message contains a secret | Generic 500 with request id; message not leaked (`test_errors_and_middleware.py`) | Pass |
| — | Malformed incoming request ids (`has space`, 65 chars, `<script>`) | Replaced with a generated id | Pass |
| — | Readiness check raising an error containing a DSN | 503, `"error"`, DSN not in body (`test_health.py`) | Pass |
| — | Readiness check hanging | 503 `"timeout"` within the configured limit (`test_health.py`) | Pass |
| — | Production with default secret / short secret / debug / default DB credentials / `CORS *` + credentials | Each rejected; all problems reported at once (`test_config.py`) | Pass |

## 3. User — PASS

Run in CI against the real stack started by `docker compose` (`tests/e2e/test_stack.py` and
the Compose job's operator steps).

| # | Who | Scenario | Expected | Result |
| --- | --- | --- | --- | --- |
| U1 | Operator / load balancer | Probe liveness and readiness | `alive`; `ready` with database ok, redis ok | Pass |
| U2 | Frontend developer | Open `/docs` and the OpenAPI schema | Docs load; health routes listed | Pass |
| U3 | API client | Call a URL that doesn't exist | 404 `application/problem+json`, `code` and `request_id` | Pass |
| U4 | API client | Send its own `X-Request-ID` | Same id returned | Pass |
| U5 | Security reviewer | Inspect response headers on the real server | `nosniff`, `DENY` present | Pass |
| U6 | Operator | Stop Redis, probe, start Redis, probe | 503 while down; back to 200 after restart | Pass |
| U7 | Operator | Start in production with unsafe defaults | Container exits non-zero with "Unsafe production configuration" | Pass |

## 4. Cross-check vs old code (`main` @ `209a9bd`) — PASS

| Old | New | Decision | Reason |
| --- | --- | --- | --- |
| `config/settings.py`: one settings module, defaults include a known JWT secret and DB password, no production checks | `app/core/config.py`: nested, frozen settings; production refuses unsafe values | Improved | Old app ran in production with public default secrets |
| `Settings.is_production()` reads a missing attribute | `Settings.is_production` property, tested | Fixed | Crashed with `AttributeError` |
| Settings for sessions, rate limits, lockout | Not yet present | Moved | Added with their features in steps 3–4 so no setting exists without code using it |
| `app.host/port/reload`, `workers=4` hard-coded | uvicorn CLI / orchestrator | Dropped | Process settings belong to the runtime, not the app |
| `config_manager.py` copies `config/env_*.txt` (files don't exist) | `.env.example` + `.env` | Replaced | The old script could never work |
| `requirement.txt` missing `pydantic-settings`, unused `passlib`, `bcrypt`, `PyJWT`, `requests` | `pyproject.toml` with only what is used | Fixed | Fresh install crashed |
| 4 log modules writing rotating files under `logs/` | One JSON logger to stdout | Improved | Containers lose local files; one system instead of three |
| Correlation id generated in each route | Request id set once in middleware, in every log line, error body and response header | Improved | Was duplicated and missing from errors |
| 5 stacked `BaseHTTPMiddleware` layers + an extra logging middleware | One pure ASGI middleware | Improved | Lower overhead; one log line per request instead of two |
| Security headers: `nosniff`, `DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`, `X-XSS-Protection`, CSP `default-src 'self'` | `nosniff`, `DENY`, `Referrer-Policy: no-referrer`, CSP `default-src 'none'; frame-ancestors 'none'`, HSTS in production | Improved | Stricter, API-appropriate. `X-XSS-Protection` dropped (deprecated and can introduce XSS); `Permissions-Policy` dropped (no effect on JSON responses) |
| HSTS only if `enable_https_redirect` | HSTS whenever environment is production | Improved | TLS is terminated at the load balancer; HSTS must not depend on an app-level redirect |
| CORS `*` with credentials by default | Explicit allow-list; `*` + credentials rejected at startup | Fixed | Old default let any website make credentialed calls |
| Error bodies `{"detail", "status_code", ...}`; validation errors echo `input` | RFC 9457 problem JSON with stable `code` and `request_id`; input never echoed | Improved | Old format leaked submitted passwords |
| `/health`, `/api/v1/health` (twice, one hard-coding `environment="development"`), `/health/detailed`, `/health/ready`, `/health/live`, `/hello`, `/` | `/health/live`, `/health/ready` | Consolidated | Duplicates removed; `/health/detailed` returned raw exception text; `/` and `/hello` exposed environment info |
| Readiness pinged DB, then Redis, sequentially, no timeout | Parallel checks with a timeout | Improved | One hung dependency stalled the probe |
| Sync SQLAlchemy engine, pool 10 + 20, `pool_recycle=3600` | Async engine, pool 5 + 5 (configurable), `pool_pre_ping` | Improved | Non-blocking; smaller default pool. Recycling isn't needed for PostgreSQL with pre-ping |
| Sync Redis singleton, `PING` before every request | Async client created in lifespan, closed on shutdown | Improved | No blocking calls, no per-request ping |
| `@app.on_event` hooks alongside `lifespan` | `lifespan` only | Fixed | Deprecated API removed |
| Docs disabled in production | Docs disabled in production | Kept | Correct in the old code |
| `.env` not git-ignored | `.env` ignored; `.env.example` committed | Fixed | Risk of committing secrets |

## 5. Independent review — PENDING

Not yet run. It needs a reviewer who didn't write this code: the owner, another developer, or
a fresh AI reviewer session given only the PR, `CLAUDE.md` and this report.

Before handing it over, the author did a critical pass. Findings:

| # | Finding | Severity | Resolution |
| --- | --- | --- | --- |
| A1 | No Content-Security-Policy (the old code had one) | Medium | Fixed: strict CSP on API responses (T9) |
| A2 | A generic `VERSION` env var could override the reported app version | Low | Fixed: version comes from code only (T10) |
| A3 | `uv.lock` not committed, so builds are not fully reproducible | Medium | Carried forward: no internet in the build environment. Generate with `make install` and commit |
| A4 | Base images and GitHub Actions pinned by tag, not digest or SHA | Low | Carried to step 9 (supply-chain hardening) |
| A5 | Unhandled-exception logs include the exception message, which could contain a DSN | Low | Accepted: logs are internal; secrets in exception messages are addressed where they arise |
| A6 | `/health/ready` is public and names the failing dependency | Low | Accepted: standard probe behaviour; reveals no details |
| A7 | Compose exposes Postgres and Redis on the host with default credentials | Low | Accepted for local development only; documented in `docker-compose.yml` |
| A8 | An exception after streaming has started is logged by both the middleware and uvicorn | Low | Accepted; rare case |

## Open items carried forward

- Commit `uv.lock`, then switch CI and Docker to `uv sync --locked` (owner action, needs internet).
- Pin images by digest and actions by SHA (step 9).
- Run check 5 before merging this PR.
