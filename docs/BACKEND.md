# FastAPI User Management — Backend Reference

Complete backend documentation: purpose, folder structure, code flow, role hierarchy, and API catalog.

**Stack:** FastAPI · SQLAlchemy · MySQL · Redis · JWT (access) · Opaque refresh tokens (DB + httpOnly cookie)

**Default port:** `9000`

---

## Table of contents

1. [System purpose](#1-system-purpose)
2. [Folder structure](#2-folder-structure)
3. [Architecture layers](#3-architecture-layers)
4. [Request code flow](#4-request-code-flow)
5. [Authentication flow](#5-authentication-flow)
6. [Role hierarchy & RBAC](#6-role-hierarchy--rbac)
7. [Multi-tenancy](#7-multi-tenancy)
8. [Database models](#8-database-models)
9. [Complete API catalog](#9-complete-api-catalog)
10. [Configuration](#10-configuration)
11. [Scripts & operations](#11-scripts--operations)
12. [Production readiness checklist](./BACKEND_PRODUCTION_READINESS.md) — all issues & required changes for go-live
13. [Code flow, hierarchy & diagrams](./BACKEND_CODE_FLOW.md) — Mermaid flows + full API catalog (2026-07-14)

---

## 1. System purpose

Enterprise **multi-tenant user management API** with:

| Domain | Capabilities |
|--------|--------------|
| **Identity** | Login, signup, logout, session control, account lockout |
| **Tokens** | Short-lived JWT access tokens + DB-backed refresh token rotation |
| **Users** | CRUD with role/org scoping, manager hierarchy |
| **Security** | 2FA (TOTP), password reset/change/history, rate limiting |
| **Compliance** | Audit logs, permissions, user groups, API keys |
| **Dashboards** | Role-specific analytics (user, admin, org-admin, super-admin) |
| **Organizations** | Tenant isolation; super-admin org CRUD |
| **Integration** | Machine-to-machine auth via `X-API-Key` header |

---

## 2. Folder structure

```
fastapi-user-management/
├── main.py                    # App entry, lifespan, health routes, router registration
├── alembic/                   # Database migrations
│   └── versions/
├── config/
│   └── settings.py            # Pydantic settings (DB, Redis, JWT, CORS, cookies, email)
├── dependencies/
│   └── auth.py                # CurrentUser, require_roles, require_staff
├── models/
│   ├── identity.py            # Organization, User, RefreshToken
│   ├── session.py             # sessions, password/email tokens, login attempts
│   ├── compliance.py          # audit, permissions, groups, api keys, retention
│   ├── rbac_model.py          # permissions catalog / roles
│   └── user_model.py          # re-exports (compat)
├── routes/                    # HTTP handlers (thin layer)
│   ├── auth_common.py         # API_PREFIX="/api/v1", create_api_router()
│   ├── auth.py                # login, signup, refresh, logout
│   ├── sessions.py            # session list, revoke
│   ├── users.py               # user list/detail/create/update (admin)
│   ├── profile.py             # self-service profile & password
│   ├── auth_2fa.py            # 2FA enable/verify/disable/status
│   ├── organizations.py       # org CRUD + organization_settings
│   ├── dashboard.py           # role dashboards (prefix /api/v1/dashboard)
│   ├── production_endpoints.py# thin aggregator (sessions_admin, permissions, groups, api-keys, password)
│   ├── audit.py               # audit logs / statistics
│   ├── sessions_admin.py      # session stats + cleanup
│   ├── permissions_mgmt.py    # user permission grants
│   ├── groups.py              # groups + group permissions
│   ├── api_keys.py            # API key CRUD
│   ├── password_history.py    # password history / policy stats
│   ├── retention.py           # data retention policies
│   ├── compliance.py          # consents + security incidents
│   ├── integration.py         # M2M whoami (prefix /api/v1/integration)
│   ├── invitations.py         # invite create/accept
│   ├── debug.py               # dev-only auth (conditional)
├── schemas/                   # Pydantic request/response models
│   ├── login.py
│   ├── auth_2fa.py
│   ├── dashboard.py
│   ├── organizations.py
│   └── compliance.py
├── services/                  # Business logic
│   ├── auth/
│   │   ├── auth_service.py           # JWT user resolution, token creation
│   │   ├── login_attempt_service.py  # authenticate + lockout
│   │   ├── refresh_token_service.py# refresh rotation, revocation
│   │   ├── logout_service.py
│   │   ├── enhanced_login_service.py # session strategies
│   │   └── two_factor_service.py
│   ├── users/
│   │   ├── user_service.py
│   │   ├── profile_update_service.py
│   │   ├── password_reset_service.py
│   │   ├── password_history_service.py
│   │   ├── organization_service.py
│   │   ├── role_scope.py             # who can view/edit whom
│   │   └── compliance_access.py      # org/user scoping for compliance APIs
│   ├── permissions/
│   │   ├── user_permission_service.py
│   │   ├── user_group_service.py
│   │   └── api_key_service.py
│   ├── audit/
│   │   └── audit_log_service.py
│   ├── sessions/
│   │   └── user_session_service.py
│   └── core/
│       ├── cache_service.py
│       └── rate_limit_service.py
├── utils/
│   ├── database.py            # SQLAlchemy engine, SessionLocal, get_db
│   ├── jwt_config.py          # JWT create/verify, bcrypt passwords
│   ├── cookie_auth.py         # httpOnly refresh cookie helpers
│   ├── security_middleware.py # CORS, headers, request ID, error handlers
│   ├── rate_limit_dependency.py
│   ├── api_key_dependency.py  # JWT or X-API-Key resolution
│   ├── api_errors.py          # APIHTTPException with error_code
│   ├── redis_config.py
│   └── loggers/               # structured app/auth/security/api logging
├── scripts/                   # bootstrap, smoke, CI helpers
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── smoke/
│   └── e2e/
├── templates/emails/            # password reset, welcome email HTML
├── deploy/                      # Helm / ArgoCD manifests
└── docs/
    └── BACKEND.md               # this file
```

---

## 3. Architecture layers

```
┌─────────────────────────────────────────────────────────┐
│  HTTP Client (browser, curl, API key)                   │
└────────────────────────┬────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│  MIDDLEWARE (utils/security_middleware.py)              │
│  CORS → HTTPS redirect → security logging → headers →   │
│  request ID → timing log (main.py)                      │
└────────────────────────┬────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│  ROUTES (routes/*.py)                                   │
│  Parse request · validate schema · call dependencies      │
└────────────────────────┬────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│  DEPENDENCIES (dependencies/auth.py, utils/*)          │
│  RateLimitDependency · CurrentUser · get_db             │
└────────────────────────┬────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│  SERVICES (services/*)                                  │
│  Business rules · RBAC · audit · token lifecycle        │
└────────────────────────┬────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│  MODELS + DATABASE (models/, MySQL via SQLAlchemy)      │
│  Redis (rate limits, cache, password-reset tokens)      │
└─────────────────────────────────────────────────────────┘
```

### Router registration (`main.py`)

| Router | Prefix | File |
|--------|--------|------|
| auth | `/api/v1` | `routes/auth.py` |
| sessions | `/api/v1` | `routes/sessions.py` |
| users | `/api/v1` | `routes/users.py` |
| profile | `/api/v1` | `routes/profile.py` |
| debug *(conditional)* | `/api/v1` | `routes/debug.py` |
| production | `/api/v1` | `routes/production_endpoints.py` (aggregator) + `audit` / `groups` / `api_keys` / … |
| retention | `/api/v1` | `routes/retention.py` |
| compliance | `/api/v1` | `routes/compliance.py` |
| integration | `/api/v1/integration` | `routes/integration.py` |
| auth_2fa | `/api/v1` | `routes/auth_2fa.py` |
| organizations | `/api/v1` | `routes/organizations.py` |
| dashboard | `/api/v1/dashboard` | `routes/dashboard.py` |
| health/root | `/` | `main.py` (inline) |

---

## 4. Request code flow

### 4.1 Typical authenticated request

```
1. Client sends: Authorization: Bearer <access_jwt>
2. RequestIDMiddleware assigns X-Request-ID
3. RateLimitDependency checks Redis (IP + user limits)
4. CurrentUser dependency:
   a. HTTPBearer extracts token
   b. AuthService.get_current_user(db, token)
   c. jwt.decode → user_id → User row from DB (fresh role/org)
5. Route handler applies inline role checks if needed
6. Service layer executes business logic
7. AuditLogService logs sensitive actions
8. JSONResponse returned (+ Set-Cookie on auth routes)
```

### 4.2 Login request

```
POST /api/v1/login { username, password }
  → LoginAttemptService.authenticate_with_lockout()
      → check locked_until
      → verify bcrypt password
      → record login_attempts row
  → AuthService.create_tokens_for_user()
      → JWT access token (5 min default)
      → opaque refresh token → SHA-256 hash in refresh_tokens table
      → user_sessions analytics row
  → build_auth_token_response()
      → access_token in JSON body
      → refresh_token in httpOnly cookie (path /api/v1)
  → AuditLogService.log_authentication_event()
```

### 4.3 Refresh request

```
POST /api/v1/refresh
  → resolve_refresh_token(request, body)
      → cookie first (browser) or body token (legacy/TestClient)
  → RefreshTokenService.verify_refresh_token()
  → rotate: revoke old refresh, issue new access + refresh
  → Set-Cookie with new refresh token
```

### 4.4 API key (M2M) request

```
GET /api/v1/integration/whoami
  Header: X-API-Key: <key>
  → ApiKeyService.validate_api_key()
  → returns principal (user_id, org_id, permissions)
```

### 4.5 Application startup (`lifespan`)

```
1. Log app version + environment
2. Ping MySQL (SELECT 1)
3. Ping Redis (rate limiting; fails open if down)
4. Log security config (CORS, lockout settings)
5. Serve requests
6. On shutdown: log graceful stop
```

---

## 5. Authentication flow

### Token types

| Token | Storage | Lifetime | Purpose |
|-------|---------|----------|---------|
| **Access JWT** | Client memory (Bearer header) | 5 min (configurable) | API authorization |
| **Refresh token** | httpOnly cookie + DB hash | 7 days | Rotate access without re-login |

### JWT claims

```json
{
  "sub": "username",
  "user_id": 2,
  "role": "user",
  "organization_id": 1,
  "email": "user@test.com",
  "exp": 1234567890
}
```

> **Important:** `get_current_user` always reloads the `User` row from DB. JWT role claims can be stale; DB is source of truth.

### Cookie settings (`AUTH_COOKIE__*`)

| Setting | Default | Notes |
|---------|---------|-------|
| `USE_HTTPONLY_REFRESH` | `true` | Refresh in httpOnly cookie |
| `LEGACY_JSON_REFRESH` | `true` | Also return refresh in JSON (transition) |
| Cookie name | `refresh_token` | |
| Path | `/api/v1` | |
| SameSite | `lax` | |
| Secure | `false` | Set `true` in HTTPS production |

### Password hashing

- **Primary:** bcrypt (`utils/jwt_config.py`)
- **Legacy:** SHA-256 hex supported; auto-rehash to bcrypt on successful login

### Account lockout

- After `SECURITY__MAX_LOGIN_ATTEMPTS` (default 5) failed attempts
- Lock duration: `SECURITY__LOCKOUT_DURATION_MINUTES` (default 15)
- Returns `423 ACCOUNT_LOCKED`

### 2FA

- TOTP via `TwoFactorService`
- Endpoints: enable → verify → status / disable
- Standard `/login` does **not** gate on 2FA (separate flow)

---

## 6. Role hierarchy & RBAC

### 6.1 Role rank

```
super_admin (4)
    └── organization_admin (3)
            └── admin (2)
                    └── user (1)
```

Defined in `services/users/role_scope.py`:

```python
_ROLE_RANK = {
    "user": 1,
    "admin": 2,
    "organization_admin": 3,
    "super_admin": 4,
}
```

### 6.2 Who can create which roles

| Creator | Can assign |
|---------|-----------|
| `super_admin` | `organization_admin`, `admin`, `user` |
| `organization_admin` | `admin`, `user` |
| `admin` | `user` |
| `user` | *(none)* |

Enforced by `RoleHierarchyValidator` in `schemas/login.py`.

### 6.3 Visibility (who can see whom)

| Viewer role | Sees in org |
|-------------|-------------|
| `super_admin` | Everyone, all orgs |
| `organization_admin` | `organization_admin`, `admin`, `user` in own org |
| `admin` | `user` only in own org |
| `user` | Self only |

`super_admin` users are **invisible** in org-scoped views (`ORG_INVISIBLE_ROLES`).

### 6.4 Edit rules

- `can_edit_user(editor, target)`: editor must outrank target in `_ROLE_RANK`
- Cannot edit yourself via admin endpoints
- Only `super_admin` can edit another `super_admin`

### 6.5 Manager hierarchy

- Only `user` role has `manager_id`
- Manager must be `admin`, `organization_admin`, or `super_admin` in same org
- `admin` can only assign themselves as manager

### 6.6 Staff vs user dependencies

| Dependency | Allowed roles | Used for |
|------------|---------------|----------|
| `CurrentUser` | any authenticated | profile, dashboards |
| `require_staff` | admin, organization_admin, super_admin | group CRUD |
| `require_roles("super_admin")` | super_admin | org CRUD |
| `compliance_access` helpers | varies | audit, permissions, api-keys scoping |

### 6.7 Dashboard access (enforced in route handlers)

| Dashboard prefix | Required role |
|------------------|---------------|
| `/api/v1/dashboard/user/*` | any authenticated |
| `/api/v1/dashboard/admin/*` | `admin` |
| `/api/v1/dashboard/organization-admin/*` | `organization_admin` |
| `/api/v1/dashboard/super-admin/*` | `super_admin` |

---

## 7. Multi-tenancy

```
organizations
    └── users (organization_id FK)
            ├── refresh_tokens
            ├── user_sessions
            ├── audit_logs
            ├── user_permissions
            ├── user_groups
            └── api_keys
```

| Role | Org scope |
|------|-----------|
| `user`, `admin`, `organization_admin` | Own `organization_id` only |
| `super_admin` | All orgs; `organization_id` often `2` (System org) |

Compliance endpoints use `services/users/compliance_access.py` to filter by `viewer.organization_id` and manageable user IDs.

---

## 8. Database models

Split across `models/identity.py`, `models/session.py`, `models/compliance.py`, `models/rbac_model.py` (`user_model.py` re-exports for compatibility):

| Model | Table | Purpose |
|-------|-------|---------|
| `Organization` | `organizations` | Tenant |
| `User` | `users` | Account, role, org, manager, 2FA |
| `RefreshToken` | `refresh_tokens` | Opaque refresh token hashes |
| `UserSession` | `user_sessions` | Session analytics |
| `AuditLog` | `audit_logs` | Security audit trail |
| `LoginAttempt` | `login_attempts` | Failed login tracking |
| `PasswordHistory` | `password_history` | Prevent password reuse |
| `UserPermission` | `user_permissions` | Granular grants (+ `organization_id`) |
| `UserGroup` | `user_groups` | Org-scoped groups |
| `UserGroupMembership` | `user_group_memberships` | Group members |
| `ApiKey` | `api_keys` | M2M programmatic access |

Migrations: `alembic/versions/` (run via `scripts/ci_bootstrap_db.py` or `alembic upgrade head`).

---

## 9. Complete API catalog

**Total:** 72 production endpoints (+ 2 debug when `SECURITY__ALLOW_DEBUG_AUTH=true`)

Legend: **Auth** = `None` | `JWT` | `Refresh` | `JWT or API-Key`

### 9.1 Health & root (`main.py`) — 7 endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/` | None | API info; dev redirects to `/docs` |
| GET | `/health` | None | Basic liveness |
| GET | `/api/v1/health` | None | Versioned health |
| GET | `/health/detailed` | None | DB + Redis status |
| GET | `/health/ready` | None | K8s readiness (503 if deps down) |
| GET | `/health/live` | None | K8s liveness |
| GET | `/hello` | None | Dev-only smoke (not registered in production) |

### 9.2 Authentication (`routes/auth.py`) — 6 endpoints

| Method | Path | Auth | Purpose | Service |
|--------|------|------|---------|---------|
| POST | `/api/v1/login` | None | Sign in | `LoginAttemptService`, `AuthService` |
| POST | `/api/v1/signup` | None* | Register | `AuthService` |
| POST | `/api/v1/refresh` | Refresh | Rotate access token | `AuthService`, `RefreshTokenService` |
| POST | `/api/v1/login-with-session-control` | None | Login + session strategy | `EnhancedLoginService` |
| POST | `/api/v1/logout` | Refresh | Revoke current session | `LogoutService` |
| POST | `/api/v1/logout-all` | JWT | Revoke all sessions | `LogoutService` |

\* Requires `SECURITY__ALLOW_PUBLIC_SIGNUP=true`

### 9.3 Sessions (`routes/sessions.py`) — 4 endpoints

| Method | Path | Auth | Purpose | Service |
|--------|------|------|---------|---------|
| GET | `/api/v1/sessions/info` | JWT | Session details | `EnhancedLoginService` |
| POST | `/api/v1/sessions/revoke-others` | JWT | Revoke other devices | `EnhancedLoginService` |
| GET | `/api/v1/sessions` | JWT | List active sessions | `RefreshTokenService` |
| DELETE | `/api/v1/sessions/{session_id}` | JWT | Revoke one session | `RefreshTokenService` |

### 9.4 Users (`routes/users.py`) — 4 endpoints

| Method | Path | Auth | Role | Purpose | Service |
|--------|------|------|------|---------|---------|
| GET | `/api/v1/users` | JWT | scoped | List users | `UserService` |
| GET | `/api/v1/users/{user_id}` | JWT | scoped | User detail | `UserService` |
| PATCH | `/api/v1/users/{user_id}` | JWT | staff | Admin update | `UserService` |
| POST | `/api/v1/admin/users/create` | JWT | staff | Create user | `UserService` |

### 9.5 Profile & password (`routes/profile.py`) — 6 endpoints

| Method | Path | Auth | Purpose | Service |
|--------|------|------|---------|---------|
| POST | `/api/v1/password/reset-request` | None | Request reset email | `PasswordResetService` |
| POST | `/api/v1/password/reset` | None | Confirm reset | `PasswordResetService` |
| GET | `/api/v1/password/reset/validate/{token}` | None | Validate token | `PasswordResetService` |
| GET | `/api/v1/profile` | JWT | Own profile | DB query |
| PUT | `/api/v1/profile` | JWT | Update email/phone | `ProfileUpdateService` |
| POST | `/api/v1/password/change` | JWT | Change password | `ProfileUpdateService` |

### 9.6 Two-factor auth (`routes/auth_2fa.py`) — 4 endpoints

| Method | Path | Auth | Purpose | Service |
|--------|------|------|---------|---------|
| POST | `/api/v1/2fa/enable` | JWT | Start 2FA (QR + backup codes) | `TwoFactorService` |
| POST | `/api/v1/2fa/verify` | JWT | Verify TOTP / backup code | `TwoFactorService` |
| POST | `/api/v1/2fa/disable` | JWT | Disable 2FA | `TwoFactorService` |
| GET | `/api/v1/2fa/status` | JWT | 2FA status | — |

### 9.7 Organizations (`routes/organizations.py`) — 4 endpoints

| Method | Path | Auth | Role | Purpose | Service |
|--------|------|------|------|---------|---------|
| GET | `/api/v1/organizations` | JWT | super_admin | List orgs | `OrganizationService` |
| GET | `/api/v1/organizations/{id}` | JWT | super_admin | Org detail | `OrganizationService` |
| POST | `/api/v1/organizations` | JWT | super_admin | Create org | `OrganizationService` |
| PATCH | `/api/v1/organizations/{id}` | JWT | super_admin | Update org | `OrganizationService` |

### 9.8 Dashboards (`routes/dashboard.py`) — 13 endpoints

Prefix: `/api/v1/dashboard`

| Method | Path | Role | Purpose |
|--------|------|------|---------|
| GET | `/user/overview` | any | Personal dashboard stats |
| GET | `/user/activity` | any | Own login activity |
| GET | `/user/sessions` | any | Own active sessions |
| GET | `/admin/overview` | admin | Org admin overview |
| GET | `/admin/users/stats` | admin | User breakdown |
| GET | `/admin/activity/stats` | admin | Activity stats |
| GET | `/organization-admin/overview` | organization_admin | Org-wide overview |
| GET | `/organization-admin/users/stats` | organization_admin | User stats |
| GET | `/organization-admin/sessions/stats` | organization_admin | Session stats |
| GET | `/super-admin/overview` | super_admin | System overview |
| GET | `/super-admin/users/stats` | super_admin | All-user stats |
| GET | `/super-admin/organizations/stats` | super_admin | Org stats |
| GET | `/super-admin/sessions/stats` | super_admin | System session stats |

### 9.9 Compliance APIs (split routers; aggregated by production_endpoints.py)


Split across `routes/audit.py`, `routes/sessions_admin.py`, `routes/permissions_mgmt.py`, `routes/groups.py`, `routes/api_keys.py`, `routes/password_history.py` (aggregated by `routes/production_endpoints.py`).

| Method | Path | Auth | Role / scope | Purpose | Service |
|--------|------|------|--------------|---------|---------|
| GET | `/api/v1/audit/logs` | JWT | org scoped | Paginated audit logs | `AuditLogService` |
| GET | `/api/v1/audit/statistics` | JWT | org scoped | Audit analytics | `AuditLogService` |
| GET | `/api/v1/sessions/statistics` | JWT | org scoped | Session analytics | `UserSessionService` |
| POST | `/api/v1/sessions/cleanup` | JWT | org_admin, super_admin | Purge expired sessions | `UserSessionService` |
| GET | `/api/v1/permissions` | JWT | user/org scoped | List permissions | `UserPermissionService` |
| GET | `/api/v1/permissions/standard` | JWT | any | Permission catalog | `UserPermissionService` |
| GET | `/api/v1/permissions/statistics` | JWT | org scoped | Permission stats | `UserPermissionService` |
| GET | `/api/v1/groups` | JWT | org scoped | List groups | `UserGroupService` |
| GET | `/api/v1/groups/{id}/members` | JWT | org scoped | Group members | `UserGroupService` |
| GET | `/api/v1/groups/statistics` | JWT | org scoped | Group stats | `UserGroupService` |
| POST | `/api/v1/groups` | JWT | staff | Create group | `UserGroupService` |
| PATCH | `/api/v1/groups/{id}` | JWT | staff | Update group | `UserGroupService` |
| DELETE | `/api/v1/groups/{id}` | JWT | staff | Soft-delete group | `UserGroupService` |
| POST | `/api/v1/groups/{id}/members` | JWT | staff | Add member | `UserGroupService` |
| DELETE | `/api/v1/groups/{id}/members/{user_id}` | JWT | staff | Remove member | `UserGroupService` |
| GET | `/api/v1/api-keys` | JWT | user/org scoped | List API keys | `ApiKeyService` |
| GET | `/api/v1/api-keys/standard-permissions` | JWT | any | Key scope catalog | `ApiKeyService` |
| GET | `/api/v1/api-keys/statistics` | JWT | org scoped | Key stats | `ApiKeyService` |
| POST | `/api/v1/api-keys` | JWT | scoped | Issue API key | `ApiKeyService` |
| PATCH | `/api/v1/api-keys/{id}` | JWT | scoped | Update key metadata | `ApiKeyService` |
| DELETE | `/api/v1/api-keys/{id}` | JWT | scoped | Revoke key | `ApiKeyService` |
| GET | `/api/v1/password/history` | JWT | user/org scoped | Password change log | `PasswordHistoryService` |
| GET | `/api/v1/password/policy-stats` | JWT | user/org scoped | Policy compliance | `PasswordHistoryService` |

### 9.10 Integration (`routes/integration.py`) — 1 endpoint

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/v1/integration/whoami` | JWT **or** `X-API-Key` | Verify M2M principal |

### 9.11 Debug (`routes/debug.py`) — 2 endpoints *(off by default)*

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/v1/debug-login` | None | Dev login (tokens in JSON only) |
| POST | `/api/v1/debug-refresh` | None | Dev refresh |

Enabled when `SECURITY__ALLOW_DEBUG_AUTH=true`.

---

## 10. Configuration

Primary file: `.env` (loaded by `config/settings.py`)

| Prefix | Section | Key settings |
|--------|---------|--------------|
| `APP__` | Application | name, port (9000), environment |
| `DB__` | Database | `URL`, pool size |
| `REDIS__` | Redis | host, port (rate limits) |
| `JWT__` | Tokens | secret, access expiry (5 min), refresh days (7) |
| `SECURITY__` | Security | CORS origins, lockout, allow_public_signup |
| `AUTH_COOKIE__` | Cookies | httponly refresh, legacy JSON, secure |
| `RATE_LIMIT__` | Rate limits | per-endpoint + global IP limits |
| `EMAIL__` | SMTP | password reset emails |

### Local development (Podman MySQL)

```env
DB__URL=mysql+pymysql://fastapi:fastapi@localhost:3306/fastapi_users
```

Bootstrap seed users:

```bash
python scripts/ci_bootstrap_db.py
```

### Seed accounts

| Username | Password | Role | Org |
|----------|----------|------|-----|
| `testadmin` | `admin123` | admin | 1 |
| `testuser` | `user123` | user | 1 |
| `testorgadmin` | `orgadmin123` | organization_admin | 1 |
| `testuser_org2` | `user2123` | user | 2 |
| `test_super_admin` | `TestSuperAdminPass123!` | super_admin | 2 |

---

## 11. Scripts & operations

### Database bootstrap (canonical)

| Environment | Script | Notes |
|-------------|--------|-------|
| **CI / local seeded** | `scripts/ci_bootstrap_db.py` | **Canonical** — Alembic `upgrade head` + seed users |
| **Local migrate-only** | `scripts/bootstrap_local_db.py` | Upgrade (or stamp legacy) without re-seeding |
| **Neon / Postgres (legacy)** | `scripts/bootstrap_neon.py` | Deprecated for greenfield; prefer Alembic on Postgres `DATABASE_URL` |

```bash
# Preferred for Codespaces / CI / new MySQL volume
python scripts/ci_bootstrap_db.py
```

### Other scripts

| Script | Purpose |
|--------|---------|
| `scripts/ci_bootstrap_db.py` | Alembic migrate + seed test users (**canonical**) |
| `scripts/bootstrap_local_db.py` | Alembic migrate only (MySQL) |
| `scripts/bootstrap_neon.py` | Legacy Postgres `create_all` / data copy |
| `scripts/export_openapi.py` | Write `artifacts/openapi.json` (prod docs disabled) |
| `scripts/curl_auth_checklist.py` | ADR-002 cookie auth smoke |
| `scripts/smoke_auth_probe.py` | CI smoke test runner |
| `scripts/signoff_bootstrap_check.py` | Full-stack sign-off check |
| `scripts/staging_post_deploy_smoke.sh` | Post-deploy validation |
| `scripts/ensure_bcrypt_seed_passwords.py` | Upgrade legacy SHA passwords |
| `scripts/export_schema_sql.py` | Dump live MySQL DDL → `docs/schema/fastapi_users_schema_latest.sql` |
| `docker-compose.codespaces.yml` | MySQL + Redis for local dev |

On-call: [OPS_RUNBOOKS.md](./OPS_RUNBOOKS.md).  
API versioning: [API_VERSIONING.md](./API_VERSIONING.md).  
Workers / replicas: [DEPLOYMENT_TOPOLOGY.md](./DEPLOYMENT_TOPOLOGY.md).

### Run locally

```bash
# MySQL + Redis (Podman)
podman run -d --name fastapi-mysql -e MYSQL_ROOT_PASSWORD=root \
  -e MYSQL_DATABASE=fastapi_users -e MYSQL_USER=fastapi -e MYSQL_PASSWORD=fastapi \
  -p 3306:3306 docker.io/library/mysql:8.0

python scripts/ci_bootstrap_db.py
python -m uvicorn main:app --host 127.0.0.1 --port 9000
```

### Error response shape

All API errors include structured fields via `utils/api_errors.py`:

```json
{
  "detail": "Incorrect username or password",
  "error_code": "INVALID_CREDENTIALS",
  "status_code": 401,
  "correlation_id": "uuid",
  "timestamp": 1234567890.0
}
```

Common `error_code` values: `INVALID_CREDENTIALS`, `ACCOUNT_LOCKED`, `SESSION_EXISTS`, `VALIDATION_ERROR`, `FORBIDDEN`.

---

## Quick reference diagram

```
                    ┌──────────────┐
                    │  super_admin │
                    └──────┬───────┘
                           │
              ┌────────────┴────────────┐
              │   organization_admin    │
              └────────────┬────────────┘
                           │
                    ┌──────┴──────┐
                    │    admin    │
                    └──────┬──────┘
                           │
                    ┌──────┴──────┐
                    │    user     │
                    └─────────────┘

Organization boundary ─────────────────────────────
  users · groups · api_keys · audit_logs · permissions
```

---

*Generated from codebase analysis. Default server: `http://127.0.0.1:9000` · OpenAPI: `/docs` (non-production).*
