"""Section 2.5: repositories, on the migrated PostgreSQL database (rolled back per test)."""

import inspect
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

from app.core import clock
from app.core.pagination import MAX_OFFSET, MAX_PAGE_SIZE, PaginationParams
from app.core.permissions import SYSTEM_ROLES
from app.models import Membership, Organization, User, UserStatus
from app.repositories import (
    MembershipRepository,
    OrganizationRepository,
    Repository,
    RoleRepository,
    UserRepository,
)
from tests.db import SERVICES
from tests.factories import add, new_membership, new_org, new_role, new_user, system_role

pytestmark = SERVICES

ORG_SCOPED: dict[type[Repository], set[str]] = {
    # repository -> methods that are deliberately NOT scoped by organization (with reason)
    MembershipRepository: {"add", "list_for_user"},  # insert; a user's own memberships
    RoleRepository: {"add", "permission_keys"},  # insert; lookup by a role already resolved
}


async def _org_with_members(db: AsyncSession, count: int) -> tuple[Organization, list[User]]:
    org = new_org()
    users = [new_user() for _ in range(count)]
    await add(db, org, *users)
    member = await system_role(db, "member")
    await add(db, *(new_membership(user, org, member) for user in users))
    return org, users


async def test_s2_5_01_users_by_id_and_email_ignoring_case(db: AsyncSession) -> None:
    repo = UserRepository(db)
    user = new_user(email="Grace.Hopper@Example.com")
    repo.add(user)
    await db.flush()
    assert await repo.get(user.id) is user
    assert await repo.get_by_email("grace.hopper@EXAMPLE.com") is user
    assert await repo.get(uuid.uuid4()) is None
    assert await repo.get_by_email("nobody@example.com") is None


async def test_s2_5_02_soft_deleted_users_are_hidden_by_default(db: AsyncSession) -> None:
    repo = UserRepository(db)
    user = new_user(status=UserStatus.DELETED, deleted_at=clock.now())
    await add(db, user)
    assert await repo.get(user.id) is None
    assert await repo.get_by_email(user.email) is None
    assert await repo.get(user.id, include_deleted=True) is user


async def test_s2_5_03_organizations_by_id_and_slug(db: AsyncSession) -> None:
    repo = OrganizationRepository(db)
    org = new_org(slug="acme-labs")
    repo.add(org)
    await db.flush()
    assert await repo.get(org.id) is org
    assert await repo.get_by_slug("ACME-labs") is org
    assert await repo.get_by_slug("other") is None
    assert await repo.get(uuid.uuid4()) is None


async def test_s2_5_04_role_lookup_prefers_the_orgs_own_role(db: AsyncSession) -> None:
    repo = RoleRepository(db)
    org, other = new_org(), new_org()
    await add(db, org, other)
    own_admin = new_role(org, key="admin")
    repo.add(own_admin)
    repo.add(new_role(other, key="billing"))
    await db.flush()
    assert await repo.get_for_org(organization_id=org.id, key="admin") is own_admin
    system_admin = await repo.get_for_org(organization_id=other.id, key="admin")
    assert system_admin is not None
    assert system_admin.is_system
    assert await repo.get_for_org(organization_id=org.id, key="billing") is None  # other org's
    keys = [(role.key, role.is_system) for role in await repo.list_for_org(organization_id=org.id)]
    assert keys == [("admin", True), ("member", True), ("owner", True), ("admin", False)]


async def test_s2_5_05_permission_keys_of_a_role(db: AsyncSession) -> None:
    repo = RoleRepository(db)
    for key, (_, permissions) in SYSTEM_ROLES.items():
        role = await system_role(db, key)
        assert await repo.permission_keys(role.id) == permissions
    assert await repo.permission_keys(uuid.uuid4()) == frozenset()


async def test_s2_5_06_membership_for_user_and_org_with_role(db: AsyncSession) -> None:
    org, (user,) = await _org_with_members(db, 1)
    repo = MembershipRepository(db)
    db.expunge_all()  # prove the role is loaded by the query, not taken from the session
    membership = await repo.get(organization_id=org.id, user_id=user.id)
    assert membership is not None
    assert membership.role.key == "member"
    assert await repo.get(organization_id=org.id, user_id=uuid.uuid4()) is None


async def test_s2_5_06_add_membership_and_list_a_users_own(db: AsyncSession) -> None:
    org_a, org_b, user = new_org(), new_org(), new_user()
    await add(db, org_a, org_b, user)
    repo = MembershipRepository(db)
    repo.add(new_membership(user, org_a, await system_role(db, "owner")))
    repo.add(new_membership(user, org_b, await system_role(db, "member")))
    await db.flush()
    db.expunge_all()  # organization and role must come from the query itself
    mine = await repo.list_for_user(user.id, PaginationParams())
    assert mine.total == 2
    assert {(m.organization.slug, m.role.key) for m in mine.items} == {
        (org_a.slug, "owner"),
        (org_b.slug, "member"),
    }
    nobody = await repo.list_for_user(uuid.uuid4(), PaginationParams())
    assert (list(nobody.items), nobody.total) == ([], 0)


