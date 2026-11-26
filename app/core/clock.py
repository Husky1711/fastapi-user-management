"""The only source of "now" in the application.

Always timezone-aware UTC. Tests replace it with `monkeypatch.setattr(clock, "now", ...)`
instead of sleeping.
"""

from datetime import UTC, datetime


def now() -> datetime:
    return datetime.now(UTC)
