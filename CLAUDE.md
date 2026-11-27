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

- The code at the repo root (`main.py`, `routes/`, `services/`, `models/`, `utils/`, …) is the
  **legacy** implementation. From roadmap step 1 it lives in `legacy/` and is reference only:
  do not import it, run it, or fix bugs in it.
- The new application is built in `app/`, step by step, following `docs/ROADMAP.md`.
- The current `README.md` describes the legacy code and overstates some features; it is
  rewritten in step 10.

## How to work

1. Find the first unfinished step in `docs/ROADMAP.md`. Work only on that step unless the
   owner asks otherwise.
2. Create a branch from up-to-date **`v2`** (the integration branch, see below):
   `step-<n>/<short-topic>` (e.g. `step-3/refresh-rotation`). Docs-only work: `docs/<topic>`.
3. Write the test first when practical, then the code.
4. Run the full check before every commit: `make lint typecheck test`
   (available from step 1).
5. Tick the finished items in `docs/ROADMAP.md` in the same PR.
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

## Definition of done (every PR)

- [ ] Matches `docs/ARCHITECTURE.md` (or updates it with reasons)
- [ ] Tests added for success, auth failure, permission failure and validation failure where relevant
- [ ] `ruff`, `mypy --strict` and `pytest` pass; coverage of touched services/core ≥ 90 %
- [ ] Schema changes come with an Alembic migration that also downgrades
- [ ] New settings appear in `.env.example` with a safe default and a comment
- [ ] New endpoints have a `response_model`, documented error codes and a rate-limit policy
- [ ] No secrets, tokens, passwords or full emails in logs, errors or fixtures
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
| Settings | `from app.core.config import settings` | Copying settings into module constants; `os.getenv` |
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

Available from roadmap step 1:

```bash
make install     # uv sync
make run         # docker compose up (app + postgres + redis)
make lint        # ruff check + ruff format --check
make typecheck   # mypy --strict
make test        # pytest with coverage
make migrate     # alembic upgrade head
```

## Things to ask the owner about (don't guess)

- Anything that changes `docs/VISION.md` scope
- Reversing an ADR
- Adding a new runtime dependency that isn't in `docs/ARCHITECTURE.md` §1
- Anything destructive on a real database or on GitHub (deleting branches, tags, releases)
