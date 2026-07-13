"""Client IP helpers for reverse-proxy aware deployments."""

from __future__ import annotations

from typing import Optional

from fastapi import Request


def get_client_ip(request: Request) -> str:
    """
    Prefer left-most X-Forwarded-For hop when present, then X-Real-IP,
    then the direct socket peer.

    Trust these headers only when the app runs behind a trusted proxy
    (e.g. uvicorn --forwarded-allow-ips).
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first

    real_ip = request.headers.get("x-real-ip")
    if real_ip and real_ip.strip():
        return real_ip.strip()

    if request.client and request.client.host:
        return request.client.host
    return "Unknown"
