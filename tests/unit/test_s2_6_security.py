"""Section 2.6: password hashing and input rules (pure logic, no database)."""

import threading
import unicodedata
from typing import Literal

import pytest
from argon2 import PasswordHasher
from argon2.profiles import RFC_9106_LOW_MEMORY

from app.core import security
from app.core.emails import EMAIL_MAX_LENGTH, InvalidEmail, normalize_email
from app.core.errors import AppError
from app.core.redaction import mask_email
from app.core.security import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    WeakPassword,
    check_password_rules,
    hash_password,
    password_needs_rehash,
    verify_password,
)

PASSWORD = "correct horse battery"


async def test_s2_6_01_hash_is_argon2id_with_rfc_9106_parameters_and_verifies() -> None:
    password_hash = await hash_password(PASSWORD)
    assert password_hash.startswith("$argon2id$v=19$m=65536,t=3,p=4$")
    assert PASSWORD not in password_hash
    assert await verify_password(password_hash, PASSWORD)
    assert not password_needs_rehash(password_hash)


async def test_s2_6_02_same_password_hashes_differently_each_time() -> None:
    first, second = await hash_password(PASSWORD), await hash_password(PASSWORD)
    assert first != second
    assert await verify_password(first, PASSWORD)
    assert await verify_password(second, PASSWORD)


@pytest.mark.parametrize(
    "stored",
    [
        "not-a-hash",
        "",
        "$argon2id$v=19$m=65536,t=3,p=4$broken",
        "$2b$12$abcdefghijklmnopqrstuuJ7bGkN0/2Zr6XJhCw6UqVqB3Q8iA4D6",  # bcrypt
    ],
)
async def test_s2_6_03_malformed_or_foreign_hash_never_verifies(stored: str) -> None:
    assert not await verify_password(stored, PASSWORD)
    assert password_needs_rehash(stored)


async def test_s2_6_03_wrong_password_does_not_verify() -> None:
    password_hash = await hash_password(PASSWORD)
    for attempt in ("correct horse battery ", "Correct horse battery", "", PASSWORD[:-1]):
        assert not await verify_password(password_hash, attempt)


async def test_s2_6_03_weaker_old_hash_is_flagged_for_rehash() -> None:
    old = "$argon2id$v=19$m=19456,t=2,p=1$c29tZXNhbHQ$" + "A" * 43
    assert password_needs_rehash(old)


@pytest.mark.parametrize(
    ("length", "accepted"),
    [
        (PASSWORD_MIN_LENGTH - 1, False),
        (PASSWORD_MIN_LENGTH, True),
        (PASSWORD_MAX_LENGTH, True),
        (PASSWORD_MAX_LENGTH + 1, False),
    ],
)
def test_s2_6_04_password_length_boundaries(length: int, accepted: bool) -> None:
    password = "x" * length
    if accepted:
        check_password_rules(password)
    else:
        with pytest.raises(WeakPassword, match="characters"):
            check_password_rules(password)


def test_s2_6_04_password_of_only_spaces_is_refused() -> None:
    with pytest.raises(WeakPassword, match="spaces"):
        check_password_rules(" " * PASSWORD_MIN_LENGTH)


@pytest.mark.parametrize("control", ["\x00", "\x1b", "\n", "\t", "\x7f"])
def test_s2_6_04_password_with_control_characters_is_refused(control: str) -> None:
    with pytest.raises(WeakPassword, match="control characters"):
        check_password_rules(f"long-enough-{control}-password")


def test_s2_6_04_spaces_inside_and_around_a_password_are_kept() -> None:
    check_password_rules("  spaces are fine here  ")


def test_s2_6_04_rule_errors_are_client_errors_with_stable_codes() -> None:
    for error, code in (
        (WeakPassword("x"), "user.password_weak"),
        (InvalidEmail(), "user.email_invalid"),
    ):
        assert isinstance(error, AppError)
        assert (error.status_code, error.code) == (422, code)
    assert InvalidEmail().detail == "Enter an email address like name@example.com."


async def test_s2_6_05_unicode_password_typed_two_ways_verifies() -> None:
    composed = "Ångström-passw0rd"
    decomposed = unicodedata.normalize("NFD", composed)
    assert composed != decomposed
    password_hash = await hash_password(composed)
    assert await verify_password(password_hash, decomposed)
    # Length is counted after normalization, both ways: a ligature expands ("ﬁ" -> "fi")...
    with pytest.raises(WeakPassword, match="at most"):
        check_password_rules("ﬁ" * 65)  # 65 characters typed, 130 after NFKC
    # ...and decomposed characters recombine: 11 composed characters is still too short.
    with pytest.raises(WeakPassword):
        check_password_rules(unicodedata.normalize("NFD", "é" * (PASSWORD_MIN_LENGTH - 1)))


async def test_s2_6_06_hashing_and_verifying_run_off_the_event_loop_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loop_thread = threading.get_ident()
    threads: list[int] = []

    class SpyHasher(PasswordHasher):
        def hash(self, password: str | bytes, *, salt: bytes | None = None) -> str:
            threads.append(threading.get_ident())
            return super().hash(password, salt=salt)

        def verify(self, hash: str | bytes, password: str | bytes) -> Literal[True]:
            threads.append(threading.get_ident())
            return super().verify(hash, password)

    monkeypatch.setattr(security, "_hasher", SpyHasher.from_parameters(RFC_9106_LOW_MEMORY))
    assert await verify_password(await hash_password(PASSWORD), PASSWORD)
    assert len(threads) == 2
    assert loop_thread not in threads


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("grace@example.com", "grace@example.com"),
        ("  Grace.Hopper@EXAMPLE.com \n", "Grace.Hopper@example.com"),
        ("a+tag@sub.example.co.uk", "a+tag@sub.example.co.uk"),
        ("o'brien@example.ie", "o'brien@example.ie"),
        ("x@a-b.io", "x@a-b.io"),
    ],
)
def test_s2_6_07_valid_emails_are_normalised(raw: str, expected: str) -> None:
    assert normalize_email(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "plainaddress",
        "@example.com",
        "grace@",
        "grace@example",
        "grace hopper@example.com",
        "grace@exa mple.com",
        ".grace@example.com",
        "grace.@example.com",
        "gr..ace@example.com",
        "grace@-example.com",
        "grace@example-.com",
        "grace@example..com",
        "grace@example.123",
        "grace@[127.0.0.1]",
        '"quoted"@example.com',
        "grace@exämple.com",
        "a" * 65 + "@example.com",
        "a@" + "b" * 64 + ".com",
        "a@" + ".".join(["b" * 60] * 5) + ".com",  # over 254 characters in total
        "grace@example.com\x00",
    ],
)
def test_s2_6_07_invalid_emails_are_refused(raw: str) -> None:
    with pytest.raises(InvalidEmail):
        normalize_email(raw)


def test_s2_6_07_email_length_limit_is_exact() -> None:
    local = "a" * 64  # the local-part limit
    at_limit = f"{local}@{'b' * 63}.{'c' * 63}.{'d' * 61}"
    over_limit = f"{local}@{'b' * 63}.{'c' * 63}.{'d' * 62}"
    assert (len(at_limit), len(over_limit)) == (EMAIL_MAX_LENGTH, EMAIL_MAX_LENGTH + 1)
    assert normalize_email(at_limit) == at_limit
    with pytest.raises(InvalidEmail):
        normalize_email(over_limit)


def test_s2_6_10_masked_email_hides_the_mailbox() -> None:
    assert mask_email("grace@example.com") == "g***@example.com"
    assert mask_email("no-at-sign") == "***"
