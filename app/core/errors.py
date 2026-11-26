"""Application errors and their HTTP representation (RFC 9457 problem details).

Services raise `AppError` subclasses; they never build HTTP responses. Handlers registered
here turn every error into the same JSON shape:

    {"type": "about:blank", "title": "Not Found", "status": 404,
     "detail": "...", "code": "user.not_found", "request_id": "..."}

`code` is a stable, machine-readable string clients can switch on.
"""

from collections.abc import Mapping
from http import HTTPStatus
from typing import ClassVar

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import request_id_var

PROBLEM_CONTENT_TYPE = "application/problem+json"


class AppError(Exception):
    """Base class for errors that map to a client-facing HTTP response."""

    status_code: ClassVar[int] = HTTPStatus.BAD_REQUEST
    default_code: ClassVar[str] = "request.invalid"
    default_detail: ClassVar[str] = "The request could not be processed."

    def __init__(
        self,
        detail: str | None = None,
        *,
        code: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.detail = detail or self.default_detail
        self.code = code or self.default_code
        self.headers = headers
        super().__init__(self.detail)


class BadRequest(AppError):
    pass


class Unauthorized(AppError):
    status_code = HTTPStatus.UNAUTHORIZED
    default_code = "auth.not_authenticated"
    default_detail = "Authentication is required."


class Forbidden(AppError):
    status_code = HTTPStatus.FORBIDDEN
    default_code = "auth.forbidden"
    default_detail = "You do not have permission to perform this action."


class NotFound(AppError):
    status_code = HTTPStatus.NOT_FOUND
    default_code = "resource.not_found"
    default_detail = "The requested resource was not found."


class Conflict(AppError):
    status_code = HTTPStatus.CONFLICT
    default_code = "resource.conflict"
    default_detail = "The request conflicts with the current state of the resource."


class RateLimited(AppError):
    status_code = HTTPStatus.TOO_MANY_REQUESTS
    default_code = "rate_limit.exceeded"
    default_detail = "Too many requests. Try again later."


def _status_phrase(status: int) -> str:
    try:
        return HTTPStatus(status).phrase
    except ValueError:  # non-standard codes such as 499 from a library
        return "Error"


def problem_response(
    status: int,
    code: str,
    detail: str,
    *,
    headers: Mapping[str, str] | None = None,
    extra: Mapping[str, object] | None = None,
) -> JSONResponse:
    body: dict[str, object] = {
        "type": "about:blank",
        "title": _status_phrase(status),
        "status": status,
        "detail": detail,
        "code": code,
        "request_id": request_id_var.get(),
    }
    if extra:
        body.update(extra)
    return JSONResponse(body, status_code=status, headers=headers, media_type=PROBLEM_CONTENT_TYPE)


def internal_error_response() -> JSONResponse:
    """Generic 500. Never includes exception details, which may contain secrets."""
    return problem_response(
        HTTPStatus.INTERNAL_SERVER_ERROR,
        "server.internal_error",
        "An unexpected error occurred. Quote the request_id when reporting it.",
    )


async def _app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, AppError):  # registered only for AppError
        raise exc
    return problem_response(exc.status_code, exc.code, exc.detail, headers=exc.headers)


async def _validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):  # registered only for this type
        raise exc
    # Deliberately drop the "input" and "ctx" keys: they echo request values back,
    # which could include passwords or tokens.
    errors = [
        {"loc": list(err["loc"]), "message": err["msg"], "type": err["type"]}
        for err in exc.errors()
    ]
    return problem_response(
        HTTPStatus.UNPROCESSABLE_ENTITY,
        "request.validation_failed",
        "The request body or parameters are invalid.",
        extra={"errors": errors},
    )


async def _http_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    # Raised by the framework itself (unknown route, wrong method). Our code raises AppError.
    if not isinstance(exc, StarletteHTTPException):  # registered only for this type
        raise exc
    try:
        status = HTTPStatus(exc.status_code)
    except ValueError:  # non-standard code: keep it, but use generic wording
        code, description = f"http.{exc.status_code}", "The request could not be processed."
    else:
        code, description = f"http.{status.name.lower()}", status.description
    detail = exc.detail if isinstance(exc.detail, str) else description
    return problem_response(exc.status_code, code, detail, headers=exc.headers)


def register_exception_handlers(app: FastAPI) -> None:
    """Unexpected exceptions are handled by RequestContextMiddleware, which owns the 500."""
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
