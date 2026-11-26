# Step 1, independent review, round 1 (verbatim)

Output of the `milestone-reviewer` agent, recorded unchanged as the process requires.
The fixes are listed in `docs/milestones/step-1.md` (failure log, R1-xx).

---

### 5. Independent review: FAIL

Reviewer: milestone-reviewer agent (`.claude/agents/milestone-reviewer.md`), 2026-11-27, commit 919dbc7

**Summary:** The step-1 code is a solid, small skeleton. It uses one pure ASGI middleware, RFC 9457 errors, production refuses unsafe settings, readiness checks run in parallel with timeouts, and CI is green with real numbers: 54 passed, 5 e2e skipped in the Test job, 5/5 e2e passed in the Compose job, and 97.18 % coverage. It still fails the gate for four reasons:
- Gate check 2 ("every category covered or N/A") is false. Five of six sections leave out categories with no N/A reason.
- Several scenario rows claim category coverage that their tests do not exercise.
- Two explicit `CLAUDE.md` rules are broken: the scenario-id test naming, and `Any` without a comment.

There are also several Medium correctness and security gaps to fix now or in the next step.

| # | Finding | Severity | Evidence | Recommended fix |
| --- | --- | --- | --- | --- |
| 1 | Gate check 2 claim is false: sections leave out checklist categories without an N/A reason. 1.2 has no C12. 1.3 has no C11 or C12. 1.4 has no C3, C11 or C12. 1.5 has no C2 or C12. 1.6 has no C9. | High | `docs/milestones/step-1.md` §1.2–1.6 tables; Gate "2. Tester: PASS" | Add a row or an N/A reason for each missing category in every section; set gate 2 to FAIL until that is done. |
| 2 | Coverage claimed for categories the cited tests don't exercise. **C3 (1.2-4):** the boundary row uses the 5-char secret `"short"`; nothing tests 31, 32 or 33 chars. **C3 (1.2-9):** CORS `*` without credentials is not a boundary. **C7 (1.5):** "checks run concurrently, covered by 1.5-2..4": no test proves the checks run in parallel or sends concurrent probes. **C8 (1.3):** "keeps one handler, covered by every test creating an app": no test asserts the handler count (F3 has no regression test). **C8 (1.5-9):** no test calls a probe twice and compares results. | High | step-1.md lines 47, 52, 81, 110, 111; `tests/unit/test_config.py:45`; `tests/integration/test_health.py` | Write real tests for these: secret at 31/32 chars; two checks of 0.6×timeout each finishing within 1×timeout; N concurrent `/health/ready`; `configure_logging` twice → exactly one `StdoutHandler`. Otherwise mark the category N/A with a reason. |
| 3 | Test names don't carry scenario ids (`test_s<step>_<section>_<n>_<what>`), as `CLAUDE.md` "Records" and README §2 require. Instead there are ad-hoc `t1..t10`, `u1..u5` and unnumbered names, so plan rows (e.g. "1.2-3") can't be traced to the automatic report. The report doesn't mention this deviation. | High | `CLAUDE.md` "Scenario ids"; `tests/integration/test_gate_step1.py:30-155`, `tests/unit/test_config.py`, `tests/e2e/test_stack.py` | Rename the tests to `test_s1_<section>_<n>_...` to match the report rows, or record an owner-approved exception. |
| 4 | `Any` is used without an explanatory comment, which `CLAUDE.md` Python style and VISION §5 forbid. | High | `app/core/errors.py:86,88`; `app/core/logging.py:25,60,64,67,70,73,76`; `tests/helpers.py:11,13` | Add a one-line reason, or use a JSON type alias / `object`. |
| 5 | "Result ✅ = passing in the CI run" is applied to rows that no CI step checks. 1.1-2 (`.gitignore` only). 1.6-2 (non-root: no `docker compose exec app id -u`). 1.1-3 (CI never runs `cp .env.example .env`; compose uses its built-in defaults). | Medium | step-1.md lines 35, 36, 119; `.github/workflows/ci.yml:91-146` | Add CI steps (`id -u` ≠ 0; quick start with a copied `.env`), or mark these rows as "inspection" rather than CI. |
| 6 | The N/A reason for settings C7–C10 says the settings "are immutable (`frozen=True`)". That is only true at the top level. Nested sections (`DatabaseSettings`, `CorsSettings`, …) are plain mutable `BaseModel`s, so `settings.database.url = ...` or `settings.cors.allow_origins.append("*")` work after the startup checks have run. | Medium | `app/core/config.py:35-71,82-88`; step-1.md line 59 | Set `model_config = ConfigDict(frozen=True)` on every nested section, use `tuple[str, ...]` for origins, and add a test. |
| 7 | `staging` gets no safety checks: it accepts the default JWT secret and default DB credentials, and serves docs. Staging is usually internet-facing and often holds copies of real data. | Medium | `app/core/config.py:110-113`, `108`; `app/main.py:65-67` | Apply `production_problems()` to every environment except development and test, or add a documented `strict` flag. |
| 8 | `JWT__ALGORITHM` accepts any string (e.g. `none`, `RS256` with an HMAC secret). This setting has no code using it yet, against the cross-check's own rule that "no setting exists without code using it". | Medium | `app/core/config.py:49`; step-1.md cross-check row "Settings for sessions…" | Remove it until step 3, or constrain it to `Literal["HS256","HS384","HS512"]`. |
| 9 | Unhandled-exception 500s are produced by the outermost middleware, outside `CORSMiddleware`, so they carry no `Access-Control-Allow-Origin`. Browser clients get an opaque CORS error and can't read the `request_id` that the error message tells them to quote. | Medium | `app/main.py:74-85`; `app/core/middleware.py:83` | Add CORS headers in the 500 path, or put CORS outside and the request-context middleware inside it. Add a test: crash route + allowed `Origin`. |
| 10 | `/health/ready` is public and unthrottled. Every call takes a DB pool connection (pool 5+5) and makes a Redis round trip, so a flood can exhaust the pool and starve real traffic once step 2 lands. The DoD item "rate-limit policy" for new endpoints isn't addressed. | Medium | `app/api/health.py:62-72`; `app/core/config.py:37-39`; `CLAUDE.md` DoD | Cache the readiness result for about 1 s (single-flight). Document the policy or carry it to step 4 explicitly. |
| 11 | The cross-check table is incomplete and has one inaccurate row. The old code had 3 `BaseHTTPMiddleware` classes plus one `@app.middleware("http")`, not "5 stacked" (`AutoRefreshMiddleware` is never added). These were dropped without a row: `HTTPSRedirectMiddleware` in production, `SecurityLoggingMiddleware` (warnings for ≥400 and suspicious paths), the `X-Process-Time` header, `user_agent` in request logs, the startup fail-fast DB check, and Redis `password` / `retry_on_timeout` settings. | Medium | `git show 209a9bd:utils/security_middleware.py:127-150`, `:57-79`; `209a9bd:main.py:36-48`; step-1.md line 171 | Correct the row and add the missing rows with Kept/Dropped/Moved decisions. |
| 12 | Coverage isn't configured for greenlet. SQLAlchemy async runs on greenlets, so lines after its awaits go untraced: `main.py:44` (shutdown) shows as missed although the services test runs the lifespan. From step 2 this will distort the 90 % gate. | Medium | `pyproject.toml:87-89`; Test job log 140124195607 (`app/main.py … 44`) | `[tool.coverage.run] concurrency = ["greenlet", "thread"]`. |
| 13 | `.gitignore` covers only `.env`, `.env.local` and `.env.*.local`. `.env.production` and `.env.staging` can be committed, which contradicts 1.1-2 ("`.env` with real secrets can't be committed"). | Medium | `.gitignore:33-35` | Ignore `.env.*` with `!.env.example`, as `.dockerignore` already does. |
| 14 | `HTTPStatus(status)` raises `ValueError` for a non-standard status code (e.g. `HTTPException(499)` from a library). The handler then crashes into a generic 500. | Low | `app/core/errors.py:90,137` | Fall back to a generic title/code when the status is unknown; add a test. |
| 15 | Structured log fields can overwrite reserved keys (`level`, `timestamp`, `message`, `request_id`). A field named `message` raises `TypeError`. | Low | `app/core/logging.py:35-37,64-78` | Reject or prefix reserved keys. |
| 16 | `health_checks` are bound once to the first lifespan's engine and Redis client. If the lifespan runs again (re-used app, tests), they still point at the disposed objects. | Low | `app/main.py:33-37` | Keep injected checks separate from defaults, and rebuild the defaults on every lifespan start. |
| 17 | The test-client setup is copy-pasted (`create_app` + `AsyncClient(transport=ASGITransport…)`) in about 7 places. `_ok` is defined twice. Production settings are built in two different ways. | Low | `tests/integration/test_health.py:12,37-52`; `test_errors_and_middleware.py:135-160`; `test_gate_step1.py:25`; `tests/conftest.py:13` | Use one `client_for(settings, checks)` helper and one `production_settings()` in `tests/helpers.py`. |
| 18 | `docs/ARCHITECTURE.md` §3 doesn't list `app/core/middleware.py` or `app/infra/database.py`. The roadmap places the request-id middleware in `logging.py`. | Low | `docs/ARCHITECTURE.md:54-80`; `docs/ROADMAP.md` step 1 | Update the layout in this PR. |
| 19 | Builds aren't reproducible: no `uv.lock`, only `>=` lower bounds, actions and images pinned by tag. Already known (A3/A4) and justified as an unticked box. | Low | `pyproject.toml:10-18`; `Dockerfile:6,13-15`; `ci.yml` | As carried forward; do it before step 2 starts. |
| 20 | `test_readiness_times_out_slow_checks` relies on a real 0.05 s wall-clock timeout over `asyncio.sleep(10)`. That is timing-based, which the "no sleeping, inject the clock" spirit discourages. | Low | `tests/integration/test_health.py:20-54` | Use an `asyncio.Event` that is never set instead of a sleep. |

