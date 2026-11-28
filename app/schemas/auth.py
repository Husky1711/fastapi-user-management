"""Request and response bodies of the auth endpoints."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Input sizes are capped before any rule or hash runs; the password rules (12-128 characters
# after normalisation) are checked by the service and answered with stable codes.
MAX_EMAIL_INPUT = 320
MAX_PASSWORD_INPUT = 1024
MAX_TOKEN_INPUT = 512


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)


class SignupIn(_Input):
    email: str = Field(max_length=MAX_EMAIL_INPUT)
    password: str = Field(max_length=MAX_PASSWORD_INPUT)
    full_name: str | None = Field(default=None, max_length=200)


class LoginIn(_Input):
    email: str = Field(max_length=MAX_EMAIL_INPUT)
    password: str = Field(max_length=MAX_PASSWORD_INPUT)


class RefreshIn(_Input):
    refresh_token: str = Field(min_length=1, max_length=MAX_TOKEN_INPUT)


class SignupAcceptedOut(BaseModel):
    detail: str = "If this email can be used, the account is ready: log in to continue."


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 - the OAuth 2 token type name
    expires_in: int = Field(description="Seconds until the access token expires.")
    refresh_expires_in: int = Field(description="Seconds until the refresh token expires.")


class ReauthIn(BaseModel):
    """The current password again, for actions that need it (ending other sessions)."""

    model_config = ConfigDict(extra="forbid")

    current_password: str | None = Field(default=None, max_length=MAX_PASSWORD_INPUT)


def password_of(body: ReauthIn | None) -> str | None:
    return body.current_password if body is not None else None
