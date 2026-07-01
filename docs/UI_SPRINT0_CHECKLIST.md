# Sprint 0 checklist (one week)

**Goal:** M1 entry criteria. No feature pages (dashboard, admin) yet.  
**Program type:** Joint full-stack — backend P0 is not optional parallel work.

## Exit criteria (all required)

- [ ] ADR-001, ADR-002, this checklist, PRD, P0 backlog committed under `docs/`
- [ ] `frontend/` scaffold builds (`pnpm build`)
- [ ] Cookie login + refresh passes **curl checklist** on local or staging API (not MSW-only)
- [ ] Global API errors include `error_code` (at minimum: 401, 403, 423, 429)
- [ ] Playwright E2E **#6** (unauthorized) and **#7** (bootstrap refresh) green
- [ ] OpenAPI codegen script exists; CI fails on drift (can be warning-only in Sprint 0)

---

## Day 1 — Contracts

- [ ] Eng lead signs ADR-001 + ADR-002
- [ ] Product confirms: **no signup page** (see `UI_PRD-MVP.md`)
- [ ] Backend: OpenAPI PR opened (cookie auth, error shape, 2FA-at-login design — even if implementation is week 2)
- [ ] Verify `GET /api/v1/profile` returns `role` + `organization_id` locally

**Owners:** Eng lead (ADRs), Backend (OpenAPI PR), Product (signup)

---

## Day 2 — Backend P0 (pair with FE)

- [ ] `Set-Cookie` / `Clear-Cookie` on login, refresh, logout (`routes/login.py`)
- [ ] CORS `allow_credentials=True` + explicit origins (`utils/security_middleware.py`, `config/settings.py`)
- [ ] Normalize `error_code` in `setup_error_handlers` (`utils/security_middleware.py`)
- [ ] curl checklist passes (see `ADR-002-deployment-topology.md`)

**Files:** `routes/login.py`, `services/auth/*`, `utils/security_middleware.py`, `config/settings.py`, `.env.codespaces.example`

---

## Day 3 — Frontend scaffold

- [ ] `pnpm create vite` → React + TypeScript (pin React version after `shadcn init`)
- [ ] shadcn/ui + Tailwind
- [ ] TanStack Query + devtools
- [ ] `src/lib/env.ts` — Zod validate `VITE_API_BASE_URL`
- [ ] `src/lib/apiClient.ts` — `credentials: 'include'`, single-flight refresh, proactive refresh timer, 401 handler
- [ ] `src/lib/auth/` — AuthProvider, AuthBootstrapShell, BroadcastChannel logout
- [ ] Orval or `openapi-typescript` script

---

## Day 4 — Auth shell

- [ ] MSW handlers mirror **cookie** behavior (not JSON-only refresh)
- [ ] Routes: `/login`, `/unauthorized`, `/maintenance`, 404, `/` redirect stub
- [ ] Sentry init (`VITE_SENTRY_DSN`)
- [ ] Swap one integration test from MSW → real local API before day end

---

## Day 5 — CI

- [ ] GitHub Action: backend pytest + OpenAPI export
- [ ] GitHub Action: frontend lint, vitest, codegen diff
- [ ] Playwright: tests 6, 7 in CI (MSW for PRs)
- [ ] Document staging nightly job (real API) — can enable post-Sprint 0

---

## E2E tests — Sprint 0 scope

| # | Test | Target |
|---|------|--------|
| 6 | User opens `/admin` → unauthorized | MSW + staging |
| 7 | Reload with valid cookie → no login form | **Real API required for exit** |

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
