# 0005. Async, layered architecture

- Status: Accepted
- Date: 2026-11-27

## Context

The legacy code declares routes `async def` but calls synchronous SQLAlchemy and Redis inside
them, which blocks the event loop and caps throughput. Business logic, queries, HTTP handling
and logging are mixed in 80–120-line route functions, with the same blocks copy-pasted up to
11 times.

## Decision

- Fully async I/O: SQLAlchemy 2.0 async + `asyncpg`, `redis.asyncio`. No blocking call inside
  `async def`; CPU-heavy work (Argon2) runs in a thread pool.
- Four layers with one-way dependencies — `api → services → repositories / infra` — as described
  in `docs/ARCHITECTURE.md` §2.
- Shared concerns are FastAPI dependencies (`get_current_user`, `require_permission`,
  `client_info`, `get_db`) and are the only way to do those things.
- Errors are raised as typed `AppError`s and converted once, centrally, to RFC 9457 responses.
- Packaging with `uv` and `pyproject.toml`; quality gates `ruff`, `mypy --strict`, `pytest`.

## Consequences

- One instance handles far more concurrent requests; behaviour under load is predictable.
- Each layer can be tested on its own; services can be tested without HTTP.
- More files than the legacy layout, and contributors must know async SQLAlchemy.
- Argon2 must be offloaded explicitly (`anyio.to_thread.run_sync`) or it will block.
