# API contract freeze (Sprint 1–2)

During internal consistency and integrity work, **HTTP paths and response shapes consumed by the React SPA must not break**. Refactors happen behind the same URLs.

## Frozen through Sprint 2

### Auth & identity (`/api/v1`)

| Method | Path | Notes |
|--------|------|-------|
| POST | `/signin`, `/signup`, `/refresh`, `/logout` | Token pair + cookie behavior unchanged |
| GET | `/profile`, `/users`, `/users/{id}` | Role-scoped listing shapes unchanged |
| POST/PATCH/DELETE | `/users`, `/users/{id}` | Admin user CRUD |

### Dashboard (role-prefixed — intentional split)

| Prefix | Role |
|--------|------|
| `/api/v1/dashboard/user/*` | `user` |
| `/api/v1/dashboard/admin/*` | `admin` |
| `/api/v1/dashboard/organization-admin/*` | `organization_admin` |
| `/api/v1/dashboard/super-admin/*` | `super_admin` |

Cross-prefix 403 responses are **correct**; see `docs/DASHBOARD_ROLE_MATRIX.md`.

### Compliance & integration

| Area | Paths |
|------|-------|
| Groups | `/api/v1/groups`, `/api/v1/groups/{id}`, membership routes |
| API keys | `/api/v1/api-keys`, `/api/v1/api-keys/{id}` |
| Integration | `/api/v1/integration/whoami` |
| Organizations | `/api/v1/organizations` (super_admin) |

### Allowed changes (non-breaking)

- Internal auth via `dependencies.auth` (`CurrentUser`, `require_roles`, `StaffUser`, `SuperAdminUser`)
- Config-driven TTLs (e.g. `JWT__REFRESH_TOKEN_EXPIRE_DAYS`)
- New **additive** JSON fields on responses
- New endpoints under existing prefixes
- Bug fixes that restore documented behavior

### Not allowed without frontend + integrator sign-off

- Renaming or removing paths above
- Changing HTTP status codes for happy paths (200 → 204, etc.)
- Global response envelope (`{ success, data, error }` everywhere)
- Merging dashboard prefixes across roles

## Exit criteria

Contract freeze lifts after **Sprint 2** staging release (A−) or when a dedicated API versioning effort is sponsored.
