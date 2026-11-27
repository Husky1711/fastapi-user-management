"""Refresh-token sessions. Every query is scoped by the owning user (sessions are not tenant
data), so one user can never read or revoke another user's sessions."""

from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import ColumnElement, CursorResult, select, update

from app.core.pagination import PaginationParams
from app.models import RevokeReason, UserSession
from app.repositories.base import Repository, Slice


def _active(now: datetime) -> ColumnElement[bool]:
    return (UserSession.revoked_at.is_(None)) & (UserSession.expires_at > now)


class SessionRepository(Repository):
    # User-scoped, not organization-scoped (2.5-11 still checks the declaration).
    unscoped = frozenset(
        {
            "add",
            "get_by_token_hash",
            "active_in_family",
            "list_active",
            "revoke_family",
            "revoke_all",
            "revoke_same_device",
            "oldest_active_families",
        }
    )

    def add(self, session: UserSession) -> None:
        self.session.add(session)

    async def get_by_token_hash(
        self, token_hash: bytes, *, for_update: bool = False
    ) -> UserSession | None:
        """Any row with this hash, revoked or not (a revoked `rotated` row means reuse)."""
        statement = select(UserSession).where(UserSession.token_hash == token_hash)
        if for_update:  # and re-read: a concurrent refresh may have just rotated it
            statement = statement.with_for_update().execution_options(populate_existing=True)
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def active_in_family(
        self, *, user_id: UUID, family_id: UUID, now: datetime
    ) -> UserSession | None:
        statement = select(UserSession).where(
            UserSession.user_id == user_id, UserSession.family_id == family_id, _active(now)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def list_active(
        self, *, user_id: UUID, now: datetime, page: PaginationParams
    ) -> Slice[UserSession]:
        statement = (
            select(UserSession)
            .where(UserSession.user_id == user_id, _active(now))
            .order_by(UserSession.family_started_at.desc(), UserSession.id)
        )
        return await self._page(statement, page)

    async def oldest_active_families(
        self, *, user_id: UUID, now: datetime, keep: int
    ) -> list[UUID]:
        """Families beyond the newest `keep`, oldest first (for `limit_sessions`)."""
        statement = (
            select(UserSession.family_id)
            .where(UserSession.user_id == user_id, _active(now))
            .order_by(UserSession.family_started_at.desc(), UserSession.id)
            .offset(keep)
        )
        return list((await self.session.execute(statement)).scalars())

    async def revoke_family(
        self, *, user_id: UUID, family_id: UUID, reason: RevokeReason, now: datetime
    ) -> int:
        return await self._revoke(
            reason, now, UserSession.user_id == user_id, UserSession.family_id == family_id
        )

    async def revoke_all(
        self,
        *,
        user_id: UUID,
        reason: RevokeReason,
        now: datetime,
        except_family: UUID | None = None,
    ) -> int:
        conditions = [UserSession.user_id == user_id]
        if except_family is not None:
            conditions.append(UserSession.family_id != except_family)
        return await self._revoke(reason, now, *conditions)

    async def revoke_same_device(
        self, *, user_id: UUID, user_agent: str, reason: RevokeReason, now: datetime
    ) -> int:
        return await self._revoke(
            reason, now, UserSession.user_id == user_id, UserSession.user_agent == user_agent
        )

    async def _revoke(
        self, reason: RevokeReason, now: datetime, *conditions: ColumnElement[bool]
    ) -> int:
        """One bulk UPDATE; rows already revoked keep their first reason."""
        statement = (
            update(UserSession)
            .where(UserSession.revoked_at.is_(None), *conditions)
            .values(revoked_at=now, revoked_reason=reason)
            .execution_options(synchronize_session=False)
        )
        result = cast("CursorResult[Any]", await self.session.execute(statement))
        return result.rowcount
