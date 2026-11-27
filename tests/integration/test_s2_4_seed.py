"""Section 2.4: the seeded permissions and system roles match app/core/permissions.py."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.permissions import OWNER_ONLY, PERMISSIONS, SYSTEM_ROLES
from app.models import Permission, Role
from tests.db import SERVICES

pytestmark = SERVICES


async def _system_roles(db: AsyncSession) -> dict[str, Role]:
    statement = (
        select(Role).where(Role.organization_id.is_(None)).options(selectinload(Role.permissions))
    )
    return {role.key: role for role in (await db.execute(statement)).scalars()}


async def test_s2_4_01_and_03_permission_catalogue_matches_the_code(db: AsyncSession) -> None:
    rows = (await db.execute(select(Permission))).scalars()
    assert {p.key: p.description for p in rows} == dict(PERMISSIONS)


async def test_s2_4_01_system_roles_exist_with_their_names(db: AsyncSession) -> None:
    roles = await _system_roles(db)
    assert {key: role.name for key, role in roles.items()} == {
        key: name for key, (name, _) in SYSTEM_ROLES.items()
    }
    assert all(role.is_system for role in roles.values())


async def test_s2_4_02_role_grants_match_the_code(db: AsyncSession) -> None:
    roles = await _system_roles(db)
    granted = {key: {p.key for p in role.permissions} for key, role in roles.items()}
    assert granted == {key: set(perms) for key, (_, perms) in SYSTEM_ROLES.items()}
    assert granted["owner"] == set(PERMISSIONS)
    assert granted["admin"] == set(PERMISSIONS) - OWNER_ONLY
    assert granted["member"] == {"org:read", "members:read"}


async def test_s2_4_05_member_role_can_only_read(db: AsyncSession) -> None:
    roles = await _system_roles(db)
    assert all(p.key.endswith(":read") for p in roles["member"].permissions)
    assert not OWNER_ONLY & {p.key for p in roles["admin"].permissions}
