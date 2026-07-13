# API versioning & deprecation policy

## Current contract

- Public HTTP API is versioned in the URL path: **`/api/v1/...`**
- Router prefix source of truth: `routes/auth_common.py` → `API_PREFIX = "/api/v1"`
- OpenAPI for operators is exported in CI (`artifacts/openapi.json`); `/docs` is off in production

There is **no** accept-header versioning today. New major versions will use a new path prefix (`/api/v2`), not content negotiation.

---

## Compatibility rules

| Change type | Allowed on `/api/v1` without bump? | Notes |
|-------------|-------------------------------------|--------|
| Add optional request field | Yes | Default must preserve old clients |
| Add response field | Yes | Clients must ignore unknown fields |
| New endpoint under `/api/v1` | Yes | Document in OpenAPI artifact |
| Tighten validation (stricter 422) | Prefer no | Treat as breaking if it rejects previously accepted payloads |
| Remove / rename field or endpoint | **No** | Requires deprecation window or `/api/v2` |
| Change auth semantic (cookies, CSRF, 2FA gate) | **No** without notice | Frontend + partners must migrate |

Breaking changes ship on **`/api/v2`** (or a later `/api/vN`) while `/api/v1` remains for the sunset period.

---

## Deprecation process

1. **Announce** in release notes + OpenAPI (`deprecated: true` on operations/schemas).
2. **Emit** `Deprecation` and `Sunset` HTTP headers on deprecated responses when practical:
   - `Deprecation: true`
   - `Sunset: <HTTP-date>` (target removal date)
   - Optional `Link: </docs/...>; rel="deprecation"`
3. **Minimum window:** 90 days for partner-facing auth endpoints; 30 days for internal-only admin tools (document exceptions).
4. **Remove** only after sunset; keep a redirect/410 stub if traffic remains material.
5. **Freeze** `/api/v1` behaviour except security patches once `/api/v2` is GA.

---

## Planning `/api/v2`

When introducing v2:

- Mount a parallel router with `API_PREFIX = "/api/v2"` (copy of `create_api_router` pattern).
- Do **not** change cookie names or CSRF header without an explicit migration guide.
- Publish both OpenAPI documents in CI (`openapi-v1.json`, `openapi-v2.json`) during overlap.
- Prefer additive shared services; isolate only the wire format in routes/schemas.

Header-based versioning (`Accept: application/vnd.*.v2+json`) is **not** planned unless a gateway requirement appears; path versioning stays canonical.

---

## Related

- OpenAPI export: `python scripts/export_openapi.py`
- Error shape: `utils/api_errors.py` (`error_code`, `correlation_id`)
- Frontend contract: [FRONTEND.md](./FRONTEND.md)
