# FastAPI User Management

A reusable, production-grade user-management backend: authentication, organizations, roles &
permissions, sessions and an audit log. New products start from it and add only their own
business logic.

> **Status: rebuild in progress on the `v2` branch.** Progress is tracked in
> [`docs/ROADMAP.md`](docs/ROADMAP.md). The previous implementation is on `main`.

## Quick start

Requirements: Docker, [`uv`](https://docs.astral.sh/uv/), `make`.

```bash
cp .env.example .env
make run                 # app + PostgreSQL + Redis
# http://localhost:8000/docs         interactive API docs
# http://localhost:8000/health/ready readiness probe

# in a second terminal, once the stack is up:
docker compose exec app alembic upgrade head          # create the schema and seed roles
docker compose exec app python -m app.cli create-admin --email you@example.com
# (type the password at the prompt; it is never passed as an argument)
```

Development:

```bash
make install             # install dependencies
make check               # lint + type check + tests (what CI runs)
make help                # all commands
```

## Notes for API clients

- **Refresh is single-flight per session.** Every refresh token works once. Sending the same
  refresh token twice (a retry after a lost response, or two tabs refreshing at the same
  time) is treated as theft: the whole session is ended and the user must log in again. Keep
  one refresh in flight per session and share its result.
- Responses under `/api/v1` carry `Cache-Control: no-store`; don't cache them.
- By default a session ends after 30 minutes without a refresh, or 12 hours after login
  (ASVS level 2). Ending another device's session, "sign out other devices" and logout-all
  need the current password (`{"current_password": "..."}`). Three wrong passwords in a row
  on these screens end that session; the user logs in again.

## Documentation

| Document | What it covers |
| --- | --- |
| [`docs/VISION.md`](docs/VISION.md) | Purpose, scope, and the measurable 10/10 quality bar |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Stack, layers, domain model, API conventions |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Milestones, checklists and status |
| [`docs/milestones/`](docs/milestones/) | The pass/fail gate and a report for each milestone |
| [`docs/adr/`](docs/adr/) | Architecture decisions and their reasons |
| [`CLAUDE.md`](CLAUDE.md) | Working rules for developers and AI agents |

This README is completed at release (roadmap step 10).

## License

MIT
