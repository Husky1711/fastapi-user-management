# Database backup & restore

## Targets (first production cutover)

| Metric | Target | Notes |
|--------|--------|--------|
| **RPO** (data loss window) | ≤ **24 hours** | Daily full logical dump; tighten with binlog / provider PITR if needed |
| **RTO** (time to restore) | ≤ **4 hours** | Includes obtain dump, restore to new instance, migrate/app smoke, DNS/cutover |
| **Retention** | **30 days** local/PVC dumps | Align with `DatabaseBackupManager.retention_days` |

Nightly dumps alone do **not** protect against mid-day corruption; enable MySQL binary logs (or managed continuous backup) for sub-day RPO.

## Canonical script

`scripts/backup_database.py` — `mysqldump` → gzip → age-based cleanup.

Credentials come from **`DATABASE_URL` / `DB_URL`** via `config.settings` (never hardcode passwords in the script). Optional notify uses `EMAIL__ENABLE_EMAILS` and `BACKUP__NOTIFY_EMAIL` (falls back to `EMAIL__FROM_EMAIL`).

```bash
# Local / bastion
export DATABASE_URL='mysql+pymysql://user:pass@host:3306/fastapi_users'
python scripts/backup_database.py
```

Store dumps outside the app container (PVC, S3, or provider snapshot). With read-only root FS, mount a writable volume at the backup path.

## Restore (outline)

1. Provision empty MySQL 8 with matching charset/collation.
2. `gunzip -c backup_YYYY-MM-DD_HHMMSS.sql.gz | mysql -h … -u … -p fastapi_users`
3. `alembic upgrade head` (no-op if dump already at head).
4. Point app `DATABASE_URL` at the restored instance; check `/health/ready` and login smoke.

Never restore over a live primary without a maintenance window and a pre-restore snapshot.

## Kubernetes / Helm

Values sketch (`deploy/helm/fastapi-user-management/values.yaml`):

```yaml
backup:
  enabled: true
  schedule: "0 2 * * *"   # daily 02:00 UTC
  retentionDays: 30
  # image uses same app image; command runs mysqldump client
  # mount Secret DATABASE_URL and a PVC at /backups
```

Recommended CronJob pattern:

- `concurrencyPolicy: Forbid`
- ServiceAccount without cluster-admin; only Secret + PVC access
- Prefer **managed backup** (RDS/Aurora/CloudSQL snapshots + PITR) in production; keep this CronJob as a portable logical export

See also [CONTAINER_HARDENING.md](./CONTAINER_HARDENING.md) and [OPS_RUNBOOKS.md](./OPS_RUNBOOKS.md).
