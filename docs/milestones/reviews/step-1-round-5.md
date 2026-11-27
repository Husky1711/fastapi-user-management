# Step 1, independent review, round 5 (verbatim)

Output of the `milestone-reviewer` agent, recorded unchanged as the process requires.

---

### 5. Independent review: PASS

Reviewer: milestone-reviewer agent (`.claude/agents/milestone-reviewer.md`), 2026-11-27, commit c82fd40

**Summary:** There are no Critical or High findings. All eleven round-4 findings are resolved in the code, the tests and CI run 45923959839 (head a887492), or carried with a sound reason, and nothing from rounds 1–3 has regressed. The fixes to Security (dev-password rejection, `SecretStr` URLs, formatter-wide redaction) and Scalability (bounded queue with drop counting) hold up. The main remaining weakness is in the new bounded queue itself: stopping the writer while the queue is full raises `queue.Full`, and if stdout is stuck the stop hangs (finding 1). That is Medium. It is narrow enough that Scalability and Code quality still reach 9, but it should be fixed now or added explicitly to step 8.

| # | Finding | Severity | Evidence | Recommended fix |
| --- | --- | --- | --- | --- |
| 1 | The bounded queue breaks writer shutdown. `_stop_writer()` calls `QueueListener.stop()`, which calls `enqueue_sentinel()` → `queue.put_nowait(sentinel)`. When the queue is full, which is exactly the stuck-stdout case R4-03 was built for, this raises `queue.Full`. The effects: (a) at process exit, the `atexit` hook raises. (b) In `configure_logging`, the root handler has already been swapped to the new queue, but `_log_queue, _listener = new_queue, new_listener` never runs. The new listener thread is then orphaned, and `flush_logs()` joins the old queue, not the one in use. If the queue is not full but the writer is stuck, `stop()` puts the sentinel and then `join()`s forever, so the process can't exit until SIGKILL. 1.3-33 avoids both cases by unblocking the writer before it reconfigures. | Medium | `app/core/logging.py:136-143` (`_stop_writer`, `atexit.register`), `:196-201` (swap, then `_stop_writer()`, then assign); stdlib `QueueListener.stop`/`enqueue_sentinel` (uses `put_nowait`); `tests/unit/test_s1_3_logging.py` `test_s1_3_33` (calls `writer.unblock.set()` before `configure_logging("INFO")`) | Override `enqueue_sentinel` to evict one queued record (counted as a drop) when the queue is full. Bound the shutdown with a join timeout, using a custom stop or a non-blocking `join(timeout)` on the thread. Assign the module globals before stopping the old writer. Add a C9 test: reconfigure and shut down while the writer is stuck and the queue is full. If deferred, add an explicit step-8 ROADMAP item. |
| 2 | `AppLogHandler.prepare` mutates the original `LogRecord` in place: `msg`, `args=None`, `exc_info=None`. The stdlib `QueueHandler.prepare` copies the record first (bpo-35726) so that other handlers in the chain still see `exc_info`. Today `AppLogHandler` is appended last, so this is mostly harmless. Any handler that runs after it, such as a pytest `caplog` handler attached later or an error-reporting handler added in step 8, loses the traceback. `stack_info` is also neither kept nor cleared. | Low | `app/core/logging.py:86-96`; `logging.handlers.QueueHandler.prepare` ("make copy of record to avoid affecting other handlers") | Run `record = copy.copy(record)` first, and freeze the copy. |
| 3 | The redaction safety net is narrower than row 1.3-37 suggests. A structured field whose *key* is sensitive (`log.info("x", password="hunter2")`, `token=…`) is written in clear, because the regex needs `password=` inside the value. Non-string field values (an exception object, a dict holding a DSN) bypass `_clean` and are stringified by `json.dumps(default=str)` without redaction. Colon/JSON forms (`"password": "x"`, `Authorization: Bearer …`) are not matched either. CLAUDE.md still forbids passing these, so this is a defence-in-depth gap, not a leak in current code. | Low | `app/core/logging.py:38-39,56-57`; `app/core/redaction.py:9-13`; `test_s1_3_37` (only tests a DSN inside a string value) | Mask values whose key matches the secret pattern, run `redact(str(v))` on non-primitive values, and add `:`/JSON forms. Extend 1.3-37. This can go to step 3, the first step with real credentials in requests. |
| 4 | The well-known-password check can be bypassed by a trivial variation. `urlsplit().password` is not percent-decoded, so `redis%2Ddev%2Dpassword` passes the check, but the drivers decode it and connect with `redis-dev-password`. The match is also case-sensitive (`Postgres`, `PASSWORD` pass). | Low | `app/core/config.py:25,164-173` | Compare `unquote(password).lower()` against a lower-cased set. Add two cases to 1.2-28. |
| 5 | 1.3-33 has no `try/finally`. If any assertion fails before `writer.unblock.set()`, the stuck writer and the 5-slot queue stay installed. The next `configure_logging` then hits finding 1 (`queue.Full`, or a hang of up to 10 s per record), so one failure cascades into misleading failures elsewhere. | Low | `tests/unit/test_s1_3_logging.py` `test_s1_3_33` | Unblock the writer and restore logging in a `finally` block or a fixture. |
| 6 | Some records are stale. CLAUDE.md "Commands" still says `make install # uv sync (creates uv.lock; commit it)`, which contradicts the R4-10 fix (`uv sync --locked`, plus a new `make lock`). `docs/milestones/SCORECARD.md` still shows the round-3 numbers (API design 8; its log row stops at round 3). CLAUDE.md requires the reviewer's scores to be recorded there. | Low | `CLAUDE.md:189`; `Makefile:7-11`; `docs/milestones/SCORECARD.md:11-27` | Update the CLAUDE.md command comment, and add the round-4 and round-5 scores to SCORECARD.md. |
| 7 | `create_app(api_routers=…)` is a test-only hook on the production factory. It is the same pattern as `health_checks`, and it adds no endpoint, so the "no test-only endpoints" rule isn't broken. It is still an extension point that production never uses. | Low | `app/main.py:82-88,126`; `app/api/v1/__init__.py:11-19` | Acceptable. Once step 3 adds a real router, consider testing against it instead and removing the hook. |
| 8 | Carried items, verified: R3-03 (disconnect on a Pydantic-body route) is in ROADMAP step 3. R3-04 is accepted in row 1.3-32. Digest and SHA pinning is step 9. | Low | `docs/ROADMAP.md`; `step-1.md:119,357-360` | As recorded. |

