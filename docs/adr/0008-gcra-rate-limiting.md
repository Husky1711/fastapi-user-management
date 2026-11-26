# 0008. GCRA rate limiting in a Redis Lua script

- Status: Accepted
- Date: 2026-11-27

## Context

The legacy limiter is a sliding-window log in a Redis sorted set. It keys members by whole
seconds (so bursts in one second count once), records rejected requests, keeps every request
in memory (up to 100,000 entries per IP per day), pings Redis before every request and makes
up to 8 round trips per request. A bare `except` also swallows the per-user 429.

## Decision

Use the Generic Cell Rate Algorithm (GCRA), implemented as a single Lua script executed with
`EVALSHA`:

- One key per (policy, identity), storing a single timestamp — O(1) memory.
- Atomic check-and-update in one round trip; several policies checked in one script call.
- Rejected requests do not consume capacity.
- Returns remaining capacity and exact retry-after, used for `RateLimit-*` and `Retry-After` headers.
- Redis failure: fail **closed** on authentication routes, **open** elsewhere (configurable).

Identities: client IP (trusted-proxy aware), user id, and for login also the normalised email.

## Consequences

- Correct under concurrency and across any number of app instances.
- Smooth limiting without the burst-at-window-edge problem of fixed windows.
- The Lua script needs its own tests against a real Redis.
- GCRA expresses limits as rate + burst rather than "N per window"; settings document both.
