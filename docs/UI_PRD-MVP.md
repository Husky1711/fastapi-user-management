# UI PRD — MVP (web portal)

| Field | Value |
|-------|-------|
| **Status** | Approved with gates |
| **Product** | FastAPI User Management — Web Portal |
| **Goal** | Secure web UI for auth, profile, sessions, and basic admin user management |

## Product decision (locked)

**Signup:** **Out of MVP scope.** This is internal IAM; admins create users via `POST /admin/users/create`. No `/signup` page unless product explicitly reopens as P1.

## Personas (MVP)

| Persona | Access |
|---------|--------|
| **User** | Auth, dashboard, profile (tabs), sessions |
| **Admin** | User persona + admin dashboard, users list, create user |
| **Org Admin / Super Admin** | Same admin shell as Admin (backend scopes data); badge "System-wide view" for super_admin until M4 |

## MVP routes (~12)

| Route | Description |
|-------|-------------|
| `/login` | Login; inline lockout (423); session-expired banner; session-conflict modal |
| `/login/2fa` | **M2.5+ only** — blocked until backend 2FA-at-login ships |
| `/forgot-password` | Request reset |
| `/reset-password` | Validate token + set password |
| `/` | Bootstrap shell → role redirect |
| `/dashboard` | User overview (stat cards + skeletons; no chart library) |
| `/profile` | Tabs: Profile \| Security \| Sessions |
| `/admin` | Admin dashboard cards |
| `/admin/users` | Users table + empty state |
| `/admin/users/new` | Create user |
| `/unauthorized` | 403 |
| `/maintenance` | API unreachable on bootstrap |
| `*` | 404 |

**Not in MVP:** `/admin/users/:id` (M3.1 after `PATCH`), signup, audit, groups, API keys, role-specific super-admin dashboards.

## RBAC

> Nav visibility ≠ authorization. Backend enforces truth. UI handles 403 on every mutation.

## Success criteria

- [ ] Login → dashboard without refresh token in `localStorage`
- [ ] Bootstrap refresh on reload (E2E #7)
- [ ] Profile edit, password change, 2FA **setup** (while logged in)
- [ ] Sessions list + revoke
- [ ] Admin list + create users
- [ ] UI deployed to `app.staging.*` with ADR-002 smoke passing

## Milestone gates

| Milestone | Exit when |
|-----------|-----------|
| **Sprint 0** | ADRs in repo; `frontend/` builds; cookie login+refresh via **curl**; E2E 6, 7 (MSW OK in PR) |
| **M1** | Auth shell on **staging**; logout clears cookie; maintenance state; E2E 1, 3, 6, 7 |
| **M2** | Profile tabs; session revoke; 2FA **setup** under Security; E2E 5 — **not** login 2FA |
| **M2.5** | `/login/2fa` + E2E 2 (requires backend 2FA-at-login) |
| **M3** | Admin list + create; E2E 4, 8 — **no** detail/edit route |
| **M3.1** | `PATCH /users/{id}` → `/admin/users/:id` |
| **M4** | Dashboards by role, audit, groups, API keys |

## UX requirements (added from review)

- Global **429** toast with `Retry-After`
- **Skeleton loaders** on dashboard cards (parallel queries + 5-min access TTL)
- **Empty state** — admin with zero users
- **Logout-all** matches `POST /logout-all` (all sessions + all tabs via BroadcastChannel)

## References

- `docs/ADR-001-frontend-auth.md`
- `docs/ADR-002-deployment-topology.md`
- `docs/BACKEND_P0_UI_BLOCKERS.md`
- `docs/UI_SPRINT0_CHECKLIST.md`
