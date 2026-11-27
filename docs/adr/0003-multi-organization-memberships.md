# 0003. Users can belong to many organizations

- Status: Accepted
- Date: 2026-11-27

## Context

The legacy model stores `organization_id` and `role` directly on the user, so a user belongs
to exactly one organization with one role. Real products often need more: a consultant
working for two clients, an agency managing several companies, a person who is an admin in
one team and a member in another. Changing from one-org-per-user to many later would touch
every query and every permission check.

## Decision

Introduce a `memberships` table: `(user_id, organization_id, role_id)`, unique on
`(user_id, organization_id)`. A user's role is always "role **in** an organization".
Org-scoped API routes name the organization in the path (`/api/v1/orgs/{org_id}/…`), so every
request states which tenant it acts on.

Products that want exactly one organization per user set `MAX_ORGS_PER_USER=1` in config.

## Consequences

- One model covers single-tenant, B2B SaaS and agency use cases.
- Every org-scoped request costs one membership lookup (cached per request, indexed).
- The client must know which organization it is working in; `GET /me/organizations` provides the list.
- Platform-wide administration is separate from org roles (see ADR-0004).
