# 0002. Use PostgreSQL instead of MySQL

- Status: Accepted
- Date: 2026-11-27

## Context

The legacy code targets MySQL through PyMySQL, with no migrations. The new data model needs
case-insensitive unique emails, real enums, JSON metadata for the audit log, partial and
composite indexes, and — optionally later — database-enforced tenant isolation. There is no
production data to migrate yet, so switching now costs almost nothing; switching later would
be expensive.

## Decision

Use PostgreSQL 16+ as the only supported database, accessed with SQLAlchemy 2.0 async and
`asyncpg`, with schema managed by Alembic.

We use: `citext` for emails and slugs, native enums or CHECK constraints, `jsonb` for audit
metadata, `inet` for IP addresses, `timestamptz` for all times, partial indexes where they
fit (e.g. active sessions).

## Consequences

- Stronger guarantees in the database itself, fewer bugs that depend on application discipline.
- Row-level security is available as a second tenant-isolation layer (backlog).
- Matches the default of most hosting platforms and FastAPI templates.
- Projects that must use MySQL would need to fork; we accept this. Supporting several
  databases would weaken every guarantee above.