**Report claims verified:**
- **Header / Gate 1.** Checked against run 45882257652, at sha 1041841 (two docs-only commits behind HEAD), with all 4 jobs successful:
  - Test job 140124195607: 54 passed, 5 skipped (the e2e tests, which need `E2E_BASE_URL`); coverage 97.18 %, above the 90 % `fail_under`.
  - Compose job 140124195358: U1–U5 passed; the Redis-stop step logged "with Redis stopped: 503" and "after Redis restart: 200"; the production run failed with `UnsafeConfigurationError: … JWT__SECRET_KEY is the development default; DATABASE__URL uses the default postgres:postgres credentials`.
  - The newest run 45882969995 (919dbc7) is also green with identical numbers.
  - `ruff check .` and `ruff format --check .` pass locally. mypy was verified only through the green CI Type check job.
- **Scenario counts.** 4+15+16+8+9+9 = 61 numbered rows, which matches the section log and totals. The test count of 54 matches the code: 23 unit + 31 integration, counting parametrized cases.
- **Cited tests.** Every cited test exists and asserts its row, except the rows in findings 2 and 5. The 1.2-14 / 1.2-12 / T1–T10 / U1–U5 bodies were read and match their descriptions.
- **Failure log.** F1–F7 are consistent with the code (`Mapping` headers, request id captured at log time, handler filtering, FastAPI `HTTPException` in T7, `asyncio.timeout`, CSP, `__version__`). "8 fixed" counts F5 (rule disabled) and F8 (process) as fixes, which is a stretch.
- **Cross-check rows, verified against `209a9bd`:**
  - old `is_production` reads a missing `self.environment`;
  - CORS default `["*"]` with `allow_credentials=True`;
  - pool 10+20 with `pool_recycle=3600`;
  - `pydantic-settings` missing from `requirement.txt`;
  - `@app.on_event` used alongside the lifespan;
  - 7 health/info routes, with `/health/detailed` returning `str(e)`;
  - validation errors echoing `exc.errors()`;
  - HSTS only when `enable_https_redirect` is set;
  - the old CSP and headers as listed.
  - The "5 stacked" row is inaccurate (finding 11).