**Report claims verified:**

**CI run 45923959839:**
- Ran on head `a887492`, event pull_request, and all 4 jobs succeeded.
- `git diff --stat a887492..HEAD` changes only `docs/milestones/step-1.md`.
- **Test job 140260893883:**
  - "145 passed, 6 skipped".
  - Coverage TOTAL is 599 statements with 7 missed and 94 branches with 7 partial: 679/693 = 98.0 %, as claimed.
  - Missed lines: `errors.py` 120/132/151, `logging.py` 73-74 and 132->exit, `middleware.py` 86-87, `redis.py` 23->exit, `main.py` 70->73.
- **Type check job 140260894063:** "no issues found in 41 source files" with uv 0.13.10.
- **Compose job 140260893920:**
  - uid=10001.
  - app, db and redis are published on `127.0.0.1` only, and Redis answers `NOAUTH`.
  - e2e: "6 passed".
  - 1.5-19 has one Redis line and one DB line, with no traceback.
  - 1.5-21 shows `password authentication failed for user "postgres"`, without the password.
  - 1.2-21 creates a Redis ACL user `app_ci`, passes `REDIS__URL` with it, and reaches ready 200; `/docs` and `/openapi.json` return 404.
  - 1.2-20's output names all three problems: JWT default, DB well-known password, Redis well-known password.

**Round-4 findings, checked against the code (diff `ccea397..a887492`):**
- R4-01: `WELL_KNOWN_PASSWORDS` and `_url_password_problems` (`config.py:22-25,164-173`); test `s1_2_28` (×4); CI 1.2-20 and 1.2-21 as above. Weaknesses in finding 4.
- R4-02: the URLs are `SecretStr` and are unwrapped only in `app/infra/database.py:11` and `app/infra/redis.py:12`. `test_s1_2_14` now asserts the JWT, DB and Redis secrets are all absent from `repr`, `str` and `model_dump`.
- R4-03: `queue.Queue(maxsize=queue_size)`, `LOG__QUEUE_SIZE` (100–1 000 000, default 10 000) in `.env.example`, `put_nowait` with a drop counter and a drop notice. Shutdown interaction in finding 1.
- R4-04: `"model"` removed, `PROBLEM_SCHEMAS` registered through `_add_problem_schemas`. 1.4-17 asserts the content types are exactly `{"application/problem+json"}`. 1.4-18 mounts a real body route under `/api/v1` and checks both the generated schema and a live 422.
- R4-05: the `StuckWriter` test blocks on an unset `threading.Event`; 50 logs go into a queue of 5; it checks `pending() <= 5` and that the drop count is reported after recovery. Test robustness in finding 5.
- R4-06: `prepare` freezes `msg`, `args` and `exc_text` (1.3-36); the handler is swapped before `_stop_writer`. Side effect in finding 2.
- R4-07: `JsonFormatter` redacts the message, string fields and the exception (1.3-37). Gaps in finding 3.
- R4-08: the stale `uv.lock` carry is removed, the 1.6 C10 N/A row is removed, and the 1.5-19 wording and CI step name are corrected.
- R4-09: the security-audit statement is at `step-1.md:277-280`.
- R4-10: the default Redis URL carries the dev password, and the Makefile has `install: uv sync --locked` plus `lock`. CLAUDE.md is left stale (finding 6).
- R4-11: carried items, verified (finding 8).

