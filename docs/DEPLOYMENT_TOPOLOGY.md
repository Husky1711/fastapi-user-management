# Process model — uvicorn workers vs Kubernetes replicas

## Defaults in this repo

`main.py` (`if __name__ == "__main__"`):

| Environment | `uvicorn` workers | Reload |
|-------------|-------------------|--------|
| `development` | **1** | allowed |
| `production` (direct `python main.py`) | **4** | off |

Prefer **not** to run multi-worker inside a single container **and** also stack many app replicas without understanding memory × workers.

---

## Prefer: replicas over in-process workers (Kubernetes / Compose)

For HTTP APIs that are mostly I/O-bound (DB, Redis):

1. Run **1 uvicorn worker per container/pod** (`workers=1` or `uvicorn main:app --workers 1`).
2. Scale **horizontally** with Deployment `replicas` (or HPA on CPU / RPS / latency).
3. Put a Service / Ingress in front for load balancing.

**Why:** process isolation, cleaner memory limits, rolling updates, and no shared in-process metrics/circuit-breaker state across workers (this app’s Redis circuit breaker and `/metrics` counters are **per process**).

```bash
# Typical container command
uvicorn main:app --host 0.0.0.0 --port 9000 --workers 1 --proxy-headers --forwarded-allow-ips='*'
```

Suggested starting point: **2–4 replicas** behind a load balancer; tune from p95 latency and DB pool usage (`DB__POOL_SIZE` × replicas × workers).

---

## When to use multi-worker or gunicorn

Use **multiple workers in one host** (or gunicorn) when:

- You cannot run a process supervisor / orchestrator, **or**
- You need more CPU cores on a single large VM without extra pods.

Recommended pattern:

```bash
gunicorn main:app \
  -k uvicorn.workers.UvicornWorker \
  -w 4 \
  -b 0.0.0.0:9000 \
  --timeout 60 \
  --graceful-timeout 30
```

Rule of thumb for worker count on one box: `2 × CPU cores + 1` for mixed I/O, **lower** if each worker keeps a large SQLAlchemy pool.

**Constraint:** total DB connections ≈ `replicas × workers × (pool_size + max_overflow)`. Keep that under MySQL/`max_connections`.

### Database pool env vars

| Variable | Default | Meaning |
|----------|---------|---------|
| `DB_POOL_SIZE` | 20 | Persistent connections per process |
| `DB_MAX_OVERFLOW` | 40 | Burst above pool size |
| `DB_POOL_TIMEOUT` | 30 | Seconds waiting for a free connection |
| `DB_POOL_RECYCLE` | 3600 | Recycle connections (avoid MySQL wait_timeout kills) |
| `DB_STATEMENT_TIMEOUT_SECONDS` | 30 | Per-statement timeout |
| `DB_URL` / `DATABASE_URL` | Codespaces MySQL | Connection string |

Example (4 replicas × 1 worker, quiet traffic):

```bash
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
# worst case ≈ 4 × (10+20) = 120 connections
```

Do not use `DB__POOL_SIZE` (double underscore) — it does not bind; use `DB_POOL_SIZE` or nested `DATABASE__POOL_SIZE`.

---

## What not to do

- Do not set `workers=4` **and** `replicas=4` without shrinking `DB__POOL_SIZE`.
- Do not enable `reload=True` in production.
- Do not assume `/metrics` aggregates cluster-wide — scrape each pod or use a shared metrics backend later.

---

## Health probes

| Probe | Path | Expectation |
|-------|------|-------------|
| Liveness | `/health` | Process up |
| Readiness | `/health/ready` | DB reachable |
| Optional | `/health/ready-full` | DB + Redis |

Point readiness at `/health/ready` so Redis outages do not drain all traffic (rate limits degrade separately).

See also: [OPS_RUNBOOKS.md](./OPS_RUNBOOKS.md).
