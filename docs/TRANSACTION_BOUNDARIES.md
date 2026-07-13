# Transaction & commit ownership

Services receive a SQLAlchemy `Session` from FastAPI's `get_db` dependency (`utils/database.py`). There is no nested unit-of-work framework; **the service that starts a logical write owns `commit` / `rollback`**.

## Rules

| Layer | Responsibility |
|-------|----------------|
| Route | Call one service method for a use case; do **not** call `db.commit()` |
| Service | Mutate ORM objects; `db.commit()` on success; `db.rollback()` on handled failure mid-flow |
| `get_db` | Open session, yield it, **rollback if the request raises**, then close |

## Patterns in this codebase

1. **Single-service write** — e.g. `UserService.create_user_by_admin` creates the user, syncs RBAC, then `commit`s once.
2. **Flush before related writes** — `db.flush()` assigns PKs (e.g. new user id) before manager validation or RBAC sync; still one `commit` at the end.
3. **Handled failure after flush** — rollback and return `{success: False}` (see manager cycle checks).
4. **Route-side side effects after commit** — welcome email, audit log. Prefer best-effort: user row already committed; email/audit failures must not orphan expectations (log + continue). Audit helpers usually open their own path with the same session — if they `commit`, keep that explicit in the service.

## Do not

- Commit in a route and again in a service for the same change
- Leave an open transaction across an HTTP call to SMTP/Redis without committing first (holds DB connections)
- Catch broad `Exception`, log, and return success without rolling back

## Dependency behavior

`get_db` now rolls back on uncaught exceptions so failed requests do not leak dirty sessions to the pool:

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

Successful paths still rely on the service `commit`.

## Refresh tokens / sessions

`RefreshTokenService` and login paths commit when issuing or rotating tokens. Logout / revoke must commit the revocation before returning 200 so concurrent refresh cannot race on a still-valid row.

## Tests

Unit tests that patch services should not assume auto-commit. Integration tests share `SessionLocal` / TestClient lifespan; prefer committing via the service under test.
