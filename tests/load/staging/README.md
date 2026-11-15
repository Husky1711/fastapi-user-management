# Staging load test

Checks that a deployment meets the launch target (1,000–2,000 users) before go-live.
Run it against **staging**, never production.

## 1. Seed test users (staging DB)

```bash
python tests/load/staging/seed_load_users.py --count 300
```

During the test, set `RATE_LIMIT__ENABLE_IP_LIMITS=false` and
`RATE_LIMIT__ENABLE_USER_LIMITS=false` on staging, or every request comes from one IP
and gets rate-limited (HTTP 429).

## 2. Run (from a machine close to staging)

```bash
pip install httpx
# steady traffic: 100 heavy users, 75 s, re-login every 100 pages, 20 s ramp-up
python tests/load/staging/loadgen.py https://staging-api.example.com 100 75 100 20
# login burst: 200 users logging in within 2 s
python tests/load/staging/loadgen.py https://staging-api.example.com 200 60 20 2
```

Each virtual user clicks every 0.2–0.6 s, far busier than a real user, so 100 virtual
users is a heavy-peak load for a 1,000–2,000-user product.

## 3. Pass criteria

| Metric | Target |
|---|---|
| Errors (steady test) | 0 |
| Pages p95 | < 1,000 ms |
| Login p95 | < 2,000 ms |
| Login burst | no timeouts; any 503s are quick "busy" replies |

Reference (local, 3 x 1-CPU processes, 120 users): ~150 req/s, pages p50 140 ms /
p95 826 ms, login p50 522 ms, 0 errors. If staging is much slower, check CPU limits
(1 CPU per pod), `APP__THREADPOOL_SIZE=2`, and replica count.

## 4. Clean up

```bash
python tests/load/staging/seed_load_users.py --delete
```
Then turn the rate limits back on.
