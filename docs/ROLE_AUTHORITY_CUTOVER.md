# Role authority (bar-1 must) — collapsed to Option A

**Status (2026-11-15):** done. Migration `20261115_role_authority` dropped `users.role`.

| Field | Value |
|-------|--------|
| Role store | `user_roles` only (system roles + org-scoped custom roles) |
| Role rules | Data on `roles`: `level`, `is_platform`, `can_view_peers` |
| Code API | `services/permissions/role_catalog.py` (`is_platform_role`, `is_manager_role`, `is_base_role`, `assignable_roles`, `visible_role_names`) |
| Access checks | `require_permission("x:y")` against `role_permissions` / groups / direct grants — **no role-name bypass**; platform roles hold every permission |

## How it works

- `user.role` is a read-only **computed property**: the highest-`level` system role in
  `user_roles`. APIs and JWTs still expose `role`, so clients are unchanged.
- `user.role = "admin"` (or `RbacCatalogService.sync_user_system_role`) is stored only in
  `user_roles`, on flush (`models/role_events.py`). New users get `DEFAULT_ROLE_NAME`.
- Hierarchy rules, all from data:
  - **assign**: only roles with a strictly lower `level`;
  - **view** (same org): strictly lower levels, plus peers if `can_view_peers`;
  - **edit**: visible and strictly lower level;
  - **platform** roles (`is_platform`) see/manage all orgs and are hidden from tenants;
  - **manager** = any role ranked above the base (lowest) role.

| Default role | level | is_platform | can_view_peers |
|---|---|---|---|
| user | 10 | | |
| admin | 20 | | |
| organization_admin | 30 | | yes |
| super_admin | 100 | yes | |

## Adding a role (no code change)

Example — a college product adds `teacher` between `user` and `admin`:

```sql
INSERT INTO roles (name, organization_id, org_scope_key, is_system, level, is_platform, can_view_peers, description)
VALUES ('teacher', NULL, 0, 1, 15, 0, 0, 'Teacher');
-- grant its permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON p.name IN ('users:read', 'users:list')
WHERE r.name = 'teacher' AND r.is_system = 1;
```

Admins and above can now assign, see and manage teachers; teachers can manage plain
users only. Role rules are cached per process for 60 s (`role_catalog.invalidate_cache()`).

## Not yet covered (next steps)

- **Memberships**: a user still belongs to one organization (`users.organization_id`).
- **Unit tree**: no departments/classes under an organization; roles apply org-wide.
- **Ownership rules** ("teacher edits *their own* students") need a policy hook.
- Persona dashboards (`AdminUser`, `OrgAdminUser`) still select a UI view by role name.
