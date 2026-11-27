"""Model factories: valid objects with unique values; override only what a test cares about.

Ids are set up front so related objects can be built before anything is flushed.
"""

import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.models import (
    AuditLog,
    Invitation,
    Membership,
    OneTimeToken,
    Organization,
    Role,
    TokenPurpose,
    User,
    UserSession,
)

PLACEHOLDER_HASH = "$argon2id$v=19$m=19456,t=2,p=1$placeholder$placeholder"


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def random_hash() -> bytes:
    """Stands in for the SHA-256 of a token."""
    return secrets.token_bytes(32)


def in_one_day() -> datetime:
    return clock.now() + timedelta(days=1)


# Any: overrides are forwarded to the model constructor, which checks them.
def new_user(**overrides: Any) -> User:
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "email": f"{unique('user')}@example.com",
        "password_hash": PLACEHOLDER_HASH,
    }
    return User(**(values | overrides))


def new_org(**overrides: Any) -> Organization:
    values: dict[str, Any] = {"id": uuid.uuid4(), "name": "Acme", "slug": unique("acme")}
    return Organization(**(values | overrides))


def new_role(org: Organization | None, key: str = "custom_role", **overrides: Any) -> Role:
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "organization_id": org.id if org else None,
        "key": key,
        "name": key.title(),
    }
    return Role(**(values | overrides))


def new_membership(user: User, org: Organization, role: Role) -> Membership:
    return Membership(id=uuid.uuid4(), user_id=user.id, organization_id=org.id, role_id=role.id)


def new_session(user: User, **overrides: Any) -> UserSession:
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "user_id": user.id,
        "family_id": uuid.uuid4(),
        "family_started_at": overrides.get("created_at") or clock.now(),
        "token_hash": random_hash(),
        "expires_at": in_one_day(),
    }
    return UserSession(**(values | overrides))


def new_one_time_token(user: User, **overrides: Any) -> OneTimeToken:
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "user_id": user.id,
        "purpose": TokenPurpose.VERIFY_EMAIL,
        "token_hash": random_hash(),
        "expires_at": in_one_day(),
    }
    return OneTimeToken(**(values | overrides))


def new_invitation(org: Organization, role: Role, **overrides: Any) -> Invitation:
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "organization_id": org.id,
        "email": f"{unique('invitee')}@example.com",
        "role_id": role.id,
        "token_hash": random_hash(),
        "expires_at": in_one_day(),
    }
    return Invitation(**(values | overrides))


def new_audit_log(**overrides: Any) -> AuditLog:
    values: dict[str, Any] = {"action": "member.added"}
    return AuditLog(**(values | overrides))


async def add(session: AsyncSession, *objects: object) -> None:
    session.add_all(objects)
    await session.flush()


async def system_role(session: AsyncSession, key: str) -> Role:
    statement = select(Role).where(Role.organization_id.is_(None), Role.key == key)
    return (await session.execute(statement)).scalar_one()
