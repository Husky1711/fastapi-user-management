# Backend Production Readiness — Issues & Required Changes

Complete checklist of every known issue, gap, and change required to make the FastAPI user management backend **production-grade**. Derived from architecture review, codebase audit, and comparison against enterprise IAM expectations.

**Related docs:** [BACKEND.md](./BACKEND.md) · [DATABASE_SCHEMA_REVIEW.md](./DATABASE_SCHEMA_REVIEW.md) · [README.md](./README.md) · [UTC_DATETIME_CONVENTION.md](./UTC_DATETIME_CONVENTION.md) · [ACCESS_TOKEN_REVOCATION.md](./ACCESS_TOKEN_REVOCATION.md) · [BACKUP_RESTORE.md](./BACKUP_RESTORE.md)

> **Document split:** This file covers **application code, APIs, config, ops, and tests**. Database ENUMs, FK hygiene, new tables, index strategy, partitioning, and RBAC normalization are detailed in [DATABASE_SCHEMA_REVIEW.md](./DATABASE_SCHEMA_REVIEW.md). Items below marked **DB** include a schema cross-reference — implement both the migration and the service/route wiring.

**Legend**

| Priority | Meaning |
|----------|---------|
| **P0** | Block production launch — security, data integrity, or broken core flows |
| **P1** | Required for enterprise production — reliability, compliance, maintainability |
| **P2** | Strongly recommended — quality, ops excellence, scale readiness |
| **P3** | Nice-to-have — cleanup, future-proofing |

| Status | Meaning |
|--------|---------|
| ⬜ | Not started |
| 🔄 | In progress |
| ✅ | Done |
| ⏸ | Deferred / accepted risk (Phase 2) |

**v1 checklist status (2026-07-14):** All actionable items are ✅ or explicitly ⏸ (JWT `jti` blocklist, repository layer). Remaining Phase 2 work lives under Sprint 5 and schema §6.3 enterprise tables.

---

## Table of contents

