# 0012. Re-entering the password uses a per-session budget, not the account lockout

- Status: Accepted (replaces the lockout consequence of [ADR-0011](0011-asvs-level-2-session-defaults.md))
- Date: 2026-11-28

## Context

Signed-in users re-enter their password to change it and, since ADR-0011, to end other
sessions. Those checks counted toward the account lockout and were refused while the
account was locked. Step 3 review round 5 found two problems:

1. The lockout was checked before Argon2 ran and not again before the write, so a burst
   of parallel guesses with a stolen access token got far more than 5 tries, and the right
   guess succeeded: a password oracle.
2. Anyone holding a stolen token could lock the account with 5 wrong re-entries and keep
   re-locking it, so the owner could neither log in nor end the thief's session for the
   session's whole life (12 hours by default).

## Decision

1. **Each session has a re-entry budget** (`AUTH__REAUTH_MAX_FAILURES`, default 3). A
   re-entry first *reserves* one attempt: one atomic `UPDATE` on the session row, under the
   user lock, that fails when the budget is used up or the session is no longer live. Only
   then does Argon2 run. Parallel requests can't exceed the budget, because the reservation
   happens before the slow check, not after it.
2. **A wrong password keeps its reservation; when the budget is used up, that session ends**
   (`revoked_reason = reauth_failed`, audited). The thief's access and refresh tokens die
   with it. A right password restores the budget.
3. **Every write after a re-entry re-checks under the user lock** (`lock_and_recheck`): the
   account is still active, the password is still the one verified, and the caller's
   session is still live. Otherwise the write is refused (401) and audited.
4. **The account lockout is for anonymous logins only.** Re-entries don't count toward it
   and aren't refused by it, so a locked account's owner, signed in elsewhere, can still
   change the password and end the thief's sessions.

## Consequences

- A stolen access or refresh token buys at most 3 password guesses before its session ends;
  stealing more sessions needs more logins, which the login lockout and step 4's rate
  limits cover.
- A person who mistypes their password three times in a row on these screens is signed out
  of that session and logs in again.
- `sessions.reauth_attempts` is carried over a refresh rotation, so refreshing doesn't
  restore the budget.
