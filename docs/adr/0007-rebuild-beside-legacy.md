# 0007. Rebuild beside the legacy code; the API may change

- Status: Accepted
- Date: 2026-11-27

## Context

The review at commit `209a9bd` rated the backend 4/10. The agreed decisions (ADR-0002 to
ADR-0006) change the database, the primary keys, the tenancy model, the authorization model
and the shape of most endpoints. Refactoring the legacy files in place would mean rewriting
each of them twice and keeping a broken API stable for no benefit. The only known client is
the owner's own `user_management_UI`.

## Decision

- All new work happens on a long-lived integration branch, `v2`, created from `main` at
  `209a9bd`. Step branches merge into `v2` through pull requests. `main` is not touched until
  release, so anything using the old API keeps working from `main`.
- `v2` is built from scratch. Roadmap step 1 deletes the legacy code from the branch; it stays
  on `main` as the reference for cross-checking APIs, tables and behaviour, and is never copied.
- Build the new application in `app/` following `docs/ARCHITECTURE.md`.
- The public API is allowed to change. At the end of the roadmap, `docs/API_MIGRATION.md`
  maps every legacy endpoint to its replacement so the UI can be updated in one pass.
- At release (step 10): tag the last legacy commit on `main`, then merge `v2` into `main`.
- Not an orphan branch: `v2` shares history with `main`, so old and new stay comparable in
  git and the final merge is an ordinary one.

## Consequences

- Every new file is written once, in the target design, with tests.
- `main` stays stable for `user_management_UI` and any deployment until release.
- The final `v2` → `main` merge is large; this is acceptable because every part of it was
  already reviewed as a step PR into `v2`.
- Fixes needed on the legacy code before release (if any) go to `main` only and are not
  carried into `v2`.
- The legacy review findings are tracked in `docs/ROADMAP.md` against the step whose new code
  removes them, so none are forgotten.
