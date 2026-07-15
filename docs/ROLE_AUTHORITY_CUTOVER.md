# Role authority cutover (bar-1 must)

**Decision (2026-07-14):** **Option B — ironclad dual-write** for v1 production cutover.

**Related docs:** [ROLE_AUTHORITY_CUTOVER.md](./ROLE_AUTHORITY_CUTOVER.md) (owner + **2026-08-14** B end date).

| Field | Value |
|-------|--------|
| Status | In sprint |
| Choice | **B** — `users.role` remains the app string API; `user_roles`/`roles` is the catalog mirror for permission grants and auth hydration |
| Owner | Backend / identity (assign named owner before merge to `main`) |
| Dual-write end date | **2026-08-14** — by this date choose collapse (**Option A**) or extend once with a new dated decision |
| Collapse target (A) | Sole authority = `user_roles` + system `roles`; demote or drop `users.role` |

## Why B for this sprint

Most filters, dashboards, and role-hierarchy checks still read `users.role`. Collapsing off that column in one sprint is higher risk than closing dual-write gaps.

## Dual-write contract (until end date)

1. **Write path:** every change to a user’s system role must update `users.role` **and** call `RbacCatalogService.sync_user_system_role`.
2. **Read path (auth):** `apply_effective_role` on login / `get_current_user` / token refresh — prefer system role from `user_roles`, else fall back to `users.role`.
3. **Seeds / bootstrap:** must sync after upserting users.
4. **Invariant tests:** drift (`users.role` vs highest system `user_roles`) fails CI / repair job.

## Covered write paths

- Signup / admin create / admin role update (`UserService`)
- Invite accept (`InvitationService`)
- CI seed (`scripts/ci_bootstrap_db.py`)

## Related

- [DATABASE_SCHEMA_REVIEW.md](./DATABASE_SCHEMA_REVIEW.md) §4.1
- `services/permissions/rbac_catalog_service.py`
