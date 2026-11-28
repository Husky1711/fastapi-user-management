# 0011. Sessions default to ASVS level 2; ending other sessions needs the password

- Status: Accepted (supersedes [ADR-0010](0010-session-limits-and-ending-sessions.md)); its lockout consequence is replaced by [ADR-0012](0012-reauthentication-budget-per-session.md)
- Date: 2026-11-28

## Context

VISION §5 sets the quality bar at "OWASP ASVS L2 sections V2 (auth), V3 (sessions) pass".
ADR-0010 kept level 1 session defaults and made V3.3.4 (re-entering credentials before
logging out other sessions) a permanent level 2 deviation. Step 3 review round 4 pointed
out that this lowers the VISION bar, which only the owner may do (CLAUDE.md). The template
should meet its own bar by default; a product that wants longer sessions can still choose
them, and that choice is then the product's, made knowingly.

## Decision

1. **Session limits default to ASVS level 2 (V3.3.2):** `AUTH__REFRESH_TTL=PT30M` (30
   minutes idle) **and** `AUTH__SESSION_MAX_AGE=PT12H` (12 hours from the first login).
   Level 2 needs both. Both are ISO 8601 durations, 5 minutes–90 days and up to 365 days;
   longer values are allowed for products that accept level 1.
2. **A refresh token outlives the access token it renews:** settings with
   `AUTH__REFRESH_TTL` below twice `JWT__ACCESS_TTL_SECONDS` are refused at startup, or every
   session would end at its first refresh.
3. **Ending other sessions needs the current password (V3.3.4):** ending another device's
   session (`POST /me/sessions/{id}/revoke`), `POST /me/sessions/revoke-others` and
   `POST /auth/logout-all` take `{"current_password": ...}`. Missing: 422
   `auth.current_password_required`; wrong: 401, counted toward the lockout and audited
   (`auth.reauth_failed`). Ending the current session (`/auth/logout`, or revoking its own id)
   needs no password. `AUTH__REAUTH_TO_END_SESSIONS=false` turns the check off for products
   that accept level 1. The route that ends one session changed from `DELETE` to
   `POST …/revoke`, because a body on `DELETE` has no defined meaning (RFC 9110) and is
   dropped by some proxies.

## Consequences

- Out of the box, a user who is idle for 30 minutes, or signed in for 12 hours, signs in
  again. Products that want "remember me for weeks" set the two durations and accept level 1.
- Re-authentication is refused while the account is locked, like every password check;
  otherwise the session-ending routes would be an unlimited password oracle. So while a lock
  lasts (15 minutes by default) the owner can't end other sessions either. Someone holding a
  stolen access token could cause that lock with wrong guesses; the default session limits
  keep their access short (an access token lives 15 minutes, a refresh token 30 minutes
  idle), and step 4 adds the rate limits that keep the lockout from being used against the
  owner (ROADMAP step 4).
- ADR-0010 is superseded; its settings names stay.
