# Client release / production readiness — gap analysis

**Date:** 2026-07-16  
**Branch baseline:** `feature/production-hardening-schema` (Alembic head `20260716_soft_unique`)  
**Purpose:** Single inventory of everything still **stopping**, **needing fix**, or **needing development** before a safe **production cutover** or **client release**.

This document mixes two bars deliberately. Do not confuse them:

| Bar | Definition | Current score |
|-----|------------|---------------|
| **Bar (1) — Controlled v1 cutover** | Single home org per user, hashed tokens, RBAC catalog, soft-delete, retention levers, short access TTL + refresh revoke | **Launch-capable only after Gate A–C below** — not “fully done” |
| **Bar (2) — Enterprise IAM completeness** | SSO, multi-org memberships, instant JWT denylist, webhooks, partitions, feature entitlements, etc. | **Not ready — roadmap** |

**Honest product verdict:** The **backend engineering checklist** for v1 is largely complete (open code items are deferred ⏸ or accepted risk). The **product is not client-release ready** until ops cutover, role-authority ownership, seed/secret hygiene, frontend/E2E sign-off, and an explicit **out-of-scope** agreement with the client on Bar (2).

---

## Related living docs

| Doc | Role |
|-----|------|
| [BACKEND_PRODUCTION_READINESS.md](./BACKEND_PRODUCTION_READINESS.md) | Full remediations + §15 env checklist |
| [DATABASE_SCHEMA_REVIEW.md](./DATABASE_SCHEMA_REVIEW.md) | Schema depth, Phase 2 tables |
| [ROLE_AUTHORITY_CUTOVER.md](./ROLE_AUTHORITY_CUTOVER.md) | Option B dual-write + **2026-08-14** end date |
| [ACCESS_TOKEN_REVOCATION.md](./ACCESS_TOKEN_REVOCATION.md) | Deferred JWT `jti` design |
| [BACKUP_RESTORE.md](./BACKUP_RESTORE.md) | Backup/RPO expectations |
| [FRONTEND.md](./FRONTEND.md) | UI surface & test notes |
| [schema/fastapi_users_schema_latest.sql](./schema/fastapi_users_schema_latest.sql) | Live DDL dump |

---

## 1. Executive summary — what blocks release

### Must clear before any production / client go-live (Gate A)

These are **release blockers** even if application code looks “done.”

| # | Blocker | Why it stops release | Owner / action |
|---|---------|----------------------|----------------|
| A1 | **§15.1 production env config not signed off** | Wrong JWT/cookies/CORS/signup/debug flags = credential leak or lockout | Ops assigns secrets; verify each row in §3 |
| A2 | **§15.2 DB migrate + backup not signed off** | Wrong schema revision or no restore path = data loss | `alembic upgrade head`; scheduled MySQL backup |
| A3 | **Role authority owner unnamed** | Dual-write without owner → privilege bugs return | Name owner in [ROLE_AUTHORITY_CUTOVER.md](./ROLE_AUTHORITY_CUTOVER.md); collapse by **2026-08-14** or re-date once |
| A4 | **CI/default seed credentials still usable in prod** | Public admin/user passwords are a known attack | Rotate/remove `testadmin` / seed users; 15.2.19 |
| A5 | **SMTP / email paths unverified in target env** | Password reset, invites, verification break for real users | Configure `EMAIL__*`; send test mail |
| A6 | **Client scope not written** | Client expects SSO / multi-org / instant revoke → surprise “incomplete” | Sign SOW: Bar (1) in; Bar (2) out or phased |

### Should clear in the same release train (Gate B)

Cheap or already partially done; leaving them open causes **real outages / compliance noise**.

| # | Item | Status | Residual risk if skipped |
|---|------|--------|---------------------------|
| B1 | Soft-delete–safe unique email/username | ✅ `20260716_soft_unique` — active-only functional unique; soft-delete keeps identifiers | — |
| B2 | `api_keys.permissions` still JSON (not catalog junction) | **Accepted transitional** | Typos / drift vs `permissions` catalog |
| B3 | Retention / purge **scheduled** in prod (not only manual `/maintenance/cleanup`) | **Ops** | Unbounded `audit_logs` / `login_attempts` growth |
| B4 | Frontend production build + cookie domain / HTTPS / CSRF header verified | **Ops + FE** | Login/refresh broken behind real TLS |
| B5 | Staging E2E / IDOR / auth smoke against production-like stack | **QA** | “Works locally” regressions |
| B6 | Log shipping + on-call runbook linked | **Ops** | Blind incidents after launch |
| B7 | Email length alignment (`users.email` 100 vs invite/verify 255) | ✅ `users.email` → `VARCHAR(255)` | — |

### Explicitly deferred — do **not** call “unsafe to ship v1,” but **disclose** (Gate C / Bar 2)

