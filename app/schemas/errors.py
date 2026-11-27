"""Error response schemas (RFC 9457 problem details), used to document every error in OpenAPI.

The bodies themselves are built by `app/core/errors.py`; these models describe them.
"""

from typing import Any

from pydantic import BaseModel, Field


class ProblemOut(BaseModel):
    type: str = Field(default="about:blank", examples=["about:blank"])
    title: str = Field(examples=["Not Found"])
    status: int = Field(examples=[404])
    detail: str = Field(examples=["The requested resource was not found."])
    code: str = Field(
        description="Stable, machine-readable error code clients can switch on.",
        examples=["resource.not_found"],
    )
    request_id: str | None = Field(
        description="Quote this when reporting a problem.", examples=["4f1c2e9a0b6d4c37"]
    )


class FieldError(BaseModel):
    # Any: path parts are field names (str) or list indexes (int), as FastAPI reports them.
    loc: list[Any] = Field(examples=[["body", "email"]])
    message: str = Field(examples=["Field required"])
    type: str = Field(examples=["missing"])


class ValidationProblemOut(ProblemOut):
    errors: list[FieldError]


def _problem(model: type[BaseModel], description: str) -> dict[str, Any]:
    # Any: FastAPI's `responses` mapping is untyped.
    return {
        "model": model,
        "description": description,
        "content": {
            "application/problem+json": {
                "schema": {"$ref": f"#/components/schemas/{model.__name__}"}
            }
        },
    }


# Documented on every route.
COMMON_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    500: _problem(ProblemOut, "Unexpected error (no internal details are returned)"),
}
# Documented on every versioned API route, which may take input.
API_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    **COMMON_ERROR_RESPONSES,
    422: _problem(ValidationProblemOut, "The request body or parameters are invalid"),
}
