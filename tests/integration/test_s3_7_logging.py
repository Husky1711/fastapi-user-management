"""Section 3.7: client disconnects on body routes (499) and broader log redaction."""

import json
import logging

import pytest
from starlette.types import Message

from app.core.logging import JsonFormatter, get_logger
from app.core.middleware import CLIENT_CLOSED_REQUEST
from app.core.redaction import REDACTED
from tests.helpers import RecordingSend, app_with, http_scope

LOGIN = "/api/v1/auth/login"


def _lines(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    return [json.loads(JsonFormatter().format(r)) for r in caplog.records]


def _log(caplog: pytest.LogCaptureFixture, message: str, **fields: object) -> dict[str, object]:
    caplog.clear()
    with caplog.at_level(logging.INFO, logger="test.redaction"):
        get_logger("test.redaction").info(message, **fields)
    return _lines(caplog)[-1]


async def test_s3_7_01_disconnect_while_reading_a_json_body_is_logged_as_499(
    caplog: pytest.LogCaptureFixture,
) -> None:
    messages: list[Message] = [
        {"type": "http.request", "body": b'{"email": "a@example.com", "pass', "more_body": True},
        {"type": "http.disconnect"},
    ]

    async def receive() -> Message:
        return messages.pop(0) if messages else {"type": "http.disconnect"}

    send = RecordingSend()
    scope = http_scope("POST", LOGIN)
    scope["headers"] = [(b"content-type", b"application/json")]
    with caplog.at_level(logging.INFO):
        await app_with()(scope, receive, send)
    assert send.messages == []  # nobody to answer: no 400 is sent
    access = [line for line in _lines(caplog) if line["message"] == "request"]
    assert access[-1]["status"] == CLIENT_CLOSED_REQUEST
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


@pytest.mark.parametrize(
    ("body", "status"), [(b'{"email": "a@example.com"}', 422), (b"{not json", 422)]
)
async def test_s3_7_02_ordinary_body_errors_still_get_their_answer(
    caplog: pytest.LogCaptureFixture, body: bytes, status: int
) -> None:
    async def receive() -> Message:
        return {"type": "http.request", "body": body, "more_body": False}

    send = RecordingSend()
    scope = http_scope("POST", LOGIN)
    scope["headers"] = [(b"content-type", b"application/json")]
    await app_with()(scope, receive, send)
    assert send.messages[0]["status"] == status


@pytest.mark.parametrize(
    "name",
    [
        "password",
        "new_password",
        "Refresh_Token",
        "SECRET",
        "authorization",
        "api_key",
        "apiKey",
        "cookie",
    ],
)
def test_s3_7_03_fields_named_like_secrets_are_replaced(
    caplog: pytest.LogCaptureFixture, name: str
) -> None:
    line = _log(caplog, "event", **{name: "s3cr3t-value"})
    assert line[name] == REDACTED
    assert "s3cr3t-value" not in json.dumps(line)


def test_s3_7_04_secret_values_of_any_type_are_redacted(caplog: pytest.LogCaptureFixture) -> None:
    line = _log(
        caplog,
        "event",
        token=123456,
        password=["a", "b"],
        payload={"user": {"password": "nested-pw", "email": "grace@example.com"}, "count": 3},
        tags=["x", "contact bob@example.org"],
    )
    assert (line["token"], line["password"]) == (REDACTED, REDACTED)
    assert line["payload"] == {
        "user": {"password": REDACTED, "email": "g***@example.com"},
        "count": 3,
    }
    assert line["tags"] == ["x", "contact b***@example.org"]
    assert "nested-pw" not in json.dumps(line)


@pytest.mark.parametrize(
    ("message", "secret"),
    [
        ("login with password=hunter2 failed", "hunter2"),
        ("header Authorization: Bearer eyJhbGciOi.payload.sig", "eyJhbGciOi"),
        ('body {"refresh_token": "abc123xyz"}', "abc123xyz"),
        ("token: t0k3n-value seen", "t0k3n-value"),
        ("Basic dXNlcjpwYXNzd29yZA== sent", "dXNlcjpwYXNzd29yZA"),
        ("user grace.hopper@example.com logged in", "grace.hopper"),
    ],
)
def test_s3_7_05_secrets_inside_messages_are_masked(
    caplog: pytest.LogCaptureFixture, message: str, secret: str
) -> None:
    line = _log(caplog, message)
    assert secret not in str(line["message"])


@pytest.mark.parametrize(
    "message",
    ["password reset email sent", "token expired", "the secret garden", "invalid api key format"],
)
def test_s3_7_06_messages_that_only_mention_the_words_are_untouched(
    caplog: pytest.LogCaptureFixture, message: str
) -> None:
    assert _log(caplog, message)["message"] == message