| # | Item | Client impact if they assume it’s included |
|---|------|--------------------------------------------|
| C1 | JWT access-token `jti` denylist | Compromised access token valid until short TTL (~5 min) |
| C2 | Repository persistence layer | Maintainability only |
| C3 | SSO / IdP (`idp_connections`, `organization_domains`) | No SAML/OIDC |
| C4 | Multi-org memberships | User locked to one `organization_id` |
| C5 | Webhooks / outbox / job_runs | No reliable external event bus |
| C6 | Feature flags / entitlements | No plan gating |
| C7 | Trusted devices / step-up 2FA devices | Only full TOTP/backup flow |
| C8 | Audit/login **partitioning** + BIGINT PKs | Scale later; volume may exhaust INT |
| C9 | Postgres primary / Neon timezone cutover | MySQL is primary |
| C10 | Dedicated `account_lockouts` table | Lockout uses `users.locked_until` + `login_attempts` |

---

## 2. What is already solid (do not re-litigate as “missing”)

Completed for Bar (1) engineering (see readiness + schema docs for ✅ rows):

- Auth lifecycle: 2FA gate, encrypted 2FA secrets, refresh rotation + reuse revoke, CSRF header on cookie refresh/logout, status checks, max sessions
- Password reset / email verify / invites (DB hashed tokens)
- RBAC catalog tables + dual-write sync on main product paths; drift helpers/tests
- Tenant: `organization_id NOT NULL`, permission org id, cross-org guards (app)
- Schema hardening (`20260714_v1_harden`): NOT NULL flags, `user_permissions.permission_id` FK + org in unique, invite pending uniqueness + role ENUM, consent `ON DELETE SET NULL`
- Soft-delete columns on users/orgs; retention policy table + cleanup endpoints
- Container/non-root image docs, backup script/docs, production config validation
- Frontend: login/signup, dashboards, compliance, invite accept / email verify pages (verify end-to-end in target env)

---

## 3. Gate A detail — production environment checklist (§15)

Copy into the release ticket. Every row must be checked on the **client target environment** (not only local MySQL).

### 3.1 Application & config

| # | Check | Env / action | Done? |
|---|-------|--------------|-------|
| 15.1.1 | JWT secret ≥32 chars, random, from secrets manager | `JWT__SECRET_KEY` | ⬜ |
| 15.1.2 | MySQL URL from secrets (no hardcoded defaults) | `DB__URL` / `DATABASE_URL` | ⬜ |
| 15.1.3 | Redis up; persistence strategy agreed | `REDIS__*` | ⬜ |
| 15.1.4 | Production mode | `APP__ENVIRONMENT=production` | ⬜ |
| 15.1.5 | Debug auth off | `SECURITY__ALLOW_DEBUG_AUTH=false` | ⬜ |
| 15.1.6 | Public signup off (unless contracted) | `SECURITY__ALLOW_PUBLIC_SIGNUP=false` | ⬜ |
| 15.1.7 | Secure cookies | `AUTH_COOKIE__SECURE=true` | ⬜ |
| 15.1.8 | No refresh in JSON body | `AUTH_COOKIE__LEGACY_JSON_REFRESH=false` | ⬜ |
| 15.1.9 | HTTPS redirect | `SECURITY__ENABLE_HTTPS_REDIRECT=true` | ⬜ |
| 15.1.10 | Explicit CORS (no `*`) | `SECURITY__CORS_ORIGINS` | ⬜ |
| 15.1.11 | SMTP works; test email | `EMAIL__*` | ⬜ |
| 15.1.12 | Links point at public UI | `EMAIL__BASE_URL` | ⬜ |
| 15.1.13 | Rate limit fail-closed | `RATE_LIMIT__FAIL_OPEN=false` | ⬜ |
| 15.1.14 | OpenAPI disabled publicly | auto in production | ⬜ |
| 15.1.15 | Logs to central aggregator | stdout JSON → stack | ⬜ |
| 15.1.16 | K8s probes wired | `/health/live`, readiness | ⬜ |
| 15.1.17 | Incident runbook linked | [OPS_RUNBOOKS.md](./OPS_RUNBOOKS.md) | ⬜ |

### 3.2 Database & data ops

| # | Check | Done? |
|---|-------|-------|
| 15.2.1 | `alembic upgrade head` on deploy (`20260716_soft_unique` or newer) | ⬜ |
| 15.2.2–15.2.16 | Schema integrity items live (ENUMs, FKs, soft-delete, reset/verify/invite tables, RBAC) — **confirm on prod DB**, not only docs | ⬜ |
| 15.2.17 | Token/session/password-history **purge scheduled** | ⬜ |
| 15.2.18 | Downgrade smoke known (CI) | ✅ in repo; ⬜ confirm in CD |
| 15.2.19 | Seed/admin passwords rotated / removed | ⬜ |
| 15.2.20 | MySQL backup job + restore drill | ⬜ |

