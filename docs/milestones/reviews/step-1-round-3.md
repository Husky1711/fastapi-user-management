# Step 1, independent review, round 3 (verbatim)

Output of the `milestone-reviewer` agent, recorded unchanged as the process requires.

---

### 5. Independent review: PASS

Reviewer: milestone-reviewer agent (`.claude/agents/milestone-reviewer.md`), 2026-11-27, commit e90cc09

**Summary:** I checked the fixes against the code, the tests and CI run 45887647468, and no Critical or High finding remains. The step now does what its report claims.
- **Round-2 findings resolved (10):** R2-01 (a, b and c), R2-02, R2-03, R2-04, R2-05, R2-06, R2-07, R2-08, R2-09 and R2-11.
- **Honestly carried forward (2):** R2-10 is now a step-9 roadmap item, and R2-12 (= R1-19) is the unticked step-1 box. None of the round-2 findings is unresolved.
- **Round-1 fixes:** none regressed.

The remaining findings are Medium or Low. The two that matter most:
- Compose publishes Postgres (with its default password) and an unauthenticated Redis on every host interface.
- The real-stack log-hygiene step 1.5-19 can't actually detect leaked credentials.

API design, scalability, maintainability and security score 8, below the ≥ 9 production-grade bar. The owner must accept that or ask for the fixes below.

| # | Finding | Severity | Evidence | Recommended fix |
| --- | --- | --- | --- | --- |
| 1 | The local stack publishes PostgreSQL (default `postgres`/`postgres`) and Redis (no auth) on all host interfaces. On Linux, Docker's published ports bypass host firewalls such as ufw. A developer on a shared network exposes a default-password database and an open Redis, a classic way machines get compromised. | Medium | `docker-compose.yml:32-33` (`"${POSTGRES_PORT:-5432}:5432"`), `:44-45` (`"${REDIS_PORT:-6379}:6379"`) | Bind to loopback: `"127.0.0.1:${POSTGRES_PORT:-5432}:5432"`, and the same for Redis (and the app port). |
| 2 | Row 1.5-19 ("No credentials, no traceback" on the real stack) can't fail on its credentials half. Step 1.5-18 runs `--force-recreate app`, so `docker compose logs app` in 1.5-19 shows only the new container. The Redis and Postgres outage logs from 1.5-13/1.5-14 are gone. The only failure line left is `"error_type": "gaierror", "error": "[Errno -3] Temporary failure in name resolution"`, which could never contain a DSN. The no-traceback half is a real check. The redaction itself is properly proven by 1.5-03. | Medium | `ci.yml:148-161`; Compose job 140142262057 log line 766 (exactly one `readiness check failed` line, database/gaierror) | Move 1.5-19 before 1.5-18, or keep logs with `docker compose logs` before recreating. Better: add a step whose failure message really contains credentials (e.g. start the app with a wrong DB password, so asyncpg reports an auth failure) and grep that the password is absent. Otherwise reword the row to "no traceback". |
| 3 | 1.3-29 proves 499 only for a route that calls `request.body()` itself. For the normal FastAPI route with a Pydantic body parameter (every endpoint from step 3 on), FastAPI's request handler wraps body-read exceptions in `HTTPException(400, "There was an error parsing the body")`. So a client disconnect would be logged as 400 and a 400 response attempted, not 499. Not harmful (no ERROR log), but the scenario doesn't cover the realistic path. | Low | `tests/integration/test_s1_3_middleware.py:332-346`; `app/core/middleware.py:81-84`. Reasoned from FastAPI's `get_request_handler` source; not run (packages can't be installed here) | In step 3, add a disconnect test on a Pydantic-body route and map that case to 499 if wanted. |
| 4 | "Logged exactly once" (1.3-32) holds only inside the app. Under uvicorn, the re-raised error after streaming also produces uvicorn's `Exception in ASGI application` with a full traceback. `configure_logging` routes `uvicorn.error` into the same JSON stream, so production gets two ERROR entries, one with a traceback. | Low | `app/core/middleware.py:85-88`; `app/core/logging.py:101-104`; `tests/integration/test_s1_3_middleware.py:377-393` | Accept this and note it in the row, or swallow the error after logging (close the stream yourself) rather than re-raise to the server. |
| 5 | Tests aren't sealed off from the shell environment. `make_settings` ignores `.env`, but every env var still applies. A developer with `JWT__SECRET_KEY` and a non-default `DATABASE__URL` exported would make `test_s1_2_19` fail (no refusal). `DEBUG=true` in the shell would break `test_s1_2_04/05` (extra problem). CI only passes because its env happens to match. | Low | `tests/helpers.py:25-43`; `tests/integration/test_s1_2_app_startup.py:323-326`; `ci.yml:64-67` | Add an autouse fixture that deletes the app's env vars (except in service tests), or have `make_settings` pass explicit values for every safety-relevant field. |
| 6 | Small test duplication was added this round. `broken_stream` and its `/_test/stream` route are defined twice, and 1.3-32 and 1.4-11 exercise the same route. | Low | `tests/integration/test_s1_3_middleware.py:382-388`; `tests/integration/test_s1_4_errors.py:344-350` | Move the helper to `tests/helpers.py` (`add_broken_stream_route`). |
| 7 | A CORS preflight from a disallowed origin gets Starlette's plain-text `400 Disallowed CORS origin`, not problem JSON. This contradicts "one error format for every failure", and no scenario tests it. | Low | `app/main.py:92-100`; scenario table 1.3/1.4 (only allowed-origin preflight, 1.3-22) | Add the scenario. Accept and document it as a framework response, or wrap it. |
| 8 | Logging writes and flushes `sys.stdout` synchronously on the event loop, which blocks under pipe back-pressure (CLAUDE.md: "never call blocking I/O inside an `async def`"). Common practice, but worth a decision. | Low | `app/core/logging.py:46-54` | Carry to step 8: `QueueHandler`/`QueueListener`. |
| 9 | Under Compose, `.env.example`'s `DATABASE__URL` and `REDIS__URL` are silently overridden. The knobs that actually change them (`POSTGRES_USER/PASSWORD/DB`, `*_PORT`) aren't in `.env.example`. | Low | `docker-compose.yml:15-19,28-33`; `.env.example:1,14,21` | Document the Compose variables in `.env.example` and say which values Compose overrides. |
| 10 | Records nits: rows 1.6-01 and R1-05 cite CI step "1.1-3", but the step is "1.1-03". `test_s1_1_04` checks only some removed paths, not `config/`, `config_manager.py` or `models/`. | Low | `docs/milestones/step-1.md:170,202`; `tests/unit/test_s1_1_repository.py:30-32` | Fix the ids; add the missing paths to the list. |
| 11 | Carried forward: no `uv.lock`, so Docker and CI use unlocked `uv sync` (R1-19 = R2-12). Images and actions are pinned by tag only. Strict-environment credential checks are narrow (R2-10). | Low | `Dockerfile:12-15`; `ci.yml:23-28,74`; `docs/ROADMAP.md` step 1 unticked box and step 9 item | As recorded. The lockfile should land before step 2 starts. |

