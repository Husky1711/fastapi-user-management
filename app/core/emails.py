"""Email address syntax rules (no sending; verification by email is roadmap step 6).

Deliberately strict and simple: the subset of RFC 5321/5322 that real mailboxes use. No
quoted local parts, no IP-literal domains, no comments, no internationalised (IDN) domains
(ADR-0009).
"""

import re

from app.core.errors import Unprocessable

EMAIL_MAX_LENGTH = 254  # RFC 5321 path limit
LOCAL_PART_MAX_LENGTH = 64

_LOCAL_PART = re.compile(r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*")
_DOMAIN_LABEL = re.compile(r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?")


class InvalidEmail(Unprocessable):
    """The address is not a usable email address. The message is safe to show."""

    default_code = "user.email_invalid"
    default_detail = "Enter an email address like name@example.com."


def normalize_email(raw: str) -> str:
    """Return the address with surrounding spaces removed and the domain lower-cased.

    The local part keeps its case (some servers treat it as case-sensitive); uniqueness is
    case-insensitive anyway because the database column is citext.
    """
    email = raw.strip()
    local, at, domain = email.rpartition("@")
    domain = domain.lower()
    if not at or not local or not domain:
        raise InvalidEmail
    labels = domain.split(".")
    if (
        len(email) > EMAIL_MAX_LENGTH
        or len(local) > LOCAL_PART_MAX_LENGTH
        or not _LOCAL_PART.fullmatch(local)
        or len(labels) < 2
        or not all(_DOMAIN_LABEL.fullmatch(label) for label in labels)
        or labels[-1].isdigit()
    ):
        raise InvalidEmail
    return f"{local}@{domain}"
