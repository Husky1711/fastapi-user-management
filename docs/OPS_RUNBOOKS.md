# Operations runbooks — when to page on-call

Source of truth for alert response. Wire these thresholds into Prometheus / Grafana / PagerDuty against `/metrics`, `/health/ready`, and `/health/ready-full`.

**Scrape:** `GET /metrics` (Prometheus text)  
**Liveness:** `GET /health`  
**Readiness (DB):** `GET /health/ready`  
**Readiness (DB+Redis):** `GET /health/ready-full`

---

## Severity matrix

| Severity | Response | Examples |
|----------|----------|----------|
| **P1 — page now** | Ack ≤ 5 min; mitigate or roll back | Ready probe failing; sustained 5xx; refresh-token reuse spike |
| **P2 — business hours** | Ack ≤ 30 min; fix same day | Redis circuit open; rate-limit storm; lockout spike |
| **P3 — ticket** | Plan next sprint | Elevated latency; capacity warnings |

---

## Alert: API 5xx rate

| Field | Value |
|-------|--------|
| **Signal** | `sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) > 0.02` (2%+) for 5 minutes, **or** absolute ≥ 10 errors/min |
| **Severity** | P1 if lasting > 5 min or impacting `/api/v1/login` / `/api/v1/refresh` |
| **First checks** | 1) Recent deploy / config change  2) `/health/ready` DB  3) App logs (`event_type` containing `error`)  4) Connection pool / MySQL processlist |
| **Mitigation** | Roll back bad release; scale replicas if pool exhaustion; disable retention job if DB locked (`APP__ENABLE_RETENTION_JOB=false`) |
| **Escalate** | Platform owner if DB is unreachable from all pods |

---

## Alert: Readiness probe failing (DB)

| Field | Value |
|-------|--------|
| **Signal** | `/health/ready` returns non-200 for ≥ 2 consecutive probes |
| **Severity** | P1 |
| **First checks** | MySQL/Postgres up; credentials/`DB__URL`; `DB__STATEMENT_TIMEOUT_SECONDS` not too aggressive; network policy |
| **Mitigation** | Failover DB / restore primary; do **not** expect fail-open in production (startup raises on DB failure) |
| **Notes** | Redis alone must **not** take the service out of rotation — that is `/health/ready-full` only |

---

## Alert: Redis down / circuit open

| Field | Value |
|-------|--------|
| **Signal** | `/health/ready-full` fails while `/health/ready` succeeds; **or** logs `event_type=redis_circuit_open` |
| **Severity** | P2 (P1 if `RATE_LIMIT__FAIL_OPEN=false` and login blocked) |
| **First checks** | Redis process/pod; memory eviction; `REDIS__*` host/port; cooldown env (`REDIS__CIRCUIT_*`) |
| **Mitigation** | Restart Redis; temporarily allow fail-open **only** outside prod compliance windows; flush pathological `rate_limit:*` keys if needed |
| **Impact** | Rate limits / 2FA challenges / some caches degrade or fail closed |

---

## Alert: Auth lockout spike

| Field | Value |
|-------|--------|
| **Signal** | `increase(auth_lockouts_total[15m]) > 20` **or** many `event_type=login_failure` from diverse IPs |
| **Severity** | P2 (P1 if confirmed credential stuffing + customer impact) |
| **First checks** | `/metrics` `auth_failures_total` / `auth_lockouts_total`; security logs; WAF/CDN; IP rate-limit buckets |
| **Mitigation** | Tighten `login` rate limits temporarily; block abusive CIDRs; confirm not a single user typo loop |
| **Do not** | Blindly unlock all accounts without audit |

---

## Alert: Refresh-token reuse

| Field | Value |
|-------|--------|
| **Signal** | `increase(refresh_reuse_total[5m]) > 0` (any reuse is suspicious) |
| **Severity** | P1 if repeated for same user / IP cluster |
| **First checks** | Security incident rows; user sessions; client cookie mishandling (multiple tabs can race) |
| **Mitigation** | Revoke all refresh tokens for the user; force re-login; investigate token theft vs buggy client |
| **Related** | Route emits security incident + metric on reuse detection |

---

## Alert: Rate-limit storm

| Field | Value |
|-------|--------|
| **Signal** | `increase(rate_limit_hits_total[5m])` ≫ baseline (e.g. 5×) |
| **Severity** | P2 |
| **First checks** | Endpoint label from logs; misconfigured client retry; scanner hitting `/login` or `/password/reset-request` |
| **Mitigation** | Confirm per-email password-reset limits working; block scanner IPs; raise limits only with owner approval |

---

## Alert: High latency

| Field | Value |
|-------|--------|
| **Signal** | avg from `http_request_duration_seconds_sum / count` > 2s for auth or dashboard paths over 10m |
| **Severity** | P2 / P3 by customer impact |
| **First checks** | Slow query logs; N+1 gone regressions; Redis circuit; retention job running heavy deletes |
| **Mitigation** | Kill long queries; scale DB / app; lower dashboard cache TTL only after diagnosing stampedes |

---

## Escalation contacts

Fill for your deployment (keep out of git if sensitive):

| Role | Contact | Notes |
|------|---------|-------|
| App on-call | _TBD_ | Owns FastAPI + frontend release |
| Data on-call | _TBD_ | Owns MySQL/Postgres |
| Security | _TBD_ | Lockouts / token reuse / incidents |

---

## Related docs

- [BACKEND.md](./BACKEND.md) — config, health, scripts  
- [BACKEND_PRODUCTION_READINESS.md](./BACKEND_PRODUCTION_READINESS.md) — gap tracker  
- Metrics endpoint: `GET /metrics`