- **Roadmap.** All step-1 boxes are ticked except `uv.lock`, which is justified. Exit criteria are met: compose `/health/ready` returned 200, CI is green, coverage is reported.
- **Not verified:** that the Docker image runs as uid 10001 at runtime (nothing checks it); the README quick start with a copied `.env`; the mypy result locally.

**Missing scenarios:**
- **1.1:** C10, a `.env.production` file being committable. C11, the quick start exactly as written in the README, run in CI.
- **1.2:**
  - C2: invalid env values must stop startup with a clear error (`ENVIRONMENT=prod`, `DATABASE__POOL_SIZE=0/101`, `LOG__LEVEL=verbose`, malformed `CORS__ALLOW_ORIGINS` JSON).
  - C3: JWT secret at 31, 32 and 33 chars; pool limits at their edges.
  - C6: `staging` with default secrets; `JWT__ALGORITHM=none`; mutating nested settings after the startup check.
  - C12 row.
- **1.3:**
  - C3: request id of exactly 64 and 1 chars; several `X-Request-ID` headers; non-ASCII header bytes.
  - C6: security headers and CSP on 404/500 responses (the 500 test checks only the request id); log fields overriding reserved keys.
  - C8: assert exactly one `StdoutHandler` after repeated `configure_logging`.
  - C9: client disconnect / `CancelledError` (the request is currently logged as status 500).
  - C11, C12 rows.
