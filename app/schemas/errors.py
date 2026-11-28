"""Error response schemas (RFC 9457 problem details), used to document every error in OpenAPI.

The bodies themselves are built by `app/core/errors.py`; these models describe them.
"""

from typing import Any

from pydantic import BaseModel, Field
from pydantic.json_schema import models_json_schema


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


_REF = "#/components/schemas/{model}"

# The error models' JSON schemas, added to the OpenAPI components by `app/main.py`. They are
# registered by hand because FastAPI would otherwise also advertise every error response as
# `application/json`, which the API never sends.
_, _all_schemas = models_json_schema(
    [(m, "serialization") for m in (ProblemOut, ValidationProblemOut, FieldError)],
    ref_template=_REF,
)
# Any: JSON schema fragments are arbitrary JSON.
PROBLEM_SCHEMAS: dict[str, Any] = _all_schemas["$defs"]


def _problem(model: type[BaseModel], description: str) -> dict[str, Any]:
    # Any: FastAPI's `responses` mapping is untyped.
    schema = {"$ref": _REF.format(model=model.__name__)}
    return {"description": description, "content": {"application/problem+json": {"schema": schema}}}


# Documented on every route.
COMMON_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    500: _problem(ProblemOut, "Unexpected error (no internal details are returned)"),
}
# Documented on every versioned API route, which may take input.
API_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    **COMMON_ERROR_RESPONSES,
    422: _problem(ValidationProblemOut, "The request body or parameters are invalid"),
}


# Per-route additions (merged with API_ERROR_RESPONSES by the router).
UNAUTHORIZED_RESPONSE: dict[int | str, dict[str, Any]] = {
    401: _problem(ProblemOut, "Not authenticated, or credentials / token not accepted"),
}
NOT_FOUND_RESPONSE: dict[int | str, dict[str, Any]] = {
    404: _problem(ProblemOut, "Not found (or not visible to you)"),
}
