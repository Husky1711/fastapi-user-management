# 0010. Session limits are configurable to ASVS level 2; ending sessions needs no password

- Status: Superseded by [ADR-0011](0011-asvs-level-2-session-defaults.md)
- Date: 2026-11-28

## Context

ASVS 4.0.3 V3.3.2 at level 2 asks for re-authentication after 12 hours, or after 30 minutes
of inactivity. V3.3.4 at level 2 asks that users can log out other sessions "having
re-entered login credentials". This template serves many products: an internal admin tool
must meet level 2, while a consumer app usually keeps people signed in for weeks. Step 3
review round 3 found that the settings could not express level 2 at all (whole days only).

## Decision

1. **Session limits are durations.** `AUTH__REFRESH_TTL` (idle limit: each refresh issues a
   new token that lives this long) and `AUTH__SESSION_MAX_AGE` (absolute limit from the first
   login) take ISO 8601 durations, from 5 minutes up to 90 / 365 days. Level 2 is
   `AUTH__REFRESH_TTL=PT30M` (30 minutes idle) or `AUTH__SESSION_MAX_AGE=PT12H`; both are
   tested at their boundaries (3.5-17). **The defaults stay at 14 days idle and 30 days
   absolute** (level 1), because most products built from the template keep users signed in;
   a deployment that needs level 2 sets the two values (documented in `.env.example`).
2. **Ending sessions needs only the access token**, not the password again: `DELETE
   /me/sessions/{id}`, `POST /me/sessions/revoke-others`, logout and logout-all. This is a
   deliberate deviation from V3.3.4 (level 2). Ending a session only removes access, it never
   grants any; the worst a holder of a stolen access token can do with it is sign the owner
   out, and the owner signs back in with the password, which the thief doesn't have. Asking
   for the password would slow down the one action a person takes right after a device is
   stolen, and products that add password-less sign-in (SSO, added per project; VISION "Not
   planned") couldn't offer it at all. Actions that *keep or extend* access (password change) do require the current
   password (V3.7.1).

## Consequences

- Level 2 is a configuration choice, not a code change; the ASVS table records the defaults
  as level 1 for V3.3.2 and the V3.3.4 deviation with this ADR as the reason.
- Settings renamed from `AUTH__REFRESH_TTL_DAYS` / `AUTH__SESSION_MAX_AGE_DAYS` (never
  released) to `AUTH__REFRESH_TTL` / `AUTH__SESSION_MAX_AGE`.
- If a product needs V3.3.4 at level 2, add an optional `current_password` requirement to the
  session-ending routes behind a setting; the per-user lock and re-check pattern of password
  change applies unchanged.
