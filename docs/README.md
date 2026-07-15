# Documentation index

Living sources of truth (edit these; archive or delete status-report drift elsewhere):

| Doc | Purpose |
|-----|---------|
| [BACKEND.md](./BACKEND.md) | Backend reference: architecture, APIs, config, scripts |
| [BACKEND_CODE_FLOW.md](./BACKEND_CODE_FLOW.md) | **Code flow, role hierarchy, Mermaid diagrams, full API list** |
| [BACKEND_PRODUCTION_READINESS.md](./BACKEND_PRODUCTION_READINESS.md) | Go-live checklist (status of each remediation) |
| [CLIENT_RELEASE_GAP_ANALYSIS.md](./CLIENT_RELEASE_GAP_ANALYSIS.md) | **What still blocks production / client release** (ops, residual schema, Bar 2 roadmap) |
| [DATABASE_SCHEMA_REVIEW.md](./DATABASE_SCHEMA_REVIEW.md) | Schema gaps, migrations, data integrity |
| [schema/fastapi_users_schema_latest.sql](./schema/fastapi_users_schema_latest.sql) | Latest live MySQL DDL dump (regenerate: `python scripts/export_schema_sql.py`) |
| [FRONTEND.md](./FRONTEND.md) | Frontend / UI auth and pages |

Operational & design notes:

| Doc | Purpose |
|-----|---------|
| [OPS_RUNBOOKS.md](./OPS_RUNBOOKS.md) | On-call playbooks |
| [DEPLOYMENT_TOPOLOGY.md](./DEPLOYMENT_TOPOLOGY.md) | Workers vs replicas, pool sizing |
| [CONTAINER_HARDENING.md](./CONTAINER_HARDENING.md) | Non-root image, read-only FS |
| [BACKUP_RESTORE.md](./BACKUP_RESTORE.md) | RPO/RTO, mysqldump, Helm backup |
| [TRANSACTION_BOUNDARIES.md](./TRANSACTION_BOUNDARIES.md) | Who commits/rolls back |
| [ACCESS_TOKEN_REVOCATION.md](./ACCESS_TOKEN_REVOCATION.md) | JWT `jti` blocklist (deferred) |
| [ROLE_AUTHORITY_CUTOVER.md](./ROLE_AUTHORITY_CUTOVER.md) | Option B dual-write decision + 2026-08-14 end date |
| [API_VERSIONING.md](./API_VERSIONING.md) | `/api/v1` stability rules |
| [UTC_DATETIME_CONVENTION.md](./UTC_DATETIME_CONVENTION.md) | Timestamps |

**Rule:** Prefer updating the living checklist rows over adding new `*_STATUS.md` / `*_COMPLETE.md` files.
