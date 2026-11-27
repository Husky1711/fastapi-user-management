"""Authentication: who is calling, and the flows that create and end sessions."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import JwtSettings
from app.core.security import InvalidToken, decode_access_token
from app.models import User, UserSession, UserStatus


@dataclass(frozen=True, slots=True)
class CurrentUser:
    user: User
    session_id: UUID  # the session family the access token belongs to


async def authenticate(
    session: AsyncSession, settings: JwtSettings, token: str, *, now: datetime
) -> CurrentUser:
    """The user behind an access token, if the token is valid, the user active and the
    session (family) still live. One query. Raises `InvalidToken` for every failure."""
    claims = decode_access_token(settings, token, now=now)
    live_session = exists().where(
        UserSession.user_id == User.id,
        UserSession.family_id == claims.session_id,
        UserSession.revoked_at.is_(None),
        UserSession.expires_at > now,
    )
    statement = select(User).where(
        User.id == claims.user_id,
        User.status == UserStatus.ACTIVE,
        User.deleted_at.is_(None),
        live_session,
    )
    user = (await session.execute(statement)).scalar_one_or_none()
    if user is None:
        raise InvalidToken
    return CurrentUser(user=user, session_id=claims.session_id)
