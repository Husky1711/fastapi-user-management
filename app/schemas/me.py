"""Bodies of the `/me` endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import UserSession
from app.schemas.auth import MAX_PASSWORD_INPUT


class MeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None
    email_verified: bool
    created_at: datetime
    last_login_at: datetime | None


class SessionOut(BaseModel):
    """One signed-in device. `id` is the session (family) id used to end it."""

    id: uuid.UUID
    started_at: datetime
    last_used_at: datetime | None
    expires_at: datetime
    ip: str | None
    user_agent: str | None
    current: bool = Field(description="True for the session making this request.")

    @classmethod
    def of(cls, row: UserSession, *, current_family: uuid.UUID) -> "SessionOut":
        """A session row as the user sees it: the family is the session."""
        return cls(
            id=row.family_id,
            started_at=row.family_started_at,
            last_used_at=row.last_used_at,
            expires_at=row.expires_at,
            ip=row.ip,
            user_agent=row.user_agent,
            current=row.family_id == current_family,
        )


class PasswordChangeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(max_length=MAX_PASSWORD_INPUT)
    new_password: str = Field(max_length=MAX_PASSWORD_INPUT)
