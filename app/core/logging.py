"""Structured JSON logging to stdout.

Usage:
    log = get_logger(__name__)
    log.info("user signed in", user_id=str(user.id))

Every line carries the current request id. Never pass passwords, tokens or full emails; as a
safety net, credentials in messages, string fields and tracebacks are redacted anyway.

Writing to stdout can block (a slow log pipe), so the request path never writes: records go
onto a bounded in-memory queue and a background thread formats and writes them. If the queue
is full (the writer is stuck), new records are dropped and counted rather than growing memory
or blocking requests; the count is logged once the writer catches up.
"""

import atexit
import json
import logging
import queue
import sys
import threading
from contextvars import ContextVar
from datetime import UTC, datetime
from logging.handlers import QueueHandler, QueueListener

from app.core.redaction import redact

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

DEFAULT_QUEUE_SIZE = 10_000
_FIELDS_ATTR = "structured_fields"
_REQUEST_ID_ATTR = "request_id"
# Keys the formatter owns. A structured field with one of these names is kept under
# "field_<name>" instead of overwriting it.
RESERVED_KEYS = frozenset({"timestamp", "level", "logger", "message", "request_id", "exception"})


def _clean(value: object) -> object:
    return redact(value) if isinstance(value, str) else value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        # Captured when the record was created (StructuredLogger, AppLogHandler), else read now.
        request_id = getattr(record, _REQUEST_ID_ATTR, None) or request_id_var.get()
        if request_id is not None:
            payload["request_id"] = request_id
        fields = getattr(record, _FIELDS_ATTR, None)
        if isinstance(fields, dict):
            for key, value in fields.items():
                payload[f"field_{key}" if key in RESERVED_KEYS else key] = _clean(value)
        exception = record.exc_text or (
            self.formatException(record.exc_info) if record.exc_info else None
        )
        if exception:
            payload["exception"] = redact(exception)
        return json.dumps(payload, default=str)


class StdoutHandler(logging.Handler):
    """Writes to whatever `sys.stdout` is at emit time (survives stdout being swapped)."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            sys.stdout.write(self.format(record) + "\n")
            sys.stdout.flush()
        except Exception:
            self.handleError(record)


class AppLogHandler(QueueHandler):
    """Root handler: queues records for the writer thread; never blocks the caller."""

    def __init__(self, log_queue: "queue.Queue[logging.LogRecord]") -> None:
        super().__init__(log_queue)
        self.dropped = 0
        self._lock = threading.Lock()

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        # Freeze everything that could change before the writer thread gets to the record:
        # the message (mutable args), the traceback text (frees the frames) and the request id
        # (the writer thread has no request context).
        record.msg = record.getMessage()
        record.args = None
        if record.exc_info:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
            record.exc_info = None
        if getattr(record, _REQUEST_ID_ATTR, None) is None:
            setattr(record, _REQUEST_ID_ATTR, request_id_var.get())
        return record

    def enqueue(self, record: logging.LogRecord) -> None:
        with self._lock:
            if self.dropped and self._try_put(_dropped_notice(self.dropped)):
                self.dropped = 0
            if not self._try_put(record):
                self.dropped += 1

    def _try_put(self, record: logging.LogRecord) -> bool:
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            return False
        return True


def _dropped_notice(count: int) -> logging.LogRecord:
    record = logging.LogRecord(
        __name__, logging.WARNING, __file__, 0, "log records dropped", None, None
    )
    setattr(record, _FIELDS_ATTR, {"dropped": count})
    return record


_log_queue: "queue.Queue[logging.LogRecord] | None" = None
_listener: QueueListener | None = None


def flush_logs() -> None:
    """Block until every queued record has been written (tests, shutdown)."""
    if _log_queue is not None:
        _log_queue.join()


def _stop_writer() -> None:
    global _listener
    if _listener is not None:
        _listener.stop()  # writes what is still queued, then ends the thread
        _listener = None


atexit.register(_stop_writer)


class StructuredLogger:
    """Thin wrapper so call sites pass fields as keyword arguments."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def _log(self, level: int, message: str, exc_info: bool, fields: dict[str, object]) -> None:
        extra = {_FIELDS_ATTR: fields, _REQUEST_ID_ATTR: request_id_var.get()}
        self._logger.log(level, message, exc_info=exc_info, stacklevel=3, extra=extra)

    # Fields are passed as keyword arguments, so a field called "message" would clash with the
    # positional parameter. Positional-only parameters ("/") avoid that.
    def debug(self, message: str, /, **fields: object) -> None:
        self._log(logging.DEBUG, message, False, fields)

    def info(self, message: str, /, **fields: object) -> None:
        self._log(logging.INFO, message, False, fields)

    def warning(self, message: str, /, **fields: object) -> None:
        self._log(logging.WARNING, message, False, fields)

    def error(self, message: str, /, **fields: object) -> None:
        self._log(logging.ERROR, message, False, fields)

    def exception(self, message: str, /, **fields: object) -> None:
        """Log at ERROR with the current exception's traceback."""
        self._log(logging.ERROR, message, True, fields)


def get_logger(name: str) -> StructuredLogger:
    return StructuredLogger(logging.getLogger(name))


def configure_logging(
    level: str,
    *,
    queue_size: int = DEFAULT_QUEUE_SIZE,
    writer: logging.Handler | None = None,
) -> AppLogHandler:
    """Send all logs, including uvicorn's, to stdout as JSON. Safe to call more than once.

    `writer` replaces the stdout writer (tests use it to simulate a stuck log pipe).
    """
    global _log_queue, _listener
    new_queue: queue.Queue[logging.LogRecord] = queue.Queue(maxsize=queue_size)
    writer = writer or StdoutHandler()
    writer.setFormatter(JsonFormatter())
    new_listener = QueueListener(new_queue, writer)
    new_listener.start()
    handler = AppLogHandler(new_queue)

    # Swap the root handler first, then stop the old writer (which drains its queue), so no
    # record is ever sent to a queue that nobody reads.
    root = logging.getLogger()
    root.handlers = [h for h in root.handlers if not isinstance(h, AppLogHandler)] + [handler]
    root.setLevel(level)
    _stop_writer()
    _log_queue, _listener = new_queue, new_listener

    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
    # Our request middleware logs every request; uvicorn's access log would duplicate it.
    logging.getLogger("uvicorn.access").disabled = True
    return handler
