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
    r"""(["']?\b(?:[a-z0-9]+[_-])*(?:password|passwd|passphrase|pwd|secret|token|api[_-]?key"""
    r"""|client[_-]?secret)["']?\s*[=:]\s*)"""
    # a quoted value runs to its closing quote (passphrases have spaces); a bare one to a
    # space or separator
    r"""("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|[^\s;&,'"}]+)""",
    re.IGNORECASE,
)


def _mask_value(match: re.Match[str]) -> str:
    value = match.group(2)
    quote = value[0] if value[0] in "\"'" else ""
    return f"{match.group(1)}{quote}***{quote}"


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
    cleaned = _KEY_VALUE_SECRET.sub(_mask_value, cleaned)
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
# Field names whose values are always secret, whatever the value looks like. A name is split
# into words (`_`, `-`, `.`, spaces, camelCase); it is secret when its last word is one of
# these, or its last two words are one of the pairs: `new_password`, `apiKey`, `token_hash`
# are secret, `compass`, `bypass_cache`, `token_type` are not.
_SECRET_LAST_WORDS = frozenset(
    {
        "password",
        "passwd",
        "passphrase",
        "pass",
        "pwd",
        "secret",
        "token",
        "authorization",
        "cookie",
        "cookies",
        "credential",
        "credentials",
        "apikey",
    }
)
_SECRET_LAST_PAIRS = frozenset(
    {("api", "key"), ("private", "key"), ("secret", "key"), ("password", "hash"), ("token", "hash")}
)
_WORD_BREAK = re.compile(r"[_\-.\s]+|(?<=[a-z0-9])(?=[A-Z])")
_EMAIL = re.compile(r"([A-Za-z0-9._%+'-])[A-Za-z0-9._%+'-]*@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)")


def mask_emails(text: str) -> str:
    """Every address in the text becomes `g***@example.com`."""
    return _EMAIL.sub(r"\1***@\2", text)


def is_secret_field(name: str) -> bool:
    words = [word.lower() for word in _WORD_BREAK.split(name) if word]
    if not words:
        return False
    return words[-1] in _SECRET_LAST_WORDS or tuple(words[-2:]) in _SECRET_LAST_PAIRS


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
