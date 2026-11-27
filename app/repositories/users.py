from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import case, exists, select, update

from app.models import User, UserSession, UserStatus
from app.repositories.base import Repository


@dataclass(frozen=True, slots=True)
class FailedLogins:
    count: int
    locked_until: datetime | None


class UserRepository(Repository):
    # Users are global, not tenant data.
    unscoped = frozenset(
        {"add", "get", "get_by_email", "get_authenticated", "get_for_update", "record_failed_login"}
    )

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

    async def get_authenticated(
        self, user_id: UUID, family_id: UUID, *, now: datetime
    ) -> User | None:
        """The user, if active, not deleted and with a live session in `family_id`. One query."""
        live_session = exists().where(
            UserSession.user_id == User.id,
            UserSession.family_id == family_id,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
        statement = select(User).where(
            User.id == user_id,
            User.status == UserStatus.ACTIVE,
            User.deleted_at.is_(None),
            live_session,
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_for_update(self, user_id: UUID) -> User | None:
        """The current row (deleted or not), locked until the transaction ends.

        Every flow that creates or ends sessions or changes credentials takes this lock
        first (user row, then session rows), so those flows run one after another per user
        and each sees what the previous one committed. `FOR NO KEY UPDATE`: it serializes
        those flows but doesn't block inserts that only reference the user (audit rows).
        """
        statement = (
            select(User)
            .where(User.id == user_id)
            .with_for_update(key_share=True)
            .execution_options(populate_existing=True)
        )
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def record_failed_login(
        self, user_id: UUID, *, now: datetime, threshold: int, lock_for: timedelta
    ) -> FailedLogins | None:
        """Count one failure atomically (one UPDATE, so concurrent failures all count).

        Reaching `threshold` locks the account until `now + lock_for`. Failures during a lock
        don't extend it (or anyone could keep an account locked forever); a lock that has
        expired starts the count again. None if the user no longer exists.
        """
        locked = User.locked_until.is_not(None) & (User.locked_until > now)
        lock_expired = User.locked_until.is_not(None) & (User.locked_until <= now)
        count = case((lock_expired, 1), else_=User.failed_login_count + 1)
        statement = (
            update(User)
            .where(User.id == user_id)
            .values(
                failed_login_count=count,
                locked_until=case(
                    (locked, User.locked_until),
                    (count >= threshold, now + lock_for),
                    (lock_expired, None),
                    else_=User.locked_until,
                ),
            )
            .returning(User.failed_login_count, User.locked_until)
            .execution_options(synchronize_session=False)
        )
        row = (await self.session.execute(statement)).one_or_none()
        if row is None:
            return None
        return FailedLogins(count=row.failed_login_count, locked_until=row.locked_until)
