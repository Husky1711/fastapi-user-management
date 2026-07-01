# Backend P0 backlog — UI blockers

Mapped to the **current codebase** (`feature/codespaces-local-db`).  
Use as GitHub issues or sprint tickets. Assign **owner + target date** before committing to MVP timeline.

**Honest estimate:** ~2–3 weeks backend work before M1–M3 are fully honest (cookie auth, errors, 2FA login, PATCH, pagination).

---

## P0 — Blocks Sprint 0 exit / M1

### 1. httpOnly refresh cookie on auth endpoints

**Status:** Not implemented. Tokens returned in JSON only (`schemas/login.py` → `TokenResponse`).

| Task | File(s) |
|------|---------|
| Set `Set-Cookie` on login | `routes/login.py` — `login()`, `login_with_session_control()` (~line 43, ~392) |
| Read cookie on refresh; rotate cookie | `routes/login.py` — `refresh()` (~359); `services/auth/auth_service.py` — `refresh_access_token` |
| Clear cookie on logout | `routes/login.py` — `logout()`, `logout_all()` (~534, ~604) |
| Cookie helper (name, path, domain, max_age) | New: `utils/cookie_auth.py` or `services/auth/cookie_service.py` |
| Settings for cookie domain/path | `config/settings.py` — new `CookieSettings` or extend `SecuritySettings` |
| Env examples | `.env.codespaces.example`, `deploy/helm/.../values.yaml` |

**Acceptance:** ADR-002 curl checklist passes on local/staging.

---

### 2. CORS credentials + explicit origins

**Status:** `cors_origins` defaults to `["*"]` (`config/settings.py` ~253). Incompatible with `allow_credentials=True`.

| Task | File(s) |
|------|---------|
| `allow_credentials=True` in CORSMiddleware | `utils/security_middleware.py` (~168–177) |
| Default origins to empty or env-specific (not `*`) | `config/settings.py` — `SecuritySettings` |
| Document staging origin | `.env.codespaces.example` |

**Acceptance:** Browser login from `http://localhost:5173` with credentials succeeds.

---

### 3. Global error contract with `error_code`

**Status:** `ErrorResponse` schema has `error_code` (`schemas/login.py` ~118) but handlers return `detail` + `status_code` only (`utils/security_middleware.py` ~207–214). Login raises plain `HTTPException(detail="...")` without codes (`routes/login.py` ~106–145).

| Task | File(s) |
|------|---------|
| Extend `http_exception_handler` to emit `error_code`, `correlation_id` | `utils/security_middleware.py` — `setup_error_handlers` |
| Custom exception class or `HTTPException` detail dict | New: `utils/exceptions.py` |
| Map login lockout to `ACCOUNT_LOCKED` (423) | `routes/login.py` ~106–110 |
| Map rate limit to `RATE_LIMIT_EXCEEDED` (429) | `utils/rate_limit_dependency.py` ~54–78 |
| Validation errors → `VALIDATION_ERROR` + `fields` | `utils/security_middleware.py` ~231–238 |

**Suggested codes:** `INVALID_CREDENTIALS`, `ACCOUNT_LOCKED`, `FORBIDDEN`, `RATE_LIMIT_EXCEEDED`, `REQUIRES_2FA`, `SESSION_EXISTS`, `VALIDATION_ERROR`.

**Acceptance:** Login lockout and rate limit responses include parseable `error_code`.

---

### 4. 2FA at login (net-new — not a spec tweak)

**Status:** **Gap confirmed in code.**

- `POST /login` calls `AuthService.create_tokens_for_user` without checking `user.is_2fa_enabled` (`routes/login.py` ~164–167).
- `POST /2fa/verify` requires Bearer token — setup flow only (`routes/auth_2fa.py` ~96–100).

| Task | File(s) |
|------|---------|
| Gate login: if `is_2fa_enabled`, return challenge (no full tokens) | `routes/login.py` — `login()` |
| New response schema `Requires2FAResponse` | `schemas/login.py` or `schemas/auth_2fa.py` |
| Short-lived `temp_token` (JWT, 5 min) | `services/auth/auth_service.py` or `two_factor_service.py` |
| New `POST /2fa/verify-login` (temp_token + TOTP → tokens + cookie) | `routes/auth_2fa.py` (new endpoint) |
| Enable `is_2fa_enabled` only after successful verify during setup | `routes/auth_2fa.py` — already partial (~140) |
| Integration tests | `tests/integration/test_auth_integration.py` |

**UI impact:** `/login/2fa` is **M2.5**, not M2. M2 ships 2FA setup under Profile → Security only.