---

## 4. Gate A detail — role authority (privilege correctness)

**Current decision:** Option **B** (ironclad dual-write) through **2026-08-14**.  
See [ROLE_AUTHORITY_CUTOVER.md](./ROLE_AUTHORITY_CUTOVER.md).

| Gap | Status | Required for release |
|-----|--------|----------------------|
| Named owner on cutover doc | ⬜ Open | **Yes** |
| Calendar end date for B | ✅ 2026-08-14 | Keep or formally extend |
| Sync on signup / admin / invite / CI seed | ✅ | Keep |
| Hydrate on login + refresh | ✅ | Keep |
| Drift find/repair + tests | ✅ | Keep in CI |
| Collapse to Option A (`user_roles` sole authority) | ⬜ After 2026-08-14 | Planned — not day-1 if B contract holds |
| Listing/dashboard SQL still filters on `users.role` | Known | OK under B; must change for A |

**Risk if ignored:** Auth/admin UI updates one store, permissions use the other → **privilege bugs**.

---

## 5. Schema / data gaps — remaining after hardening sprint

### 5.1 Fixed in `20260714_v1_harden` (verify on client DB)

| Item | Fix |
|------|-----|
| Nullable boolean / flag columns | `NOT NULL DEFAULT …` |
| `user_permissions.permission_name` free text without FK | `permission_id` FK → `permissions` |
| Unique grant ignored tenant | Unique includes `organization_id` |
| Invite role free varchar | ENUM aligned with system roles |
| Multiple pending invites same org+email | Functional unique index |
| Consent CASCADE erased evidence | `ON DELETE SET NULL` + nullable `user_id`; `policy_version` column |

### 5.2 Still open or partial (fix or accept with tests)

| Priority | Issue | Why it matters | Recommended action |
|----------|-------|----------------|--------------------|
| **P0 residual** | Soft-delete vs global UNIQUE email/username | — | ✅ Fixed: active-only functional unique (`uq_users_*_active`) |
| **P1** | `users.email` VARCHAR(100) vs invite/verify 255 | — | ✅ Aligned to 255 |
| **P1** | `api_keys.permissions` JSON | Second ACL model | Junction `api_key_permissions` or keep strict catalog validation only |
| **P1** | `roles.org_scope_key` mirror of org | Desync risk | Prefer generated uniqueness pattern |
| **P2** | INT PKs on `audit_logs` / `login_attempts` / `security_incidents` | Exhaustion at scale | Migrate to BIGINT before high volume |
| **P2** | Remaining redundant `ix_*_id` on some tables | Write amplification | Drop after EXPLAIN review |
| **P2** | `permissions`: unique + non-unique index on name | Hygiene | Drop redundant non-unique |
| **P2** | `security_incidents.severity` free varchar | Inconsistent reporting | ENUM or lookup |
| **P2** | Mixed lifecycle: soft-delete vs `is_active` | Ops confusion | Document one policy per entity |
| **P2** | Few/no CHECK constraints | Bad retention/expiry rows | Add CHECKs where MySQL version allows |
| **P2** | Audit index density + growth | Cost / slow queries | Archive/partition plan before load tests |
| **P2** | Org hard CASCADE to children | Fine only if org soft-delete always | Ops policy: never hard-delete active orgs |

### 5.3 Tables / product surfaces missing for Bar (2) — develop only if sold

| Missing object | Purpose | Develop if client needs… |
|----------------|---------|--------------------------|
| `organization_memberships` | Multi-org users + per-org role | Multi-tenant SaaS seats |
| `external_identities` | OIDC/SAML subjects | SSO |
| `trusted_devices` / `device_challenges` | Remembered 2FA / step-up | Enterprise device trust |
| `jwt_denylist` / access revocation ledger | Instant access revoke | Compliance beyond short TTL |
| `api_key_permissions` | Normalize key ACLs | Strong API-key governance |
| `policy_documents` (+ richer consent) | Versioned ToS | Formal privacy program |
| `webhook_endpoints` / `webhook_deliveries` | Tenant integrations | Event subscription product |
| `outbox` / `job_runs` | Reliable email & purge jobs | High reliability async |
| `idempotency_keys` | Safe POST retries | Billing / admin APIs |
| `ip_allowlists` | Network control | Enterprise security package |
| `feature_entitlements` | Plan gating | Commercial packaging |
| Optional: `notification_preferences`, DSAR/`export_requests`, `data_subject_requests` | Privacy/ops UX | Regulated deployments |

---

## 6. Application / architecture gaps (deferred or residual)

