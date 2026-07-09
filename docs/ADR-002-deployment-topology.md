# ADR-002: UI and API deployment topology

| Field | Value |
|-------|-------|
| **Status** | Approved for staging MVP |
| **Date** | 2026-07-02 |
| **Depends on** | ADR-001-frontend-auth.md |

## Topology (staging / production)

```
Internet
    │
    ├── app.{env}.example.com  →  CDN / Nginx  →  Vite static (dist/)
    │
    └── api.{env}.example.com  →  K8s Ingress  →  FastAPI :9000 (Helm chart)
```

### Alternative (simpler cookies)

Single host: `example.com` (UI) + `example.com/api` (API reverse proxy). Same-site cookies avoid cross-subdomain `Domain` issues. Evaluate before locking infra; current plan assumes subdomains.

## Cookie configuration

| Attribute | Value |
|-----------|-------|
| Name | `refresh_token` |
| `Domain` | `.example.com` (or `.staging.example.com`) |
| `Path` | `/api/v1` |
| Flags | `HttpOnly; Secure; SameSite=Lax` |
| `Max-Age` | Match `JWT__REFRESH_TOKEN_EXPIRE_DAYS` (7 days default) |

`Secure` requires TLS at the client edge. Ingress terminates TLS; API sees HTTP internally — cookie `Secure` is still set by FastAPI responses to the client over HTTPS.

Set by: `routes/login.py`, refresh and logout handlers (after P0 implementation).

## CORS (API)

Environment:

```env
SECURITY__ENABLE_CORS=true
SECURITY__CORS_ORIGINS=["https://app.staging.example.com"]
```

Middleware (`utils/security_middleware.py`) must include:

- `allow_credentials=True`
- Explicit origin list (never `*` with credentials)
- `allow_headers`: `Authorization`, `Content-Type`, `X-Request-ID`

## UI Content-Security-Policy (Nginx / CDN)

Separate from API CSP in `utils/security_middleware.py`.

```
default-src 'self';
script-src 'self';
style-src 'self' 'unsafe-inline';
img-src 'self' data: https:;
connect-src 'self' https://api.staging.example.com;
font-src 'self';
frame-ancestors 'none';
```

## Build-time environment (UI)

| Variable | Secret? | Notes |
|----------|---------|-------|
| `VITE_API_BASE_URL` | No | Per environment |
| `VITE_APP_ENV` | No | `development` / `staging` / `production` |
| `VITE_SENTRY_DSN` | Public DSN | Error tracking (M1) |

Never put JWT secrets, DB URLs, or SMTP credentials in `VITE_*`.

## CI/CD

### Pull request

1. Backend: lint + pytest
2. Export `openapi.json` artifact
3. Frontend: `pnpm lint`, `vitest`, OpenAPI codegen diff check
4. Playwright with MSW (tests 6, 7)

### Main branch

1. Build and deploy API image → `api.{env}`
2. Build UI `dist/` → deploy → `app.{env}`
3. Post-deploy smoke (below)

### Nightly

Playwright against **staging API** (no MSW): tests 1, 3, 6, 7, 8.

## Version coupling and rollback

| Artifact | Tag |
|----------|-----|
| API | `api-v{semver}-{git-sha}` |
| UI | `ui-v{semver}-{git-sha}` |

Release manifest pins both. Roll back UI and API together when OpenAPI contract changes.

## Post-deploy smoke (required)

Use `scripts/staging_post_deploy_smoke.sh` or `scripts/curl_auth_checklist.py` with real URLs:

```bash
STAGING_API_URL=https://api.staging.example.com \
STAGING_APP_URL=https://app.staging.example.com \
bash scripts/staging_post_deploy_smoke.sh
```

Equivalent manual curls:

```bash
# UI alive
curl -sf https://app.staging.example.com/ -o /dev/null

# API alive
curl -sf https://api.staging.example.com/health

# Cookie + CORS (or: CHECKLIST_BASE_URL=... CHECKLIST_ORIGIN=... python scripts/curl_auth_checklist.py)
curl -v -X POST https://api.staging.example.com/api/v1/login \
  -H "Content-Type: application/json" \
  -H "Origin: https://app.staging.example.com" \
  -d '{"username":"ADMIN_USER","password":"ADMIN_PASS"}' \
  -c cookies.txt
# Expect: Set-Cookie refresh_token; Access-Control-Allow-Credentials: true

curl -v -X POST https://api.staging.example.com/api/v1/refresh \
  -H "Origin: https://app.staging.example.com" \
  -b cookies.txt
# Expect: new access_token in body; rotated Set-Cookie
```

**GitHub Actions:** run workflow `Staging E2E` (manual) after configuring repository secrets:
`STAGING_API_URL`, `STAGING_APP_URL`, `STAGING_CHECKLIST_USER`, `STAGING_CHECKLIST_PASSWORD`.

## Production gaps (post-MVP)

- WAF / edge rate limiting
- JWT secret rotation without mass logout
- Single-host vs subdomain cookie strategy finalization
- Synthetic monitoring beyond `GET /`

## References

- `deploy/helm/fastapi-user-management/values.yaml` — API service today
- `config/settings.py` — `SecuritySettings.cors_origins`
- `.env.codespaces.example` — local CORS template
