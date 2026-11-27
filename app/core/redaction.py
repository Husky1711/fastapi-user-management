"""Remove credentials and personal data before anything is logged or audited.

Used for every log line (message, fields, tracebacks), readiness errors and audit details.
"""

import re
from collections.abc import Mapping

# "scheme://user:password@host" → "scheme://***@host"
_URL_CREDENTIALS = re.compile(r"([a-z][a-z0-9+.-]*://)[^@/\s]+@", re.IGNORECASE)
# "password=hunter2", "token: abc", '"api_key": "abc"' (DSNs, query strings, headers, JSON)
# → the value becomes ***. A word alone ("password reset sent") is left as it is.
_KEY_VALUE_SECRET = re.compile(
    r"""(["']?\b(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?token"""
    r"""|refresh[_-]?token|client[_-]?secret)["']?\s*[=:]\s*)(["']?)[^\s;&,'"}]+""",
    re.IGNORECASE,
)
# "Authorization: Bearer abc" → "Authorization: Bearer ***" (always, after the header name)
_AUTH_HEADER = re.compile(
    r"(\bauthorization\s*[:=]\s*(?:bearer|basic)\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE
)
# Elsewhere "Bearer eyJ…" / "Basic dXNl…" only when the word after it looks like a credential
# (a digit or token symbol, or 16+ characters), so prose like "Basic information" survives.
_AUTH_SCHEME = re.compile(
    r"\b(Bearer|Basic)\s+(?=\S*[0-9\-._~+/=]|\S{16})[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE
)


def redact(text: str, *, limit: int | None = None) -> str:
    """Remove credentials (URLs, key/value pairs, auth headers); optionally cap the length."""
    cleaned = _URL_CREDENTIALS.sub(r"\1***@", text)
    cleaned = _KEY_VALUE_SECRET.sub(r"\1\2***", cleaned)
    cleaned = _AUTH_HEADER.sub(r"\1***", cleaned)
    cleaned = _AUTH_SCHEME.sub(r"\1 ***", cleaned)
    return cleaned if limit is None else cleaned[:limit]


def mask_email(email: str) -> str:
    """`grace@example.com` -> `g***@example.com`: enough to recognise, not to harvest."""
    local, at, domain = email.rpartition("@")
    if not at:
        return "***"
    return f"{local[:1]}***@{domain}"


REDACTED = "[REDACTED]"
# Field names whose values are always secret, whatever the value looks like.
_SECRET_FIELD = re.compile(
    r"pass(word|wd|phrase)?|pwd|secret|token|authorization|api[_-]?key|cookie|credential"
    r"|private[_-]?key",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"([A-Za-z0-9._%+'-])[A-Za-z0-9._%+'-]*@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)")


def mask_emails(text: str) -> str:
    """Every address in the text becomes `g***@example.com`."""
    return _EMAIL.sub(r"\1***@\2", text)


def is_secret_field(name: str) -> bool:
    return _SECRET_FIELD.search(name) is not None


def redact_value(value: object) -> object:
    """Strings lose credentials and full emails; containers are redacted all the way down."""
    if isinstance(value, str):
        return mask_emails(redact(value))
    if isinstance(value, Mapping):
        return redact_fields({str(name): item for name, item in value.items()})
    if isinstance(value, list | tuple | set | frozenset):
        return [redact_value(item) for item in value]
    return value


def redact_fields(fields: Mapping[str, object]) -> dict[str, object]:
    """Secret-named fields are replaced whole (numbers and lists too); the rest is cleaned."""
    return {
        name: REDACTED if is_secret_field(name) else redact_value(value)
        for name, value in fields.items()
    }
