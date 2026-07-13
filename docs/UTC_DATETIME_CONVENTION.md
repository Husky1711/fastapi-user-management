# UTC datetime convention

## Current stack (MySQL)

- Columns use naive `DATETIME` (SQLAlchemy `DateTime(timezone=True)` does not store TZ on MySQL).
- Application code must store and compare **UTC wall time** only.
- Use `utils.datetime_utc.utc_now()` (and helpers in that module) instead of `datetime.utcnow()` / local time.

## Comparison rules

- Prefer comparing in SQL against `utc_now()`-produced naive values, or normalize both sides to naive UTC before Python comparison.
- Do not mix aware (`tzinfo` set) and naive datetimes in the same expression.

## PostgreSQL / Neon path

If production moves to Postgres, prefer `TIMESTAMPTZ` for all timestamps and store aware UTC (`datetime.now(timezone.utc)`). Revisit models and `utc_now()` when that migration starts (see `DATABASE_SCHEMA_REVIEW.md` §4.6.3).
