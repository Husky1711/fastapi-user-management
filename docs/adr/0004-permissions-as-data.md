# 0004. Permission-based access control, stored as data

- Status: Accepted
- Date: 2026-11-27

## Context

The legacy code checks role names in `if/elif` chains (`super_admin`, `admin`, `user`). Every
product built on this base would need different roles, so it would have to edit core code —
the opposite of reusable. Role checks also spread: a new role means finding every `if`.

## Decision

- **Permissions** are strings of the form `resource:action` (e.g. `members:invite`), stored in a
  `permissions` table and seeded by migration.
- **Roles** are named sets of permissions (`role_permissions`). System roles (`owner`, `admin`,
  `member`) are seeded with `organization_id = NULL`; organizations may add custom roles.
- Routes declare the permission they need: `Depends(require_permission("members:invite"))`.
  No code ever compares role names.
- **Platform administration** is a separate flag, `users.is_platform_admin`, used only by
  `/api/v1/admin/*` routes. It does not grant org permissions implicitly through the org API;
  admin actions go through the admin API and are always audited.
- Non-members receive 404 for org resources, so the existence of an org is not revealed.

## Consequences

- Products rename, add or remove roles with data, not code.
- A permission check costs one cached lookup per request.
- Adding a feature means adding its permissions in a migration and granting them to roles.
- Safeguards are needed so an org can never lose its last `owner`.
