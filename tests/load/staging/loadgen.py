"""Async load generator: N virtual users log in, then browse; re-login every K page loads.

Usage: python loadgen.py <base_url> <concurrency> <seconds> [relogin_every] [ramp_seconds]
Users load_user_0000.. must exist (see seed_load_users.py). See README.md here.
"""
import asyncio
import random
import statistics
import sys
import time

import httpx

BASE, CONC, SECS = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
RELOGIN_EVERY = int(sys.argv[4]) if len(sys.argv) > 4 else 20
RAMP = float(sys.argv[5]) if len(sys.argv) > 5 else 2.0
PASSWORD = "LoadTest123!"
PAGES = [
    ("profile", "/api/v1/profile"),
    ("dashboard", "/api/v1/dashboard/user/overview"),
    ("activity", "/api/v1/dashboard/user/activity"),
    ("sessions", "/api/v1/dashboard/user/sessions"),
]
lat: dict[str, list[float]] = {}
errors: dict[str, int] = {}
codes: dict[str, int] = {}


def record(name: str, start: float, resp: httpx.Response | None, exc: str | None = None) -> None:
    lat.setdefault(name, []).append((time.perf_counter() - start) * 1000)
    if exc or resp is None or resp.status_code >= 400:
        errors[name] = errors.get(name, 0) + 1
        key = exc or str(resp.status_code)
        codes[f"{name}:{key}"] = codes.get(f"{name}:{key}", 0) + 1


async def login(client: httpx.AsyncClient, user: str) -> str | None:
    t = time.perf_counter()
    try:
        r = await client.post("/api/v1/login", json={"username": user, "password": PASSWORD})
        record("login", t, r)
        return r.json().get("access_token") if r.status_code == 200 else None
    except Exception as e:  # noqa: BLE001
        record("login", t, None, type(e).__name__)
        return None


async def vu(i: int, deadline: float) -> None:
    user = f"load_user_{i:04d}"
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as client:
        await asyncio.sleep(random.random() * RAMP)  # ramp-up
        token, n = None, 0
        while time.perf_counter() < deadline:
            if token is None or n % RELOGIN_EVERY == 0:
                token = await login(client, user)
                if token is None:
                    await asyncio.sleep(0.5)
                    continue
            name, path = random.choice(PAGES)
            t = time.perf_counter()
            try:
                r = await client.get(path, headers={"Authorization": f"Bearer {token}"})
                record(name, t, r)
                if r.status_code == 401:
                    token = None
            except Exception as e:  # noqa: BLE001
                record(name, t, None, type(e).__name__)
            n += 1
            await asyncio.sleep(random.uniform(0.2, 0.6))  # think time


def pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * p))]


async def main() -> None:
    start = time.perf_counter()
    await asyncio.gather(*(vu(i, start + SECS) for i in range(CONC)))
    wall = time.perf_counter() - start
    total = sum(len(v) for v in lat.values())
    print(f"concurrency={CONC} duration={wall:.0f}s requests={total} rps={total / wall:.1f}")
    print(f"{'endpoint':10} {'n':>6} {'err':>5} {'p50':>7} {'p95':>7} {'p99':>7}  (ms)")
    allv: list[float] = []
    for name in ["login"] + [p[0] for p in PAGES]:
        xs = lat.get(name, [])
        if not xs:
            continue
        allv += xs
        print(f"{name:10} {len(xs):6} {errors.get(name, 0):5} {statistics.median(xs):7.0f} {pct(xs, .95):7.0f} {pct(xs, .99):7.0f}")
    pages = [x for k, v in lat.items() if k != "login" for x in v]
    if pages:
        print(f"{'ALL PAGES':10} {len(pages):6} {sum(v for k, v in errors.items() if k != 'login'):5} "
              f"{statistics.median(pages):7.0f} {pct(pages, .95):7.0f} {pct(pages, .99):7.0f}")
    if codes:
        print("error breakdown:", dict(sorted(codes.items(), key=lambda kv: -kv[1])[:8]))


asyncio.run(main())
