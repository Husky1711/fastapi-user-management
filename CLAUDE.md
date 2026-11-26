# CLAUDE.md

Working rules for anyone changing this repository — human developers and AI coding agents
alike. Read this file fully before making a change.

## What this project is

A **reusable, production-grade user-management backend** (auth, organizations, roles &
permissions, sessions, audit log) that new products start from. The quality bar is the
measurable "10/10" table in `docs/VISION.md` §5.

**Read before working:**

1. `docs/VISION.md` — why, scope, quality bar
2. `docs/ARCHITECTURE.md` — target design; the source of truth for structure and conventions
3. `docs/ROADMAP.md` — the current step and its checklist
4. `docs/adr/` — decisions already made; don't reopen them without a new ADR

## Current state

- `v2` is built from scratch: it holds only the new application (`app/`), its tests and docs.
- The **old implementation lives untouched on `main`** (last commit `209a9bd`). Use it only as a
  reference to cross-check APIs, tables and behaviour (milestone gate check 4). Never copy its
  code or patterns; it scored 4/10.
- The new application grows step by step, following `docs/ROADMAP.md`.

## How to work

1. Find the first unfinished step in `docs/ROADMAP.md`. Work only on that step unless the
   owner asks otherwise.
2. Create a branch from up-to-date **`v2`** (the integration branch, see below):
   `step-<n>/<short-topic>` (e.g. `step-3/refresh-rotation`). Docs-only work: `docs/<topic>`.
3. Work section by section (see "Testing, logging and scoring"): scenario plan first, then
   tests, then code. Never move to the next section with the current one untested.
4. Run the full check before every commit: `make check`.
5. Tick the finished items in `docs/ROADMAP.md` and update the step report in the same PR.
6. Open a pull request **into `v2`** using the template. Never push directly to `v2` or `main`;
   never force-push a shared branch.
7. If you discover the plan or architecture is wrong, stop and say so in the PR. Change the
   doc (and add an ADR for a design decision) in that PR rather than silently diverging.

### Branches

| Branch | Holds | Changes by |
| --- | --- | --- |
| `main` | The legacy code, untouched, until the new backend is released | One final merge of `v2` at release (roadmap step 10) |
| `v2` | The new backend in progress | Pull requests from step branches only |
| `step-<n>/<topic>`, `docs/<topic>` | One step or part of a step | You; short-lived, deleted after merge |

### Commits

[Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `refactor:`,
`test:`, `docs:`, `chore:`, `ci:`. Subject in the imperative, ≤ 72 characters. One logical
change per commit.

## Testing, logging and scoring (mandatory)

Full process: `docs/milestones/README.md`. These rules are not optional and are not skipped
for small changes or to save time.

**Mindset.** Test as the most experienced tester and a doubtful senior engineer: assume the
code is broken and try to prove it. Passing tests you wrote for the happy path proves nothing.

**Level 1: every section.**
1. At the start of a step, split it into sections and create `docs/milestones/step-<n>.md`
   from the template, with the section log.
2. Before coding a section, write its scenario plan covering **every category C1–C12** of the
   scenario checklist (happy path, invalid input, boundaries, authentication, authorization,
   security abuse, concurrency, repeat calls, dependency failure, data integrity, real user
   flow, regression). A category is either covered or marked N/A with a reason.
3. A section is done only when all its scenarios pass in CI. **Never start the next section
   while the current one is untested.**
4. Then update the section log (✅, scenario counts), commit and push.

**Level 2: every step.** When all sections are ✅, retest the whole step together on the real
stack and run the five-check gate: automated, tester, user, cross-check vs the old code on
`main`, independent review. PASS plus the owner's approval is required before merge, and the
next step starts only after that.

**Session rule.** Before any session ends, every finished section is tested, committed, pushed
and marked ✅. Unfinished work is committed and marked 🔄 with a note on what is left. A new
session starts by reading the section log and continues from the first section that isn't ✅.

**Records.**
- *Automatic test report*: CI publishes every test's result plus coverage on every run. It is
  the proof; never type test results by hand.
- *Written log* in the step report: section log, scenario plan with results per category,
  totals (passed / failed / fixed), and a link to the CI run.
- *Failure log*: every failure found (CI, gate, review) with cause and fix. Never hide or
  silently fix a failure; record it.
- *Scenario ids* in test names (`test_s<step>_<section>_<n>_<what>`) link plan, test and report.

**Scoring.** After each step, the **independent reviewer** (never the author) scores the nine
review areas against the old code's baseline, one line of evidence per score, and updates
`docs/milestones/SCORECARD.md`. Areas not built yet are marked "not built yet", not given a
number. A step is production-grade when every area it touches scores ≥ 9, or a lower score is
explained and accepted by the owner.

## Definition of done (every PR)

- [ ] Matches `docs/ARCHITECTURE.md` (or updates it with reasons)
- [ ] Tests added for success, auth failure, permission failure and validation failure where relevant
- [ ] `ruff`, `mypy --strict` and `pytest` pass; coverage of touched services/core ≥ 90 %
- [ ] Schema changes come with an Alembic migration that also downgrades
- [ ] New settings appear in `.env.example` with a safe default and a comment
- [ ] New endpoints have a `response_model`, documented error codes and a rate-limit policy
- [ ] No secrets, tokens, passwords or full emails in logs, errors or fixtures
- [ ] Scenario checklist C1–C12 covered for each section touched; section log and failure log updated
- [ ] `docs/ROADMAP.md` boxes ticked; README/docs updated if behaviour changed

## Code rules

### Layers (see `docs/ARCHITECTURE.md` §2)

- **Routers** (`app/api/`) do HTTP only: take dependencies, call **one** service method, return
  a schema. No queries, no business rules, no `try/except` that turns errors into 500s.
- **Services** (`app/services/`) hold business rules and own transactions. They never see
  `Request`, headers or status codes; they raise `AppError` subclasses.
- **Repositories** (`app/repositories/`) hold queries. Org-scoped queries always take
  `organization_id` as a required argument.
- **Infra** (`app/infra/`) wraps Redis, email and other external systems behind small interfaces.

### One way to do each thing

| Need | Use | Never |
| --- | --- | --- |
| Current user | `Depends(get_current_user)` | Decode JWTs in routes or services |
| Access check | `Depends(require_permission("members:invite"))` | `if user.role == "admin"` |
| Client IP / user agent | `Depends(client_info)` | `request.client.host` |
| Errors | `raise NotFound(...)`, `raise Forbidden(...)` (from `app/core/errors.py`) | `HTTPException` in services; returning error dicts |
| Response shape | Pydantic `*Out` schema with `from_attributes=True` | Hand-built dicts |
| Lists | `Page[T]` + `PaginationParams` | Unbounded `.all()` |
| Settings | `get_settings()` (or `request.app.state.settings`) from `app/core/config.py` | Copying settings into module constants; `os.getenv` |
| Time | `app.core.clock.now()` (UTC, aware) | `datetime.utcnow()` |
| Passwords | `security.hash_password` / `verify_password` (Argon2id) | Any other hashing |
| Logging | `get_logger()` from `app/core/logging.py`, with structured fields | f-strings with secrets; `print` |

If you are about to write the same 3+ lines a second time, extract them.

### Python style

- Python 3.12+, full type hints, `mypy --strict` clean. No `Any` without a comment.
- `async def` all the way down for I/O (async SQLAlchemy, `redis.asyncio`). Never call
  blocking I/O inside an `async def`.
- Plain functions or small injected classes; no classes made only of `@staticmethod`s.
- No bare `except:`. Catch specific exceptions, and only where you can handle them.
- No imports inside functions to dodge circular imports — fix the dependency direction.
- Functions stay short (aim < 40 lines). Names say what, comments say why.
- Delete dead code; don't comment it out.

### Database rules

- PostgreSQL only. UUID primary keys (except `audit_logs.id`). `timestamptz` everywhere.
- Every FK declares `ondelete`. Enum-like columns are enums or CHECK constraints.
- Every new query pattern has a supporting index, added in the same migration.
- No N+1: load related data with `selectinload`/joins; bulk `UPDATE`/`DELETE` for sets.
- Migrations are reviewed like code; never edit a migration that has been merged.

### Security rules (non-negotiable)

- Never weaken a default to make a test pass.
- Tokens (refresh, reset, verify, invite) are random ≥ 256 bits and stored only as hashes.
- Responses must not reveal whether an email exists (login, reset, signup conflicts → generic message + rate limit).
- Non-members get **404** for org resources, not 403.
- No debug or test-only endpoints in the app. Use tests and fixtures instead.
- Any change to auth, sessions or permissions needs tests for the attack case, not only the happy path.

### Testing rules

- `tests/unit` for pure logic; `tests/integration` hits the app through `httpx.AsyncClient`
  with real Postgres and Redis (Docker / CI services), rolled back per test.
- Factories over fixtures with hard-coded ids. No sleeping in tests; inject the clock.
- Each org-scoped endpoint is added to the tenant-isolation test suite.

## Commands

```bash
make install     # uv sync (creates uv.lock; commit it)
make run         # docker compose up (app + postgres + redis) → http://localhost:8000/docs
make lint        # ruff check + ruff format --check
make typecheck   # mypy --strict
make test        # pytest with coverage
make migrate     # alembic upgrade head (from step 2)
make check       # lint + typecheck + test, exactly what CI runs
```

Tests that need real PostgreSQL and Redis are marked `services` and run when
`RUN_SERVICE_TESTS=1` (CI sets it). Locally: `make run` in one terminal, then
`RUN_SERVICE_TESTS=1 DATABASE__URL=... REDIS__URL=... make test`.

## Things to ask the owner about (don't guess)

- Anything that changes `docs/VISION.md` scope
- Reversing an ADR
- Adding a new runtime dependency that isn't in `docs/ARCHITECTURE.md` §1
- Anything destructive on a real database or on GitHub (deleting branches, tags, releases)
