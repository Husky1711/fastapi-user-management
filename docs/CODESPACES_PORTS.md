# Codespaces ports — quick reference

| Service | Port | Public URL |
|---------|------|------------|
| **Web UI (Vite)** | **5173** | `https://<codespace>-5173.app.github.dev` |
| **FastAPI API / Swagger** | **9000** | `https://<codespace>-9000.app.github.dev/docs` |
| MySQL | 3306 | private |
| Redis | 6379 | private |

**Single source of truth:** [`codespaces.ports.env`](../codespaces.ports.env) (also mirrored in `codespaces.yaml` and `.devcontainer/devcontainer.json`).

## Common mistakes

| Symptom | Cause | Fix |
|---------|-------|-----|
| **502** on port 5173 | Vite not running | `bash scripts/codespaces-ui-start.sh` |
| **500** on `/docs` | Duplicate API routes / wrong port | `bash scripts/codespaces-recover.sh` |
| API works on **8000** not **9000** | Stale uvicorn on wrong port | recover script kills 8000, starts **9000** |

## Recover

```bash
git pull origin feature/codespaces-local-db
bash scripts/codespaces-recover.sh
bash scripts/codespaces-diagnose.sh
```
