import json
import logging

import pytest

from app.core import clock
from app.core.logging import JsonFormatter, configure_logging, get_logger, request_id_var


def _format(record: logging.LogRecord) -> dict[str, object]:
    result: dict[str, object] = json.loads(JsonFormatter().format(record))
    return result


def test_structured_fields_and_request_id_are_included(caplog: pytest.LogCaptureFixture) -> None:
    token = request_id_var.set("req-123")
    try:
        with caplog.at_level(logging.INFO):
            get_logger("test").info("user signed in", user_id="u-1")
    finally:
        request_id_var.reset(token)

    line = _format(caplog.records[-1])
    assert line["message"] == "user signed in"
    assert line["user_id"] == "u-1"
    assert line["request_id"] == "req-123"
    assert line["level"] == "INFO"
    assert line["logger"] == "test"


def test_request_id_is_omitted_outside_a_request(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        get_logger("test").info("background job")
    assert "request_id" not in _format(caplog.records[-1])


def test_exception_includes_traceback(caplog: pytest.LogCaptureFixture) -> None:
    log = get_logger("test")
    try:
        raise ValueError("boom")
    except ValueError:
        log.exception("failed", step="parse")
    line = _format(caplog.records[-1])
    assert line["level"] == "ERROR"
    assert "ValueError: boom" in str(line["exception"])


@pytest.mark.parametrize("method", ["debug", "warning", "error"])
def test_every_level_is_available(caplog: pytest.LogCaptureFixture, method: str) -> None:
    with caplog.at_level(logging.DEBUG):
        getattr(get_logger("test"), method)("message")
    assert caplog.records[-1].levelname == method.upper()


def test_configure_logging_writes_json_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    get_logger("test").info("hello", answer=42)
    output = capsys.readouterr().out.strip().splitlines()[-1]
    assert json.loads(output)["answer"] == 42
    assert logging.getLogger("uvicorn.access").disabled


def test_clock_is_timezone_aware() -> None:
    assert clock.now().tzinfo is not None
