# Access token revocation (JWT `jti` blocklist)

## Current posture (v1)

Aligned with readiness item **1.12** (deferred):

- Access JWTs are **short-lived** (default **5 minutes** via `JWT__ACCESS_TOKEN_EXPIRE_MINUTES`).
- Logout / revoke-others / logout-all invalidate **refresh** tokens in MySQL (`refresh_tokens`).
- Compromised access tokens remain valid until natural expiry — accepted risk for v1 when TTL is short.

There is **no** `access_token_revocations` table and **no** Redis access-JWT blocklist in production code today.

## When to pull this forward

Enable immediate access revocation if compliance requires kill-switch on token theft (e.g. session revoke must stop API calls within seconds, not minutes).

### Recommended design (Phase 2)

1. Add `jti` (UUID) claim when creating access tokens (`utils/jwt_config.create_access_token`).
2. On logout / revoke-all / password change: write `jti` → Redis key `access:revoked:{jti}` with TTL = remaining access lifetime (or max access TTL).
3. Auth dependency: after JWT signature verify, reject if Redis key exists.
4. Redis is a **hard dependency** for this path (same stance as rate limiting in production). Document AOF/RDB persistence so restarts do not clear the blocklist mid-TTL — or dual-write to an `access_token_revocations` MySQL table for durability.

Do **not** invent a table-only blocklist without also wiring verify-time checks in `dependencies/auth.py`.

## Tracking

| Item | Status |
|------|--------|
| Readiness 1.12 / 13.3.6 | Deferred (⏸) until compliance requires it |
| Schema §4.2.4 | Documented here; table optional once Redis design lands |
