# 0001. Record architecture decisions

- Status: Accepted
- Date: 2026-11-27

## Context

This project is meant to be a reusable base that other people build on. They will ask "why
is it done this way?" long after the original conversation is forgotten. AI agents working on
the code also need the reasoning, or they will "fix" deliberate choices.

## Decision

Every significant decision — anything that affects structure, data model, security, public
API or dependencies — is recorded as a short ADR in `docs/adr/`, using the template in
`docs/adr/README.md`. A decision that reverses an ADR must be a new ADR.

## Consequences

- Reviewers can reject a PR that makes a significant change without an ADR.
- Some small overhead per decision; in exchange, decisions are not relitigated.
