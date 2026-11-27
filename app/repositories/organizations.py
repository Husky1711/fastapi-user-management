from uuid import UUID

from sqlalchemy import select

from app.models import Organization
from app.repositories.base import Repository


class OrganizationRepository(Repository):
    unscoped = frozenset({"add", "get", "get_by_slug"})  # the tenant itself

    def add(self, organization: Organization) -> None:
        self.session.add(organization)

    async def get(self, organization_id: UUID) -> Organization | None:
        return await self.session.get(Organization, organization_id)

    async def get_by_slug(self, slug: str) -> Organization | None:
        statement = select(Organization).where(Organization.slug == slug)
        return (await self.session.execute(statement)).scalar_one_or_none()
