# Step 1, independent review, round 2 (verbatim)

Output of the `milestone-reviewer` agent, recorded unchanged as the process requires.
The fixes are listed in `docs/milestones/step-1.md` (failure log, R2-xx).

---

### 5. Independent review: FAIL

Reviewer: milestone-reviewer agent (`.claude/agents/milestone-reviewer.md`), 2026-11-27, commit 180a554

**Summary:** The code is much better than in round 1. I checked the round-1 findings against the code, the tests and CI run 45884857593:
- **Resolved (18):** R1-01, R1-02, R1-04 to R1-18, and R1-20.
- **Honestly carried forward (1):** R1-19.
- **Only partly resolved (1):** R1-03. Scenario 1.5-10 still has no test that carries its id.

The gate still fails because of one High finding: several report claims don't match what their cited evidence actually tested. This is the same kind of problem as round-1 finding 2.
- The production-refusal container (1.2-20) ran with neither default value.
- The cross-check table says `is_production` is "tested", but CI coverage shows its line was never run.
- "App starts with the DB down" cites a CI step that never starts the app with the DB down.

There are also Medium findings: possible secrets in readiness logs, Compose not passing `.env` settings to the app, and an overstated client-disconnect scenario.

| # | Finding | Severity | Evidence | Recommended fix |
| --- | --- | --- | --- | --- |
| 1 | **Report claims that their cited evidence doesn't prove.** **(a)** Row 1.2-20 says "Real container started as production with unsafe defaults". The CI step actually starts it with `-e JWT__SECRET_KEY=` (empty) and the job-level `POSTGRES_PASSWORD=ci-not-the-default-password`. So neither the default secret nor the default DB credentials were present. The container refused only for "JWT__SECRET_KEY must be at least 32 characters". The default-secret refusal is never shown on a real container. **(b)** A cross-check row says "`is_production` / `is_strict` properties, tested". `is_production` is never called anywhere in `app/` or `tests/`, and CI coverage lists `app/core/config.py … Missing 119` (its body). **(c)** A cross-check row says "App starts; `/health/ready` returns 503 until the DB is reachable (1.5-14)". But 1.5-14 stops PostgreSQL *after* the app is up. Compose's `depends_on: service_healthy` means a start with the DB down is never exercised. Round 1 listed this missing scenario. | High | step-1.md:71, :232, :250; `.github/workflows/ci.yml:95,159`; Compose job 140132911649 log ("Unsafe configuration for production: JWT__SECRET_KEY must be at least 32 characters"); Test job 140132911812 coverage (`config.py 119`); `app/core/config.py:117-119`; `docker-compose.yml:17-21` | **(a)** Run 1.2-20 with the real defaults: no `-e JWT__SECRET_KEY=` override and the default DB password, so it fails on both. Or reword the row to "empty secret". **(b)** Delete the unused `is_production` (dead code, per `CLAUDE.md`) or test it, then correct the row. **(c)** Add a CI step: `docker compose stop db`, start the app, check live 200 and ready 503, then start the DB and check ready 200. Or drop the evidence claim. |
| 2 | Readiness failures log the full exception and traceback at ERROR. The module's own docstring says these "can contain connection strings", so it knowingly sends possible secrets to logs, against the DoD "no secrets … in logs". Test 1.5-03 uses an error text containing `user:secret@` but checks only the response body, not the logs. During an outage this also writes about 5 KB of traceback per instance every cache window (seen in the Compose log). | Medium | `app/services/health.py:3-4,39-41`; `tests/integration/test_s1_5_health.py:14-38`; Compose job log (`readiness check failed` with full traceback) | Log `type(exc).__name__` plus a redacted message (strip `scheme://user:pw@`), not the traceback. Assert with `caplog` that `secret` never appears. Consider logging only state changes (ok to error, error to ok). |
| 3 | Compose passes only 5 variables to the app (`environment:` with no `env_file:`). Settings a developer edits in `.env`, as the README quick start says, have no effect on the stack: `DEBUG`, `DATABASE__POOL_*`, `JWT__ALGORITHM`, `CORS__ALLOW_CREDENTIALS`, `HEALTH__*`, `FORWARDED_ALLOW_IPS`. This contradicts `.env.example` ("Every setting the app reads is listed here") and the "Copy to .env and adjust" workflow. Also, the "quick start exactly as the README says" step (1.1-03) runs with job-level `POSTGRES_PASSWORD` and `CORS__ALLOW_ORIGINS` overriding `.env`, and with `--detach --wait` instead of `make run`, so "exactly" is overstated. | Medium | `docker-compose.yml:10-16`; `.env.example:1,10-47`; `ci.yml:95-103`; step-1.md:42 | Add `env_file: .env` (optional, `required: false`) and keep `environment:` only for container-specific values (DB/Redis hosts). Run 1.1-03 without job-level overrides, then set the overrides in later steps. |
| 4 | Scenario 1.3-24 ("Client disconnects mid-request: logged as 499") is proven only by injecting `asyncio.CancelledError`. Under uvicorn, a client disconnect does not cancel the app task. A route reading the body raises Starlette's `ClientDisconnect` (an `Exception`), which `ErrorBoundaryMiddleware` would log as "unhandled exception" plus a 500 access line. So the row describes a different event from the one tested. | Medium | `tests/integration/test_s1_3_middleware.py:193-211`; `app/core/middleware.py:79-83,124-128`; step-1.md:105 | Rename to "request cancelled (e.g. shutdown): 499". Add a `ClientDisconnect` scenario that maps to 499 without an ERROR log (needed once step 3 adds request bodies). |
| 5 | R1-03 is only partly resolved. Scenario 1.5-10 has no test carrying `s1_5_10`. It is the second half of `test_s1_5_09_…`, so the automatic report can't show its result separately. | Low | `tests/integration/test_s1_5_health.py:76-103`; step-1.md:148 | Split it into `test_s1_5_10_second_lifespan_rebinds_checks`. |
| 6 | Readiness fails open when it has no checks. `create_app` installs a probe with `{}` checks until the lifespan runs, and `health_checks={}` is treated as "injected". `run_checks({})` returns `ready`. With `--lifespan off`, or an empty mapping passed by mistake, `/health/ready` says ready without checking anything. | Low | `app/main.py:43-48,83`; `app/services/health.py:48`; `tests/helpers.py:54` | Treat an empty check set as `not_ready`, or refuse to build a probe without checks. Use `None` (not `{}`) as the "use defaults" signal. |
| 7 | The C7 evidence for request-id isolation (1.3-15, also cited for 1.4 C7) can't fail. Each `asyncio.gather` task runs in its own copied context, so the ids are isolated whatever the middleware does. A missing `request_id_var.reset` would go unnoticed. | Low | `tests/integration/test_s1_3_middleware.py:83-90`; `app/core/middleware.py:145` | Add a same-task test: after a request, `request_id_var.get() is None`. Accept 1.3-15 only as a smoke test. |
| 8 | The last-resort 500 path in `RequestContextMiddleware` (an exception outside the error boundary) is untested. If the boundary re-raises after the response started, the exception is logged twice ("unhandled exception" from both layers). | Low | Test job coverage `middleware.py 126->128, 134`; `app/core/middleware.py:79-82,129-134` | Add a test with a failing inner middleware. Log only in the boundary when re-raising. |
| 9 | Response schemas live outside `app/schemas/`: `ReadinessOut` is in the service module and `LivenessOut` in the router. The router reads `request.app.state.readiness` directly instead of through a dependency. ARCHITECTURE §3 lists `infra/redis.py` twice. | Low | `app/services/health.py:27-29`; `app/api/health.py:18-19,32-33`; `docs/ARCHITECTURE.md:76,81,84` | Move them to `app/schemas/health.py`, add a `get_readiness_probe` dependency, and fix the doc. |
| 10 | The strict-environment checks are narrow. A 32-character run of one letter passes the JWT check (no entropy check). Only the literal `postgres:postgres@` is rejected, so a password-less `postgres@` or another trivial password passes. A Redis URL without auth or TLS isn't flagged. | Low | `app/core/config.py:136-145` | Carry to step 3/9: reject low-variety secrets, and require a password in `DATABASE__URL` and `REDIS__URL` in strict environments. |
| 11 | Small test duplication remains: `ALLOWED_ORIGIN`, the crash route, and the fake `receive`/`send` are defined in two files. | Low | `tests/integration/test_s1_3_middleware.py:17,25-32,183-187,199-203`; `tests/integration/test_s1_4_errors.py:18,45-47` | Move them to `tests/helpers.py`. |
| 12 | Builds are still not reproducible: no `uv.lock`, and Docker runs an unlocked `uv sync --no-dev`. This is recorded as R1-19 and carried forward. | Low | `Dockerfile:13-15`; `ROADMAP.md` step 1 unticked box | As carried forward; do it before step 2. |

