"""Section 1.5: readiness checking logic (parallel checks, time limits, cache, single flight)."""

import asyncio

from app.services.health import ReadinessProbe, redact, run_checks
from tests.helpers import check_never_finishes, check_ok


class FakeMonotonic:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


class CountingCheck:
    def __init__(self) -> None:
        self.calls = 0
        self.release = asyncio.Event()

    async def __call__(self) -> None:
        self.calls += 1
        await self.release.wait()


async def test_s1_5_05_checks_run_in_parallel_not_one_after_another() -> None:
    # Each check waits for the other. Run one after the other, neither could finish and both
    # would time out; run in parallel, both succeed. No timing assumptions involved.
    a_started, b_started = asyncio.Event(), asyncio.Event()

    async def check_a() -> None:
        a_started.set()
        await b_started.wait()

    async def check_b() -> None:
        b_started.set()
        await a_started.wait()

    result = await run_checks({"a": check_a, "b": check_b}, limit_seconds=5)
    assert result.status == "ready"


async def test_s1_5_04_a_hanging_check_is_cut_off_at_the_limit() -> None:
    result = await run_checks({"db": check_ok, "redis": check_never_finishes}, limit_seconds=0.01)
    assert result.status == "not_ready"
    assert result.checks == {"db": "ok", "redis": "timeout"}


async def test_s1_5_06_concurrent_probes_trigger_one_check_run() -> None:
    check = CountingCheck()
    probe = ReadinessProbe(
        {"db": check}, limit_seconds=5, cache_seconds=1, monotonic=FakeMonotonic()
    )
    callers = [asyncio.create_task(probe.run()) for _ in range(20)]
    await asyncio.sleep(0)  # let every caller reach the probe
    check.release.set()
    results = await asyncio.gather(*callers)
    assert check.calls == 1
    assert all(r.status == "ready" for r in results)


async def test_s1_5_07_repeated_probe_reuses_result_within_window_and_refreshes_after() -> None:
    check, clock = CountingCheck(), FakeMonotonic()
    check.release.set()
    probe = ReadinessProbe({"db": check}, limit_seconds=5, cache_seconds=1, monotonic=clock)
    first = await probe.run()
    clock.now += 0.999
    assert await probe.run() == first
    assert check.calls == 1
    clock.now += 0.001  # exactly at the window edge: refresh
    await probe.run()
    assert check.calls == 2


async def test_s1_5_07_cache_can_be_disabled() -> None:
    check = CountingCheck()
    check.release.set()
    probe = ReadinessProbe({"db": check}, limit_seconds=5, cache_seconds=0)
    await probe.run()
    await probe.run()
    assert check.calls == 2


async def test_s1_5_03_failure_is_reported_and_recovery_is_seen_after_the_window() -> None:
    clock = FakeMonotonic()
    healthy = False

    async def flaky() -> None:
        if not healthy:
            raise ConnectionError("down")

    probe = ReadinessProbe({"db": flaky}, limit_seconds=5, cache_seconds=1, monotonic=clock)
    assert (await probe.run()).checks == {"db": "error"}
    healthy = True
    clock.now += 1
    assert (await probe.run()).status == "ready"


async def test_s1_5_16_an_empty_check_set_is_never_ready() -> None:
    result = await run_checks({}, limit_seconds=1)
    assert (result.status, result.checks) == ("not_ready", {})


def test_s1_5_03_redaction_removes_url_credentials_and_caps_length() -> None:
    message = "connect postgresql+asyncpg://app:s3cr3t@db:5432/x and redis://:pw@cache:6379"
    assert (
        redact(message) == "connect postgresql+asyncpg://***@db:5432/x and redis://***@cache:6379"
    )
    assert len(redact("x" * 1000)) == 200