1. [P0 — Security & broken flows](#1-p0--security--broken-flows)
2. [P0 — Secrets & configuration](#2-p0--secrets--configuration)
3. [P1 — Authentication & sessions](#3-p1--authentication--sessions)
4. [P1 — Authorization & RBAC](#4-p1--authorization--rbac)
5. [P1 — Data & migrations](#5-p1--data--migrations)
6. [P1 — Email & account recovery](#6-p1--email--account-recovery)
7. [P1 — Architecture & code structure](#7-p1--architecture--code-structure)
8. [P2 — Observability & operations](#8-p2--observability--operations)
9. [P2 — Performance & reliability](#9-p2--performance--reliability)
10. [P2 — Testing & CI/CD](#10-p2--testing--cicd)
11. [P2 — Dependencies & supply chain](#11-p2--dependencies--supply-chain)
12. [P3 — Technical debt & cleanup](#12-p3--technical-debt--cleanup)
13. [P1 — Database schema & data integrity](#13-p1--database-schema--data-integrity) *(from [DATABASE_SCHEMA_REVIEW.md](./DATABASE_SCHEMA_REVIEW.md))*
14. [P2 — Database indexes & performance](#14-p2--database-indexes--performance)
15. [Production environment checklist](#15-production-environment-checklist)
16. [Summary counts](#16-summary-counts)

---

## 1. P0 — Security & broken flows

| # | Status | Issue | Location | Required change |
|---|--------|-------|----------|-----------------|
| 1.1 | ✅ | **2FA not enforced at login** — users with `is_2fa_enabled=true` receive full tokens from `POST /login` without TOTP | `routes/auth.py`, `services/auth/login_2fa_service.py` | Two-step login: `POST /login` returns `requires_2fa` + challenge token; `POST /login/2fa` verifies TOTP/backup code before issuing tokens |
| 1.2 | ✅ | **`revoke-others` revokes current session** — passes `keep_session_id=0`, so no session is preserved | `routes/sessions.py`, `services/auth/enhanced_login_service.py` | Resolves current `refresh_tokens.id` from httpOnly cookie hash; passes real ID to `revoke_other_sessions()` |
| 1.3 | ✅ | **Password reset token returned in API response** — leaks reset token to any caller | `services/users/password_reset_service.py` | `reset_token` only in response when `APP__ENVIRONMENT=development`; email path via `EMAIL__ENABLE_EMAILS` |
| 1.4 | ✅ | **2FA secrets stored in plaintext** — `two_factor_secret` column comment says "encrypted" but value is stored raw | `utils/field_encryption.py`, `routes/auth_2fa.py` | Fernet encrypt at rest; legacy plaintext still decrypts; never returned after enable |
| 1.5 | ✅ | **Debug auth endpoints** — bypass normal cookie/security flows when flag enabled | `main.py`, `SECURITY__ALLOW_DEBUG_AUTH` | Router mounts only in development + flag; production validation refuses boot if flag is true |
| 1.6 | ✅ | **Default JWT secret in source** — predictable if env not set | `config/settings.py` | Dev placeholder kept for local only; `validate_production_config()` rejects it in production |
| 1.7 | ✅ | **SMTP credentials hardcoded in source** | `config/settings.py` | Defaults cleared; `EMAIL__ENABLE_EMAILS=false` by default |
| 1.8 | ✅ | **Neon Postgres URL with credentials in source** | `config/settings.py` | Removed; use env-only `DB__URL` / `DATABASE_URL` |
| 1.9 | ✅ | **Refresh cookie `Secure=false` by default** — token sent over HTTP | `AUTH_COOKIE__SECURE` | Dev default `false`; **prod checklist + startup validation** requires `true` (deploy config, not open code gap) |
| 1.10 | ✅ | **Legacy refresh token in JSON body** — refresh token exposed to JS during transition | `AUTH_COOKIE__LEGACY_JSON_REFRESH` | Dev default `true`; **prod checklist + startup validation** requires `false` |
| 1.11 | ✅ | **No CSRF protection on cookie-based refresh/logout** — `SameSite=lax` mitigates but POST from cross-site forms may still be an issue | `utils/cookie_auth.py`, `routes/auth.py`, frontend `apiClient` | Require `X-Requested-With: XMLHttpRequest` on `POST /refresh` and `POST /logout`; SPA sends header on all requests |
| 1.12 | ⏸ | **Access JWT has no `jti` / revocation** — compromised token valid until expiry | `utils/jwt_config.py`, `AuthService` | **Accepted risk for v1 / Phase 2:** access TTL ~5 min; logout/revoke-all invalidate refresh. Pull forward if compliance requires immediate access revocation |
| 1.13 | ✅ | **Suspicious-path middleware flags legitimate routes** — `"login"`, `"admin"` in path trigger security warnings | `utils/security_middleware.py` | Known `/api/v1/*` prefixes excluded; attack signatures only (traversal, probes, injection in query) |
| 1.14 | ✅ | **Rate limiting fails open when Redis is down** — unlimited requests possible | `RATE_LIMIT__FAIL_OPEN`, `validate_production_config()` | Production startup requires `RATE_LIMIT__FAIL_OPEN=false` (Redis hard dependency for first prod cutover); in-memory fallback optional later |
| 1.15 | ✅ | **Public signup defaults org to `organization_id=1`** — tenant bleed if signup enabled **DB:** §3.2.1, §3.2.5 | `UserSignupRequest`, `user_service.create_user()` | `organization_id` required on signup; org existence validated |

---

## 2. P0 — Secrets & configuration

| # | Status | Issue | Location | Required change |
|---|--------|-------|----------|-----------------|
| 2.1 | ✅ | **Duplicate lockout settings** — `SecuritySettings.max_login_attempts` and `PasswordPolicySettings.max_login_attempts`; only security block is used | `config/settings.py` | Lockout fields removed from `PasswordPolicySettings`; single source under `security` |
| 2.2 | ✅ | **Conflicting session TTL config** — `session.refresh_token_expire_hours=24` vs `jwt.refresh_token_expire_days=7` | `config/settings.py` | Removed session-level access/refresh TTL fields; refresh expiry driven only by `jwt.refresh_token_expire_days` |
| 2.3 | ✅ | **Settings module prints secrets on import** — `print(f"JWT Secret Key Length: ...")` | `config/settings.py` `__main__` | Debug print no longer logs DB URL, Redis URL, or JWT secret length |
| 2.4 | ✅ | **No production config validation at startup** — weak secrets, debug flags, missing SMTP not fatal | `main.py` lifespan, `settings.validate_production_config()` | Validates JWT secret, cookie secure, legacy JSON refresh, debug auth, public signup, **fail_open** |
| 2.5 | ✅ | **`.env` tracked in git status** — risk of committing secrets | `.gitignore` | `.env` ignored; use `.env.codespaces.example`; untrack local `.env` with `git rm --cached .env` if still tracked |
| 2.6 | ✅ | **README.md deleted** — no onboarding for operators | repo root | Restored README with env var table, bootstrap steps, production deploy pointer |

---

## 3. P1 — Authentication & sessions

| # | Status | Issue | Location | Required change |
|---|--------|-------|----------|-----------------|
| 3.1 | ✅ | **Dead JWT refresh helpers** — `create_refresh_token` / `verify_refresh_token` in jwt_config unused; actual refresh is opaque DB tokens | `utils/jwt_config.py` | Deleted dead JWT refresh helpers; `TokenResponse` documents opaque refresh token |
| 3.2 | ✅ | **Dual "session" terminology** — `refresh_tokens` (auth) vs `user_sessions` (analytics) both called "sessions" in APIs | models, routes, docs | API responses clarified as auth sessions (`session_kind`, Schema docs); endpoints unchanged for compatibility |
| 3.3 | ✅ | **Session list missing `is_current` flag** — UI cannot highlight active device | `routes/sessions.py`, `EnhancedLoginService` | Compares current refresh cookie hash; sets `is_current=true` |
| 3.4 | ✅ | **`AutoRefreshMiddleware` not mounted and broken** — passes `db=None`, mutates read-only headers | `utils/auto_refresh_middleware.py` | Deleted unused middleware and `auto_refresh_service.py` (SPA owns proactive refresh) |
| 3.5 | ✅ | **`datetime.utcnow()` used widely** — deprecated in Python 3.12+; naive datetimes | `utils/datetime_utc.py` + services/routes | Migrated app code to `utc_now()` (UTC wall time, MySQL DATETIME-compatible) |
| 3.6 | ✅ | **Refresh token rotation does not detect reuse** — stolen rotated token not flagged as breach | `RefreshTokenService.verify_refresh_token` | Revoked token hash reuse triggers revoke-all for that user |
| 3.7 | ✅ | **No max concurrent sessions enforced** — `SessionSettings.max_sessions_per_user` defined in enhanced_login_service stub, not in real config | `AuthService.create_tokens_for_user`, `config/settings.py` | Enforced on token creation; stub SessionSettings class removed |
| 3.8 | ✅ | **Login does not check `user.status`** — inactive/disabled users may still authenticate if not filtered **DB:** §3.1.2 | `LoginAttemptService` | Rejects non-active with `403 ACCOUNT_DISABLED` |
| 3.9 | ✅ | **Logout-all requires JWT but not refresh** — access-only clients can revoke all without proving refresh possession | `routes/auth.py` logout-all | Requires refresh cookie owned by user + CSRF header |
| 3.10 | ✅ | **IP address from `request.client.host` only** — wrong behind reverse proxy | `utils/request_ip.py`, auth routes | Auth routes use `X-Forwarded-For` / `X-Real-IP` helper |

---

## 4. P1 — Authorization & RBAC

| # | Status | Issue | Location | Required change |
|---|--------|-------|----------|-----------------|
| 4.1 | ✅ | **RBAC enforced in 4 different styles** — dependencies, services, inline route checks, schema validators | `dependencies/auth.py`, `routes/dashboard.py`, `role_policy.py` | `require_roles` / `require_permission` / `role_policy`; dashboard + compliance beachheads; org-scope filters remain in services |
| 4.2 | ✅ | **`RoleHierarchyValidator` in schemas layer** — business logic in Pydantic module | `services/users/role_policy.py` | Moved to service layer; schemas re-exports for compatibility |
| 4.3 | ✅ | **Granular `user_permissions` not enforced on routes** — table + service exist; routes gate on role string only **DB:** §4.1 | `dependencies/auth.py`, `services/permissions/user_permission_service.py` | Added `require_permission()`; beachhead on users create/update + permissions statistics (staff bypass; full `roles` tables still later) |
| 4.4 | ✅ | **Dashboard RBAC is inline `if role !=`** — duplicated 9+ times | `routes/dashboard.py` | Uses `AdminUser` / `OrgAdminUser` / `DashboardSuperAdminUser` dependencies |
| 4.5 | ✅ | **No DB constraint on `users.role`** — free-form string; typo creates orphan role **DB:** §3.1.1 | `models/user_model.py:59` | Alembic `20260714_enums_reset`: ENUM `user`, `admin`, `organization_admin`, `super_admin`; status ENUM too |
| 4.6 | ✅ | **Model comment outdated** — lists `super_admin, admin, user` but omits `organization_admin` | `models/user_model.py` | Comment lists all four roles |
| 4.7 | ✅ | **Admin user update may not invalidate cached profile** — stale role/org in Redis after PATCH | `routes/users.py` | `invalidate_user_profile` on update; `invalidate_all_user_cache` when role/status/org/manager changes |
| 4.8 | ✅ | **Self-edit via admin endpoints not uniformly blocked** — documented but verify all PATCH paths | `UserService.update_user_by_admin`, `role_policy.assert_not_self_admin_edit` | Centralized self-edit guard |
| 4.9 | ✅ | **API key permissions are string arrays without schema validation** — arbitrary permission strings accepted | `services/permissions/api_key_service.py` | `validate_permissions()` against `STANDARD_API_PERMISSIONS` on create/update |
| 4.10 | ✅ | **Organization admin cannot access admin dashboard** — by design, but not documented in route errors | `dependencies/auth.py` | `403` with `error_code=DASHBOARD_ROLE_REQUIRED` and allowed roles in detail |

---

## 5. P1 — Data & migrations

| # | Status | Issue | Location | Required change |
|---|--------|-------|----------|-----------------|
| 5.1 | ✅ | **Baseline migration uses `create_all()`** — not reproducible incremental DDL for prod **DB:** §4.7.1 | `alembic/versions/20260708_baseline_schema.py` | Greenfield: metadata create on empty DB; legacy: stamp + skip if `users` exists; follow-ups idempotent |
| 5.2 | ✅ | **Unused `users.login_attempts` column** — dead field; `failed_login_attempts` is the real counter **DB:** §3.4.1 | `models/user_model.py:49` | Dropped in soft-delete migration |
| 5.3 | ✅ | **All models in single file** — 200+ lines, hard to navigate | `models/` | Split: `identity.py`, `session.py`, `compliance.py`; `user_model.py` re-exports |
| 5.4 | ⏸ | **No repository layer** — services embed raw SQLAlchemy queries | All `services/*` | Deferred for v1 — services remain the persistence boundary |
| 5.5 | ✅ | **Transaction boundaries inconsistent** — some services commit mid-flow without rollback wrapper | `user_service.py`, `refresh_token_service.py` | Use unit-of-work pattern or FastAPI dependency with transaction scope; document commit ownership |
| 5.6 | ✅ | **Index scripts separate from Alembic** — `scripts/add_database_indexes*.py` may drift from migrations **DB:** §4.7.2, §5 | `scripts/` | Indexes in Alembic; scripts deprecated |
| 5.7 | ✅ | **Password history retention job missing** — `password_history_retention_days` configured but no cron **DB:** §4.5.3 | `config/settings.py` | `RetentionService` + `/maintenance/cleanup` + optional `APP__ENABLE_RETENTION_JOB` |
| 5.8 | ✅ | **Expired refresh token / session cleanup** — manual `sessions/cleanup` only **DB:** §4.5.4, §4.5.5 | `routes/production_endpoints.py` | `sessions/cleanup` runs full retention suite; background loop optional |
| 5.9 | ✅ | **Duplicate foreign keys on 8 compliance tables** — slower writes, migration confusion **DB:** §3.3 | `alembic/versions/20260708_compliance_foreign_keys.py` | Drop duplicate `*_ibfk_*` constraints; keep one named FK per relationship |
| 5.10 | ✅ | **`users.password` column misnamed** — stores hash, not plaintext **DB:** §3.4.2 | `models/identity.py` | Renamed to `password_hash` (`20260714_password_hash_col`); ORM + seed updated |
| 5.11 | ✅ | **No `email_verified_at` on users** — cannot enforce verified-email login **DB:** §3.4.3, §6.4.1 | `users` table | Column + `SECURITY__REQUIRE_EMAIL_VERIFICATION` login gate |
| 5.12 | ✅ | **No `password_changed_at` on users** — `max_password_age_days` policy unenforceable **DB:** §3.4.4, §6.4.2 | `users` table | Column + `PASSWORD__ENFORCE_MAX_PASSWORD_AGE` login gate (`PASSWORD_EXPIRED`) |

---

## 6. P1 — Email & account recovery

| # | Status | Issue | Location | Required change |
|---|--------|-------|----------|-----------------|
| 6.1 | ✅ | **Password reset email not sent** — TODO in service | `services/users/password_reset_service.py:77` | Wired `email_service.send_password_reset_email` when `EMAIL__ENABLE_EMAILS` |
| 6.2 | ✅ | **Welcome email on admin create may be incomplete** — verify all create paths send email | `routes/users.py`, `UserService` | Audit create/signup flows; ensure `enable_emails` respected |
| 6.3 | ✅ | **Email `base_url` defaults to port 8000** — app runs on 9000 / UI on 5173 | `config/settings.py` | Default `EMAIL__BASE_URL=http://localhost:5173` (frontend) |
| 6.4 | ✅ | **Password reset stored only in Redis** — lost on Redis flush; no DB audit trail **DB:** §3.6 | `password_reset_service.py` | `password_reset_tokens` table + hashed tokens; Redis optional cache |
| 6.5 | ✅ | **Password policy settings not fully enforced** — `require_uppercase`, `max_password_age_days` in config but not validated on signup/change **DB:** §5.12 | `schemas/login.py`, `PASSWORD__*` | Complexity validators use `settings.password_policy`; age via `enforce_max_password_age` |
| 6.6 | ✅ | **Schema password rules hardcoded to min_length=8** — ignores `PASSWORD__MIN_PASSWORD_LENGTH` env | `schemas/login.py` | Validators use `settings.password_policy` lengths and flags |
| 6.7 | ✅ | **No email verification flow** — signup does not verify email ownership **DB:** §4.2.1, §6.1.2 | — | `email_verification_tokens` + `/email/verify` + `/email/resend-verification`; login gate via flag |
| 6.8 | ✅ | **No admin invite flow for multi-tenant onboarding** — relies on public signup or manual DB **DB:** §4.2.2, §6.1.3 | — | `user_invitations` + create/list/revoke/accept/validate endpoints |

---

## 7. P1 — Architecture & code structure

| # | Status | Issue | Location | Required change |
|---|--------|-------|----------|-----------------|
| 7.1 | ✅ | **`production_endpoints.py` is ~1100 lines** — audit, permissions, groups, api-keys, password history in one file | `routes/` | Split into `audit`, `sessions_admin`, `permissions_mgmt`, `groups`, `api_keys`, `password_history`; thin aggregator remains |
| 7.2 | ✅ | **`dashboard.py` is ~1200 lines with inline DB queries** — business logic in route layer | `routes/dashboard.py` | Thin router; logic in `services/dashboard/` (user, admin, org_admin, super_admin) |
| 7.3 | ✅ | **Deprecated `routes/login.py` still in repo** — not mounted but confusing | `routes/login.py` | Deleted |
| 7.4 | ✅ | **Duplicate startup hooks** — `lifespan` + deprecated `@app.on_event` | `main.py` | Removed `on_event` handlers; lifespan only |
| 7.5 | ✅ | **Duplicate request logging** — `RequestIDMiddleware` + `log_requests` in main | `main.py`, `utils/security_middleware.py` | Removed `log_requests`; RequestIDMiddleware remains |
| 7.6 | ✅ | **Duplicate `SessionSettings` class in enhanced_login_service** — shadow config | `services/auth/enhanced_login_service.py` | Stub already removed; uses `config/settings.py` |
| 7.7 | ✅ | **Static service classes with lazy imports** — `from services.users import UserService` inside methods | `auth_service.py` and others | Acceptable for now; optional: constructor injection for testing |
| 7.8 | ✅ | **No API versioning strategy beyond `/api/v1`** — breaking changes will hurt | `docs/API_VERSIONING.md`, `routes/auth_common.py` | Path-versioned `/api/v1`; breaking → `/api/v2` + ≥90d deprecation for auth |
| 7.9 | ✅ | **OpenAPI disabled in production** — good for security, but operators need spec | `scripts/export_openapi.py`, CI artifact | CI exports `artifacts/openapi.json`; `/docs` still off in production |

---

## 8. P2 — Observability & operations

| # | Status | Issue | Location | Required change |
|---|--------|-------|----------|-----------------|
| 8.1 | ✅ | **Logs written to local `logs/` directory** — not container-friendly | `utils/loggers/`, `utils/logger.py` | Production defaults to JSON stdout; file handlers optional via `LOG__FORCE_FILE` |
| 8.2 | ✅ | **No distributed tracing** — request ID exists but no OpenTelemetry | `RequestIDMiddleware` | Add OTEL FastAPI instrumentation; propagate trace ID to logs |
| 8.3 | ✅ | **Readiness probe requires Redis** — app degrades rate limits but won't receive traffic | `main.py` | `/health/ready` = DB only; `/health/ready-full` = DB + Redis |
| 8.4 | ✅ | **Detailed health exposes raw DB errors** — information leak | `main.py` | Generic error in production; details logged server-side |
| 8.5 | ✅ | **No metrics endpoint** — Prometheus /stats absent | `utils/metrics.py`, `main.py` | `/metrics` with request latency, auth failures, lockouts, rate-limit hits |
| 8.6 | ✅ | **Audit log retention policy undefined** — table grows unbounded; 13 single-column indexes **DB:** §4.5.1, §5.1 | `audit_logs` | Age-based purge via `RetentionService` (`APP__AUDIT_LOGS_RETENTION_DAYS`); monthly partitioning deferred |
| 8.11 | ✅ | **`login_attempts` table grows unbounded** — no retention or partition **DB:** §4.5.2 | `login_attempts` | Purge via `RetentionService` (`APP__LOGIN_ATTEMPTS_RETENTION_DAYS`); partitioning deferred |
| 8.7 | ✅ | **Security log false positives** — every `/api/v1/login` logged as suspicious | `security_middleware.py` | Attack detection via 1.13; API 4xx no longer elevated to security warnings (5xx + unknown-path 4xx only) |
| 8.8 | ✅ | **Correlation ID not propagated to all loggers** — partial context | `utils/production_logging.py`, `utils/logger.py` | `RequestIDMiddleware` sets ContextVar; `BaseLogger` auto-injects `correlation_id`/`user_id` |
| 8.9 | ✅ | **No structured alert rules documented** — lockout spikes, 5xx rate, Redis down | `docs/OPS_RUNBOOKS.md` | Runbooks for 5xx, readiness, Redis circuit, lockouts, refresh reuse, rate-limit storms |
| 8.10 | ✅ | **GitHub Actions DB startup fail-open** — prod-like tests may mask DB failure | `main.py` | Fail-open only for test/CI (`test` env, pytest, GITHUB_ACTIONS); never when `environment=production` |

---

## 9. P2 — Performance & reliability

| # | Status | Issue | Location | Required change |
|---|--------|-------|----------|-----------------|
| 9.1 | ✅ | **N+1 queries in user list** — `serialize_user` may hit DB per row for manager | `UserService.serialize_user` | Uses `organization`/`manager` relationships; list/detail queries `joinedload` both |
| 9.2 | ✅ | **Dashboard super-admin endpoints uncached inconsistently** — partial Redis use | `services/dashboard/` | All super-admin stats use `dashboard:v1:*` keys + 60s TTL; invalidated on user mutations |
| 9.3 | ✅ | **Cache invalidation manual and easy to miss** — only some routes call invalidate | `UserService`, `ProfileUpdateService` | Invalidate centrally after create/update/soft-delete/profile mutations |
| 9.4 | ✅ | **Connection pool may be undersized at scale** — pool 20, overflow 40 | `config/settings.py` | Load-test; tune per `SYSTEM_CAPACITY_ANALYSIS.md`; expose via env |
| 9.5 | ✅ | **Single uvicorn worker in dev, 4 in prod** — no gunicorn/uvicorn multi-worker doc | `docs/DEPLOYMENT_TOPOLOGY.md`, `main.py` | Prefer replicas × workers=1; gunicorn UvicornWorker documented for single-VM |
| 9.6 | ✅ | **No DB query timeout** — hung queries block workers | `utils/database.py`, `DB__STATEMENT_TIMEOUT_SECONDS` | MySQL `MAX_EXECUTION_TIME` / Postgres `statement_timeout` via connect_args (default 30s) |
| 9.7 | ✅ | **No circuit breaker for Redis** — repeated connection attempts under load | `utils/redis_config.py` | Circuit opens after N failures; exponential cooldown (`REDIS__CIRCUIT_*`) |
| 9.8 | ✅ | **Password reset rate limit per IP only** — email bombing possible | `rate_limit` config, `profile.py` | Per-email Redis bucket (`RATE_LIMIT__ENABLE_EMAIL_LIMITS`, 3/min · 10/hour) |

---

## 10. P2 — Testing & CI/CD

| # | Status | Issue | Location | Required change |
|---|--------|-------|----------|-----------------|
| 10.1 | ✅ | **2FA login flow untested end-to-end** — enable works; login gate missing | `tests/unit/test_login_2fa.py` | Challenge gate + invalid/stale code rejection + successful TOTP completion |
| 10.2 | ✅ | **revoke-others behavior untested for current session preservation** | `tests/integration/test_auth_integration.py` | Two-client test: current cookie session kept; other refresh returns 401 |
| 10.3 | ✅ | **IDOR smoke tests exist but not full matrix** — compliance endpoints | `tests/smoke/test_idor_smoke.py` | Expand to all user-scoped IDs: api-keys, permissions, groups, audit |
| 10.4 | ✅ | **No contract tests for error_code shape** — UI depends on structured errors | `utils/api_errors.py` | Snapshot tests for all `APIHTTPException` codes |
| 10.5 | ✅ | **Load tests in repo but not in CI gate** | `tests/load/` | Add performance regression threshold to CI (optional nightly) |
| 10.6 | ✅ | **E2E tests may use debug auth paths** — not prod-like | `tests/e2e/` | Ensure CI runs against cookie-auth flow per ADR-002 |
| 10.7 | ✅ | **Migration rollback not tested** **DB:** §4.7.4 | `alembic/versions/` | Add downgrade test in CI for each revision |
| 10.9 | ✅ | **Schema constraint tests missing** — ENUM values, unique constraints, cross-org guards **DB:** §8 | `tests/` | Add integration tests for DB constraints after each schema migration |
| 10.8 | ✅ | **Coverage gaps on production_endpoints** — 23 endpoints, few dedicated unit tests | `tests/unit/` | Add service-level tests for audit, api-key, group services |

---

## 11. P2 — Dependencies & supply chain

| # | Status | Issue | Location | Required change |
|---|--------|-------|----------|-----------------|
| 11.1 | ✅ | **Flask + Locust in main requirements.txt** — prod image bloat, attack surface | `requirements*.txt` | Split: `requirements.txt` (prod), `requirements-dev.txt` (pytest), `requirements-load.txt` (Locust/Flask) |
| 11.2 | ✅ | **Both `python-jose` and `PyJWT` present** — redundant JWT libs | `requirements.txt`, `utils/jwt_config.py` | Standardized on **PyJWT**; removed `python-jose` |
| 11.3 | ✅ | **Both `passlib` and direct `bcrypt`** — passlib may be unused | `requirements.txt` | Removed unused `passlib`; hashing uses `bcrypt` directly |
| 11.4 | ✅ | **No pinned lockfile for reproducible builds** — only requirements.txt | — | Add `pip-tools` or `poetry.lock` / `uv.lock` |
| 11.5 | ✅ | **No automated dependency vulnerability scan** — Dependabot/Snyk | `.github/dependabot.yml`, `ci.yml` | Weekly Dependabot (pip/npm/Actions); PR dependency-review fails on **critical** |
| 11.6 | ✅ | **Container image hardening not documented** — non-root user, read-only FS | `deploy/` | Add Dockerfile best practices doc; run as non-root |

---

## 12. P3 — Technical debt & cleanup

| # | Status | Issue | Location | Required change |
|---|--------|-------|----------|-----------------|
| 12.1 | ✅ | **Pydantic v1 `@validator` used** — should migrate to v2 `@field_validator` | `schemas/` | Migrated to `@field_validator` + `ConfigDict` |
| 12.2 | ✅ | **`schemas/login.py` is oversized** — auth, admin, password, role logic mixed | `schemas/` | Split: `auth.py`, `users.py`, `password.py`; `login.py` re-exports |
| 12.3 | ✅ | **`performance_monitor.py` simplified without psutil in some paths** — misleading utility | `utils/performance_monitor.py` | Wired `psutil` for CPU/RSS/host memory; `/metrics` remains prod scrape path |
| 12.4 | ✅ | **Multiple bootstrap scripts** — `ci_bootstrap_db`, `bootstrap_local_db`, `bootstrap_neon` | `scripts/`, `docs/BACKEND.md` §11 | Canonical = `ci_bootstrap_db.py`; migrate-only + Neon legacy documented/deprecated |
| 12.5 | ✅ | **Legacy SHA-256 password support** — security debt | `utils/jwt_config.py` | Force bcrypt migration script in prod cutover; remove SHA path after migration window |
| 12.6 | ✅ | **`/hello` legacy endpoint** — unnecessary attack surface | `main.py` | Development-only registration |
| 12.7 | ✅ | **Inconsistent response models** — some routes use raw dicts | `routes/users.py` list endpoint | Add typed response models for OpenAPI consistency |
| 12.8 | ✅ | **Backup/restore scripts not integrated with deploy** | `scripts/backup_database.py` | Document RPO/RTO; automate backup in Helm chart |
| 12.9 | ✅ | **21 docs files with overlapping status reports** — drift risk | `docs/` | Consolidate status docs; keep BACKEND.md + this file as living sources |
| 12.10 | ✅ | **Frontend dist committed to git** — build artifact in repo | `.gitignore`, `frontend/.gitignore` | `frontend/dist/` ignored at root + frontend; CI builds artifacts only |

---

## 13. P1 — Database schema & data integrity

Items from [DATABASE_SCHEMA_REVIEW.md](./DATABASE_SCHEMA_REVIEW.md) that require **both** Alembic migrations **and** application changes. Full SQL examples and ER diagrams are in the schema doc.

### 13.1 P0 schema — data integrity & tenant isolation

| # | Status | Issue | DB ref | Required change |
|---|--------|-------|--------|-----------------|
| 13.1.1 | ✅ | `users.status` free-form VARCHAR | §3.1.2 | ENUM: `active`, `inactive`, `suspended`, `pending`; login gate for non-active still via existing checks |
| 13.1.2 | ✅ | `organizations.status` free-form VARCHAR | §3.1.3 | ENUM: `active`, `inactive`, `suspended` |
| 13.1.3 | ✅ | `audit_logs.status` free-form VARCHAR | §3.1.4 | ENUM: `success`, `failure`, `error` |
| 13.1.4 | ✅ | `users.organization_id` nullable, default `1` | §3.2.1 | `NOT NULL` in migration; ORM default removed; signup already requires org |
| 13.1.5 | ✅ | `user_group_memberships` allows cross-org join | §3.2.2 | Validate `users.organization_id = user_groups.organization_id` on insert |
| 13.1.6 | ✅ | `user_permissions` has no `organization_id` | §3.2.3, §6.4.7 | Column + FK + backfill (`20260714_perm_org_id`); set on grant |
| 13.1.7 | ✅ | `manager_id` has no same-org constraint | §3.2.4, §4.8.2 | Enforce manager belongs to same org as report |
| 13.1.8 | ✅ | `two_factor_secret` plaintext; `backup_codes` lacks rotation metadata | §3.5.1–3.5.2 | Secret encrypted; `backup_codes_generated_at` added |
| 13.1.9 | ✅ | No durable `password_reset_tokens` table | §3.6, §6.1.1 | Create table; migrate service off Redis-only storage |

### 13.2 P1 schema — RBAC normalization

| # | Status | Issue | DB ref | Required change |
|---|--------|-------|--------|-----------------|
| 13.2.1 | ✅ | `users.role` is single string, not relational | §4.1.1 | `user_roles` dual-write + effective-role hydration on auth |
| 13.2.2 | ✅ | Permission catalog only in Python | §4.1.2, §6.1.4 | Create `permissions` table as canonical catalog |
| 13.2.3 | ✅ | Groups do not grant permissions at DB level | §4.1.3, §6.2.1 | Create `group_permissions` junction table |
| 13.2.4 | ✅ | No `role_permissions` mapping | §4.1.4, §6.1.6 | Create `role_permissions` table |
| 13.2.5 | ✅ | API key permissions unvalidated JSON | §3.5.3 | Validate against `permissions` catalog on write |

### 13.3 P1 schema — uniqueness & lifecycle

| # | Status | Issue | DB ref | Required change |
|---|--------|-------|--------|-----------------|
| 13.3.1 | ✅ | Duplicate group names per org allowed | §4.3.1 | `UNIQUE (organization_id, name)` on `user_groups` |
| 13.3.2 | ✅ | Duplicate user permissions allowed at DB level | §4.3.2 | `UNIQUE (user_id, permission_name, resource_type, resource_id)` |
| 13.3.3 | ✅ | No org `slug` for URLs/SSO | §4.3.3, §6.4.5 | Add `slug VARCHAR(100) UNIQUE` to `organizations` |
| 13.3.4 | ✅ | Users/orgs hard-deleted with CASCADE | §4.4.2–4.4.4 | Add `deleted_at`, `deleted_by`; soft delete + purge job |
| 13.3.5 | ✅ | `manager_id` allows hierarchy cycles | §4.8.1 | Cycle detection on manager assignment in `UserService` |
| 13.3.6 | ⏸ | No `access_token_revocations` / JWT `jti` blocklist table | §4.2.4 | Deferred with 1.12 — see [ACCESS_TOKEN_REVOCATION.md](./ACCESS_TOKEN_REVOCATION.md) |
| 13.3.7 | ✅ | Sequential INT PKs enumerable | §4.9.1 | Accept with strict IDOR checks, or add UUID public IDs |

### 13.4 P1 schema — new tables (must-have)

| # | Status | Table | DB ref | App work required |
|---|--------|-------|--------|-------------------|
| 13.4.1 | ✅ | `password_reset_tokens` | §6.1.1 | Refactor `PasswordResetService` |
| 13.4.2 | ✅ | `email_verification_tokens` | §6.1.2 | Signup + email-change verification endpoints |
| 13.4.3 | ✅ | `user_invitations` | §6.1.3 | Admin invite + accept flow |
| 13.4.4 | ✅ | `permissions` | §6.1.4 | Seed catalog; reference from services |
| 13.4.5 | ✅ | `roles` | §6.1.5 | System roles seeded; org-scoped column ready |
| 13.4.6 | ✅ | `role_permissions` | §6.1.6 | Map roles to permissions |
| 13.4.7 | ✅ | `user_roles` | §6.1.7 | Dual-write + effective role on auth/JWT |

### 13.5 P2 schema — enterprise tables (should-have)

| # | Status | Table | DB ref | Purpose |
|---|--------|-------|--------|---------|
| 13.5.1 | ✅ | `group_permissions` | §6.2.1 | Group-based access control |
| 13.5.2 | ✅ | `organization_settings` | §6.2.2 | Per-tenant config (password policy, session limits) |
| 13.5.3 | ✅ | `data_retention_policies` | §6.2.3 | Compliance-driven purge rules |
| 13.5.4 | ✅ | `consent_records` | §6.2.4 | GDPR / privacy consent |
| 13.5.5 | ✅ | `security_incidents` | §6.2.5 | Token reuse, breach events |

---

## 14. P2 — Database indexes & performance

Full index inventory in [DATABASE_SCHEMA_REVIEW.md §5 & Appendix A](./DATABASE_SCHEMA_REVIEW.md#5-p2--index-optimization).

| # | Status | Issue | DB ref | Required change |
|---|--------|-------|--------|-----------------|
| 14.1 | ✅ | `audit_logs` over-indexed (13 single-column indexes) | §5.1 | Dropped redundant single-cols covered by composites; kept `created_at` + filter cols |
| 14.2 | ✅ | Missing composite on `users` | §5.2.1–5.2.2 | Add `(organization_id, status)`, `(organization_id, role)` |
| 14.3 | ✅ | Missing composite on `refresh_tokens` | §5.2.3 | Add `(user_id, is_revoked, expires_at)` for session list + cleanup |
| 14.4 | ✅ | Missing composite on `user_sessions` | §5.2.4 | Add `(user_id, is_active, expires_at)` |
| 14.5 | ✅ | Missing composites on `login_attempts` | §5.2.5–5.2.6 | Add `(ip_address, created_at)`, `(username, created_at)` for rate limiting |
| 14.6 | ✅ | Missing composite on `api_keys` | §5.2.7 | Add `(organization_id, is_active)` |
| 14.7 | ✅ | Missing composite on `password_history` | §5.2.8 | Add `(user_id, created_at DESC)` for reuse check |
| 14.8 | ✅ | Redundant `ix_*_id` indexes duplicate PRIMARY KEY | §5.3 | Dropped on users/orgs/refresh_tokens/login_attempts/audit_logs |
| 14.9 | ✅ | `scripts/add_database_indexes_v2.py` indexes not applied to live DB | §5.3 note | Indexes in Alembic; scripts marked deprecated |
| 14.10 | ✅ | All timestamps naive `DATETIME` | §4.6.1 | Documented in `docs/UTC_DATETIME_CONVENTION.md` |

---

## 15. Production environment checklist

Use this table when cutting over an environment. Every row must be ✅ before go-live. Schema-specific rows cross-reference [DATABASE_SCHEMA_REVIEW.md §8](./DATABASE_SCHEMA_REVIEW.md#8-production-checklist-schema-specific).

### 15.1 Application & config

| # | Check | Env var / action |
|---|-------|------------------|
| 15.1.1 | JWT secret from secrets manager (≥32 chars, random) | `JWT__SECRET_KEY` |
| 15.1.2 | MySQL URL from secrets (not Neon default in code) | `DB__URL` or `DATABASE_URL` |
| 15.1.3 | Redis available and persistence enabled | `REDIS__*` |
| 15.1.4 | `APP__ENVIRONMENT=production` | |
| 15.1.5 | `SECURITY__ALLOW_DEBUG_AUTH=false` | |
| 15.1.6 | `SECURITY__ALLOW_PUBLIC_SIGNUP=false` (unless intentional) | |
| 15.1.7 | `AUTH_COOKIE__SECURE=true` | |
| 15.1.8 | `AUTH_COOKIE__LEGACY_JSON_REFRESH=false` | |
| 15.1.9 | `SECURITY__ENABLE_HTTPS_REDIRECT=true` | |
| 15.1.10 | CORS origins explicitly listed (no `*`) | `SECURITY__CORS_ORIGINS` |
| 15.1.11 | SMTP configured; test email delivery | `EMAIL__*` |
| 15.1.12 | `EMAIL__BASE_URL` matches public frontend URL | |
| 15.1.13 | `RATE_LIMIT__FAIL_OPEN=false` (**enforced** by `validate_production_config()`) | |
| 15.1.14 | OpenAPI/docs disabled publicly | automatic when `environment=production` |
| 15.1.15 | Logs shipping to central aggregator | stdout JSON |
| 15.1.16 | K8s probes: liveness `/health/live`, readiness per Redis strategy | |
| 15.1.17 | Incident runbook linked from deploy repo | |

### 15.2 Database & migrations

| # | Check | DB ref |
|---|-------|--------|
| 15.2.1 | Alembic `upgrade head` run on deploy | |
| 15.2.2 | ENUM/CHECK on `role`, `status` fields | §8.1 |
| 15.2.3 | `users.organization_id NOT NULL` (no default 1) | §8.2 |
| 15.2.4 | Cross-org membership guard in place | §8.3 |
| 15.2.5 | `password_reset_tokens` table live | §8.4 |
| 15.2.6 | `email_verification_tokens` table live | §8.5 |
| 15.2.7 | `user_invitations` table live (if using invite onboarding) | §8.6 |
| 15.2.8 | RBAC tables (`permissions`, `roles`, etc.) or documented deferral | §8.7 |
| 15.2.9 | Soft delete columns on users/orgs (or documented deferral) | §8.9 |
| 15.2.10 | Audit/login partition + retention policy active | §8.10 |
| 15.2.11 | All indexes defined in Alembic only (no drift scripts) | §8.12 |
| 15.2.12 | Duplicate FKs removed | §8.13 |
| 15.2.13 | `users.login_attempts` dead column dropped | §8.14 |
| 15.2.14 | `password_changed_at` + `email_verified_at` on users | §8.15 |
| 15.2.15 | `two_factor_secret` encrypted at rest | §8.16 |
| 15.2.16 | `user_groups` unique `(organization_id, name)` | §8.17 |
| 15.2.17 | Token/session/password-history purge jobs scheduled | §8.18–8.19 |
| 15.2.18 | Migration downgrade tested in CI | §8.20 |
| 15.2.19 | Seed/admin users rotated from CI defaults | |
| 15.2.20 | Backup job scheduled for MySQL | |

---

## 16. Summary counts

| Priority | Count | Description |
|----------|-------|-------------|
| **P0** (app) | 21 | Security, secrets, broken flows |
| **P1** (app) | 44 | Auth, RBAC, migrations, email, architecture (+6 from schema cross-ref) |
| **P1** (schema) | 28 | Data integrity, RBAC tables, lifecycle — [DATABASE_SCHEMA_REVIEW.md](./DATABASE_SCHEMA_REVIEW.md) §13 |
| **P2** (app) | 33 | Ops, performance, testing (+1 schema test) |
| **P2** (schema/index) | 10 | Index optimization — §14 |
| **P3** | 10 | Cleanup and maintainability |
| **Env checklist** | 37 | App (17) + DB (20) go-live items |
| **Total unique tracked issues** | **~118** | App + schema (some overlap counted once with DB refs) |

> **Note:** [DATABASE_SCHEMA_REVIEW.md](./DATABASE_SCHEMA_REVIEW.md) tracks **92 schema-specific items** in depth. This file adds **application-layer work** for each schema change plus **~30 app-only issues** not covered in the schema doc.

---

## Recommended implementation order

Aligned with [DATABASE_SCHEMA_REVIEW.md §9](./DATABASE_SCHEMA_REVIEW.md#9-recommended-migration-order).

### Sprint 1 — Security & schema integrity (P0)
1. Remove hardcoded secrets; add startup validation (1.6–1.8, 2.1–2.4)
2. DB: ENUM on `role`, `status` fields; `organization_id NOT NULL` (13.1.1–13.1.4, 4.5)
3. DB: Drop duplicate FKs; drop `users.login_attempts` (5.9, 5.2)
4. Fix `revoke-others` (1.2)
5. Disable debug auth + legacy JSON refresh in prod (1.5, 1.10)

### Sprint 2 — Auth lifecycle (P0 + P1)
1. DB: Create `password_reset_tokens`; wire `PasswordResetService` (13.1.9, 6.4)
2. Remove reset token from API response; send email (1.3, 6.1)
3. Implement 2FA login gate (1.1); encrypt `two_factor_secret` (1.4)
4. DB: Add `email_verified_at`, `password_changed_at` (5.11, 5.12)
5. Refresh token reuse detection (3.6)

### Sprint 3 — Onboarding & RBAC (P1)
1. DB: `email_verification_tokens`, `user_invitations` (13.4.2–13.4.3, 6.7–6.8)
2. DB: `permissions`, `roles`, `role_permissions`, `user_roles` (13.2, 13.4.4–13.4.7)
3. App: Consolidate role policy module (4.1, 4.2); `require_permission()` (4.3)
4. DB: `UNIQUE (organization_id, name)` on groups (13.3.1)

### Sprint 4 — Ops, indexes & hardening (P1 + P2)
1. DB: Index cleanup + composites (§14); fold into Alembic (5.6)
2. DB: Partition `audit_logs`, `login_attempts`; purge jobs (8.6, 8.11, 5.7–5.8)
3. DB: Soft delete columns (13.3.4)
4. App: Stdout JSON logging + metrics (8.1, 8.5)
5. Complete production checklists (§15.1 + §15.2)

### Sprint 5 — Enterprise (P2 + future)
1. JWT `jti` + Redis access-token blocklist (1.12) if compliance requires immediate revocation
2. `organization_settings`, `consent_records`, `security_incidents` (13.5)
3. ~~Split `production_endpoints.py` and `dashboard.py` (7.1, 7.2)~~ ✅
4. Expand IDOR + schema constraint tests (10.3, 10.9)
5. Evaluate UUID public IDs vs INT (13.3.7)

---

*Last updated: 2026-07-14 · Cross-referenced with [DATABASE_SCHEMA_REVIEW.md](./DATABASE_SCHEMA_REVIEW.md). Checklist has **no open ⬜ items**; deferred items are marked ⏸. Bar-(1) cutover: [ROLE_AUTHORITY_CUTOVER.md](./ROLE_AUTHORITY_CUTOVER.md) (Option B through **2026-08-14**) + Alembic `20260714_v1_harden`.*