**Report claims verified:**
- **CI run 45884857593** is at sha 1bacbc0, and `git diff --stat 1bacbc0..HEAD` changes only `docs/milestones/step-1.md` and `reviews/step-1-round-1.md`. All 4 jobs succeeded.
  - Test job 140132911812: "110 passed, 6 skipped" (the 6 e2e tests); coverage 96.98 % (reported as 97.0 %).
  - Type check job 140132911802: "Success: no issues found in 38 source files".
  - Compose job 140132911649: every named step succeeded. The e2e run reports "6 passed". `uid=10001`. Redis and PostgreSQL went 503 and then 200, with live staying 200. On port 8001, ready was 200, HSTS was matched, and `/docs` and `/openapi.json` returned 404. The unsafe run refused, but for a different reason than the report says (finding 1).
- **Newest run on the branch:** 45885612007 at HEAD 180a554 is green in all 4 jobs. The failed run 45884417207 (4eae8b5, Type check) matches F9.
- **Test count:** I counted the test functions and parametrizations: 60 unit + 50 integration = 110, plus 6 e2e. This matches.
- **Scenario counts:** 5 + 23 + 28 + 15 + 15 + 8 = 94. The C1–C12 coverage or N/A reason is present in every section; C4/C5 are globally N/A with a credible reason.
- **Failure-log totals:** 9 F + 20 R1 = 29, of which 26 fixed, 1 waiver, 1 process change and 1 carried forward. This is consistent.
- **Local checks:** `ruff check .` and `ruff format --check .` pass locally.
- **Round-1 findings, confirmed in code and tests:**
  - R1-01: every category is covered or has an N/A reason.
  - R1-02: 31/32/33-character secrets tested; one handler checked after configuring twice; parallel checks proven with mutual-wait events; single flight with `calls == 1`; cache edge at 0.999/1.000 s.
  - R1-04: no `Any` in `app/`; it is commented in `tests/helpers.py`.
  - R1-05: real CI steps exist.
  - R1-06: all sections frozen with `extra=forbid`; origins are a tuple (1.2-18).
  - R1-07: `STRICT_ENVIRONMENTS` and `DOCS_ENVIRONMENTS`.
  - R1-08: HMAC-only `Literal`.
  - R1-09: middleware order is RequestContext, CORS, ErrorBoundary (1.4-12).
  - R1-10: cache and lock.
  - R1-11: rows added. The table still has new inaccuracies (finding 1b/1c).
  - R1-12: `concurrency = ["greenlet","thread"]`; `main.py` is now fully covered.
  - R1-13: `.env.*` with `!.env.example`, tested with `git check-ignore`.
  - R1-14: `_status_phrase` fallback and the handler fallback (1.4-10).
  - R1-15: `field_*` prefix (1.3-07).
  - R1-16: probe rebuilt in the lifespan (1.5-09).
  - R1-17: helpers exist; minor leftovers remain (finding 11).
  - R1-18: ARCHITECTURE §3 updated; it has a duplicate line (finding 9).
  - R1-20: `check_never_finishes` waits on an event.
