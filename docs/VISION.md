# Vision

> **A production-grade, reusable user-management backend.** Authentication, organizations,
> roles and permissions, and sessions — done once, done right. Any new product (an admin
> panel, a SaaS app, an internal tool) starts from this template and adds only its own
> business logic.

---

## 1. The problem

Almost every product rebuilds the same foundation: sign-up, login, password reset, "who can
see what", teams or organizations, sessions across devices, and an audit trail. Rebuilt in a
hurry, it is usually where the worst security bugs live — weak password hashing, broken
token revocation, tenants that can see each other's data.

This project exists so that foundation is written **once**, reviewed properly, tested
thoroughly, and reused.

## 2. Who it is for

| User | What they need from this project |
| --- | --- |
| **A developer starting a new product** | Clone the template, set a few config values, run `docker compose up`, and have working auth, orgs, roles and admin APIs in minutes. |
| **A frontend developer** | A stable, consistent, fully documented REST API (OpenAPI), with predictable errors and pagination. |
| **An operator / DevOps** | A stateless service that scales horizontally, exposes health and metrics, logs JSON to stdout, and refuses to start with unsafe config. |
| **A security reviewer** | Clear threat model, documented decisions, and passing OWASP ASVS Level 2 checks for auth, sessions and access control. |

## 3. Principles

These decide every trade-off. When two options look equal, pick the one that fits these better.

1. **Secure by default.** The safe option is the default. Unsafe settings (default secrets,
   `CORS *` with credentials, debug endpoints) stop the app from starting in production.
2. **Configurable, not forked.** Roles, permissions, features and limits come from config and
   data. A product built on this base should never need to edit core code.
3. **Tenant isolation is not optional.** Every query that touches organization data is scoped
   to the current organization by construction, not by remembering to add a `WHERE`.
4. **Boring, proven technology.** Well-known libraries, standard patterns, no clever tricks.
   Every non-obvious decision is written down as an ADR (`docs/adr/`).
5. **One way to do each thing.** One way to get the current user, one way to check a
   permission, one error format, one pagination style. Duplication is a bug.
6. **Tested or it does not exist.** Behaviour without a test is not finished.
7. **Small, reviewable steps.** One roadmap step = one branch = one pull request.

## 4. Scope

### Version 1 (the reusable base)

- **Authentication** — email + password login, Argon2 hashing, short-lived JWT access tokens,
  rotating refresh tokens with reuse detection, logout, logout everywhere.
- **Account lifecycle** — sign-up, email verification, password reset, change password,
  account lockout after repeated failures, deactivate / delete.
- **Organizations (multi-tenant)** — a user can belong to many organizations through
  memberships; invitations by email; transfer ownership.
- **Roles & permissions as data** — permissions like `members:invite`; roles are sets of
  permissions; default roles seeded (`owner`, `admin`, `member`) and editable per project.
- **Platform administration** — a platform-level super admin who can manage all
  organizations and users.
- **Sessions** — list active sessions per device, revoke one, revoke all others.
- **Audit log** — who did what, to whom, when, from where.
- **Rate limiting** — per IP and per user, Redis-backed, correct under concurrency.
- **Email** — behind one interface; console backend for development, SMTP backend for real use.
- **Extension points** — domain events/hooks (e.g. `user.created`) and a documented way to add
  fields and endpoints without editing the core.
- **Operations** — Docker Compose, health/readiness probes, Prometheus metrics, JSON logs.

### Version 2 (designed for now, built later)

- Two-factor authentication (TOTP + recovery codes).
- API keys / personal access tokens for machine clients.
- Webhooks for domain events.

### Not planned (add per project via extension points)

- Social login / SSO (Google, Microsoft, SAML, OIDC).
- Billing, subscriptions, feature plans.
- A bundled frontend. The existing `user_management_UI` repo will be migrated to the new API
  separately, using the migration note produced at the end of the roadmap.

## 5. What "10 / 10" means

A score is only useful if it can be checked. The project is "10/10" when **every** item below is true.

| Area | Measurable target |
| --- | --- |
| Security | OWASP ASVS L2 sections V2 (auth), V3 (sessions), V4 (access control) pass; no secrets in code; startup fails on unsafe production config. |
| Correctness | Every endpoint has tests for success, auth failure, permission failure and validation failure. |
| Tests | ≥ 90 % line coverage on `app/services` and `app/core`; suite runs in < 60 s. |
| Types & lint | `mypy --strict` and `ruff` pass with zero ignores added without a comment explaining why. |
| Database | Every schema change is an Alembic migration; upgrade and downgrade both tested in CI. |
| API | 100 % of endpoints have typed request/response models; one error format (RFC 9457); list endpoints paginate. |
| Tenant isolation | Automated tests prove a member of org A cannot read or change anything in org B. |
| Performance | Login p95 < 250 ms (Argon2 dominates), authenticated read p95 < 50 ms, at 200 req/s on one 2-vCPU instance. |
| Operations | `docker compose up` starts everything; `/health/live`, `/health/ready`, `/metrics` work; logs are JSON on stdout. |
| Reusability | A new project can rename roles, add a permission and add an endpoint by following `docs/EXTENDING.md`, without editing `app/core`. |
| Docs | README, architecture, ADRs and API docs match the code. |

## 6. Success, in one sentence

> A developer we have never met can start a new product on this base, ship it to production,
> and pass a security review — without changing a line of the core.
