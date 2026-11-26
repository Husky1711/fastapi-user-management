"""Section 1.3: structured JSON logging."""

import json
import logging

import pytest

from app.core import clock
from app.core.logging import (
    JsonFormatter,
    StdoutHandler,
    configure_logging,
    get_logger,
    request_id_var,
)


def _line(record: logging.LogRecord) -> dict[str, object]:
    parsed: dict[str, object] = json.loads(JsonFormatter().format(record))
    return parsed


def test_s1_3_01_fields_and_request_id_are_in_the_line(caplog: pytest.LogCaptureFixture) -> None:
    token = request_id_var.set("req-123")
    try:
        with caplog.at_level(logging.INFO):
            get_logger("test").info("user signed in", user_id="u-1")
    finally:
        request_id_var.reset(token)
    line = _line(caplog.records[-1])
    assert line["message"] == "user signed in"
    assert line["user_id"] == "u-1"
    assert line["request_id"] == "req-123"
    assert (line["level"], line["logger"]) == ("INFO", "test")


def test_s1_3_02_no_request_id_outside_a_request(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        get_logger("test").info("background job")
    assert "request_id" not in _line(caplog.records[-1])


def test_s1_3_03_exception_includes_the_traceback(caplog: pytest.LogCaptureFixture) -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        get_logger("test").exception("failed", step="parse")
    line = _line(caplog.records[-1])
    assert line["level"] == "ERROR"
    assert "ValueError: boom" in str(line["exception"])


@pytest.mark.parametrize("level", ["debug", "warning", "error"])
def test_s1_3_04_every_level_is_available(caplog: pytest.LogCaptureFixture, level: str) -> None:
    with caplog.at_level(logging.DEBUG):
        getattr(get_logger("test"), level)("message")
    assert caplog.records[-1].levelname == level.upper()


def test_s1_3_05_json_goes_to_stdout_and_uvicorn_access_log_is_off(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("INFO")
    get_logger("test").info("hello", answer=42)
    output = capsys.readouterr().out.strip().splitlines()[-1]
    assert json.loads(output)["answer"] == 42
    assert logging.getLogger("uvicorn.access").disabled


def test_s1_3_06_configuring_twice_keeps_one_handler_and_foreign_handlers() -> None:
    root = logging.getLogger()
    foreign = logging.NullHandler()
    root.addHandler(foreign)
    try:
        configure_logging("INFO")
        configure_logging("INFO")
        ours = [h for h in root.handlers if isinstance(h, StdoutHandler)]
        assert len(ours) == 1
        assert foreign in root.handlers
    finally:
        root.removeHandler(foreign)


def test_s1_3_07_fields_named_like_reserved_keys_cannot_overwrite_them(
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = request_id_var.set("real-id")
    try:
        with caplog.at_level(logging.INFO):
            get_logger("test").info(
                "real message", message="fake", level="fake", request_id="fake", timestamp="x"
            )
    finally:
        request_id_var.reset(token)
    line = _line(caplog.records[-1])
    assert (line["message"], line["level"], line["request_id"]) == (
        "real message",
        "INFO",
        "real-id",
    )
    assert line["field_message"] == "fake"
    assert line["field_request_id"] == "fake"


def test_s1_3_27_clock_is_timezone_aware_utc() -> None:
    offset = clock.now().utcoffset()
    assert offset is not None
    assert offset.total_seconds() == 0
