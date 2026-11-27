"""What a signed-in user does with their own account: sessions and password."""

import unicodedata
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.client import ClientInfo
from app.core.config import Settings
from app.core.errors import NotFound, Unprocessable
from app.core.pagination import PaginationParams
from app.core.security import check_password_rules, hash_password
from app.infra.database import transaction
from app.models import RevokeReason, User, UserSession
from app.repositories import SessionRepository, Slice
from app.services import audit
from app.services.auth import (
    REAUTH_REFUSED,
    CurrentUser,
    Refusal,
    lock_and_recheck,
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
    verified = None
    if session_id != current.session_id and settings.auth.reauth_to_end_sessions:
        verified = await verify_current_password(
            session, settings, current, current_password, client=client, now=now
        )
    async with transaction(session):
        _, refusal = await lock_and_recheck(session, current, verified, now)
        if refusal is None:
            ended = await SessionRepository(session).revoke_family(
                user_id=current.user.id, family_id=session_id, reason=RevokeReason.REVOKED, now=now
            )
            if ended == 0:
                raise NotFound(code="session.not_found")
        _audit_outcome(session, current, client, refusal, "auth.session_ended", session_id)
    if refusal is not None:  # raised after the commit, so the refusal stays audited
        raise refusal


async def end_other_sessions(
    session: AsyncSession,
    settings: Settings,
    current: CurrentUser,
    *,
    current_password: str | None,
    client: ClientInfo,
    now: datetime,
) -> None:
    verified = None
    if settings.auth.reauth_to_end_sessions:
        verified = await verify_current_password(
            session, settings, current, current_password, client=client, now=now
        )
    async with transaction(session):
        _, refusal = await lock_and_recheck(session, current, verified, now)
        if refusal is None:
            await SessionRepository(session).revoke_all(
                user_id=current.user.id,
                reason=RevokeReason.REVOKED,
                now=now,
                except_family=current.session_id,
            )
        _audit_outcome(session, current, client, refusal, "auth.other_sessions_ended")
    if refusal is not None:
        raise refusal


def _audit_outcome(
    session: AsyncSession,
    current: CurrentUser,
    client: ClientInfo,
    refusal: Refusal | None,
    action: str,
    session_id: UUID | None = None,
) -> None:
    audit.record(
        session,
        action=REAUTH_REFUSED if refusal is not None else action,
        client=client,
        actor_user_id=current.user.id,
        target=("session", session_id) if session_id is not None else None,
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
    within the session's re-entry budget (ADR-0012). Every other session ends; this one
    stays signed in."""
    check_password_rules(new_password)
    if _same(new_password, current_password):  # decided on the inputs: reveals nothing
        raise PasswordUnchanged
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
    new_hash = await hash_password(new_password)
    async with transaction(session):
        user, refusal = await lock_and_recheck(session, current, stored_hash, now)
        if user is not None and refusal is None:
            await _replace_password(session, user, current.session_id, new_hash, now)
        action = CHANGE_REFUSED_ACTION if refusal else "auth.password_changed"
        actor = user.id if user is not None else None  # a removed user can't be referenced
        audit.record(session, action=action, client=client, actor_user_id=actor)
    if refusal is not None:  # raised after the commit, so the "refused" audit entry is kept
        raise refusal


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
