# Step 1, independent review, round 4 (verbatim)

Output of the `milestone-reviewer` agent, recorded unchanged as the process requires.

---

### 5. Independent review: PASS

Reviewer: milestone-reviewer agent (`.claude/agents/milestone-reviewer.md`), 2026-11-27, commit ccea397

**Summary:** There are no Critical or High findings. All 11 round-3 findings are fixed in the code, tests and CI run 45921977725, or carried to a named later step, and nothing from rounds 1–2 has regressed. The step still doesn't meet the autonomous-merge bar: Security stays at 8. Strict environments accept the dev Redis password committed in the repo, and printing the settings shows the DB and Redis passwords; both fixes belong to step 1. Scalability stays at 8 because the new log queue has no size limit.

| # | Finding | Severity | Evidence | Recommended fix |
| --- | --- | --- | --- | --- |
| 1 | Staging and production accept the Redis password that is published in the repo. The new check only asks that `REDIS__URL` contains *a* password. `redis-dev-password` is the default in `.env.example` and `docker-compose.yml`, and it passes. CI proves it: the 1.2-21 "production with safe settings" container takes Compose's `REDIS__URL=redis://:redis-dev-password@redis:6379/0`, because the step doesn't override it, and reaches ready 200. The database check is also only a substring match on `postgres:postgres@`. A known default JWT secret is rejected, but a known default Redis password is not, which is inconsistent. | Medium | `app/core/config.py:140-141`, `_has_password` `:160-164`; `.env.example` (`REDIS_PASSWORD=redis-dev-password`); `docker-compose.yml:21,46`; `ci.yml` step "1.2-21" (no `REDIS__URL` override); Compose job 140254580406 | Add a `DEFAULT_REDIS_PASSWORD` constant and reject it in strict environments, as the JWT default is rejected. Add a test (1.2-28). Make CI 1.2-21 pass a non-default Redis password, and make 1.2-20 also grep for the Redis message. |
| 2 | `DatabaseSettings.url` and `RedisSettings.url` are plain `str`, so `repr(settings)` and `settings.model_dump()` print both passwords. Row 1.2-14 ("Settings printed or dumped → Secret not visible") is overstated: `test_s1_2_14` checks only the JWT secret. CLAUDE.md says "No secrets … in logs, errors". A settings object in a traceback, a debugger or a `log.info(settings=…)` call leaks the DB password. | Medium | `app/core/config.py:50,58`; `tests/unit/test_s1_2_settings.py:131-135` | Store the URLs as `SecretStr` (unwrap only in `app/infra/`), or give them a redacting repr. Extend 1.2-14 to assert that neither password appears in `repr`/`model_dump`. |
| 3 | The new log queue has no size limit (`queue.Queue()`, maxsize 0). Under the condition it was built for (stdout stalled by a slow log pipe or a blocked container log driver), memory grows until the process is OOM-killed. This swaps a latency problem for an availability problem. | Medium | `app/core/logging.py:131` | Use a bounded queue (e.g. 10 000). Override `enqueue` to `put_nowait`, drop on `queue.Full` and count the drops, and log the drop count when the writer catches up. Add a C9 test with a writer that blocks. If deferred, add an explicit item to ROADMAP step 8. |
| 4 | Error documentation in OpenAPI is likely wrong in a subtle way, and 1.4-18 doesn't test the generated schema. `_problem()` passes both `"model"` and an explicit `application/problem+json` content. FastAPI's `get_openapi_path` also adds the model schema under `route_response_media_type` (`application/json`), so every route probably advertises the 500 and 422 bodies as `application/json` too. `test_s1_4_17` checks only that `problem+json` is present, not that `application/json` is absent. `test_s1_4_18` was cut back after F12 to inspect the router's `responses` dict. It doesn't prove that a versioned route documents anything, yet row 1.4-18 says "Versioned API routes document 422 … and 500". | Low | `app/schemas/errors.py:37-47`; `tests/integration/test_s1_4_errors.py:194-214`; failed run 45921063060 (job 140251645486, assertion on `ValidationProblemOut` in components). Reasoned from the FastAPI source, not run. | Drop `"model"` and register the schemas yourself, or post-process the generated schema. In 1.4-17, assert the content types are exactly `{"application/problem+json"}`. In 1.4-18, mount a throwaway route with a body on `api_router` in a test app and assert on `/openapi.json`. |
| 5 | Row 1.3-33 says "Request path logs while stdout is slow", but the test never slows stdout. It only checks that no `StdoutHandler` is on the root logger and that a line comes out after `flush_logs()`. | Low | `tests/unit/test_s1_3_logging.py:114-127` | Add a writer that blocks on an unset `threading.Event`, and assert that `log.info` returns while the writer is blocked. Combine this with finding 3. |
| 6 | `AppLogHandler.prepare` skips the formatting that `QueueHandler.prepare` does by default, so the message is formatted later on the writer thread. A mutable `args` object changed after the call is logged in its later state, and traceback frames stay alive until the record is written. While `configure_logging` runs, a record emitted between `_stop_writer()` and the handler swap goes to a queue nobody reads, so it is silently lost. | Low | `app/core/logging.py:63-71,127-140` | Call `record.getMessage()` in `prepare` and store the result in `msg` with `args=None`, so the message text is fixed when it is logged. Swap the handler before stopping the old listener. |
| 7 | Unhandled-exception logs are not redacted. `log.exception` writes the full exception message and traceback. Readiness errors are redacted, but a driver or library exception whose message carries a DSN would be logged in clear. The CI test log shows `RuntimeError: database password is hunter2` from the crash fixture: the response is clean, the log is not. | Low | `app/core/middleware.py:105,149`; Test job 140254580808 log | Carry to step 8 or 9: apply `redact()` in `JsonFormatter` to `message` and `exception`, or log only the exception type and a redacted message in the boundary. |
| 8 | Records are inconsistent in three places. "Carried forward" still lists "Commit `uv.lock`…" although the ROADMAP box is ticked and R1-19 is fixed. Section 1.6 lists C10 as covered (1.6-11) and also as "N/A: no application data". The 1.5-19 CI step still can't detect a leaked credential, because the only lines left are DNS-failure messages (`gaierror`, `Error -3 connecting to redis:6379`). The real credential check is 1.5-21. | Low | `docs/milestones/step-1.md:192-194,338-341`; Compose job 140254580406 lines 714-715 | Delete the stale carried item. Remove the 1.6 C10 N/A row. Reword 1.5-19 to "no traceback; at least one Redis and one DB failure line". |
| 9 | CLAUDE.md now requires "a security audit for security-relevant steps" as a gate check. Nothing on this branch defines it (the skill is in out-of-scope PR #3), and step 1, which builds the settings safety checks, CORS and headers, doesn't say whether it applies. | Low | `CLAUDE.md:76-77`; `docs/milestones/README.md` (no mention) | Define the check in `docs/milestones/README.md`, or state in the step report that it applies from step 3 and why. |
| 10 | Local developer experience has drifted. The code default `RedisSettings.url` (`redis://localhost:6379/0`) has no password, but the Compose Redis now requires one, so running the app on the host without `.env` fails its readiness check. `make install` runs plain `uv sync`, so a local lockfile can drift silently; CI catches it only after a push. | Low | `app/core/config.py:58`; `docker-compose.yml:46`; `Makefile:7-8` | Point the default at the dev password, or document it. Make `install` run `uv sync --locked` and add a `lock` target for intentional updates. |
| 11 | Carried, verified: R3-03 (disconnect on a Pydantic-body route) is ROADMAP step 3 line 139. R3-04 (uvicorn's own record after a streaming error) is accepted in row 1.3-32. Digest and SHA pinning is step 9. | Low | `docs/ROADMAP.md:139`; `step-1.md:118` | As recorded. |

**Report claims verified:**
- **Which commit CI tested:** run 45921977725 ran on head sha bc90bc7, event pull_request, and all 4 jobs succeeded. `git diff --stat bc90bc7..HEAD` changes only `docs/milestones/step-1.md` (1 line). The run at ccea397 (45922341680) is also green.
- **Test job 140254580808:**
  - "139 passed, 6 skipped".
  - Coverage TOTAL: 538 statements with 7 missed, 86 branches with 6 partial, which gives 611/624 = 97.9 %, as claimed.
  - Uncovered lines: `errors.py` 120/132/151, `logging.py` 59-60 and 80->exit, `middleware.py` 86-87, `redis.py` 23->exit.
- **Type check job 140254580809:** "no issues found in 40 source files", with uv 0.13.10.
- **Compose job 140254580406:**
  - uid=10001.
  - 1.6-10: `app/db/redis -> 127.0.0.1:*`, and Redis answers "NOAUTH Authentication required."
  - The e2e run reports "6 passed".
  - 1.5-19 found two failure lines, one Redis and one database. Both are DNS errors.
  - 1.5-21 logged `DBAPIError … password authentication failed for user "postgres"`, without the password.
  - 1.2-20 shows both the JWT-default and the DB-default messages.
  - Limit: no real driver error contains the password, so redaction itself is proven only by the unit tests `s1_5_03` and `s1_5_20`.
- **Failed run 45921063060 (b419882):** the Test job failed on `ValidationProblemOut` missing from the OpenAPI components, which matches F12. The fix weakened the test (finding 4).
- **Round-3 findings, checked in code:**
  - R3-01: `docker-compose.yml`, all three ports bound to `127.0.0.1`, and Redis started with `--requirepass`.
  - R3-02: the 1.5-19 step was moved before 1.5-18, and the 1.5-21 step was added.
  - R3-03: carried (finding 11).
  - R3-04: accepted (finding 11).
  - R3-05: the autouse fixture in `tests/conftest.py:14-19`. The service URLs are read when the module is imported (`test_s1_5_health.py:16-17`), so 1.5-11 still gets them.
  - R3-06: `add_broken_stream_route` in `tests/helpers.py`.
  - R3-07: `ProblemCORSMiddleware`, tested by `test_s1_3_35` for a disallowed origin and a disallowed method.
  - R3-08: `QueueHandler`/`QueueListener` (findings 3 and 6).
  - R3-09: Compose section in `.env.example`.
  - R3-10: the ids are fixed, and the `test_s1_1_04` list now includes `config`, `models` and `config_manager.py`.
  - R3-11: `uv.lock` committed; `--locked` used in all CI jobs and in Docker; uv 0.13.10 pinned in both.
- **Round 1–2 fixes, checked for regressions:** none found.
  - Middleware order is still RequestContext, then CORS, then ErrorBoundary.
  - Settings sections are still frozen with `extra=forbid`; JWT is still HMAC-only.
  - CSP, HSTS and the docs gating are unchanged.
  - Readiness still fails closed, with single flight.
- **Counts:**
  - Scenarios: 5+27+35+18+21+11 = 117.
  - Failure log: 13 F + 20 R1 + 12 R2 + 11 R3 = 56, of which 52 fixed, 1 waiver, 1 process change, 1 accepted and 1 carried. This matches the stated totals.
- **Local checks:** `ruff check .` and `ruff format --check .` pass.
- **Not verified:**
  - pytest and mypy locally; packages can't be installed here.
  - FastAPI's duplicate `application/json` content (finding 4) is reasoned from the library source, not run.
  - That the owner actually gave the "Autonomous progression" instruction; it appears only as an author edit to CLAUDE.md in b419882.

**Missing scenarios:**
- **1.2**
  - C6: the strict check rejects the dev Redis password committed in the repo (finding 1).
  - C6: `repr`/`model_dump` of settings hides the DB and Redis passwords (finding 2).
- **1.3**
  - C9: the writer blocks or stdout stalls while the request path keeps logging, and the queue stays bounded with drops counted (findings 3 and 5).
  - C10: a record logged with mutable `args` keeps its value at log time (finding 6).
- **1.4**
  - C1: the generated OpenAPI for a real versioned route documents 422 and 500 as `application/problem+json` only (finding 4).
  - C6: an unhandled exception whose message contains a DSN is redacted in the log (finding 7).
- **1.6**
  - C11: the app runs on the host against the Compose stack using the code defaults or `.env` (finding 10).

## Scorecard (by the independent reviewer)

| Area | Old code | After step 1 | Evidence |
| --- | --- | --- | --- |
| Folder structure & architecture | 6 | 9 | The error schemas moved to `app/schemas/errors.py` and the routers only reference them (`app/api/health.py:288`, `app/api/v1/__init__.py`). Imports still go one way (api → services → core/infra), and there are no imports inside functions. |
| API design | 5 | 9 | One problem-JSON format now covers rejected CORS preflights too (`test_s1_3_35`), and the 500/422 errors are in OpenAPI (`test_s1_4_17`). Holding it at 9, not 10: the content-type docs are likely duplicated, and the versioned-route docs aren't tested on the generated schema (finding 4). |
| Database schema | 5 | not built yet | Only an engine and `SELECT 1` (`app/infra/database.py`). |
| Scalability & load balancing | 4 | 8 | Logging is off the event loop, readiness uses single flight with a cache (`test_s1_5_17`), and the app starts with the DB down (CI 1.5-18). But the log queue has no size limit (finding 3, fix now or add to step 8), and there are no metrics or load figures yet (step 8). |
| DSA / algorithms | 4 | not built yet | Nothing algorithmic beyond a lock-guarded cache. |
| Code quality & correctness | 3 | 9 | Every round-1/2/3 correctness item is fixed and tested. Coverage is 97.9 % (job 140254580808), and mypy strict is clean on 40 files. Only edge cases in the log queue remain (finding 6). |
| Duplication & reuse | 3 | 9 | `_problem()` builds both error-doc maps, `_jwt_secret_problems` and `_has_password` are extracted, and the test helpers are consolidated (`add_broken_stream_route`). |
| Maintainability | 3 | 9 | Locked, reproducible installs (`uv sync --locked` with the same uv 0.13.10 in CI and Docker), tests isolated from the shell environment (`test_s1_2_24`), and records consistent with CI. Minor stale entries remain (finding 8), and `make install` isn't locked (finding 10). |
| Security | 2 | 8 | Strict checks now cover repetitive JWT secrets and DB/Redis URLs without a password (`test_s1_2_25/26/27`). Ports are loopback-only and Redis requires auth (CI 1.6-10), and the wrong-password log check passes (CI 1.5-21). But production accepts the committed dev Redis password (finding 1, proven by CI 1.2-21), and the settings repr shows the DB/Redis passwords (finding 2); both fixes belong to step 1. |
| **Overall** | **4** | **9** (8.7 average) | 7 areas scored, no Critical or High findings. Security (8) fails the autonomous-merge bar of "every touched area ≥ 9", and its fixes belong to this step, so it can't be carried. Scalability (8) passes only if the queue limit is fixed or added explicitly to step 8. |