**Acceptance:** User with 2FA enabled cannot get refresh cookie without TOTP; E2E #2 passes.

---

## P0 — Blocks M3 / M3.1

### 5. `PATCH /api/v1/users/{user_id}`

**Status:** Not in codebase. Only `GET /users`, `GET /users/{id}`, `POST /admin/users/create` (`routes/login.py`).

| Task | File(s) |
|------|---------|
| Request/response schemas | `schemas/login.py` — e.g. `AdminUpdateUserRequest` |
| Route handler with RBAC | `routes/login.py` or new `routes/users.py` |
| Service method | `services/users/user_service.py` |
| Audit log entry | `services/audit/audit_log_service.py` |
| Tests | `tests/unit/test_user_service.py`, integration tests |

**Acceptance:** Admin can update `status` and `role` for users in scope; M3.1 UI unblocked.

---

## P1 — Blocks quality / scale (schedule before M3)

### 6. `GET /users` pagination and stable response shape

**Status:** `UsersListResponse` defines `page` / `per_page` / `total_count` (`schemas/login.py` ~91) but **`GET /users` ignores query params** and returns ad-hoc dicts (`routes/login.py` ~715–783). No `total_count` in response.

| Task | File(s) |
|------|---------|
| Add `page`, `per_page`, `query` query params | `routes/login.py` — `get_all_users` |
| Pass `skip`/`limit` to service | `services/users/user_service.py` — `get_users_by_role_and_organization` (has skip/limit; not wired) |
| Return `UsersListResponse` / `SuperAdminUsersResponse` consistently | `routes/login.py`, `schemas/login.py` |
| Super admin grouped response documented in OpenAPI | Same |

**Acceptance:** Admin table can paginate without frontend rewrite.

---

### 7. Access token TTL for web clients

**Status:** 5 minutes (`config/settings.py` ~60).

| Task | File(s) |
|------|---------|
| Increase to 15 min **or** add `JWT__WEB_ACCESS_TOKEN_EXPIRE_MINUTES` | `config/settings.py` — `JWTSettings` |
| Return `expires_in` on refresh (already on `TokenResponse`) | verify `routes/login.py` |

**Frontend:** proactive refresh either way (ADR-001).

---

### 8. OpenAPI export + CI diff

| Task | File(s) |
|------|---------|
| Script to dump OpenAPI | `scripts/export_openapi.py` (new) or `curl localhost:9000/openapi.json` |
| CI job | `.github/workflows/` (new or extend) |
| Frontend codegen | `frontend/package.json` scripts |

---

## P2 — M4 (unchanged)

- API keys CRUD — `services/permissions/api_key_service.py`, `routes/production_endpoints.py`
- Groups CRUD — `services/permissions/user_group_service.py`
- Organization CRUD — `models/user_model.py` (Organization), new routes
- Audit export — `services/audit/audit_log_service.py`

---

## Codebase vs plan — quick reference

| Plan assumption | Codebase reality |
|-----------------|------------------|
| Cookie refresh | JSON body only |
| `error_code` on errors | Schema exists; handlers don't emit consistently |
| 2FA at login | Login ignores `is_2fa_enabled` |
| `PATCH /users` | Missing |
| Paginated `GET /users` | Schema exists; route not wired |
| `GET /profile` returns role | Yes — `UserResponse` (`routes/login.py` ~1244) |
| `frontend/` directory | Does not exist yet |
| Signup | API exists; **UI deferred** per PRD |

---

## Suggested GitHub issue titles

1. `[P0] httpOnly refresh cookie — login/refresh/logout`
2. `[P0] CORS credentials + explicit origins for UI`
3. `[P0] Global API error handler with error_code`
4. `[P0] 2FA challenge at login + verify-login endpoint`
5. `[P0] PATCH /api/v1/users/{user_id}`
6. `[P1] GET /users pagination + consistent response schema`
7. `[P1] Web access token TTL + OpenAPI CI export`

---

## Test mapping

| E2E | Blocked by |
|-----|------------|
| #1 Login → dashboard | P0 #1, #2, #3 |
| #2 Login + 2FA | P0 #4 |
| #3 Session expired | P0 #1 |
| #4 Admin create user | M1 + existing `POST /admin/users/create` |
| #5 Revoke session | M1 + existing session routes |
| #6 Unauthorized | M1 auth shell |
| #7 Bootstrap refresh | P0 #1, #2 |
| #8 403 on mutation | M3 + consistent `FORBIDDEN` code (P0 #3) |