**Rounds 1–3, checked for regressions:** none found.
- Middleware order is still RequestContext, then CORS, then ErrorBoundary (`main.py:112-124`).
- Settings sections are still frozen with `extra="forbid"`; JWT is still HMAC-only (`config.py:49,69`).
- Readiness still fails closed, with single flight.
- `redact` moved to `app/core/redaction.py`, which removes the duplication, and its cap is kept for readiness errors (`health.py:40`).

**Counts:**
- Scenarios: 5+28+37+18+21+11 = 120.
- Failure log: 13 F + 20 R1 + 12 R2 + 11 R3 + 11 R4 = 67. That splits into 62 fixed, 1 waiver, 1 process change, 1 accepted, 1 carried and 1 carried-check, which matches the stated totals.
- There are 109 test functions; the 151 collected (145 passed + 6 skipped) is consistent with the parametrizations.

**Local checks:** `ruff check .` and `ruff format --check .` pass.

**Not verified:**
- pytest and mypy locally, because packages can't be installed here.
- Individual test names in CI: the log isn't verbose, and the JUnit summary is only in the run's Summary page and artifact.
- The `queue.Full` and hang behaviour in finding 1 is reasoned from the stdlib source (`QueueListener.stop`/`enqueue_sentinel`), not executed.

**Missing scenarios:**
- **1.2**
  - C6: a well-known password in percent-encoded or different-case form (finding 4).
- **1.3**
  - C9: reconfiguring logging, or shutting the process down, while the writer is stuck and the queue is full (finding 1).
  - C10: other root handlers still receive `exc_info` after `AppLogHandler` processes a record (finding 2).
  - C6: a structured field named `password` or `token` with a plain value, and a non-string field value that contains a DSN (finding 3).

## Scorecard (by the independent reviewer)

| Area | Old code | After step 1 | Evidence |
| --- | --- | --- | --- |
| Folder structure & architecture | 6 | 9 | Redaction is now a single core module (`app/core/redaction.py`) used by both logging and health. Secrets are unwrapped only in `app/infra/`, and imports still go one way (api → services → core/infra). |
| API design | 5 | 9 | The generated OpenAPI documents 422 and 500 as `application/problem+json` only, proven on a real `/api/v1` body route and a live 422 (`test_s1_4_17`, `test_s1_4_18`). Not 10: there are no feature endpoints yet, and rate-limit policy only arrives in step 4. |
| Database schema | 5 | not built yet | Only an engine and `SELECT 1` (`app/infra/database.py`). |
| Scalability & load balancing | 4 | 9 | The log queue is bounded and drops are counted (`logging.py:96-115`, `test_s1_3_33`), readiness uses single flight with a cache (`test_s1_5_17`), and the app starts with the DB down (CI 1.5-18). Held below 10 by the shutdown edge case with a full queue (finding 1), and by the missing metrics and load figures, which belong to step 8. |
| DSA / algorithms | 4 | not built yet | Nothing algorithmic beyond a lock-guarded cache and a bounded queue. |
| Code quality & correctness | 3 | 9 | Coverage is 98.0 % (job 140260893883), mypy strict is clean on 41 files, and ruff is clean. Every round-4 correctness item is tested. The remaining issues are narrow edge cases in the log queue (findings 1 and 2). |
| Duplication & reuse | 3 | 9 | `redact` is extracted from health into core and reused. `_url_password_problems` replaces three branches. `_problem()` and `_REF` build every error doc. Test helpers are shared (`tests/helpers.py`). |
| Maintainability | 3 | 9 | Installs are locked (`make install` uses `--locked`, with a separate `make lock`), and the report's counts match CI exactly. Minor stale docs remain: CLAUDE.md `make install` and SCORECARD.md not updated (finding 6). |
| Security | 2 | 9 | Strict environments reject published and well-known passwords for the DB and Redis (`test_s1_2_28`, CI 1.2-20 with all three messages). DB, Redis and JWT secrets are hidden from `repr` and dumps (`test_s1_2_14`). Every log line passes through redaction (`test_s1_3_37`). Ports are loopback-only and Redis requires auth (CI 1.6-10). Held below 10 by the gaps in findings 3 and 4, and by image and action pinning, which is carried to step 9. |
| **Overall** | **4** | **9** (9.0 average) | 7 areas scored, all ≥ 9, with no Critical or High findings. This meets the autonomous-merge bar. Finding 1 (Medium) should be fixed now or recorded as a step-8 carry. |
