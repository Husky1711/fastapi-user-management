from uuid import UUID

from sqlalchemy import ColumnElement, or_, select

from app.models import Role, role_permissions
from app.repositories.base import Repository


def _visible_to(organization_id: UUID) -> ColumnElement[bool]:
    """System roles plus the organization's own roles."""
    return or_(Role.organization_id == organization_id, Role.organization_id.is_(None))


class RoleRepository(Repository):
    """Roles visible to an organization: the system roles plus its own custom roles."""

    unscoped = frozenset({"add"})

    def add(self, role: Role) -> None:
        self.session.add(role)

    async def get_for_org(self, *, organization_id: UUID, key: str) -> Role | None:
        """The org's own role with this key, otherwise the system role with this key."""
        statement = (
            select(Role)
            .where(
                Role.key == key,
                _visible_to(organization_id),
            )
            .order_by(Role.organization_id.is_(None))  # false (own role) sorts first
            .limit(1)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def list_for_org(self, *, organization_id: UUID) -> list[Role]:
        """Bounded by design: system roles plus the org's custom roles (a handful)."""
        statement = (
            select(Role)
            .where(_visible_to(organization_id))
            .order_by(Role.organization_id.is_not(None), Role.key)
        )
        return list((await self.session.execute(statement)).scalars())

    async def permission_keys(self, *, organization_id: UUID, role_id: UUID) -> frozenset[str]:
        """Permissions of a role visible to this org; empty for another org's role."""
        statement = (
            select(role_permissions.c.permission_key)
            .join(Role, Role.id == role_permissions.c.role_id)
            .where(Role.id == role_id, _visible_to(organization_id))
        )
        return frozenset((await self.session.execute(statement)).scalars())
