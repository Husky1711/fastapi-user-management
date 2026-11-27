from uuid import UUID

from sqlalchemy import select

from app.models import User
from app.repositories.base import Repository


class UserRepository(Repository):
    def add(self, user: User) -> None:
        self.session.add(user)

    async def get(self, user_id: UUID, *, include_deleted: bool = False) -> User | None:
        statement = select(User).where(User.id == user_id)
        if not include_deleted:
            statement = statement.where(User.deleted_at.is_(None))
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Case-insensitive (the column is citext). Deleted users are never matched."""
        statement = select(User).where(User.email == email, User.deleted_at.is_(None))
        return (await self.session.execute(statement)).scalar_one_or_none()
