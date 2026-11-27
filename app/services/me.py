"""What a signed-in user does with their own account: sessions and password."""

import unicodedata
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.client import ClientInfo
from app.core.config import Settings
from app.core.errors import NotFound, Unprocessable
from app.core.pagination import PaginationParams
from app.core.security import check_password_rules, hash_password, verify_password
from app.infra.database import end_read, transaction
from app.models import RevokeReason, UserSession
from app.repositories import SessionRepository, Slice, UserRepository
from app.services import audit
from app.services.auth import CurrentUser, InvalidCredentials, count_failed_login


class PasswordUnchanged(Unprocessable):
    default_code = "user.password_unchanged"
    default_detail = "The new password must differ from the current one."


async def list_sessions(
    session: AsyncSession, current: CurrentUser, *, page: PaginationParams, now: datetime
) -> Slice[UserSession]:
    return await SessionRepository(session).list_active(user_id=current.user.id, now=now, page=page)


async def end_session(
    session: AsyncSession,
    current: CurrentUser,
    session_id: UUID,
    *,
    client: ClientInfo,
    now: datetime,
) -> None:
    """End one of the user's sessions. Someone else's id is "not found", like an unknown one."""
    async with transaction(session):
        ended = await SessionRepository(session).revoke_family(
            user_id=current.user.id, family_id=session_id, reason=RevokeReason.REVOKED, now=now
        )
        if ended == 0:
            raise NotFound(code="session.not_found")
        audit.record(
            session,
            action="auth.session_ended",
            client=client,
            actor_user_id=current.user.id,
            target=("session", session_id),
        )


async def end_other_sessions(
    session: AsyncSession, current: CurrentUser, *, client: ClientInfo, now: datetime
) -> None:
    async with transaction(session):
        ended = await SessionRepository(session).revoke_all(
            user_id=current.user.id,
            reason=RevokeReason.REVOKED,
            now=now,
            except_family=current.session_id,
        )
        audit.record(
            session,
            action="auth.other_sessions_ended",
            client=client,
            actor_user_id=current.user.id,
            details={"ended": ended},
        )


async def change_password(
    session: AsyncSession,
    settings: Settings,
    current: CurrentUser,
    *,
    current_password: str,
    new_password: str,
    client: ClientInfo,
    now: datetime,
) -> None:
    """Needs the current password (a stolen access token alone can't take the account).
    Every other session ends; this one stays signed in."""
    check_password_rules(new_password)
    user_id, stored_hash = current.user.id, current.user.password_hash
    await end_read(session)  # no pool connection is held while Argon2 runs
    if not await verify_password(stored_hash, current_password):
        await count_failed_login(session, settings.auth, user_id, client, now)
        raise InvalidCredentials
    if _same(new_password, current_password):
        raise PasswordUnchanged
    new_hash = await hash_password(new_password)
    async with transaction(session):
        user = await UserRepository(session).get_for_update(user_id)
        if user is None:  # deleted meanwhile
            raise InvalidCredentials
        user.password_hash = new_hash
        await SessionRepository(session).revoke_all(
            user_id=user_id,
            reason=RevokeReason.PASSWORD_CHANGED,
            now=now,
            except_family=current.session_id,
        )
        audit.record(session, action="auth.password_changed", client=client, actor_user_id=user_id)


def _same(first: str, second: str) -> bool:
    return unicodedata.normalize("NFKC", first) == unicodedata.normalize("NFKC", second)