| ID | Item | Status | Block client release? |
|----|------|--------|------------------------|
| 1.12 / 13.3.6 | Access JWT no `jti` / Redis denylist | ⏸ Phase 2 | **No** for Bar (1) if TTL short & disclosed; **Yes** if contract requires instant revoke |
| 5.4 | No repository layer | ⏸ | No (maintainability) |
| Dual-write residual paths | Ad-hoc scripts must call sync | Mitigated for CI; watch custom scripts | Yes if operators create users via SQL |
| List filters on `users.role` | By design under Option B | No under B | Blocks Option A |
| Granular permissions | Catalog + role/group/direct grants | Done with gaps on API keys JSON | Soft |
| Email enable gate | `EMAIL__ENABLE_EMAILS` | Must be on in prod for UX | **Yes** for invite/reset flows |

---

## 7. Frontend / UX / client-facing product gaps

| Area | Gap | Release impact |
|------|-----|----------------|
| Production UI host | Must use HTTPS, correct cookie `Secure`/`SameSite`/domain | Hard blocker if misconfigured |
| CSRF | SPA must send `X-Requested-With: XMLHttpRequest` on refresh/logout | Already in `apiClient` — verify deployed build |
| 2FA UX | Challenge flow after login | Must be tested on staging |
| Invite / verify email deep links | `EMAIL__BASE_URL` + FE routes (`AcceptInvite`, `VerifyEmail`) | Broken onboarding if wrong |
| Compliance / admin surfaces | Dense; may need client UAT | Soft — UAT sign-off |
| E2E coverage | Playwright specs exist; real-API / staging must pass | Soft hardener |
| Accessibility / design polish | Not production-hardening security | Soft / contractual |
| Multi-language / branding | Not built as product packaging | Soft |

---

## 8. Security / compliance disclosures for the client

Put these in the release notes / security appendix unless remediated:

1. **Access tokens are not instantly revocable** until expiry (~5 minutes) without Phase 2 denylist.  
2. **Refresh revoke + logout-all** are the session kill switches.  
3. **Single organization per user** — not multi-org SaaS.  
4. **No SSO** out of the box.  
5. **Consent rows** are retained on hard-delete (`user_id` null); soft-delete is preferred.  
6. **Rate limiting depends on Redis** with fail-closed in production.  
7. **2FA secrets** are encrypted at rest (Fernet); key management is an ops responsibility (`FIELD_ENCRYPTION` / related secret).  
8. **Role model is dual-write (Option B)** until the published collapse date.

---

## 9. Recommended client-release plan

### Phase 0 — Decide scope (1 meeting)

- [ ] Client signs **Bar (1)** in-scope / **Bar (2)** out or phased  
- [ ] Name role-authority owner; confirm **2026-08-14** collapse or extension  
- [ ] Decide invite-only vs public signup

### Phase 1 — Cutover gates (release blocking)

- [ ] Complete §3 (§15) env + DB checklist on staging  
- [ ] Rotate seeds; verify SMTP; run backup restore drill  
- [ ] Staging FE + API smoke (login, 2FA, refresh, invite, reset, IDOR)  
- [ ] Deploy: migrate to Alembic head, Helm/Docker hardening applied  
- [ ] Production §15 repeat + monitor 48h

### Phase 2 — Post-launch hardening (scheduled)

- [ ] Soft-delete functional uniqueness (or keep rewrite with permanent tests)  
- [ ] Email VARCHAR alignment  
- [ ] API key permission junction (if keys are sold)  
- [ ] Option A role collapse  
- [ ] BIGINT / partition plan before load growth  
- [ ] Pull forward denylist / SSO / memberships only if contracted

---

## 10. Status tally (how “done” vs “not done”)

| Bucket | Approx. state | Meaning for release |
|--------|---------------|---------------------|
| App remediation checklist (P0–P3 code) | ~98% ✅; 3 ⏸ | Not the main release risk |
| Schema review checklist | ~92% ✅; 8 ⏸ | Phase 2 tables are product scope |
| Hardening sprint (flags, perm FK, invites, consent) | ✅ in branch | Re-verify on client DB |
| **§15 ops cutover** | **Mostly ⬜** | **Primary release blocker** |
| Role cutover ownership | **Owner ⬜** | **Primary correctness blocker** |
| Frontend/E2E on prod-like env | Verify ⬜ | Product completeness |
| Enterprise tables / SSO / multi-org | ⏸ | Contract scope, not silent gaps |

---

## 11. One-line sign-off criteria

**Ready to release to a client under Bar (1)** when:

1. Gates **A1–A6** are green,  
2. Staging UAT for core auth/admin journeys passes,  
3. Client has written acknowledgement of **Gate C / Bar (2)** exclusions,

…and **not before**.

**Ready as enterprise IAM (Bar 2)** only after the Phase 2 table in §5.3 and denylist/SSO/memberships land per contract.

---

*Generated from production readiness, schema review, external schema verdict calibration, and the Option B cutover decision. Update this file when Gate A rows flip or the dual-write end date changes.*
