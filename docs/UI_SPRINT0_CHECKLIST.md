# Sprint 0 checklist (one week)

**Goal:** M1 entry criteria. No feature pages (dashboard, admin) yet.  
**Program type:** Joint full-stack — backend P0 is not optional parallel work.

## Exit criteria (all required)

- [x] ADR-001, ADR-002, this checklist, PRD, P0 backlog committed under `docs/`
- [x] `frontend/` scaffold builds (`npm run build`)
- [x] Cookie login + refresh passes **curl checklist** on local or staging API (CI TestClient + `scripts/staging_post_deploy_smoke.sh` for deployed URLs)
- [x] Global API errors include `error_code` (401, 403, 423, 429 via `utils/api_errors.py`)
- [x] Playwright E2E **#6** (unauthorized) and **#7** (bootstrap refresh) green in PR CI (MSW)
- [x] OpenAPI codegen script exists; CI warning-only drift check in Sprint 0 (`npm run openapi:check`)

**Staging sign-off (post-deploy, manual until env exists):**

- [ ] Run `bash scripts/staging_post_deploy_smoke.sh` against `api/app.staging.*`
- [ ] Run GitHub workflow **Staging E2E** (Playwright #6/#7 on real API)

---

## Day 1 — Contracts

- [ ] Eng lead signs ADR-001 + ADR-002
- [ ] Product confirms: **no signup page** (see `UI_PRD-MVP.md`)
- [ ] Backend: OpenAPI PR opened (cookie auth, error shape, 2FA-at-login design — even if implementation is week 2)
- [ ] Verify `GET /api/v1/profile` returns `role` + `organization_id` locally

**Owners:** Eng lead (ADRs), Backend (OpenAPI PR), Product (signup)

---

## Day 2 — Backend P0 (pair with FE)

- [x] `Set-Cookie` / `Clear-Cookie` on login, refresh, logout (`routes/auth.py`)
- [x] CORS `allow_credentials=True` + explicit origins (`utils/security_middleware.py`, `config/settings.py`)
- [x] Normalize `error_code` in `setup_error_handlers` (`utils/security_middleware.py`)
- [x] curl checklist passes (see `ADR-002-deployment-topology.md`, `scripts/curl_auth_checklist.py`)

**Files:** `routes/auth.py`, `services/auth/*`, `utils/security_middleware.py`, `config/settings.py`, `.env.codespaces.example`

---

## Day 3 — Frontend scaffold

- [x] Vite → React + TypeScript
- [x] TanStack Query + devtools
- [x] `src/lib/env.ts` — Zod validate `VITE_API_BASE_URL`
- [x] `src/lib/apiClient.ts` — `credentials: 'include'`, single-flight refresh, proactive refresh timer, 401 handler
- [x] `src/lib/auth/` — AuthProvider, AuthBootstrapShell, BroadcastChannel logout
- [x] OpenAPI check script (`frontend/scripts/check-openapi.mjs`)

---

## Day 4 — Auth shell

- [x] MSW handlers mirror **cookie** behavior (Playwright `e2e/apiMocks.ts`)
- [x] Routes: `/login`, `/unauthorized`, `/maintenance`, 404, `/` redirect stub
- [ ] Sentry init (`VITE_SENTRY_DSN`) — deferred to M1
- [ ] Swap one integration test from MSW → real local API before day end

---

## Day 5 — CI

- [x] GitHub Action: backend pytest + smoke + ADR-002 checklist
- [x] GitHub Action: frontend lint, build, codegen diff (warning-only)
- [x] Playwright: tests 6, 7 in CI (MSW for PRs)
- [x] Staging nightly job documented — `.github/workflows/staging-e2e.yml` (manual dispatch)

---

## E2E tests — Sprint 0 scope

| # | Test | Target |
|---|------|--------|
| 6 | User opens `/admin` → unauthorized | MSW (CI) + `e2e/sprint0-auth-real-api.spec.ts` (staging) |
| 7 | Reload with valid cookie → no login form | MSW (CI) + real API via **Staging E2E** workflow |

---

## Red lines (do not start)

- Dashboards or admin users table
- `/login/2fa` page
- `/admin/users/:id`
- Refresh token in `localStorage`
- M1 "done" with MSW-only auth

---

## References

- `docs/BACKEND_P0_UI_BLOCKERS.md`
- `docs/ADR-001-frontend-auth.md`
- `scripts/staging_post_deploy_smoke.sh`
- `scripts/curl_auth_checklist.py`
