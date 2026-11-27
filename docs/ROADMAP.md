# Roadmap

How we get from the current code (reviewed at commit `209a9bd`, rated 4/10) to the target in
`docs/VISION.md` and `docs/ARCHITECTURE.md`.

**Rules**

- All work happens on the `v2` integration branch; `main` keeps the legacy code untouched until
  release (ADR-0007).
- One step = one branch off `v2` = one pull request into `v2`. Large steps may split into
  several PRs; each PR still leaves `v2` installable with CI green.
- Each step is split into sections. Each section is tested against the full scenario checklist
  before the next one starts (`docs/milestones/README.md`).
- A step is done only when every task is ticked, its exit criteria are met, **and it passes the
  step gate** (`docs/milestones/README.md`) with an independent scorecard where every touched
  area is ≥ 9 (or carried to a named later step). The next step then starts automatically.
- Tick boxes in this file in the same PR that does the work.
- If a step reveals that the plan is wrong, change this file in that PR and say why.

## Status

| Step | Title | Status |
| --- | --- | --- |
| 0 | Foundation docs | ✅ Done |
| 1 | Project skeleton & tooling | ✅ Done (review round 5: 9.0/10) |
| 2 | Database foundation | ⬜ Not started |
| 3 | Authentication core | ⬜ Not started |
| 4 | Rate limiting | ⬜ Not started |
| 5 | Organizations, memberships & permissions | ⬜ Not started |
| 6 | Account lifecycle & email | ⬜ Not started |
| 7 | Platform admin, audit log & events | ⬜ Not started |
| 8 | API polish, performance & operations | ⬜ Not started |
| 9 | Security hardening & review | ⬜ Not started |
| 10 | Template release (v1.0.0) | ⬜ Not started |

## Strategy: rebuild beside, then switch

The agreed decisions (PostgreSQL, UUID keys, multi-org memberships, permissions as data, a
new API shape) change the data model and every endpoint. Patching the old code in place would
mean rewriting each file twice. So:

0. `main` is not touched until release. Anything that runs the old API (e.g.
   `user_management_UI`) keeps using `main`.
1. `v2` starts clean: step 1 deletes the old code from the branch. It stays complete on `main`
   for reference and cross-checking.
2. Steps 1–8 build the new app in `app/` from scratch, test-first, in the target architecture.
3. Step 10 merges `v2` into `main` as the v1.0.0 release.

Known bugs in the old code (from the review) are **not** fixed on `main`; each one is
listed below against the step where the new code makes it impossible, so nothing is lost.

---

## Step 0 — Foundation docs

**Goal:** agree the vision and rules before writing code.

- [x] `CLAUDE.md` — working rules for developers and AI agents
- [x] `docs/VISION.md` — purpose, scope, measurable 10/10 bar
- [x] `docs/ARCHITECTURE.md` — target stack, layers, domain model, conventions
- [x] `docs/ROADMAP.md` — this file
- [x] `docs/adr/` — the decisions agreed so far
- [x] Pull request template
- [x] Testing, logging and scoring process (`docs/milestones/README.md`, `SCORECARD.md`)
- [x] Security audit skill vendored and pinned (`.claude/skills/security-audit/`)

**Exit criteria:** reviewed and merged by the project owner.

---

## Step 1 — Project skeleton & tooling

**Goal:** an empty-but-production-shaped app that installs, starts, lints, type-checks and
tests in CI.

