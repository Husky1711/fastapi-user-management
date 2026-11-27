"""Platform administration that runs outside HTTP (the `create-admin` command)."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.emails import normalize_email
from app.core.errors import Conflict
from app.core.security import check_password_rules, hash_password
from app.models import User
from app.repositories import UserRepository


async def create_platform_admin(session: AsyncSession, *, email: str, password: str) -> User:
    """Create a verified platform admin.

    Raises `InvalidEmail` / `WeakPassword` (ValueError) for bad input and `Conflict` if the
    email is taken, including by a deleted account (its row still holds the address).
    """
    email = normalize_email(email)
    check_password_rules(password)
    password_hash = await hash_password(password)  # before the transaction: it's slow
    users = UserRepository(session)
    user = User(
        email=email, password_hash=password_hash, email_verified=True, is_platform_admin=True
    )
    try:
        async with session.begin():
            if await users.get_by_email(email) is not None:
                raise Conflict(code="user.email_taken")
            users.add(user)
    except IntegrityError as error:  # taken by a deleted user, or by a concurrent create
        raise Conflict(code="user.email_taken") from error
    return user
