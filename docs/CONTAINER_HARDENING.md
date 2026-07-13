# Container image hardening

Canonical image: repository-root [`Dockerfile`](../Dockerfile). Deploy values live under [`deploy/helm/fastapi-user-management/`](../deploy/helm/fastapi-user-management/).

## Build

```bash
docker build -t fastapi-user-management:local .
# Prefer distroless / slim tags; never bake .env or secrets into layers
```

The image:

- Uses a multi-stage build (compile deps in `builder`, ship only the venv + app in `runtime`)
- Runs as **UID/GID 10001** (`app`), not root
- Does not install a shell-friendly login for the app user
- Starts a **single** uvicorn worker (scale with Kubernetes replicas — see [DEPLOYMENT_TOPOLOGY.md](./DEPLOYMENT_TOPOLOGY.md))

## Kubernetes / Podman security context

Recommended pod settings (set in the Deployment / Compose equivalent):

| Setting | Value | Why |
|---------|-------|-----|
| `runAsNonRoot` | `true` | Refuse root even if image USER is wrong |
| `runAsUser` / `runAsGroup` | `10001` | Match image USER |
| `readOnlyRootFilesystem` | `true` | Block write to `/` after start |
| `allowPrivilegeEscalation` | `false` | Drop setuid-style escalation |
| `capabilities.drop` | `[ALL]` | Minimal ambient capabilities |
| `seccompProfile.type` | `RuntimeDefault` | Kernel syscall filter |

### Read-only root filesystem

With `readOnlyRootFilesystem: true`, mount writable volumes only where needed:

- **tmp / emptydir** for `/tmp` (Python / libraries may need it)
- Optional emptydir for app cache if you enable file logging (`LOG__FORCE_FILE`) — prefer JSON **stdout** in production instead ([BACKEND.md](./BACKEND.md) logging)

Do **not** mount the application code as writable.

Example (Helm values sketch):

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
  runAsGroup: 10001
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  capabilities:
    drop: ["ALL"]

volumeMounts:
  - name: tmp
    mountPath: /tmp
volumes:
  - name: tmp
    emptyDir: {}
```

## Secrets and config

- Pass `DB_URL` / `DATABASE_URL`, `JWT__SECRET_KEY`, Redis, and SMTP via **secrets / env**, never `COPY` of `.env`
- Production startup runs `validate_production_config()` (rejects weak JWT, insecure cookies, legacy SHA-256 password acceptance, etc.)

## Network and probes

- Expose only **9000**
- Liveness: `/health/live`
- Readiness: `/health/ready` (DB); use `/health/ready-full` when Redis must be up before traffic

## Image supply chain

- Rebuild from `requirements.lock` (`pip-compile` from `requirements.in`); scan with Dependabot / dependency-review
- Prefer digest pins (`image@sha256:…`) in production Helm values once you promote immutable tags
