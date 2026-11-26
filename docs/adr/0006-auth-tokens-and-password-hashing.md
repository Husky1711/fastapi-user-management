# 0006. Argon2id, PyJWT and rotating refresh tokens

- Status: Accepted
- Date: 2026-11-27

## Context

The legacy code hashes passwords with unsalted SHA-256, uses `python-jose` (poorly maintained)
alongside an unused `PyJWT`, puts role and organization in the access token (so demotions
don't take effect until expiry), and its session revocation silently does nothing.

## Decision

**Passwords**

- Argon2id via `argon2-cffi`, with OWASP-recommended parameters, configurable.
- On successful login, if `needs_rehash` is true, rehash and save.
- Unknown emails still run a dummy verify, so timing does not reveal registered emails.
- Lockout after N failures for M minutes (defaults 5 and 15), plus per-email rate limiting.

**Access tokens**

- JWT signed with HS256 by default (RS256/EdDSA configurable for multi-service setups), via `PyJWT`.
- Lifetime 15 minutes (configurable). Claims: `sub`, `sid`, `iat`, `exp`, `iss`, `aud`, `jti`.
- No role, permission or organization claims. Authorization is read live from the database.

**Refresh tokens / sessions**

- 256-bit random opaque strings, stored only as SHA-256 hashes in `sessions`.
- Lifetime 14 days (configurable). Rotated on every use.
- Rotations share a `family_id`. Presenting an already-rotated token revokes the whole family
  and writes an audit event (theft detection).
- Session policy (`allow_multiple`, `replace_all`, `replace_same_device`, `limit_sessions`) is
  a server setting, not a client parameter.

## Consequences

- A leaked database does not expose usable passwords or refresh tokens.
- Demotions and removals take effect on the next request, at the cost of a membership lookup.
- Argon2 makes login deliberately slow (~50–150 ms); the login performance target accounts for it.
- Existing legacy SHA-256 hashes cannot be verified with Argon2. As there is no production data,
  we do not carry a migration path; projects with legacy data would need a one-off rehash-on-login shim.
