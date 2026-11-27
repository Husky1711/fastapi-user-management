from uuid import UUID

from sqlalchemy import or_, select

from app.models import Role, role_permissions
from app.repositories.base import Repository


class RoleRepository(Repository):
    """Roles visible to an organization: the system roles plus its own custom roles."""

    def add(self, role: Role) -> None:
        self.session.add(role)

    async def get_for_org(self, *, organization_id: UUID, key: str) -> Role | None:
        """The org's own role with this key, otherwise the system role with this key."""
        statement = (
            select(Role)
            .where(
                Role.key == key,
                or_(Role.organization_id == organization_id, Role.organization_id.is_(None)),
            )
            .order_by(Role.organization_id.is_(None))  # false (own role) sorts first
            .limit(1)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def list_for_org(self, *, organization_id: UUID) -> list[Role]:
        """Bounded by design: system roles plus the org's custom roles (a handful)."""
        statement = (
            select(Role)
            .where(or_(Role.organization_id == organization_id, Role.organization_id.is_(None)))
            .order_by(Role.organization_id.is_not(None), Role.key)
        )
        return list((await self.session.execute(statement)).scalars())

    async def permission_keys(self, role_id: UUID) -> frozenset[str]:
        statement = select(role_permissions.c.permission_key).where(
            role_permissions.c.role_id == role_id
        )
        return frozenset((await self.session.execute(statement)).scalars())
