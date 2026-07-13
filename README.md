# FastAPI User Management

Enterprise multi-tenant user management API with a React frontend. Role-based access control, session management, 2FA, audit logging, and compliance features.

**Documentation**

| Doc | Purpose |
|-----|---------|
| [docs/BACKEND.md](docs/BACKEND.md) | API reference, configuration, scripts |
| [docs/BACKEND_CODE_FLOW.md](docs/BACKEND_CODE_FLOW.md) | Code flow diagrams, role hierarchy, full API list |
| [docs/FRONTEND.md](docs/FRONTEND.md) | UI pages, routing, API integration |
| [docs/BACKEND_PRODUCTION_READINESS.md](docs/BACKEND_PRODUCTION_READINESS.md) | Production gaps and sprint plan |
| [docs/DATABASE_SCHEMA_REVIEW.md](docs/DATABASE_SCHEMA_REVIEW.md) | Schema audit and migration items |
| [docs/OPS_RUNBOOKS.md](docs/OPS_RUNBOOKS.md) | On-call alerts: 5xx, Redis, lockouts, readiness |
| [docs/API_VERSIONING.md](docs/API_VERSIONING.md) | `/api/v1` compatibility & deprecation |
| [docs/DEPLOYMENT_TOPOLOGY.md](docs/DEPLOYMENT_TOPOLOGY.md) | Workers vs replicas, gunicorn |

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- MySQL 8.0
- Redis 6+
- (Optional) Podman or Docker for local containers

---

## Quick start (local)

### 1. Clone and configure

```bash
cp .env.codespaces.example .env
# Edit .env — at minimum set DB_URL (or DATABASE_URL) and JWT__SECRET_KEY
```

### 2. Start MySQL and Redis

With Podman (example):

```bash
podman run -d --name fastapi-mysql -p 3306:3306 \
  -e MYSQL_DATABASE=fastapi_users \
  -e MYSQL_USER=fastapi \
  -e MYSQL_PASSWORD=fastapi \
  -e MYSQL_ROOT_PASSWORD=root \
  docker.io/library/mysql:8.0

podman run -d --name fastapi-redis -p 6379:6379 docker.io/library/redis:7
```

### 3. Bootstrap database

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements-dev.txt   # prod + pytest; use requirements.txt for runtime-only
python scripts/ci_bootstrap_db.py
```

### 4. Run backend

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 9000
```

API docs: http://127.0.0.1:9000/docs

### 5. Run frontend

```bash
cd frontend
npm install
npm run dev
```

UI: http://127.0.0.1:5173

---

## Seed test accounts

| Username | Password | Role |
|----------|----------|------|
| `testuser` | `user123` | user |
| `testadmin` | `admin123` | admin |
| `testorgadmin` | `orgadmin123` | organization_admin |
| `testuser_org2` | `user2123` | user (org 2) |
| `test_super_admin` | `TestSuperAdminPass123!` | super_admin |

---

## Key environment variables

| Variable | Description | Default (dev) |
|----------|-------------|---------------|
| `APP__ENVIRONMENT` | `development` / `staging` / `production` | `development` |
| `APP__DEBUG` | FastAPI debug mode | `false` |
| `DB__URL` | SQLAlchemy database URL | local MySQL |
| `REDIS__HOST` | Redis host | `localhost` |
| `JWT__SECRET_KEY` | JWT signing secret (min 32 chars) | dev placeholder |
| `JWT__ACCESS_TOKEN_EXPIRE_MINUTES` | Access token TTL | `5` |
| `JWT__REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token TTL | `7` |
| `AUTH_COOKIE__SECURE` | httpOnly cookie `Secure` flag | `false` (set `true` in prod) |
| `AUTH_COOKIE__LEGACY_JSON_REFRESH` | Return refresh token in JSON body | `true` |
| `SECURITY__ALLOW_PUBLIC_SIGNUP` | Enable `POST /api/v1/signup` | `false` |
| `SECURITY__ALLOW_DEBUG_AUTH` | Enable debug login endpoints | `false` |
| `SECURITY__CORS_ORIGINS` | JSON array of allowed origins | localhost Vite ports |
| `EMAIL__ENABLE_EMAILS` | Send transactional email | `false` |

Copy `.env.codespaces.example` for a fuller template. **Do not commit `.env`** — it is gitignored.

Production startup runs `validate_production_config()` and refuses to boot with weak secrets, debug auth, or insecure cookie settings.

---

## Tests

```bash
pytest tests/smoke -q
pytest tests/integration/test_auth_integration.py -q
```

---

## Production deploy

1. Set `APP__ENVIRONMENT=production`
2. Provide strong `JWT__SECRET_KEY` via secrets manager
3. Set `AUTH_COOKIE__SECURE=true` and HTTPS
4. Set `AUTH_COOKIE__LEGACY_JSON_REFRESH=false`
5. Set `SECURITY__ALLOW_DEBUG_AUTH=false` and `SECURITY__ALLOW_PUBLIC_SIGNUP=false`
6. Configure explicit `SECURITY__CORS_ORIGINS`
7. Run Alembic migrations against production MySQL
8. See [docs/BACKEND_PRODUCTION_READINESS.md](docs/BACKEND_PRODUCTION_READINESS.md) for the full checklist

---

## Project layout

```
├── main.py              # FastAPI app entry
├── config/settings.py   # Pydantic settings
├── routes/              # HTTP handlers
├── services/            # Business logic
├── models/              # SQLAlchemy models
├── frontend/            # React + Vite UI
├── scripts/             # Bootstrap, CI helpers
├── tests/               # pytest suite
└── docs/                # Reference documentation
```