- [x] Remove the old code from `v2` (it stays on `main` for reference)
- [x] `pyproject.toml` managed by `uv`; Python 3.12+
- [x] `uv.lock` committed (generated in CI, checksum-verified); CI and Docker use `uv sync --locked`
- [x] `app/` skeleton matching `docs/ARCHITECTURE.md` §3 (empty packages with `__init__.py`)
- [x] `app/core/config.py` — `Settings` with nested sections; `.env.example` listing every variable
- [x] Safety check for staging and production: startup fails on default/short JWT secret, default DB credentials or debug on; `CORS *` + credentials rejected everywhere
- [x] `app/core/logging.py` — JSON logs to stdout; `app/core/middleware.py` — request id, security headers, access log, error boundary (pure ASGI)
- [x] `app/core/errors.py` — `AppError` hierarchy and RFC 9457 handlers for app, validation and unexpected errors
- [x] `app/api/health.py` — `/health/live`, `/health/ready` (checks DB + Redis)
- [x] `app/main.py` — `create_app()` factory with lifespan (no `on_event`)
- [x] `Dockerfile` (multi-stage, non-root user) and `docker-compose.yml` (app, Postgres 16, Redis 7)
- [x] `ruff`, `mypy --strict`, `pytest` configured in `pyproject.toml`
- [x] `Makefile` (or `justfile`) with `install`, `run`, `lint`, `typecheck`, `test`, `migrate`
- [x] GitHub Actions: lint, type-check, test with Postgres + Redis services, on every PR
- [x] First tests: app starts, health endpoints, error format, production safety check

**Fixes from review:** missing `pydantic-settings` dependency; `settings.environment`
AttributeError; `config_manager.py` copying files that don't exist; deprecated `on_event`;
five stacked `BaseHTTPMiddleware` layers; logs written to local files; default secrets
accepted in production; README referring to a missing `.env.example`.

**Exit criteria:** `docker compose up` serves `/health/ready` = 200; CI green; coverage
reported.

---

## Step 2 — Database foundation

**Goal:** the full v1 schema in PostgreSQL, managed by Alembic, with tested repositories.

- [x] Async engine + session factory; `get_db` dependency (one session per request; the service opens its one transaction)
- [x] Models per `docs/ARCHITECTURE.md` §4: users, organizations, memberships, roles, permissions, role_permissions, sessions, one_time_tokens, invitations, audit_logs
- [x] `citext` extension, enums / CHECK constraints, `ON DELETE` rules, unique and supporting indexes
- [x] Alembic configured for async; initial migration; `downgrade` works
- [x] Seed migration for permissions and system roles (`owner`, `admin`, `member`)
- [x] CLI command to create the first platform admin (`python -m app.cli create-admin`)
- [x] Repository base with tenant scoping helpers
- [x] Test fixtures: per-test transaction rollback against a real Postgres
- [x] CI runs `alembic upgrade head` then `alembic downgrade base` then `upgrade head` again

**Fixes from review:** free-text roles; nullable `organization_id` defaulting to 1; missing
composite index on refresh tokens; no index on `expires_at`; naive vs aware datetimes;
fake default phone number; duplicated `device_info`/`user_agent`; no FK delete rules; no soft
delete; no migrations; lockout columns unused.

**Exit criteria:** migrations round-trip in CI; every repository method has a test.

---

## Step 3 — Authentication core

**Goal:** secure sign-up, login, refresh, logout and session management.

