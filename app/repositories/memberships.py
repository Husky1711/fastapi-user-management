from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.core.pagination import PaginationParams
from app.models import Membership
from app.repositories.base import Repository, Slice


class MembershipRepository(Repository):
    unscoped = frozenset({"add", "list_for_user"})  # insert; a user's own memberships

    def add(self, membership: Membership) -> None:
        self.session.add(membership)

    async def get(self, *, organization_id: UUID, user_id: UUID) -> Membership | None:
        """The user's membership in this organization, with its role loaded."""
        statement = (
            select(Membership)
            .where(Membership.organization_id == organization_id, Membership.user_id == user_id)
            .options(joinedload(Membership.role))
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def list_members(
        self, *, organization_id: UUID, page: PaginationParams
    ) -> Slice[Membership]:
        """Oldest first; each membership comes with its user and role (one query, no N+1)."""
        statement = (
            select(Membership)
            .where(Membership.organization_id == organization_id)
            .options(joinedload(Membership.user), joinedload(Membership.role))
            .order_by(Membership.created_at, Membership.id)
        )
        return await self._page(statement, page)

    async def list_for_user(self, user_id: UUID, page: PaginationParams) -> Slice[Membership]:
        """A user's own memberships (scoped by user, not organization), with org and role."""
        statement = (
            select(Membership)
            .where(Membership.user_id == user_id)
            .options(joinedload(Membership.organization), joinedload(Membership.role))
            .order_by(Membership.created_at, Membership.id)
        )
        return await self._page(statement, page)