async def test_s2_5_07_one_orgs_members_never_appear_in_another(db: AsyncSession) -> None:
    org_a, users_a = await _org_with_members(db, 2)
    org_b, users_b = await _org_with_members(db, 3)
    repo = MembershipRepository(db)
    page = PaginationParams(limit=MAX_PAGE_SIZE)
    members_a = await repo.list_members(organization_id=org_a.id, page=page)
    assert {m.user_id for m in members_a.items} == {u.id for u in users_a}
    assert members_a.total == 2
    assert await repo.get(organization_id=org_a.id, user_id=users_b[0].id) is None
    role_repo = RoleRepository(db)
    custom_b = new_role(org_b, key="only_b")
    await add(db, custom_b)
    assert await role_repo.get_for_org(organization_id=org_a.id, key="only_b") is None
    assert custom_b not in await role_repo.list_for_org(organization_id=org_a.id)


async def test_s2_5_08_pages_cover_the_list_exactly_once(db: AsyncSession) -> None:
    org, users = await _org_with_members(db, 5)
    repo = MembershipRepository(db)
    seen: list[uuid.UUID] = []
    for offset in range(5):
        page = await repo.list_members(
            organization_id=org.id, page=PaginationParams(limit=1, offset=offset)
        )
        assert page.total == 5
        seen.extend(m.user_id for m in page.items)
    everyone = await repo.list_members(organization_id=org.id, page=PaginationParams(limit=100))
    # Same order page by page as in one go (stable sort), and every member exactly once.
    assert seen == [m.user_id for m in everyone.items]
    assert sorted(seen) == sorted(u.id for u in users)
    past_end = await repo.list_members(organization_id=org.id, page=PaginationParams(offset=50))
    assert (list(past_end.items), past_end.total) == ([], 5)


@pytest.mark.parametrize(
    "bad",
    [
        {"limit": 0},
        {"limit": MAX_PAGE_SIZE + 1},
        {"limit": -1},
        {"offset": -1},
        {"offset": MAX_OFFSET + 1},
        {"limit": "ten"},
        {"page": 2},
    ],
)
def test_s2_5_09_invalid_pagination_is_rejected_before_any_query(bad: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        PaginationParams(**bad)


@contextmanager
def _counting_queries(connection: AsyncConnection) -> Iterator[list[str]]:
    statements: list[str] = []

    def record(*args: Any) -> None:  # Any: SQLAlchemy event signature
        statements.append(str(args[2]))

    event.listen(connection.sync_connection, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(connection.sync_connection, "before_cursor_execute", record)


async def test_s2_5_10_listing_members_takes_the_same_queries_for_1_or_25(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    counts = []
    for size in (1, 25):
        org, _ = await _org_with_members(db, size)
        db.expunge_all()
        with _counting_queries(db_connection) as statements:
            page = await MembershipRepository(db).list_members(
                organization_id=org.id, page=PaginationParams(limit=MAX_PAGE_SIZE)
            )
            names = [(m.user.email, m.role.key) for m in page.items]  # lazy="raise" if not loaded
        assert len(names) == size
        counts.append(len(statements))
    assert counts == [2, 2]  # count + one joined select


def _public_methods(repository: type[Repository]) -> dict[str, inspect.Signature]:
    return {
        name: inspect.signature(member)
        for name, member in inspect.getmembers(repository, inspect.isfunction)
        if not name.startswith("_")
    }


def test_s2_5_11_org_scoped_methods_require_organization_id_by_keyword() -> None:
    for repository, unscoped in ORG_SCOPED.items():
        methods = _public_methods(repository)
        assert unscoped <= set(methods)
        for name, signature in methods.items():
            if name in unscoped:
                continue
            parameter = signature.parameters.get("organization_id")
            assert parameter is not None, f"{repository.__name__}.{name}"
            assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
            assert parameter.default is inspect.Parameter.empty


def test_s2_5_12_repositories_never_commit_or_roll_back() -> None:
    package = Path(__file__).resolve().parents[2] / "app" / "repositories"
    source = "\n".join(p.read_text() for p in package.glob("*.py"))
    for forbidden in (".commit(", ".rollback(", ".begin(", ".begin_nested("):
        assert forbidden not in source


async def test_s2_5_12_added_rows_are_invisible_until_the_caller_commits(
    db_engine: AsyncEngine,
) -> None:
    email = f"uncommitted-{uuid.uuid4().hex[:12]}@example.com"
    async with AsyncSession(db_engine) as writer, AsyncSession(db_engine) as reader:
        UserRepository(writer).add(new_user(email=email))
        await writer.flush()
        assert await UserRepository(reader).get_by_email(email) is None
        await writer.rollback()
    async with AsyncSession(db_engine) as reader:
        assert await UserRepository(reader).get_by_email(email) is None


async def test_s2_5_13_repeated_lookups_are_stable_and_write_nothing(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    org, (user,) = await _org_with_members(db, 1)
    repo = MembershipRepository(db)
    with _counting_queries(db_connection) as statements:
        first = await repo.get(organization_id=org.id, user_id=user.id)
        second = await repo.get(organization_id=org.id, user_id=user.id)
    assert first is second
    assert all(s.lstrip().upper().startswith("SELECT") for s in statements)
    assert not db.new
    assert not db.dirty
    count = select(Membership).where(Membership.organization_id == org.id)
    assert len((await db.execute(count)).scalars().all()) == 1
