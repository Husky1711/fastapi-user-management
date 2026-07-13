"""UTC datetime helpers — prefer these over datetime.utcnow().

Convention (MySQL): store naive UTC wall-clock in DATETIME columns.
See docs/UTC_DATETIME_CONVENTION.md.
"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """
    Current UTC time as a naive datetime.

    MySQL DATETIME columns in this project are timezone-naive; values are
    always stored/compared as UTC wall time. Uses datetime.now(timezone.utc)
    to avoid the deprecated datetime.utcnow().
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utc_today_start() -> datetime:
    """Start of the current UTC day (00:00:00)."""
    now = utc_now()
    return datetime(now.year, now.month, now.day)
