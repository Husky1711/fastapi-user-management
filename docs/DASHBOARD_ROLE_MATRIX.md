# Dashboard role × route matrix

This document records **product intent** for role-specific dashboards. It is the sign-off artifact for Sprint 0.

## Summary

Each staff role has its **own** dashboard API prefix and frontend home. Cross-access denials on another role’s dashboard prefix are **intentional**, not bugs.

| Role | Home (UI) | Dashboard API prefix | Notes |
|------|-----------|----------------------|-------|
| `user` | `/dashboard` | `/api/v1/dashboard/user/*` | Self-service stats only |
| `admin` | `/admin` | `/api/v1/dashboard/admin/*` | Org-scoped user management stats |
| `organization_admin` | `/org-admin` | `/api/v1/dashboard/organization-admin/*` | Broader org visibility (admins + users) |
| `super_admin` | `/super-admin` | `/api/v1/dashboard/super-admin/*` | Cross-org platform stats |

## Frontend → API mapping

| UI page | API client | Example endpoints |
|---------|------------|-------------------|
| User dashboard | (inline / dashboard user APIs) | `GET /api/v1/dashboard/user/overview` |
| Admin portal | `frontend/src/lib/admin/api.ts` | `GET /api/v1/dashboard/admin/overview` |
| Org admin portal | `frontend/src/lib/orgAdmin/api.ts` | `GET /api/v1/dashboard/organization-admin/overview` |
| Super admin portal | `frontend/src/lib/superAdmin/api.ts` | `GET /api/v1/dashboard/super-admin/overview` |

## Intentional denials (not bugs)

| Actor | Endpoint | Expected |
|-------|----------|----------|
| `organization_admin` | `/api/v1/dashboard/admin/*` | **403** — use org-admin dashboard |
| `admin` | `/api/v1/dashboard/super-admin/*` | **403** — use admin dashboard |
| `user` | `/api/v1/dashboard/admin/*` | **403** — use user dashboard |

Higher roles **do not** automatically inherit lower dashboard routes. They use their dedicated surface.

## Shared surfaces (compliance, user CRUD)

Compliance and user-management APIs use **org-scoped RBAC** via `role_scope` and `compliance_access`, not dashboard prefixes:

| Surface | Who | Scoping |
|---------|-----|---------|
| `GET /api/v1/users` | staff roles | `UserService.get_users_by_role_and_organization` |
| `GET /api/v1/audit/*` | staff roles | `compliance_access` |
| `POST /api/v1/groups` | admin, org_admin, super_admin | `require_group_manager` |
| `POST /api/v1/api-keys` | self + manageable users | `require_user_data_access` |

## Product sign-off (Sprint 0)

- [x] **Dashboard gates are role-specific by design** — do not widen `/dashboard/admin/*` to org_admin.
- [x] **Naming note:** `/dashboard/admin` sounds global but means **organization admin role `admin`**; consider renaming in a future API version only if external integrators exist.

## Enforcement in CI

Table-driven smoke tests in `tests/smoke/test_rbac_smoke.py` encode the matrix above. Any change to dashboard gates must update this doc and those tests together.