- **1.4:**
  - C2: malformed JSON body (`json_invalid`) without echoing input; validation errors on query parameters; user-controlled keys appearing in `loc`.
  - C3: non-standard status code (499).
  - C6: 500 response for a CORS-allowed origin (finding 9).
  - C11: a browser client reading an error's `request_id`.
  - C12 row.
- **1.5:**
  - C2 (N/A reason or a test).
  - C7: N concurrent `/health/ready` calls with pool pressure.
  - C9: Postgres stopped, then restarted on the real stack (only Redis is tested); app started while the DB is down (live 200, ready 503).
  - Lifespan shutdown closes the engine and Redis (uncovered).
  - C12 row.
- **1.6:**
  - C6: automated non-root check; image contains no `tests/` or `.env`.
  - C9: N/A reason or a test.
  - C11: production container with safe settings starts, sends HSTS and hides docs on the real stack (only the refusal case is tested).

## Scorecard (by the independent reviewer)

| Area | Old code | After step 1 | Evidence |
| --- | --- | --- | --- |
| Folder structure & architecture | 6 | 8 | `app/` matches ARCHITECTURE §3 for this scope with one-way imports (`core`←`api`/`infra`/`main`); deductions: doc drift (finding 18) and probe logic living in the router module (`app/api/health.py:36-54`). |
| API design | 5 | 7 | One RFC 9457 format with stable codes (`app/core/errors.py`) and typed health models; but error responses aren't documented in OpenAPI and there is no rate-limit policy (finding 10). |
| Database schema | 5 | not built yet | Only an engine and a `SELECT 1` ping (`app/infra/database.py`). |
| Scalability & load balancing | 4 | 7 | Stateless, fully async, pure ASGI, bounded pool, check timeouts (`app/core/middleware.py`, `app/api/health.py:36-46`); but readiness is unthrottled on DB and Redis (finding 10), and there is no `/metrics` or performance measurement yet. |
| DSA / algorithms | 4 | not built yet | No algorithmic code yet beyond contextvar request ids (`test_t5_…`) and `asyncio.gather` over the checks. |
| Code quality & correctness | 3 | 7 | Short, typed, clear functions, and ruff is clean; known bugs: findings 6, 9, 14, 15, 16. |
| Duplication & reuse | 3 | 8 | Each concern is implemented once (one middleware, one `problem_response`, one logger); test setup is duplicated (finding 17). |
| Maintainability | 3 | 7 | 4-job CI with automatic report, mypy `--strict`, 97 % coverage (run 45882257652); but no lockfile (finding 19), the naming and `Any` rules are broken (findings 3, 4), and coverage misses greenlet code (finding 12). |
| Security | 2 | 6 | Production refuses unsafe config (`app/core/config.py:110-129`), no secret echo in errors or validation, strict CSP/HSTS, non-root image; gaps: findings 7, 8, 9, 10, 13. |
| **Overall** | **4** | **7** | Average of the 7 scored areas (7.1). The gate fails on 4 High findings: 1 and 2 are process and evidence problems, 3 and 4 are `CLAUDE.md` rule breaks. |
