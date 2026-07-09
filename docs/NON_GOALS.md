# Project non-goals

Explicit boundaries for **fastapi-user-management**. Use this to avoid scope creep when hardening toward staging (A−) or production (A+).

## What this project is

- A **user management and RBAC demo** with a full React UI
- A **credible staging** target for Codespaces / local MySQL development
- An learning and portfolio codebase with real auth, org isolation, and compliance **read** surfaces

## What this project is not

| Non-goal | Rationale |
|----------|-----------|
| **Full IAM / Okta competitor** | JWT role hierarchy covers the UI; building a universal identity plane is out of scope |
| **Full ABAC / permission engine** | `user_permissions` table exists for showcase unless grant/revoke + enforcement is explicitly sponsored |
| **Single merged session table** | `refresh_tokens` (auth) and `user_sessions` (analytics) stay linked, not merged |
| **DB ENUM for roles** | Roles enforced in app code (`role_scope`, Pydantic) until the role model is frozen |
| **Public API productization** | No breaking path renames or global response envelopes without external integrators |
| **Enterprise-only features first** | Passkeys, IP allowlists, SAML/OIDC federation — post–A+ sales-driven items |

## API keys and permissions — honest scope

| Feature | Current stance | A− target | A+ target |
|---------|----------------|-----------|-----------|
| API keys | Issue/revoke via JWT; auth on `/integration/whoami` | Document as preview | Enforce read scopes on 3–5 routes **or** strip permissions UI |
| `user_permissions` | Read-only APIs + UI | **Descope** in UI/docs **or** minimal grant/revoke | Route-level enforcement on 2–3 actions only |
| JWT `role` | Enforced everywhere that matters | Keep as primary authorization | Keep |

**Rule:** Do not add UI or docs that imply enforcement that does not exist in code.

## Release gates (reference)

| Gate | Meaning |
|------|---------|
| **A− (staging)** | CI green, IDOR smoke tests, migrations work, dashboard matrix documented, no new RBAC inconsistencies |
| **A+ (production)** | Metrics, runbooks, retention jobs, admin audit writes, Redis policy by endpoint class, backup drill |

## When to revisit non-goals

Re-open a non-goal only with a **named consumer**:

- Paying customer requiring SAML → federation spike
- M2M partner → API key scope enforcement on agreed routes
- Compliance auditor → admin audit trail + minimal permission grants

Until then, prefer **descope + honesty** over **half-built enterprise features**.
