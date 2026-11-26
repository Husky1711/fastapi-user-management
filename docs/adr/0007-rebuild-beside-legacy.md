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

- Move the legacy code to `legacy/` in roadmap step 1. It is reference only: not imported,
  run, tested or fixed.
- Build the new application in `app/` following `docs/ARCHITECTURE.md`.
- The public API is allowed to change. At the end of the roadmap, `docs/API_MIGRATION.md`
  maps every legacy endpoint to its replacement so the UI can be updated in one pass.
- Delete `legacy/` at release (step 10).

## Consequences

- Every new file is written once, in the target design, with tests.
- Until step 10, `user_management_UI` keeps working only against the legacy code at the
  `legacy-final` tag (commit `209a9bd`), not against `main`.
- The legacy review findings are tracked in `docs/ROADMAP.md` against the step whose new code
  removes them, so none are forgotten.
