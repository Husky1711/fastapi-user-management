"""Section 1.3: structured JSON logging."""

import json
import logging
import threading

import pytest

from app.core import clock
from app.core.logging import (
    AppLogHandler,
    JsonFormatter,
    configure_logging,
    flush_logs,
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
    flush_logs()  # written by the background writer thread
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
        ours = [h for h in root.handlers if isinstance(h, AppLogHandler)]
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


class StuckWriter(logging.Handler):
    """A log writer stuck on a blocked pipe until released."""

    def __init__(self) -> None:
        super().__init__()
        self.unblock = threading.Event()
        self.stuck = threading.Event()  # set once the writer thread is blocked on a record
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.stuck.set()
        self.unblock.wait(timeout=10)
        self.lines.append(self.format(record))


def test_s1_3_33_request_path_never_blocks_and_memory_stays_bounded_when_stdout_is_stuck() -> None:
    writer = StuckWriter()
    handler = configure_logging("INFO", queue_size=5, writer=writer)
    log = get_logger("test")
    try:
        log.info("first")
        assert writer.stuck.wait(timeout=10)  # the writer now holds "first" and is blocked
        for i in range(50):  # would block forever (or grow memory) if logging waited on it
            log.info("busy", n=i)
        assert handler.pending() == 5
        assert handler.dropped == 45  # exact: no slot frees while the writer is stuck
        writer.unblock.set()
        flush_logs()
        log.info("after recovery")
        flush_logs()
        notices = [json.loads(line) for line in writer.lines if '"log records dropped"' in line]
        assert [n["dropped"] for n in notices] == [45]
        assert json.loads(writer.lines[-1])["message"] == "after recovery"
    finally:  # never leave a stuck writer and a full queue to the next test
        writer.unblock.set()
        configure_logging("INFO")


def test_s1_3_36_message_is_fixed_at_the_moment_it_is_logged(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("INFO")
    items = ["first"]
    logging.getLogger("test").info("items: %s", items)
    items.append("changed later")
    flush_logs()
    line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert line["message"] == "items: ['first']"


def test_s1_3_37_credentials_are_redacted_in_messages_fields_and_tracebacks(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("INFO")
    log = get_logger("test")
    log.info("connecting to postgresql://app:pw-in-message@db/x", dsn="redis://:pw-in-field@r:6379")
    try:
        raise ConnectionError("password=pw-in-traceback refused")
    except ConnectionError:
        log.exception("failed")
    flush_logs()
    output = capsys.readouterr().out
    for secret in ("pw-in-message", "pw-in-field", "pw-in-traceback"):
        assert secret not in output
    assert "postgresql://***@db/x" in output


def test_s1_3_34_third_party_log_lines_keep_the_request_id_across_the_queue(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("INFO")
    token = request_id_var.set("uvicorn-req")
    try:
        logging.getLogger("uvicorn.error").warning("from a library")
    finally:
        request_id_var.reset(token)
    flush_logs()
    line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert (line["logger"], line["request_id"]) == ("uvicorn.error", "uvicorn-req")
