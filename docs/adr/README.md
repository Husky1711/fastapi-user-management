# Architecture Decision Records

An ADR records one significant decision: the context, what we chose, and what it costs us.
They are short on purpose. Accepted ADRs are not edited; to change a decision, write a new
ADR that supersedes the old one and update the old one's status line.

| # | Decision | Status |
| --- | --- | --- |
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-postgresql.md) | Use PostgreSQL instead of MySQL | Accepted |
| [0003](0003-multi-organization-memberships.md) | Users can belong to many organizations | Accepted |
| [0004](0004-permissions-as-data.md) | Permission-based access control, stored as data | Accepted |
| [0005](0005-async-layered-architecture.md) | Async, layered architecture | Accepted |
| [0006](0006-auth-tokens-and-password-hashing.md) | Argon2id, PyJWT and rotating refresh tokens | Accepted |
| [0007](0007-rebuild-beside-legacy.md) | Rebuild beside the legacy code; the API may change | Accepted |
| [0008](0008-gcra-rate-limiting.md) | GCRA rate limiting in a Redis Lua script | Accepted |
| [0009](0009-ascii-email-domains.md) | Email domains are ASCII only (no IDN) for now | Accepted |
| [0010](0010-session-limits-and-ending-sessions.md) | Session limits configurable to ASVS level 2; ending sessions needs no password | Superseded by 0011 |
| [0011](0011-asvs-level-2-session-defaults.md) | Sessions default to ASVS level 2; ending other sessions needs the password | Accepted (lockout consequence replaced by 0012) |
| [0012](0012-reauthentication-budget-per-session.md) | Re-entering the password uses a per-session budget, not the account lockout | Accepted |

## Template

```markdown
# NNNN. Title

- Status: Proposed | Accepted | Superseded by NNNN
- Date: YYYY-MM-DD

## Context
What forces are at play? What problem are we solving?

## Decision
What we will do.

## Consequences
What becomes easier, what becomes harder, what we must watch for.
```
