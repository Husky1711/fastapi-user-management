"""What a signed-in user does with their own account: sessions and password."""

import unicodedata
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.client import ClientInfo
from app.core.config import Settings
from app.core.errors import NotFound, Unprocessable
from app.core.pagination import PaginationParams
from app.core.security import InvalidToken, check_password_rules, hash_password
from app.infra.database import transaction
from app.models import RevokeReason, User, UserSession
from app.repositories import SessionRepository, Slice
from app.services import audit
from app.services.auth import (
    CurrentUser,
    InvalidCredentials,
    can_log_in,
    lock_user,
    verify_current_password,
)

CHANGE_FAILED_ACTION = "auth.password_change_failed"
CHANGE_REFUSED_ACTION = "auth.password_change_refused"


class PasswordUnchanged(Unprocessable):
    default_code = "user.password_unchanged"
    default_detail = "The new password must differ from the current one."


async def list_sessions(
    session: AsyncSession, current: CurrentUser, *, page: PaginationParams, now: datetime
) -> Slice[UserSession]:
    return await SessionRepository(session).list_active(user_id=current.user.id, now=now, page=page)


async def end_session(
    session: AsyncSession,
    settings: Settings,
    current: CurrentUser,
    session_id: UUID,
    *,
    current_password: str | None,
    client: ClientInfo,
    now: datetime,
) -> None:
    """End one of the user's sessions. Someone else's id is "not found", like an unknown one.
    Ending another device's session needs the current password again (ASVS V3.3.4) when
    `AUTH__REAUTH_TO_END_SESSIONS` is on; ending this one is a logout and doesn't."""
    if session_id != current.session_id and settings.auth.reauth_to_end_sessions:
        await verify_current_password(
            session, settings, current, current_password, client=client, now=now
        )
    async with transaction(session):
        await lock_user(session, current.user.id)
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
    session: AsyncSession,
    settings: Settings,
    current: CurrentUser,
    *,
    current_password: str | None,
    client: ClientInfo,
    now: datetime,
) -> None:
    if settings.auth.reauth_to_end_sessions:
        await verify_current_password(
            session, settings, current, current_password, client=client, now=now
        )
    async with transaction(session):
        await lock_user(session, current.user.id)
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
    """Needs the current password (a stolen access token alone can't take the account),
    and is refused while the account is locked, like a login. Every other session ends;
    this one stays signed in."""
    check_password_rules(new_password)
    user_id = current.user.id
    stored_hash = await verify_current_password(
        session,
        settings,
        current,
        current_password,
        client=client,
        now=now,
        failed_action=CHANGE_FAILED_ACTION,
        refused_action=CHANGE_REFUSED_ACTION,
    )
    if _same(new_password, current_password):
        raise PasswordUnchanged
    new_hash = await hash_password(new_password)
    async with transaction(session):
        user = await lock_user(session, user_id)
        refusal = await _refusal_under_lock(session, user, current.session_id, stored_hash, now)
        if user is not None and refusal is None:
            await _replace_password(session, user, current.session_id, new_hash, now)
        action = CHANGE_REFUSED_ACTION if refusal else "auth.password_changed"
        actor = user_id if user is not None else None  # a removed user can't be referenced
        audit.record(session, action=action, client=client, actor_user_id=actor)
    if refusal is not None:  # raised after the commit, so the "refused" audit entry is kept
        raise refusal


async def _refusal_under_lock(
    session: AsyncSession, user: User | None, family_id: UUID, verified_hash: str, now: datetime
) -> InvalidCredentials | InvalidToken | None:
    """What was checked before the slow hashing may have changed since: the session may
    have ended, the account may be locked, disabled or removed, or the password changed by
    another request."""
    if user is None or not can_log_in(user, now):
        return InvalidCredentials()
    if user.password_hash != verified_hash:
        return InvalidCredentials()
    live = await SessionRepository(session).active_in_family(
        user_id=user.id, family_id=family_id, now=now
    )
    return InvalidToken() if live is None else None


async def _replace_password(
    session: AsyncSession, user: User, keep_family: UUID, new_hash: str, now: datetime
) -> None:
    user.password_hash = new_hash
    user.failed_login_count = 0
    await SessionRepository(session).revoke_all(
        user_id=user.id,
        reason=RevokeReason.PASSWORD_CHANGED,
        now=now,
        except_family=keep_family,
    )


def _same(first: str, second: str) -> bool:
    return unicodedata.normalize("NFKC", first) == unicodedata.normalize("NFKC", second)
