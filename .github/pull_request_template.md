## What and why

<!-- One or two sentences. Link the roadmap step, e.g. "Roadmap step 3: refresh rotation". -->

## Changes

-

## How it was tested

-

## Definition of done (from CLAUDE.md)

- [ ] Matches `docs/ARCHITECTURE.md`, or updates it with reasons (and an ADR for design decisions)
- [ ] Tests cover success, auth failure, permission failure and validation failure where relevant
- [ ] `ruff`, `mypy --strict` and `pytest` pass; coverage of touched services/core ≥ 90 %
- [ ] Schema changes include an Alembic migration that also downgrades
- [ ] New settings added to `.env.example` with safe defaults
- [ ] New endpoints have a `response_model`, documented error codes and a rate-limit policy
- [ ] No secrets, tokens, passwords or full emails in logs, errors or fixtures
- [ ] `docs/ROADMAP.md` boxes ticked; docs updated if behaviour changed

## Notes for the reviewer

<!-- Risks, follow-ups, anything you want a second opinion on. -->
