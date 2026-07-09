# Alembic migration playbook

Strategy **A** (adopted): baseline revision creates tables from SQLAlchemy metadata; integrity constraints (FKs, uniques) ship in follow-on revisions. This keeps fresh installs and legacy `create_all()` databases on a predictable path.

## Revision chain

| Revision | File | Purpose |
|----------|------|---------|
| `20260708_baseline` | `alembic/versions/20260708_baseline_schema.py` | `Base.metadata.create_all()` — tables only |
| `20260708_compliance_fks` | `alembic/versions/20260708_compliance_foreign_keys.py` | Compliance FKs + idempotent guards |

New schema changes: add a **new** revision; do not edit applied revisions.

## Fresh database (CI, local, Codespaces)

```bash
export DATABASE_URL=mysql+pymysql://fastapi:fastapi@127.0.0.1:3306/fastapi_users
python scripts/ci_bootstrap_db.py
# or: alembic upgrade head && seed users manually
```

`ci_bootstrap_db.py` waits for MySQL, runs `alembic upgrade head`, and seeds bcrypt test users.

## Existing database (created before Alembic)

If tables already exist from `create_all()` or manual setup **and** schema matches head:

```bash
alembic stamp head
```

This records the current revision without re-running `create_all()`. Use only when the live schema already matches what `upgrade head` would produce.

If schema is behind head, run:

```bash
alembic upgrade head
```

The compliance FK migration skips constraints that already exist.

## Rollback (dev only)

```bash
alembic downgrade -1          # one step back
alembic downgrade 20260708_baseline
alembic downgrade base          # drop all (destructive)
```

**Production:** prefer forward-only migrations; test downgrade in staging before relying on it.

## Adding a new revision

```bash
alembic revision -m "short_description"
```

Guidelines:

1. One concern per revision (FKs, indexes, column adds).
2. Make additive changes idempotent when touching legacy DBs (check `information_schema` before `create_foreign_key`).
3. Run `alembic upgrade head` on an empty MySQL instance in CI before merging.

## Squash policy (Strategy C — later)

When the revision chain stabilizes (post–Sprint 2), a one-time squash to a single baseline is optional. Requires:

- Documented stamp procedure for all environments
- CI green on empty DB
- No open Codespaces instances on old revision IDs

Until then, keep Strategy A.
