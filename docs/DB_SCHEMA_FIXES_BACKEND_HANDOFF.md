# Database schema & lifecycle fixes — backend handoff

**Audience:** Backend developers  
**Bar:** **A — controlled v1 cutover** (not “enterprise-complete schema before any traffic”)  
**Source:** Live MySQL `fastapi_users` review + codebase check (app already covers parts of C3/H6)  

This doc is a **prioritized work list**, not a claim that all 16 original DBA items block launch.

---

## How to read this

| Bucket | Meaning |
|--------|---------|
| **Must before prod traffic** | Real security / integrity gaps for v1 |
| **Cheap / defense-in-depth** | Small schema or process wins; do when touching the area |
| **Park (post-v1 / Gate C)** | Correct eventually; low near-term ROI or already partially done |
| **Verify only** | Do not rebuild — confirm existing implementation |

Original DBA IDs (C1–C4, H1–H6, M1–M6) are kept so older notes still map.

---

## Must before prod traffic

### 1. H5 — Soft-delete credential cleanup *(backend — highest)*

| | |
|--|--|
| **Where** | `UserService` soft-delete · `refresh_tokens` · `user_sessions` · `api_keys` · memberships that grant access |
| **Why it matters more than C2/C3 schema** | Soft-delete ≠ `ON DELETE CASCADE`. Soft-delete must kill all usable credentials in one transaction — not mark deleted then best-effort revoke. |
| **Change type** | **Backend** (primary) — no schema required |
| **Work** | In **one transaction** with soft-delete: revoke all refresh tokens, end/deactivate sessions, deactivate API keys (and group memberships if cheap). Do not leave revoke after commit as fire-and-forget. **Refresh path must reject deleted users even if a refresh row was left active.** |
| **Test** | Soft-deleted user cannot login, cannot refresh, cannot use API keys. |
| **Done when** | Soft-delete + revoke are atomic; integration test covers login/refresh/API key after delete; refresh rejects `deleted_at` users. |
| **Status** | ✅ Implemented (`UserService.soft_delete_user` + refresh/API-key guards + integration + HTTP e2e `tests/e2e/test_soft_delete_credentials_e2e.py`) |

---

### 2. C1 — Dual role authority *(process, not big-bang schema)*

| | |
|--|--|
| **Where** | `users.role` ENUM · `user_roles` → `roles` |
| **Why** | Drift risk is real. Product already chose **Option B dual-write** with an end date — do not panic-drop the column this week. |
| **Change type** | **Backend process** now · schema drop **later** |
| **Work** | Name an owner for cutover. Add **invariant tests** (active users: `users.role` matches catalog `user_roles`). Stop **new** authz branches on `users.role` where the RBAC catalog should win. Keep dual-write until cutover date. |
| **Do not** | Same-week schema drop of `users.role`. |
| **Done when** | Invariant test in CI; new authz code paths prefer catalog; drop column scheduled post-cutover. |

---

### 3. C4 — Consent org FK `CASCADE` *(schema or ops policy — pick one)*

| | |
|--|--|
| **Where** | `consent_records.organization_id` → `organizations.id` **ON DELETE CASCADE** |
| **Why** | Hard-deleting an org wipes GDPR evidence. Urgency is high **if** hard-delete is possible; lower if ops policy is soft-delete only forever. |
| **Change type** | **Schema** *or* **ops runbook** (prefer both eventually; pick one for v1) |
| **Option A (cleaner)** | Alembic: change FK to `ON DELETE SET NULL` (align with `user_id` SET NULL). |
| **Option B (policy)** | Hard-ban org hard-delete in runbooks/scripts; only soft-delete live orgs. |
| **Done when** | Either FK cannot CASCADE-wipe consents, or hard-delete is impossible in ops. |

---

## Cheap / defense-in-depth

### 4. C3 — Invite `super_admin` ENUM trim *(schema; app mostly done)*

| | |
|--|--|
| **Where** | `user_invitations.role` ENUM includes `super_admin` |
| **Status** | **`InvitationService` already rejects `super_admin`.** Schema lockdown = defense-in-depth, not a missing product fix. |
| **Work** | After data clean: alter invite ENUM to `('user','admin','organization_admin')` only. Longer term: prefer `role_id` FK. |
| **Done when** | DB cannot store `super_admin` on invitations. |

---

## Verify only (do not rebuild)

