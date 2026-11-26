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
```

Development:

```bash
make install             # install dependencies
make check               # lint + type check + tests (what CI runs)
make help                # all commands
```

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
