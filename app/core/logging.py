"""Structured JSON logging to stdout.

Usage:
    log = get_logger(__name__)
    log.info("user signed in", user_id=str(user.id))

Every line carries the current request id. Never pass passwords, tokens or full emails.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_FIELDS_ATTR = "structured_fields"
_REQUEST_ID_ATTR = "request_id"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Captured when the record was created (StructuredLogger), else read now (other loggers).
        request_id = getattr(record, _REQUEST_ID_ATTR, None) or request_id_var.get()
        if request_id is not None:
            payload["request_id"] = request_id
        fields = getattr(record, _FIELDS_ATTR, None)
        if isinstance(fields, dict):
            payload.update(fields)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class StdoutHandler(logging.Handler):
    """Writes to whatever `sys.stdout` is at emit time (survives stdout being swapped)."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            sys.stdout.write(self.format(record) + "\n")
            sys.stdout.flush()
        except Exception:
            self.handleError(record)


class StructuredLogger:
    """Thin wrapper so call sites pass fields as keyword arguments."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def _log(self, level: int, message: str, exc_info: bool, fields: dict[str, Any]) -> None:
        extra = {_FIELDS_ATTR: fields, _REQUEST_ID_ATTR: request_id_var.get()}
        self._logger.log(level, message, exc_info=exc_info, stacklevel=3, extra=extra)

    def debug(self, message: str, **fields: Any) -> None:
        self._log(logging.DEBUG, message, False, fields)

    def info(self, message: str, **fields: Any) -> None:
        self._log(logging.INFO, message, False, fields)

    def warning(self, message: str, **fields: Any) -> None:
        self._log(logging.WARNING, message, False, fields)

    def error(self, message: str, **fields: Any) -> None:
        self._log(logging.ERROR, message, False, fields)

    def exception(self, message: str, **fields: Any) -> None:
        """Log at ERROR with the current exception's traceback."""
        self._log(logging.ERROR, message, True, fields)


def get_logger(name: str) -> StructuredLogger:
    return StructuredLogger(logging.getLogger(name))


def configure_logging(level: str) -> None:
    """Send all logs, including uvicorn's, to stdout as JSON. Safe to call more than once."""
    handler = StdoutHandler()
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    # Replace only our own handler, so handlers installed by others (e.g. test capture) survive.
    root.handlers = [h for h in root.handlers if not isinstance(h, StdoutHandler)] + [handler]
    root.setLevel(level)

    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
    # Our request middleware logs every request; uvicorn's access log would duplicate it.
    logging.getLogger("uvicorn.access").disabled = True
