# ADR-001: Frontend authentication and token storage

| Field | Value |
|-------|-------|
| **Status** | Approved (conditional on backend P0) |
| **Date** | 2026-07-02 |
| **Scope** | React SPA in `frontend/` consuming `/api/v1` |

## Context

FastAPI today returns access and refresh tokens in JSON (`TokenResponse`). Refresh is sent in request bodies. `CORS_ORIGINS` defaults to `["*"]`. Login does not gate on `is_2fa_enabled`. The UI must meet enterprise IAM expectations (XSS-resistant refresh, predictable errors, multi-tab behavior).

## Decision

| Token | Storage | Transport |
|-------|---------|-----------|
| **Access token** | In-memory only (module singleton / React context) | `Authorization: Bearer` header |
| **Refresh token** | `httpOnly`, `Secure`, `SameSite=Lax` cookie | `credentials: 'include'` on API calls |
| **User profile** | TanStack Query cache | `GET /api/v1/profile` after auth |

**Rejected:** long-lived refresh in `localStorage` or `sessionStorage` (including temporary use).

### Transition period (calendar-bound)

| Phase | Target date | Backend | Frontend |
|-------|-------------|---------|----------|
| **Phase A** | Sprint 0 end | Return cookie **and** JSON `refresh_token` (legacy) | Build `apiClient` for cookie mode only; ignore JSON refresh |
| **Phase B** | +2 weeks after Phase A | `AUTH__LEGACY_JSON_REFRESH=false` — cookie only | Remove legacy JSON fallback |
| **Phase C** | Post-MVP | Optional: stop returning access in body | Out of MVP scope |

Flags: `AUTH__USE_HTTPONLY_REFRESH=true` (backend), `VITE_AUTH_COOKIE_MODE=true` (frontend).

## Auth flows

### Bootstrap (app load)

1. Render `AuthBootstrapShell` (full-screen loader; no nav).
2. `POST /api/v1/refresh` with `credentials: 'include'`.
3. On success: store access in memory → `GET /profile` → set role/org → render router.
4. On failure: public routes only.
5. **Never** flash protected UI before steps 2–3 complete.

JWT `role` is a hint only until `/profile` succeeds. Nav and `/` redirect use profile data.

### Role redirect at `/`

| Role | Redirect |
|------|----------|
| `user` | `/dashboard` |
| `admin`, `organization_admin`, `super_admin` | `/admin` (MVP; dedicated super-admin IA in M4) |

### Single-flight refresh

Parallel 401 responses must not trigger multiple refresh calls. Use a module-level refresh promise mutex. On second 401 after failed refresh → hard logout → `/login?reason=session_expired`.

### Proactive refresh

Access TTL is **5 minutes** (`config/settings.py` → `JWTSettings.access_token_expire_minutes`). Schedule refresh at `expires_in - 60` seconds (or after each successful response that returns `expires_in`). Do not rely on 401-only refresh.

**Backend option (P1):** bump web client access TTL to 15 minutes via config.

### Multi-tab logout

On logout (any tab):

1. `POST /api/v1/logout`
2. `BroadcastChannel('auth')` → `{ type: 'LOGOUT' }`
3. Clear memory + TanStack Query cache
4. Redirect to `/login`

Other tabs listen and redirect without calling logout again.

### Logout-all

`POST /api/v1/logout-all` clears server sessions, clears refresh cookie, and triggers the same client cleanup as logout (including `BroadcastChannel`).

### 2FA — two distinct flows

| Flow | When | API today | UI milestone |
|------|------|-----------|--------------|
| **2FA setup** | Logged-in user enables 2FA | `POST /2fa/enable`, `/2fa/verify` (Bearer required) | **M2** — Profile → Security tab |
| **2FA at login** | User with `is_2fa_enabled` logs in | **Not implemented** — login issues full tokens | **M2.5+** — `/login/2fa` blocked until backend P0 |

**2FA login partial state (when implemented):** `sessionStorage` may hold `temp_token` only (max 5 min TTL). Never store password or refresh token there. Clear on success, failure, or abandon.

## RBAC rule

> Nav visibility ≠ authorization. Every mutation shows API loading/error. Never enable actions optimistically from stale JWT; wait for `/profile` on bootstrap.

## Backend dependencies (P0)

See `docs/BACKEND_P0_UI_BLOCKERS.md`.

## Consequences

- Requires CORS `allow_credentials=True` and explicit origins (not `*`).
- Requires cookie `Domain` / `Path` alignment per `ADR-002-deployment-topology.md`.
- MSW may unblock UI scaffold in PR CI; **M1 exit requires real cookie auth on staging**.

## References

- `schemas/login.py` — `TokenResponse`, `ErrorResponse`, `UserResponse`
- `utils/security_middleware.py` — CORS, error handlers
- `routes/login.py` — login, refresh, logout
- `routes/auth_2fa.py` — setup flow (not login challenge)
