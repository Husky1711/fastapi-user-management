# FastAPI User Management — Frontend Reference

Complete frontend documentation: purpose, folder structure, code flow, routing, role hierarchy, pages, and API integration.

**Stack:** React 19 · TypeScript · Vite · React Router · TanStack Query · Axios

**Default dev URL:** `http://127.0.0.1:5173`  
**API proxy target:** `http://localhost:9000` (via Vite `/api` proxy)

---

## Table of contents

1. [System purpose](#1-system-purpose)
2. [Folder structure](#2-folder-structure)
3. [Architecture layers](#3-architecture-layers)
4. [Application code flow](#4-application-code-flow)
5. [Authentication flow](#5-authentication-flow)
6. [Role hierarchy & routing](#6-role-hierarchy--routing)
7. [Pages & user journeys](#7-pages--user-journeys)
8. [State management](#8-state-management)
9. [API integration catalog](#9-api-integration-catalog)
10. [Configuration & local dev](#10-configuration--local-dev)
11. [Testing & E2E](#11-testing--e2e)

---

## 1. System purpose

Single-page application (SPA) for the FastAPI User Management backend. It provides:

| Area | What the UI does |
|------|------------------|
| **Auth** | Login, signup, password reset, session conflict handling |
| **Self-service** | Profile, password change, 2FA, session management |
| **Dashboards** | Role-specific home pages with stats |
| **User admin** | List, create, edit users (staff roles) |
| **Org admin** | Organization-wide dashboard |
| **Super admin** | System dashboard + organization CRUD |
| **Compliance** | Audit logs, permissions, groups, API keys, password policy |

All authenticated API calls use a shared `apiClient` with cookie-based refresh and in-memory Bearer access tokens.

---

## 2. Folder structure

```
frontend/
├── index.html
├── package.json
├── vite.config.ts              # Dev server, /api proxy, @ alias
├── playwright.config.ts        # E2E tests
├── e2e/                        # Playwright specs + route mocks
│   ├── sprint0-auth.spec.ts
│   ├── sprint0-auth-real-api.spec.ts
│   └── apiMocks.ts
├── public/
└── src/
    ├── main.tsx                # React DOM mount
    ├── App.tsx                 # Renders AppRouter
    ├── router.tsx              # Routes, QueryClient, AuthProvider
    ├── index.css / App.css     # Global styles
    │
    ├── components/             # Shared layout & guards
    │   ├── ProtectedRoute.tsx  # Auth + role gate
    │   ├── AuthBootstrapShell.tsx
    │   ├── AdminShell.tsx
    │   ├── OrgAdminShell.tsx
    │   ├── SuperAdminShell.tsx
    │   ├── StaffShell.tsx      # Picks shell by role for user mgmt
    │   ├── ComplianceShell.tsx
    │   ├── TwoFactorPanel.tsx
    │   └── UsersTable.tsx
    │
    ├── pages/                  # Route screens
    │   ├── LoginPage.tsx
    │   ├── SignupPage.tsx
    │   ├── ForgotPasswordPage.tsx
    │   ├── HomeRedirect.tsx
    │   ├── DashboardPage.tsx
    │   ├── ProfilePage.tsx
    │   ├── AdminPage.tsx
    │   ├── AdminUsersPage.tsx
    │   ├── AdminCreateUserPage.tsx
    │   ├── AdminUserDetailPage.tsx
    │   ├── OrgAdminPage.tsx
    │   ├── SuperAdminPage.tsx
    │   ├── SuperAdminOrganizationsPage.tsx
    │   ├── SuperAdminCreateOrganizationPage.tsx
    │   ├── SuperAdminOrganizationDetailPage.tsx
    │   ├── CompliancePage.tsx
    │   ├── UnauthorizedPage.tsx
    │   ├── MaintenancePage.tsx
    │   └── NotFoundPage.tsx
    │
    ├── lib/                    # Business logic & API wrappers
    │   ├── apiClient.ts        # Axios singleton, refresh interceptor
    │   ├── env.ts              # VITE_* validation (Zod)
    │   ├── auth/
    │   │   ├── AuthProvider.tsx  # Session context
    │   │   ├── api.ts          # signup, session-control login
    │   │   ├── routing.ts      # Home paths, role helpers
    │   │   ├── authChannel.ts  # Cross-tab logout (BroadcastChannel)
    │   │   └── types.ts
    │   ├── profile/api.ts
    │   ├── dashboard/api.ts
    │   ├── admin/
    │   │   ├── api.ts
    │   │   ├── roles.ts        # canEditUser, allowedCreateRoles
    │   │   └── types.ts
    │   ├── orgAdmin/api.ts
    │   ├── superAdmin/api.ts
    │   ├── compliance/
    │   │   ├── api.ts
    │   │   ├── types.ts
    │   │   └── display.tsx     # Stat grids, tables
    │   └── security/api.ts     # 2FA, password reset
    │
    └── mocks/
        └── fixtures.ts         # Static mock data (no MSW handlers)
```

---

## 3. Architecture layers

```
┌─────────────────────────────────────────────────────────┐
│  Browser (React SPA)                                    │
└────────────────────────┬────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│  ROUTER (router.tsx)                                    │
│  QueryClientProvider → BrowserRouter → AuthProvider     │
└────────────────────────┬────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│  ROUTE GUARDS (ProtectedRoute.tsx)                    │
│  bootstrapping → authenticated → role check → <Outlet>  │
└────────────────────────┬────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│  PAGES (pages/*.tsx)                                    │
│  UI + local form state + TanStack Query hooks           │
└────────────────────────┬────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│  API MODULES (lib/*/api.ts)                             │
│  Typed wrappers around apiClient                        │
└────────────────────────┬────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│  apiClient.ts (Axios)                                   │
│  Bearer header · withCredentials · refresh interceptor  │
└────────────────────────┬────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│  Vite dev proxy: /api → http://localhost:9000           │
│  (Set-Cookie forwarded, Secure/Domain stripped locally) │
└────────────────────────┬────────────────────────────────┘
                         ▼
                    FastAPI backend
```

### Layout shells (navigation chrome)

| Shell | Used by | Nav links |
|-------|---------|-----------|
| `AdminShell` | `AdminPage` | Dashboard, Users, Create user, Compliance, Profile |
| `OrgAdminShell` | `OrgAdminPage` | Dashboard, Users, Compliance, Profile |
| `SuperAdminShell` | Super admin pages | Dashboard, Organizations, Users, Compliance, Profile |
| `StaffShell` | User mgmt pages | Delegates to correct shell by `user.role` |
| `ComplianceShell` | `CompliancePage` | Compliance tabs + back link to role home |
| *(none)* | Login, Dashboard, Profile | Page-specific header |

---

## 4. Application code flow

### 4.1 Cold start (first page load)

```
main.tsx
  → App.tsx
    → AppRouter
      → QueryClientProvider (retry: 1, no refetch on focus)
      → BrowserRouter
      → AuthProvider mounts
          1. configureApiClient(token ref, forced logout handler)
          2. subscribeLogout() via BroadcastChannel
          3. bootstrap():
             POST /api/v1/refresh  (httpOnly cookie, withCredentials)
             → if token: GET /api/v1/profile
             → status = authenticated | unauthenticated
             → on network error: bootstrapError = true
      → Routes match current URL
```

### 4.2 Home redirect (`/`)

```
HomeRedirect
  → bootstrapError?     → /maintenance
  → bootstrapping?      → AuthBootstrapShell (spinner)
  → unauthenticated?    → /login
  → authenticated?      → getHomePathForRole(role)
```

### 4.3 Protected route access

```
ProtectedRoute
  → bootstrapping?           → AuthBootstrapShell
  → not authenticated?       → /login
  → superAdminOnly mismatch? → /unauthorized
  → orgAdminOnly mismatch?   → /unauthorized
  → adminOnly mismatch?      → /unauthorized
  → userMgmtOnly mismatch?   → /unauthorized
  → complianceOnly mismatch? → /unauthorized
  → OK                       → <Outlet /> (child page)
```

### 4.4 Page data loading pattern

```
Page component
  → useQuery({ queryKey, queryFn: lib/*/api })
  → useMutation({ mutationFn, onSuccess: refetch/invalidate })
  → render loading / error / data states
```

Pages do **not** call `apiClient` directly (except `AuthProvider`). All HTTP goes through `lib/*/api.ts`.

---

## 5. Authentication flow

### 5.1 Login

```
LoginPage.onSubmit
  → AuthProvider.login(username, password)
    → POST /api/v1/login
    → applyLoginTokens(data)        # store access token in ref
    → GET /api/v1/profile
    → status = authenticated
    → navigate(getHomePathForRole(role))
```

### 5.2 Session conflict login

```
LoginPage → "Already signed in elsewhere?"
  → POST /api/v1/login-with-session-control
    ?session_strategy=replace_all | allow_multiple | replace_same_device
  → same token + profile flow as standard login
```

### 5.3 Token refresh (automatic)

```
apiClient.doRefresh()
  → POST /api/v1/refresh  (cookie sent automatically)
  → setAccessToken(new access_token)
  → scheduleProactiveRefresh(expires_in - 60s)

Triggered by:
  - AuthProvider bootstrap
  - Proactive timer before expiry
  - 401 response interceptor (one retry per request)
```

### 5.4 Logout

```
logout()
  → POST /api/v1/logout
  → broadcastLogout()          # other tabs sign out
  → clearAuthTimers()
  → accessTokenRef = null
  → navigate(/login)
```

### 5.5 Token storage model

| Asset | Where stored | Notes |
|-------|--------------|-------|
| Access JWT | `useRef` in AuthProvider | Not in localStorage; attached as `Authorization: Bearer` |
| Refresh token | httpOnly cookie | Set by backend; `withCredentials: true` on all requests |
| User profile | React state in AuthProvider | From `GET /api/v1/profile` |

### 5.6 Error handling

`getApiError(err)` in `apiClient.ts` normalizes Axios errors to `{ detail, error_code?, ... }`.

Login page shows `error_code === "SESSION_EXISTS"` → reveals session strategy buttons.

---

## 6. Role hierarchy & routing

### 6.1 Role rank (mirrors backend)

```
super_admin (4)
    └── organization_admin (3)
            └── admin (2)
                    └── user (1)
```

Defined in `lib/admin/roles.ts` (`ROLE_RANK`).

### 6.2 Home path by role

| Role | Home route | Set by |
|------|------------|--------|
| `user` | `/dashboard` | `getHomePathForRole()` |
| `admin` | `/admin` | |
| `organization_admin` | `/org-admin` | |
| `super_admin` | `/super-admin` | |

### 6.3 Route guards (`ProtectedRoute` flags)

| Flag | Allowed roles | Routes |
|------|---------------|--------|
| *(none)* | any authenticated | `/dashboard`, `/profile` |
| `adminOnly` | `admin` | `/admin` |
| `userMgmtOnly` | `super_admin`, `organization_admin`, `admin` | `/admin/users/*` |
| `orgAdminOnly` | `organization_admin` | `/org-admin` |
| `complianceOnly` | `super_admin`, `organization_admin`, `admin` | `/compliance` |
| `superAdminOnly` | `super_admin` | `/super-admin/*` |

### 6.4 Who can create which roles (UI enforcement)

| Creator | Can assign | File |
|---------|-----------|------|
| `super_admin` | `organization_admin`, `admin`, `user` | `lib/admin/roles.ts` |
| `organization_admin` | `admin`, `user` | |
| `admin` | `user` | |
| `user` | *(none)* | |

### 6.5 Edit rules (in-page, beyond routing)

- Cannot edit yourself on admin user detail page
- `canEditUser(editorRole, targetRole)` — editor must outrank target
- Only `super_admin` can edit another `super_admin`

### 6.6 Compliance UI permissions

| Action | Who |
|--------|-----|
| View compliance tabs | `admin`, `organization_admin`, `super_admin` |
| Create/edit/delete groups | `canManageUsers` roles |
| Session cleanup button | `super_admin`, `organization_admin` only |
| Issue/revoke API keys | any compliance viewer |

---

## 7. Pages & user journeys

### 7.1 Public pages

| Page | Route | Purpose | APIs |
|------|-------|---------|------|
| **LoginPage** | `/login` | Sign in | `POST /login`, `POST /login-with-session-control` |
| **SignupPage** | `/signup` | Register | `POST /signup` |
| **ForgotPasswordPage** | `/forgot-password` | Reset password | `POST /password/reset-request`, `GET /password/reset/validate/:token`, `POST /password/reset` |
| **VerifyEmailPage** | `/verify`, `/verify/:token` | Confirm email | `POST /email/verify`, `POST /email/resend-verification` |
| **AcceptInvitePage** | `/accept-invite/:token` | Accept org invite | `GET /invitations/validate/:token`, `POST /invitations/accept` |
| **MaintenancePage** | `/maintenance` | API unreachable at bootstrap | — |
| **UnauthorizedPage** | `/unauthorized` | Role mismatch | — |
| **NotFoundPage** | `*` | 404 | — |

### 7.2 Authenticated — all roles

| Page | Route | Purpose | APIs |
|------|-------|---------|------|
| **DashboardPage** | `/dashboard` | Personal overview, activity, sessions | `GET /dashboard/user/overview`, `.../activity`, `.../sessions` |
| **ProfilePage** | `/profile` | Edit profile, password, sessions, 2FA | `GET/PUT /profile`, `POST /password/change`, sessions APIs, 2FA APIs |

### 7.3 Admin (`admin` role)

| Page | Route | Purpose | APIs |
|------|-------|---------|------|
| **AdminPage** | `/admin` | Org admin dashboard | `GET /dashboard/admin/overview`, `.../users/stats`, `.../activity/stats` |

### 7.4 User management (staff roles)

| Page | Route | Purpose | APIs |
|------|-------|---------|------|
| **AdminUsersPage** | `/admin/users` | User list | `GET /users` |
| **AdminCreateUserPage** | `/admin/users/new` | Create user | `GET /users` (managers), `POST /admin/users/create` |
| **AdminUserDetailPage** | `/admin/users/:userId` | View/edit user | `GET /users/:id`, `PATCH /users/:id` |

### 7.5 Organization admin

| Page | Route | Purpose | APIs |
|------|-------|---------|------|
| **OrgAdminPage** | `/org-admin` | Org-wide dashboard | `GET /dashboard/organization-admin/overview`, `.../users/stats`, `.../sessions/stats` |

### 7.6 Super admin

| Page | Route | Purpose | APIs |
|------|-------|---------|------|
| **SuperAdminPage** | `/super-admin` | System dashboard | `GET /dashboard/super-admin/*` (4 endpoints) |
| **SuperAdminOrganizationsPage** | `/super-admin/organizations` | List orgs | `GET /organizations`, org stats |
| **SuperAdminCreateOrganizationPage** | `/super-admin/organizations/new` | Create org | `POST /organizations` |
| **SuperAdminOrganizationDetailPage** | `/super-admin/organizations/:orgId` | Edit org | `GET /organizations/:id`, `PATCH /organizations/:id` |

### 7.7 Compliance (staff roles)

| Page | Route | Tabs | APIs |
|------|-------|------|------|
| **CompliancePage** | `/compliance` | Overview, Audit, Sessions, Permissions, Groups, API keys, Password policy | 22 compliance endpoints (see §9) |

---

## 8. State management

### 8.1 Global auth state (`AuthProvider`)

```typescript
status: "bootstrapping" | "authenticated" | "unauthenticated"
user: UserProfile | null
bootstrapError: boolean
login(), loginWithSessionStrategy(), logout()
```

Access token held in `useRef` — refreshes do not trigger React re-renders.

### 8.2 Server state (TanStack Query)

| Pattern | Usage |
|---------|-------|
| `useQuery` | Dashboard stats, user lists, compliance data |
| `useMutation` | Create user, edit group, revoke API key |
| `queryKey` | Domain-scoped: `["admin", "users"]`, `["compliance", "audit-logs"]` |
| Defaults | `retry: 1`, `refetchOnWindowFocus: false` |

### 8.3 Local UI state

`useState` in pages for: form fields, active tab, editing mode, selected group ID, action messages.

No Redux, Zustand, or global server cache outside React Query.

### 8.4 Cross-tab sync

`BroadcastChannel("auth")` — logout in one tab signs out all tabs via `authChannel.ts`.

---

## 9. API integration catalog

**64 endpoints** called from the UI. All traffic goes through `apiClient`.

### 9.1 Core auth (`apiClient.ts`, `AuthProvider`, `lib/auth/api.ts`)

| Method | Path | Used by |
|--------|------|---------|
| POST | `/api/v1/refresh` | Bootstrap, proactive refresh, 401 retry |
| POST | `/api/v1/login` | LoginPage |
| POST | `/api/v1/logout` | All shells (logout button) |
| POST | `/api/v1/signup` | SignupPage |
| POST | `/api/v1/login-with-session-control` | LoginPage (session options) |
| GET | `/api/v1/profile` | AuthProvider, ProfilePage |

### 9.2 Profile & sessions (`lib/profile/api.ts`)

| Method | Path | Used by |
|--------|------|---------|
| PUT | `/api/v1/profile` | ProfilePage |
| POST | `/api/v1/password/change` | ProfilePage |
| GET | `/api/v1/sessions` | ProfilePage |
| GET | `/api/v1/sessions/info` | ProfilePage |
| DELETE | `/api/v1/sessions/{id}` | ProfilePage |
| POST | `/api/v1/sessions/revoke-others` | ProfilePage |
| POST | `/api/v1/logout-all` | ProfilePage |

### 9.3 Security (`lib/security/api.ts`)

| Method | Path | Used by |
|--------|------|---------|
| GET | `/api/v1/2fa/status` | TwoFactorPanel |
| POST | `/api/v1/2fa/enable` | TwoFactorPanel |
| POST | `/api/v1/2fa/verify` | TwoFactorPanel |
| POST | `/api/v1/2fa/disable` | TwoFactorPanel |
| GET | `/api/v1/password/history` | TwoFactorPanel |
| POST | `/api/v1/password/reset-request` | ForgotPasswordPage |
| POST | `/api/v1/password/reset` | ForgotPasswordPage |
| GET | `/api/v1/password/reset/validate/{token}` | ForgotPasswordPage |

### 9.4 User dashboard (`lib/dashboard/api.ts`)

| Method | Path | Used by |
|--------|------|---------|
| GET | `/api/v1/dashboard/user/overview` | DashboardPage |
| GET | `/api/v1/dashboard/user/activity` | DashboardPage |
| GET | `/api/v1/dashboard/user/sessions` | DashboardPage |

### 9.5 Admin (`lib/admin/api.ts`)

| Method | Path | Used by |
|--------|------|---------|
| GET | `/api/v1/dashboard/admin/overview` | AdminPage |
| GET | `/api/v1/dashboard/admin/users/stats` | AdminPage |
| GET | `/api/v1/dashboard/admin/activity/stats` | AdminPage |
| GET | `/api/v1/users` | AdminUsersPage, CreateUser, UserDetail |
| GET | `/api/v1/users/{id}` | AdminUserDetailPage |
| PATCH | `/api/v1/users/{id}` | AdminUserDetailPage |
| POST | `/api/v1/admin/users/create` | AdminCreateUserPage |

### 9.6 Org admin (`lib/orgAdmin/api.ts`)

| Method | Path | Used by |
|--------|------|---------|
| GET | `/api/v1/dashboard/organization-admin/overview` | OrgAdminPage |
| GET | `/api/v1/dashboard/organization-admin/users/stats` | OrgAdminPage |
| GET | `/api/v1/dashboard/organization-admin/sessions/stats` | OrgAdminPage |

### 9.7 Super admin (`lib/superAdmin/api.ts`)

| Method | Path | Used by |
|--------|------|---------|
| GET | `/api/v1/dashboard/super-admin/overview` | SuperAdminPage |
| GET | `/api/v1/dashboard/super-admin/users/stats` | SuperAdminPage |
| GET | `/api/v1/dashboard/super-admin/organizations/stats` | SuperAdminPage, OrganizationsPage |
| GET | `/api/v1/dashboard/super-admin/sessions/stats` | SuperAdminPage |
| GET | `/api/v1/organizations` | SuperAdminOrganizationsPage |
| GET | `/api/v1/organizations/{id}` | SuperAdminOrganizationDetailPage |
| POST | `/api/v1/organizations` | SuperAdminCreateOrganizationPage |
| PATCH | `/api/v1/organizations/{id}` | SuperAdminOrganizationDetailPage |

### 9.8 Compliance (`lib/compliance/api.ts`)

| Method | Path | Used by |
|--------|------|---------|
| GET | `/api/v1/audit/logs` | CompliancePage |
| GET | `/api/v1/audit/statistics` | CompliancePage |
| GET | `/api/v1/sessions/statistics` | CompliancePage |
| POST | `/api/v1/sessions/cleanup` | CompliancePage |
| GET | `/api/v1/permissions` | CompliancePage |
| GET | `/api/v1/permissions/standard` | CompliancePage |
| GET | `/api/v1/permissions/statistics` | CompliancePage |
| GET | `/api/v1/groups` | CompliancePage |
| GET | `/api/v1/groups/{id}/members` | CompliancePage |
| GET | `/api/v1/groups/statistics` | CompliancePage |
| POST | `/api/v1/groups` | CompliancePage |
| PATCH | `/api/v1/groups/{id}` | CompliancePage (Edit) |
| DELETE | `/api/v1/groups/{id}` | CompliancePage |
| POST | `/api/v1/groups/{id}/members` | CompliancePage |
| DELETE | `/api/v1/groups/{id}/members/{userId}` | CompliancePage |
| GET | `/api/v1/api-keys` | CompliancePage |
| GET | `/api/v1/api-keys/standard-permissions` | CompliancePage |
| GET | `/api/v1/api-keys/statistics` | CompliancePage |
| POST | `/api/v1/api-keys` | CompliancePage |
| PATCH | `/api/v1/api-keys/{id}` | CompliancePage (Edit) |
| DELETE | `/api/v1/api-keys/{id}` | CompliancePage |
| GET | `/api/v1/password/policy-stats` | CompliancePage |

### 9.9 Backend APIs NOT called from UI

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/v1/integration/whoami` | Documented on CompliancePage for manual `curl` testing only |
| GET | `/health`, `/health/ready`, `/health/ready-full`, `/` | Infrastructure — not for SPA (`/hello` is development-only) |
| POST | `/api/v1/debug-login`, `/debug-refresh` | Dev only, backend flag |

### 9.10 Coverage summary

| Scope | Backend | UI integrated |
|-------|---------|---------------|
| Product `/api/v1` | 65 | **64** (98%) |
| All endpoints | 72 | **64** (89%) |

---

## 10. Configuration & local dev

### 10.1 Environment files

| File | Purpose |
|------|---------|
| `.env` | `VITE_API_BASE_URL=` (empty = same-origin proxy) |
| `.env.development` | `VITE_DEV_PORT=5173`, `VITE_API_PROXY_TARGET=http://localhost:9000` |
| `.env.example` | Template |

### 10.2 API base URL resolution (`lib/env.ts`)

1. **Codespaces** (`*.github.dev`) → always `window.location.origin` (Vite proxies `/api`)
2. **Local** with empty `VITE_API_BASE_URL` → same-origin (Vite proxy)
3. **Production build** → set `VITE_API_BASE_URL=https://api.example.com`

### 10.3 Vite proxy (`vite.config.ts`)

```
Browser  http://127.0.0.1:5173/api/v1/login
    ↓ proxy
Backend  http://localhost:9000/api/v1/login
```

Set-Cookie headers are rewritten for local dev (strips `Secure` and `Domain`).

### 10.4 Run locally

```bash
# Terminal 1 — backend (from repo root)
python -m uvicorn main:app --host 127.0.0.1 --port 9000

# Terminal 2 — frontend
cd frontend
npm install
npm run dev
```

Open: **http://127.0.0.1:5173/login**

### 10.5 Test accounts

| Username | Password | Role | Lands on |
|----------|----------|------|----------|
| `testuser` | `user123` | user | `/dashboard` |
| `testadmin` | `admin123` | admin | `/admin` |
| `testorgadmin` | `orgadmin123` | organization_admin | `/org-admin` |
| `test_super_admin` | `TestSuperAdminPass123!` | super_admin | `/super-admin` |

### 10.6 Build & preview

```bash
cd frontend
npm run build      # tsc + vite build → dist/
npm run preview    # serves dist/ with API proxy
```

---

## 11. Testing & E2E

| File | Purpose |
|------|---------|
| `e2e/sprint0-auth.spec.ts` | Playwright auth flow with route mocks |
| `e2e/sprint0-auth-real-api.spec.ts` | Auth against live backend (sign-off) |
| `e2e/apiMocks.ts` | Playwright `page.route()` mocks for auth + dashboard |
| `src/mocks/fixtures.ts` | Static fixture objects (not runtime mocks) |

CI runs: `npm run lint`, `npm run build`, Playwright specs.

---

## Quick reference diagram

```
Anonymous                    Authenticated
─────────                    ─────────────
/login ──────────┐
/signup          │
/forgot-password │
/verify          │
/accept-invite/* │
                 ▼
         ┌───────────────┐
         │  AuthProvider │
         │  refresh +    │
         │  profile      │
         └───────┬───────┘
                 │
    ┌────────────┼────────────┬─────────────┐
    ▼            ▼            ▼             ▼
/dashboard   /admin    /org-admin   /super-admin
 (user)      (admin)  (org_admin)  (super_admin)
    │            │            │             │
    └────────────┴────────────┴─────────────┘
                 │
         /profile (all roles)
         /compliance (staff)
         /admin/users/* (staff)
         /super-admin/organizations/* (super_admin)
```

---

*Companion doc: `docs/BACKEND.md` · Default UI: `http://127.0.0.1:5173` · API via proxy: `http://localhost:9000`*
