# Frontend (Sprint 0)

React + TypeScript + Vite SPA for the User Management portal.

## Dev setup

```bash
# Terminal 1 — API (port 9000)
cd ..
python main.py

# Terminal 2 — UI (port 5173, proxies /api → API)
cd frontend
npm install
npm run dev
```

Set `SECURITY__CORS_ORIGINS` to include `http://localhost:5173` (see `.env.codespaces.example`).

## Codespaces

On Codespace start, the UI is launched automatically via `.devcontainer/start.sh`.

```bash
# Restart API + UI + dependencies
bash .devcontainer/start.sh

# UI only
bash scripts/codespaces-ui-start.sh
```

Public URL (when port 5173 is forwarded): `https://<codespace-name>-5173.app.github.dev`

The Vite dev server proxies `/api` to FastAPI on port 9000 (same-origin cookies, no CORS setup needed in the browser).

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Dev server with API proxy |
| `npm run build` | Production build |
| `npm run preview` | Preview production build |

## Auth

- Access token: in-memory only
- Refresh token: httpOnly cookie (`/api/v1` path)
- See `docs/ADR-001-frontend-auth.md`

## Milestone status

Sprint 0 scaffold: login, bootstrap refresh, protected routes, admin guard stubs.