- [ ] `core/security.py`: PyJWT encode/decode with `iss`, `aud`, `jti`, `sid` (Argon2id hash/verify and `password_needs_rehash` already built in step 2)
- [ ] Record `last_login_at` on users (new migration; the old code's `last_login`, deferred from step 2) and rehash on login when `password_needs_rehash`
- [ ] Dummy Argon2 verify for unknown emails (no timing leak)
- [ ] `get_current_user` dependency — the **only** place a token is decoded and a user loaded
- [ ] `client_info` dependency — IP (trusted proxy aware) and user agent
- [ ] `POST /auth/signup` (behind `FEATURE_SIGNUP`), `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `POST /auth/logout-all`
- [ ] Refresh rotation with `family_id` and reuse detection (reuse ⇒ revoke family + audit event)
- [ ] Account lockout: failed counter, `locked_until`, reset on success
- [ ] Session strategy from settings (`allow_multiple`, `replace_all`, `limit_sessions`, `replace_same_device`)
- [ ] `GET /me`, `GET /me/sessions`, `DELETE /me/sessions/{id}`, `POST /me/sessions/revoke-others` (keeps the current session via `sid`)
- [ ] `POST /me/password` (change password; revokes other sessions)
- [ ] Tests for every path, including reuse detection, lockout and expiry
- [ ] A client that disconnects while a Pydantic-body route reads its body is logged as 499, not 400 (from step 1 review, R3-03)
- [ ] Log redaction also masks fields named like secrets (`password`, `token`, …), non-string values and `key: value` / `Authorization:` forms (from step 1 review, R5-03)

**Fixes from review:** unsalted SHA-256 passwords; `/debug-login` and `/debug-refresh`
(not recreated); revocation that hashed the hash and revoked nothing; revoke-others killing the
current session; `settings` NameError; role/org trusted from JWT claims; hard-coded
`expires_in`; 7 copies of the token-check block; unused refresh JWT.

- [ ] Security audit (gate check 6): no confirmed Critical/High findings

**Exit criteria:** ASVS V2/V3 items for these flows pass; coverage ≥ 90 % on auth services.

---

## Step 4 — Rate limiting

**Goal:** correct, cheap, shared rate limiting.

- [ ] GCRA in one Lua script: atomic, O(1) memory per key, one Redis round trip per check
- [ ] Policies in settings: per IP global, per IP per route, per user per route; per-email limit on login
- [ ] `rate_limit("login")` dependency; standard `RateLimit-*` and `Retry-After` headers
- [ ] Fail closed for auth routes, open for others (configurable); no per-request `PING`
- [ ] Use `SCAN`/key sets, never `KEYS`
- [ ] Tests with real Redis: burst, steady rate, reset, concurrency, Redis down

**Fixes from review:** same-second requests counted once; rejected requests recorded;
swallowed per-user 429; O(n) memory per key; up to 8 Redis round trips per request; `KEYS`
blocking Redis; wrong `Retry-After`.

- [ ] Security audit (gate check 6): no confirmed Critical/High findings

**Exit criteria:** a load test shows limits enforced within ±1 % at 500 req/s.

---

## Step 5 — Organizations, memberships & permissions

**Goal:** multi-tenant organizations with permission-based access control.

- [ ] Organizations CRUD; creator becomes `owner`; slug unique
- [ ] `get_current_org` + `require_permission("x:y")` dependencies (404 for non-members, 403 for missing permission)
- [ ] Members: list (paginated), change role, remove; cannot remove or demote the last owner
- [ ] Roles: list, create custom role, edit permissions (`roles:manage`)
- [ ] Transfer ownership
- [ ] `MAX_ORGS_PER_USER` setting (ADR-0003) enforced on create and accept-invite
- [ ] `GET /me/organizations`
- [ ] Tenant-isolation test suite: a member of org A gets 404 for every org-B endpoint

**Fixes from review:** hard-coded role `if/elif` chains; missing org-admin role; signup
forcing org 1; `/users` returning a different shape per role; no pagination (limit 100);
missing CRUD.

- [ ] Security audit (gate check 6): no confirmed Critical/High findings

**Exit criteria:** isolation suite passes for every org-scoped route; ASVS V4 items pass.

---

## Step 6 — Account lifecycle & email

**Goal:** the account flows every product needs.

- [ ] `EmailSender` protocol; `console` and `smtp` backends; simple templates
- [ ] One-time tokens (hashed, single use, short expiry) for email verification and password reset
- [ ] `POST /auth/verify-email`, `POST /auth/verify-email/resend`
- [ ] `POST /auth/password-reset/request` (same response whether or not the email exists), `POST /auth/password-reset/confirm` (revokes all sessions)
- [ ] Invitations: create, list, revoke, accept (existing user or sign up through invite)
- [ ] Setting `REQUIRE_VERIFIED_EMAIL` to block login until verified
- [ ] Tests for expiry, reuse, enumeration resistance

- [ ] Security audit (gate check 6): no confirmed Critical/High findings

**Exit criteria:** every flow works end to end with the console backend in Docker Compose.

---

## Step 7 — Platform admin, audit log & events

**Goal:** operators can manage everything, and every sensitive action is recorded.

- [ ] Event dispatcher (`app/events`) with typed events; subscribers registered at startup
- [ ] Audit-log subscriber for auth, membership, role, invitation and admin events
- [ ] `GET /orgs/{id}/audit` (`audit:read`) and `GET /admin/audit` — filtered, paginated
- [ ] `/admin/users` and `/admin/organizations`: list, search, disable, enable, delete (soft)
- [ ] Every admin action audited with actor, target, IP

- [ ] Security audit (gate check 6): no confirmed Critical/High findings

**Exit criteria:** every state-changing endpoint produces exactly one audit entry (tested).

---

## Step 8 — API polish, performance & operations

**Goal:** production-ready behaviour under load.

- [ ] Every endpoint has typed `response_model`, examples and documented error codes
- [ ] Prometheus `/metrics`
- [ ] Cleanup command for expired sessions/tokens/invitations, documented for cron / k8s CronJob
- [ ] DB pool sizing from settings; uvicorn proxy headers; graceful shutdown
- [ ] Load test (k6 or Locust) in `tests/load/`; record results in `docs/PERFORMANCE.md`
- [ ] Meet the performance targets in `docs/VISION.md` §5
- [ ] Log writer: shutdown and reconfigure never raise or hang when the queue is full or stdout is stuck (evict for the stop signal, bounded join); `prepare` works on a copy so other handlers keep `exc_info`; stuck-writer test cleans up in `finally` (from step 1 review, R5-01/02/05)

**Fixes from review:** blocking calls inside `async` routes; duplicate DB lookups per request;
120 DB connections per instance; client IP wrong behind a load balancer; no metrics; expired
tokens never cleaned.

**Exit criteria:** performance targets met and documented.

---

## Step 9 — Security hardening & review

**Goal:** prove the security claims.

- [ ] `docs/SECURITY.md`: threat model, data classification, reporting process
- [ ] ASVS L2 V2/V3/V4 checklist in `docs/security/asvs.md`, each item linked to code or test
- [ ] Security headers reviewed; CORS allow-list only
- [ ] `pip-audit` and `bandit` in CI; Dependabot enabled
- [x] Stricter startup checks in staging/production: reject low-variety JWT secrets; require a password in `DATABASE__URL` and `REDIS__URL` (done early, in step 1)
- [ ] Independent review pass (a fresh reviewer that did not write the code)
- [ ] Well-known-password check compares percent-decoded, case-insensitive passwords (from step 1 review, R5-04)

- [ ] Security audit (gate check 6): no confirmed Critical/High findings

**Exit criteria:** every ASVS item in scope is "pass" or has a documented, accepted reason.

---

## Step 10 — Template release (v1.0.0)

**Goal:** others can build on it.

- [ ] `docs/EXTENDING.md` with worked examples (new permission, new endpoint, profile table, event subscriber, email provider)
- [ ] New `README.md`: what it is, quick start, configuration, links to docs
- [ ] `docs/API_MIGRATION.md`: every legacy endpoint → new endpoint, for `user_management_UI`
- [ ] Tag the last legacy commit on `main` (e.g. `legacy-final`), then merge `v2` into `main`
- [ ] Mark the GitHub repo as a template; tag `v1.0.0`; `CHANGELOG.md`
- [ ] Re-score the backend against `docs/VISION.md` §5 and record the result

**Exit criteria:** every row of the 10/10 table in `docs/VISION.md` is met.

---

## Backlog (version 2)

- [ ] TOTP two-factor auth with recovery codes
- [ ] API keys / personal access tokens
- [ ] Webhooks for domain events
- [ ] Optional Postgres row-level security as a second tenant-isolation layer