- **Cross-check rows** against `209a9bd` were confirmed in round 1 and are unchanged, except the rows in finding 1.
- **Not verified:** mypy and pytest locally (packages can't be installed); I relied on the CI logs. Whether uvicorn cancels on disconnect (finding 4) is reasoned from uvicorn and Starlette behaviour, not run.

**Missing scenarios:**
- **1.1**
  - C11: quick start with no CI overrides, so only `.env` drives the stack (finding 3).
- **1.2**
  - C11: real production container refusing with the actual default secret and default DB password (finding 1a).
  - C6: password-less or trivial `DATABASE__URL`, and an unauthenticated `REDIS__URL`, in strict environments (finding 10).
- **1.3**
  - C9: a real `ClientDisconnect` while reading a body (finding 4).
  - C7: request-id context reset after a request in the same task (finding 7).
  - C9: exception outside the error boundary, which should give one log line and a 500 with headers (finding 8).
- **1.4**
  - C2: user-controlled keys in a validation `loc` (dict body keys), which echo client input back. Raised in round 1; not addressed.
- **1.5**
  - C9/C11: app started while PostgreSQL is down (finding 1c).
  - C6: secrets in readiness failure logs (finding 2).
  - C3: empty check set (finding 6).
  - C7 integration: 30 probes with a counting check, to prove single flight through HTTP, not only in the unit test.
- **1.6**
  - C1: `.env` settings actually reach the container (finding 3).

## Scorecard (by the independent reviewer)

| Area | Old code | After step 1 | Evidence |
| --- | --- | --- | --- |
| Folder structure & architecture | 6 | 8 | Layers and one-way imports match ARCHITECTURE §3. Response schemas are outside `app/schemas/` and the router reads `app.state` directly (finding 9). |
| API design | 5 | 7 | One RFC 9457 format with stable codes, including non-standard statuses (`app/core/errors.py:80-151`). `/health/ready` bypasses its `response_model` (`app/api/health.py:32-36`), and no error responses are documented in OpenAPI except the 503. |
| Database schema | 5 | not built yet | Only an engine and `SELECT 1` (`app/infra/database.py`). |
| Scalability & load balancing | 4 | 8 | Async, pure ASGI, bounded pool, readiness cache with single flight (`app/services/health.py:55-93`, tests 1.5-05/06/07). No metrics or load figures yet. |
| DSA / algorithms | 4 | not built yet | Nothing algorithmic beyond a lock-guarded cache. |
| Code quality & correctness | 3 | 8 | Round-1 bugs fixed (R1-06/09/14/15/16). Remaining: dead `is_production` (`config.py:117-119`), fail-open empty probe (finding 6), double exception logging (finding 8). |
| Duplication & reuse | 3 | 8 | Shared `tests/helpers.py`; one middleware and one problem builder. Small test leftovers remain (finding 11). |
| Maintainability | 3 | 7 | 4-job CI with automatic report, mypy strict on 38 files, 96.98 % coverage (run 45884857593). No lockfile (finding 12); Compose ignores `.env` (finding 3); evidence mislabelled (finding 1). |
| Security | 2 | 7 | Strict staging/production checks, HMAC-only JWT, frozen settings, CSP/HSTS, CORS-readable 500s, non-root image (uid 10001 in CI). Gaps: possible secrets in readiness logs (finding 2), narrow credential checks (finding 10). |
| **Overall** | **4** | **8** | Average of the 7 scored areas is 7.6. The gate fails on one High finding (finding 1: claims not backed by evidence), which is cheap to fix. |