**Report claims verified:**
- **CI run 45887647468:** head sha 61451b7, all 4 jobs green. `git diff --stat 61451b7..HEAD` touches only `docs/milestones/step-1.md`. The newest run on the branch, 45888218713 at e90cc09, is also green.
  - Test job 140142262203: "120 passed, 6 skipped". Coverage TOTAL is 470 statements / 7 missed, 72 branches / 5 partial, which gives 97.8 %, as reported. Uncovered: `errors.py` 120/132/151 (unreachable guards), `logging.py` 53-54, `middleware.py` 69-70.
  - Type check job 140142261703: "no issues found in 39 source files".
  - Compose job 140142262057:
    - uid=10001 (1.6-02).
    - The e2e run reports "6 passed".
    - 1.5-13/14: 503, then live 200, then ready 200.
    - 1.5-18: live 200 and ready 503 with the DB down, then 200.
    - 1.2-21: ready 200 on :8001; `/docs` and `/openapi.json` 404; HSTS grep passed.
    - 1.2-20: the log shows "Unsafe configuration for production: JWT__SECRET_KEY is the development default; DATABASE__URL uses the default postgres:postgres credentials". Both default values were really in effect (`.env` from `.env.example` plus Compose's default `POSTGRES_PASSWORD`).
- **Failed runs:** 45886748591 (50e87f7) failed on `assert False is None`, which matches F10. 45887203183 (d5aad05) failed on caplog text lacking `ConnectionError`, which matches F11.
- **Round-2 fixes, checked in code:**
  - R2-01: (a) CI step `ci.yml:174-184`, no secret override; (b) `is_production` is gone from `config.py` and the cross-check row is corrected; (c) `ci.yml:148-155`.
  - R2-02: `services/health.py:42-49` logs a warning with `error_type` and `redact()`, without `exc_info`. `test_s1_5_03` asserts on the formatted JSON lines.
  - R2-03: `env_file` with `required: false`. The 1.1-03 job runs with no job-level overrides. 1.6-09 shows a `.env` edit reaching the container, and e2e 1.4-14 then uses it.
  - R2-04: 1.3-24 renamed; 1.3-29 drives a real `ClientDisconnect` and asserts nothing was sent, a 499 status and no ERROR records.
  - R2-05: `test_s1_5_10_…` exists.
  - R2-06: `run_checks` fails closed; `test_s1_5_16` × 2.
  - R2-07: `test_s1_3_30`. httpx's ASGITransport runs the app in the calling task, so this test can fail.
  - R2-08: `test_s1_3_31`/`32`; `middleware.py:136-138`.
  - R2-09: `app/schemas/health.py`, the `get_readiness_probe` dependency, return-type `response_model`, and ARCHITECTURE §3 fixed.
  - R2-10: the item is in ROADMAP step 9.
  - R2-11: helpers moved (a new duplicate appeared, finding 6).
  - R2-12: carried.
- **Round-1 fixes, no regressions:**
  - Middleware order is still RequestContext, then CORS, then ErrorBoundary.
  - Sections are frozen with `extra=forbid`.
  - JWT is HMAC-only.
  - CSP, HSTS and the strict environments are unchanged.
  - The `field_*` guard and the greenlet coverage setting are still in place.
- **Counts and records:**
  - Test functions with their parametrizations: 120 unit + integration, plus 6 e2e.
  - Every scenario id cited in the tables has a matching test name. CI-step ids match the step names in `ci.yml`, except the "1.1-3" typo (finding 10).
  - Scenarios: 5 + 23 + 32 + 16 + 19 + 9 = 104. Every section covers C1–C12 or gives an N/A reason.
  - Failure log: 11 F + 20 R1 + 12 R2 = 43. Of these, 38 fixed, 1 waiver, 1 process change and 3 carried forward, which matches the totals.
- **Local checks:** `ruff check .` and `ruff format --check .` pass.
- **Not verified:** pytest and mypy locally (packages can't be installed), so I relied on the CI logs. FastAPI's body-parse wrapping (finding 3) and uvicorn's error log (finding 4) are reasoned from the library source, not run; the FastAPI source fetch was blocked.

**Missing scenarios:**
- **1.1**
  - C10: the "no old code" test should also cover `config/`, `config_manager.py` and `models/`.
- **1.2**
  - C12/C10: the test suite should be independent of the shell environment (finding 5).
- **1.3**
  - C9: client disconnect on a Pydantic-body route (finding 3).
  - C9/C11: error after streaming on a real uvicorn server, counting log entries (finding 4).
  - C6/C2: CORS preflight from a disallowed origin (finding 7).
- **1.5**
  - C6/C11: a real-stack failure whose message actually carries credentials or a username (e.g. a wrong DB password), checked for redaction (finding 2).
  - C6: redaction of non-URL credential forms (`password=…` key/value DSNs).
  - C9: the Redis-outage log line on the real stack, which is lost today (finding 2).
- **1.6**
  - C6: published database and Redis ports reachable only from loopback (finding 1).

## Scorecard (by the independent reviewer)

| Area | Old code | After step 1 | Evidence |
| --- | --- | --- | --- |
| Folder structure & architecture | 6 | 9 | Layers match ARCHITECTURE §3: schemas in `app/schemas/health.py`, the router uses the `get_readiness_probe` dependency, imports go one way (api → services → core/infra), and the doc duplicate is fixed. |
| API design | 5 | 8 | RFC 9457 everywhere with stable codes and typed `response_model`s (`app/api/health.py:22-37`). Problem-JSON 4xx/5xx aren't documented in OpenAPI, and CORS preflight rejection is plain text (finding 7). |
| Database schema | 5 | not built yet | Only an engine and `SELECT 1` (`app/infra/database.py`). |
| Scalability & load balancing | 4 | 8 | Async, pure ASGI, bounded pool, readiness cache with single flight proven over HTTP (`test_s1_5_17`); starts with the DB down (CI 1.5-18). Logging to stdout is synchronous (finding 8); no metrics or load figures yet. |
| DSA / algorithms | 4 | not built yet | Nothing algorithmic beyond a lock-guarded cache. |
| Code quality & correctness | 3 | 9 | All round-1/2 bugs fixed and tested (fail-closed probe, one log line, `ClientDisconnect`, frozen settings). Only edge behaviours left (findings 3, 4). |
| Duplication & reuse | 3 | 9 | One middleware, one problem builder, shared `tests/helpers.py`; one small new duplicate (finding 6). |
| Maintainability | 3 | 8 | 4-job CI with the automatic report, mypy strict on 39 files, 97.8 % coverage, records consistent with CI (run 45887647468). No `uv.lock` (finding 11); tests depend on the shell environment (finding 5). |
| Security | 2 | 8 | Strict staging/production checks proven on a real container (1.2-20/21); redacted readiness logs (1.5-03); CSP, HSTS, non-root image, HMAC-only JWT. Compose exposes the DB and Redis on all interfaces (finding 1); credential checks are narrow (R2-10, carried). |
| **Overall** | **4** | **8** | Average of the 7 scored areas is 8.4; no Critical or High findings. The four areas at 8 are below the ≥ 9 bar and need the owner's acceptance or the Medium fixes. |