### H6 — Secrets at rest

| | |
|--|--|
| **Status** | **Mostly done.** TOTP via field encryption (`TwoFactorSecretService` / Fernet envelope); backup codes hashed. |
| **Work** | Verify a DB dump / query does not show plaintext TOTP or raw backup codes. Fix only if gaps found. |
| **Do not** | Treat as an open rebuild item in the handoff. |

### H2 — UTC / `DATETIME(3)`

| | |
|--|--|
| **Status** | Convention largely in place (`utc_now()` used widely). |
| **Work** | Keep UTC writes. `DATETIME(3)` is optional polish when already migrating those columns. |

---

## Park — post-v1 / scale / hygiene

Do these when you have scale evidence, RBAC cutover, or a dedicated hardening sprint — **not** as launch blockers.

| ID | Item | Why parked |
|----|------|------------|
| **C2** | Drop `user_permissions.permission_name` | Real smell / rename hazard; fix when collapsing RBAC. Don’t block traffic if writes stay in sync. |
| **H1** | `INT` → `BIGINT` on audit/login/sessions/refresh | Correct eventually; painful migration; not needed unless you expect huge row counts soon. |
| **H3** | `updated_at` auto-maintain | Nice for support/cache; not authz-critical. |
| **H4** | `roles.org_scope_key` CHECK | Ugly hack; low if you mostly use system roles. Add CHECK when custom org roles matter. |
| **M1** | Drop redundant indexes | Hygiene; confirm with `EXPLAIN` first. |
| **M2** | Group membership unique vs `is_active` | Product decision; not launch-blocking. |
| **M3** | `security_incidents.severity` ENUM | Allow-list in app + ENUM later. |
| **M4** | Full CHECK sweep | Pydantic already validates many inputs; DB CHECKs are defense-in-depth. |
| **M5** | Audit partition + retention job | Gate C / scale; wire retention job when audit volume hurts. |
| **M6** | Email lowercase normalize | Collation already CI for uniqueness; normalize on write when convenient. |

---

## v1 execution order

1. **H5** — atomic soft-delete + revoke (sessions, refresh, API keys) + tests  
2. **C1** — dual-write invariant test + stop new `users.role` authz branches  
3. **C4** — consent FK `SET NULL` **or** hard-ban org hard-delete  
4. **C3** — cheap invite ENUM trim (optional same PR as related invite work)  
5. **H6** — dump verification only  
6. Everything else → backlog / Gate C  

---

## Quick reference

| ID | Title | v1 action | Schema | Backend |
|----|-------|-----------|:------:|:-------:|
| H5 | Soft-delete cleanup | **Done** | — | ✅ Atomic + guards + test |
| C1 | Dual role authority | **Must (process)** | Drop later | Invariants + authz paths |
| C4 | Consent CASCADE | **Must (pick one)** | FK preferred | Runbook if no FK yet |
| C3 | Invite `super_admin` | Cheap | ENUM trim | Already rejects |
| H6 | Secrets at rest | Verify | — | Already encrypt/hash |
| H2 | UTC / DATETIME(3) | Keep convention | Optional | Already `utc_now()` |
| C2 | `permission_name` | Park | After RBAC cutover | With cutover |
| H1 | BIGINT PKs | Park | Later | Models later |
| H3–H4, M1–M6 | Hardening | Park | As needed | As needed |

---

## Framing (for PMs / reviewers)

- **Hierarchy / product shape is fine.** This list is **data integrity, lifecycle, and ops maturity** — not “user management was built wrong.”  
- The original DBA-max ordering overstated launch blockers. This rewrite matches a **product-realistic v1 bar**.  
- Gap analysis / release gates already deferred several items (BIGINT, partition, etc.); keep them there.

---

## Notes for implementers

1. Prefer **Alembic** for any schema change (C3, C4).  
2. Pair **H5** and **C1** with integration tests in the same PR when possible.  
3. After schema changes: `python scripts/export_schema_sql.py` → refresh `docs/schema/fastapi_users_schema_latest.sql`.  
4. Do not commit `.env` or secrets.

---

## Optional later tables (not v1)

`oauth_identities`, `mfa_devices` / `webauthn_credentials`, `outbox_events`, `webhook_*`, `organization_domains`, `idempotency_keys`, `data_deletion_requests` — product roadmap, not this cutover.
