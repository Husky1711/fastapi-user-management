"""Remove credentials from text before it is logged.

Used for every log line (message, string fields, tracebacks) and for readiness errors.
"""

import re

# "scheme://user:password@host" → "scheme://***@host"
_URL_CREDENTIALS = re.compile(r"([a-z][a-z0-9+.-]*://)[^@/\s]+@", re.IGNORECASE)
# "password=hunter2" (libpq key/value DSNs, query strings) → "password=***"
_KEY_VALUE_SECRET = re.compile(
    r"\b(password|passwd|pwd|secret|token)\s*=\s*[^\s;&'\"]+", re.IGNORECASE
)


def redact(text: str, *, limit: int | None = None) -> str:
    """Remove credentials (in URLs and key=value pairs); optionally cap the length."""
    without_urls = _URL_CREDENTIALS.sub(r"\1***@", text)
    cleaned = _KEY_VALUE_SECRET.sub(r"\1=***", without_urls)
    return cleaned if limit is None else cleaned[:limit]


def mask_email(email: str) -> str:
    """`grace@example.com` -> `g***@example.com`: enough to recognise, not to harvest."""
    local, at, domain = email.rpartition("@")
    if not at:
        return "***"
    return f"{local[:1]}***@{domain}"
