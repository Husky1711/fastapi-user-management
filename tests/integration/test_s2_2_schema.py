"""Section 2.2: the schema's own rules, on the migrated PostgreSQL database.

Every test runs inside a transaction that is rolled back (the `db` fixture). Expected failures
run inside a savepoint (`rejected`) so the test can carry on afterwards.
"""

import asyncio
import re
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import DateTime, UniqueConstraint, delete, func, insert, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError, StatementError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core import clock
from app.models import (
    AuditLog,
    Base,
    Invitation,
    Membership,
    OneTimeToken,
    Organization,
    Permission,
    Role,
    User,
    UserSession,
    role_permissions,
)
from app.models.base import AwareDateTime
from tests.db import SERVICES
from tests.factories import (
    add,
    new_audit_log,
    new_invitation,
    new_membership,
    new_one_time_token,
    new_org,
    new_role,
    new_session,
    new_user,
    random_hash,
    system_role,
)

pytestmark = SERVICES


@asynccontextmanager
async def rejected(session: AsyncSession, reason: str) -> AsyncIterator[None]:
    """The writes in the block must be refused by the database, naming `reason`."""
    # The savepoint has to wrap the caller's whole block, so the block can't be one statement.
    with pytest.raises(IntegrityError, match=re.escape(reason)):  # noqa: PT012
        async with session.begin_nested():
            yield
            await session.flush()


async def _count(session: AsyncSession, model: type[Base], **where: object) -> int:
    statement = select(func.count()).select_from(model).filter_by(**where)
    return int((await session.execute(statement)).scalar_one())


async def _org_with_member(db: AsyncSession) -> tuple[User, Organization, Membership]:
    user, org = new_user(), new_org()
    membership = new_membership(user, org, await system_role(db, "member"))
    await add(db, user, org)
    await add(db, membership)
    return user, org, membership


async def test_s2_2_01_valid_row_in_every_table_gets_defaults(db: AsyncSession) -> None:
    user, org, _ = await _org_with_member(db)
    role = new_role(org)
    await add(db, role)
    await add(
        db,
        new_session(user, ip="203.0.113.7", user_agent="pytest"),
        new_one_time_token(user),
        new_invitation(org, role, invited_by_user_id=user.id),
        log := new_audit_log(organization_id=org.id, actor_user_id=user.id),
    )
    assert (user.status, user.email_verified, user.is_platform_admin) == ("active", False, False)
    assert user.failed_login_count == 0
    assert org.status == "active"
    assert user.created_at.tzinfo is not None
    assert user.updated_at == user.created_at
    assert log.id > 0
    assert log.details == {}
    await db.execute(insert(role_permissions).values(role_id=role.id, permission_key="org:read"))
    for model in (UserSession, OneTimeToken, Invitation, AuditLog, Membership):
        assert await _count(db, model) >= 1


async def test_s2_2_02_email_is_unique_ignoring_case(db: AsyncSession) -> None:
    await add(db, new_user(email="Mixed.Case@Example.com"))
    async with rejected(db, "uq_users_email"):
        db.add(new_user(email="mixed.case@example.COM"))
    found = await db.execute(select(User).where(User.email == "MIXED.CASE@EXAMPLE.COM"))
    assert found.scalar_one().email == "Mixed.Case@Example.com"  # stored as typed


@pytest.mark.parametrize(
    ("statement", "constraint"),
    [
        ("UPDATE users SET status = 'banned'", "ck_users_status"),
        ("UPDATE organizations SET status = 'archived'", "ck_organizations_status"),
        ("UPDATE one_time_tokens SET purpose = 'login'", "ck_one_time_tokens_purpose"),
        ("UPDATE users SET status = 'deleted'", "ck_users_deleted_status_has_deleted_at"),
        ("UPDATE users SET deleted_at = now()", "ck_users_deleted_status_has_deleted_at"),
        ("UPDATE organizations SET slug = 'Bad Slug'", "ck_organizations_slug_format"),
        ("UPDATE organizations SET slug = '-acme'", "ck_organizations_slug_format"),
        ("UPDATE organizations SET name = ''", "ck_organizations_name_length"),
        ("UPDATE roles SET key = 'Has-Caps'", "ck_roles_key_format"),
        ("UPDATE audit_logs SET action = 'no_dot'", "ck_audit_logs_action_format"),
    ],
)
async def test_s2_2_03_invalid_enum_and_format_values_are_rejected(
    db: AsyncSession, statement: str, constraint: str
) -> None:
    user, org, _ = await _org_with_member(db)
    await add(db, new_one_time_token(user), new_role(org), new_audit_log())
    async with rejected(db, constraint):
        await db.execute(text(statement))


async def test_s2_2_03_orm_refuses_unknown_enum_values_before_the_database(
    db: AsyncSession,
) -> None:
    with pytest.raises(StatementError):
        await add(db, new_user(status="banned"))


async def test_s2_2_04_email_length_boundaries(db: AsyncSession) -> None:
    domain = "@example.com"
    at_limit = "a" * (254 - len(domain)) + domain
    await add(db, new_user(email=at_limit))
    for email in ("b" * (255 - len(domain)) + domain, "", "a@"):
        async with rejected(db, "ck_users_email_length"):
            db.add(new_user(email=email))


async def test_s2_2_05_user_can_join_an_organization_once(db: AsyncSession) -> None:
    user, org, _ = await _org_with_member(db)
    async with rejected(db, "uq_memberships_user_id_organization_id"):
        db.add(new_membership(user, org, await system_role(db, "admin")))


async def test_s2_2_06_role_of_another_organization_is_refused(db: AsyncSession) -> None:
    _, org, membership = await _org_with_member(db)
    other_org = new_org()
    foreign_role = new_role(other_org)
    await add(db, other_org)
    await add(db, foreign_role)
    await add(db, outsider := new_user())
    async with rejected(db, "role belongs to another organization"):
        db.add(new_membership(outsider, org, foreign_role))
    async with rejected(db, "role belongs to another organization"):
        await db.execute(
            update(Membership).where(Membership.id == membership.id).values(role_id=foreign_role.id)
        )
    async with rejected(db, "role belongs to another organization"):
        db.add(new_invitation(org, foreign_role))
    async with rejected(db, "role cannot move to another organization"):
        await db.execute(
            update(Role).where(Role.id == foreign_role.id).values(organization_id=org.id)
        )


async def test_s2_2_07_system_role_or_own_custom_role_is_accepted(db: AsyncSession) -> None:
    _, org, _ = await _org_with_member(db)
    own_role = new_role(org)
    await add(db, own_role, joiner := new_user())
    await add(db, new_membership(joiner, org, own_role))
    await add(
        db, new_invitation(org, own_role), new_invitation(org, await system_role(db, "admin"))
    )
    await db.flush()
    assert await _count(db, Membership, organization_id=org.id) == 2


async def test_s2_2_08_role_keys_unique_per_organization_and_among_system_roles(
    db: AsyncSession,
) -> None:
    async with rejected(db, "uq_roles_organization_id_key"):
        db.add(new_role(None, key="owner"))
    first_org, second_org = new_org(), new_org()
    await add(db, first_org, second_org)
    await add(db, new_role(first_org, key="billing"), new_role(second_org, key="billing"))
    await add(db, new_role(first_org, key="owner"))  # a custom role may reuse a system key
    async with rejected(db, "uq_roles_organization_id_key"):
        db.add(new_role(first_org, key="billing"))


async def test_s2_2_09_deleting_a_user_keeps_history(db: AsyncSession) -> None:
    user, org, _ = await _org_with_member(db)
    member_role = await system_role(db, "member")
    await add(
        db,
        new_session(user),
        new_one_time_token(user),
        invitation := new_invitation(org, member_role, invited_by_user_id=user.id),
        log := new_audit_log(organization_id=org.id, actor_user_id=user.id),
    )
    await db.execute(delete(User).where(User.id == user.id))
    for model in (Membership, UserSession, OneTimeToken):
        assert await _count(db, model, user_id=user.id) == 0
    await db.refresh(log)
    await db.refresh(invitation)
    assert log.actor_user_id is None
    assert log.organization_id == org.id
    assert invitation.invited_by_user_id is None


async def test_s2_2_10_deleting_an_organization_keeps_history(db: AsyncSession) -> None:
    user, org, _ = await _org_with_member(db)
    custom = new_role(org)
    await add(db, custom)
    await add(db, new_invitation(org, custom), log := new_audit_log(organization_id=org.id))
    await db.execute(delete(Organization).where(Organization.id == org.id))
    assert await _count(db, Membership, organization_id=org.id) == 0
    assert await _count(db, Role, organization_id=org.id) == 0
    assert await _count(db, Invitation, organization_id=org.id) == 0
    assert await _count(db, User, id=user.id) == 1
    await db.refresh(log)
    assert log.organization_id is None


async def test_s2_2_11_role_in_use_cannot_be_deleted(db: AsyncSession) -> None:
    _, org, _ = await _org_with_member(db)
    custom = new_role(org)
    await add(db, custom, holder := new_user())
    await add(db, new_membership(holder, org, custom))
    async with rejected(db, "fk_memberships_role_id_roles"):
        await db.execute(delete(Role).where(Role.id == custom.id))
    invited_role = new_role(org, key="invited_only")
    await add(db, invited_role)
    await add(db, new_invitation(org, invited_role))
    async with rejected(db, "fk_invitations_role_id_roles"):
        await db.execute(delete(Role).where(Role.id == invited_role.id))
    async with rejected(db, "fk_memberships_role_id_roles"):
        await db.execute(delete(Role).where(Role.key == "member", Role.organization_id.is_(None)))


async def test_s2_2_12_deleting_a_permission_removes_its_grants(db: AsyncSession) -> None:
    granted = select(func.count()).select_from(role_permissions)
    before = await db.execute(granted.where(role_permissions.c.permission_key == "audit:read"))
    assert before.scalar_one() == 2  # owner and admin
    await db.execute(delete(Permission).where(Permission.key == "audit:read"))
    after = await db.execute(granted.where(role_permissions.c.permission_key == "audit:read"))
    assert after.scalar_one() == 0


@pytest.mark.parametrize("key", ["members", "Members:read", "members:read:all", ":read", "a b:c"])
async def test_s2_2_13_permission_key_must_be_resource_colon_action(
    db: AsyncSession, key: str
) -> None:
    async with rejected(db, "ck_permissions_key_format"):
        db.add(Permission(key=key, description="x"))


async def test_s2_2_14_one_pending_invitation_per_email_per_org(db: AsyncSession) -> None:
    _, org, _ = await _org_with_member(db)
    role = await system_role(db, "member")
    first = new_invitation(org, role, email="Invitee@Example.com")
    await add(db, first)
    async with rejected(db, "uq_invitations_organization_id_email_pending"):
        db.add(new_invitation(org, role, email="invitee@example.com"))
    other_org = new_org()
    await add(db, other_org)
    await add(db, new_invitation(other_org, role, email="invitee@example.com"))
    await db.execute(
        update(Invitation).where(Invitation.id == first.id).values(revoked_at=func.now())
    )
    await add(db, second := new_invitation(org, role, email="invitee@example.com"))
    await db.execute(
        update(Invitation).where(Invitation.id == second.id).values(accepted_at=func.now())
    )
    await add(db, new_invitation(org, role, email="invitee@example.com"))
    async with rejected(db, "ck_invitations_not_accepted_and_revoked"):
        await db.execute(
            update(Invitation).where(Invitation.id == second.id).values(revoked_at=func.now())
        )


async def test_s2_2_15_token_hashes_are_unique_and_32_bytes(db: AsyncSession) -> None:
    user, org, _ = await _org_with_member(db)
    role = await system_role(db, "member")
    builders: dict[str, Callable[[bytes], Base]] = {
        "sessions": lambda token_hash: new_session(user, token_hash=token_hash),
        "one_time_tokens": lambda token_hash: new_one_time_token(user, token_hash=token_hash),
        "invitations": lambda token_hash: new_invitation(org, role, token_hash=token_hash),
    }
    for table, build in builders.items():
        taken = random_hash()
        await add(db, build(taken))
        async with rejected(db, f"uq_{table}_token_hash"):
            db.add(build(taken))
        for wrong_size in (random_hash()[:31], random_hash() + b"x", b""):
            async with rejected(db, f"ck_{table}_token_hash_size"):
                db.add(build(wrong_size))


async def test_s2_2_16_every_timestamp_is_timestamptz_and_naive_values_are_refused(
    db: AsyncSession,
) -> None:
    expected = {
        (table.name, column.name)
        for table in Base.metadata.sorted_tables
        for column in table.columns
        if isinstance(column.type, AwareDateTime | DateTime)
    }
    rows = await db.execute(
        text(
            "SELECT table_name, column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = 'public' AND data_type LIKE 'timestamp%'"
        )
    )
    found = {(r.table_name, r.column_name): r.data_type for r in rows}
    assert set(found) == expected
    assert set(found.values()) == {"timestamp with time zone"}
    with pytest.raises(StatementError, match="naive datetime"):
        await add(db, new_session(new_user(), expires_at=datetime(2030, 1, 1)))


async def test_s2_2_17_updated_at_moves_on_bulk_update_but_not_on_no_op(db: AsyncSession) -> None:
    user = new_user()
    await add(db, user)
    created = user.created_at
    await db.execute(update(User).where(User.id == user.id).values(email=user.email))
    unchanged = (await db.execute(select(User.updated_at).where(User.id == user.id))).scalar_one()
    assert unchanged == created
    await db.execute(update(User).where(User.id == user.id).values(full_name="Ada"))
    moved = (await db.execute(select(User.updated_at).where(User.id == user.id))).scalar_one()
    assert moved > created


async def test_s2_2_18_expiry_must_be_after_creation(db: AsyncSession) -> None:
    user, org, _ = await _org_with_member(db)
    role = await system_role(db, "member")
    at = clock.now()
    for table, row in (
        ("sessions", new_session(user, created_at=at, expires_at=at)),
        ("one_time_tokens", new_one_time_token(user, created_at=at, expires_at=at)),
        ("invitations", new_invitation(org, role, created_at=at, expires_at=at - timedelta(1))),
    ):
        async with rejected(db, f"ck_{table}_expires_after_created"):
            db.add(row)


async def test_s2_2_19_counters_and_lengths_have_limits(db: AsyncSession) -> None:
    async with rejected(db, "ck_users_failed_login_count_not_negative"):
        db.add(new_user(failed_login_count=-1))
    async with rejected(db, "ck_users_full_name_length"):
        db.add(new_user(full_name="x" * 201))
    await add(db, user := new_user(full_name="x" * 200))
    async with rejected(db, "ck_sessions_user_agent_length"):
        db.add(new_session(user, user_agent="u" * 257))
    await add(db, new_session(user, user_agent="u" * 256))


def _leading_columns_with_full_index() -> dict[str, set[tuple[str, ...]]]:
    """Per table, the column lists that a non-partial index (or PK / unique) starts with."""
    covered: dict[str, set[tuple[str, ...]]] = {}
    for table in Base.metadata.sorted_tables:
        lists = [tuple(c.name for c in table.primary_key.columns)]
        lists += [
            tuple(c.name for c in index.columns)
            for index in table.indexes
            if index.dialect_options["postgresql"]["where"] is None
        ]
        lists += [
            tuple(c.name for c in constraint.columns)
            for constraint in table.constraints
            if isinstance(constraint, UniqueConstraint)
        ]
        covered[table.name] = {cols[:n] for cols in lists for n in range(1, len(cols) + 1)}
    return covered


async def test_s2_2_20_every_foreign_key_is_indexed_and_has_a_delete_rule(db: AsyncSession) -> None:
    covered = _leading_columns_with_full_index()
    unindexed = [
        f"{fk.parent.name}({', '.join(fk.column_keys)})"
        for table in Base.metadata.sorted_tables
        for fk in table.foreign_key_constraints
        if tuple(fk.column_keys) not in covered[table.name]
    ]
    assert unindexed == []
    no_delete_rule = [
        f"{fk.parent.name}.{fk.name}"
        for table in Base.metadata.sorted_tables
        for fk in table.foreign_key_constraints
        if fk.ondelete is None
    ]
    assert no_delete_rule == []
    declared = {index.name for table in Base.metadata.sorted_tables for index in table.indexes}
    rows = await db.execute(text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'"))
    assert declared <= set(rows.scalars())


async def test_s2_2_21_concurrent_signups_with_one_email_keep_one(db_engine: AsyncEngine) -> None:
    email = f"race-{uuid.uuid4().hex[:12]}@example.com"
    gate = asyncio.Barrier(2)

    async def sign_up(variant: str) -> None:
        async with AsyncSession(db_engine) as session, session.begin():
            await gate.wait()  # both transactions are open before either inserts
            session.add(new_user(email=variant))
            await session.flush()  # the second insert waits for the first to commit, then fails

    results = await asyncio.gather(sign_up(email), sign_up(email.upper()), return_exceptions=True)
    try:
        assert sum(r is None for r in results) == 1
        assert sum(isinstance(r, IntegrityError) for r in results) == 1
    finally:
        async with AsyncSession(db_engine) as session, session.begin():
            await session.execute(delete(User).where(User.email == email))


async def test_s2_2_23_length_and_type_boundaries(db: AsyncSession) -> None:
    org = new_org(name="n" * 200, slug="s" * 63)
    await add(db, org)
    await add(db, new_role(org, key="k" * 50, name="r" * 100))
    for row, constraint in (
        (new_org(name="n" * 201), "ck_organizations_name_length"),
        (new_org(slug="s" * 64), "ck_organizations_slug_format"),
        (new_role(org, key="k" * 51), "ck_roles_key_format"),
        (new_role(org, key="x"), "ck_roles_key_format"),
        (new_role(org, key="role_101", name="r" * 101), "ck_roles_name_length"),
    ):
        async with rejected(db, constraint):
            db.add(row)
    user = new_user()
    await add(db, user, new_session(user, ip="2001:db8::1"))
    with pytest.raises(DBAPIError):  # not an IP address: refused, never stored as text
        async with db.begin_nested():
            await add(db, new_session(user, ip="not-an-ip"))


async def test_s2_2_24_every_table_with_updated_at_has_the_trigger(db: AsyncSession) -> None:
    with_updated_at = {
        table.name for table in Base.metadata.sorted_tables if "updated_at" in table.columns
    }
    rows = await db.execute(
        text(
            "SELECT c.relname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
            "WHERE t.tgname = c.relname || '_set_updated_at' AND NOT t.tgisinternal"
        )
    )
    assert set(rows.scalars()) == with_updated_at
    _, org, membership = await _org_with_member(db)
    await db.execute(update(Organization).where(Organization.id == org.id).values(name="Renamed"))
    admin = await system_role(db, "admin")
    await db.execute(
        update(Membership).where(Membership.id == membership.id).values(role_id=admin.id)
    )
    for model, row_id in ((Organization, org.id), (Membership, membership.id)):
        stamps = await db.execute(
            select(model.created_at, model.updated_at).where(model.id == row_id)
        )
        created, updated = stamps.one()
        assert updated > created


async def test_s2_2_25_rows_written_with_an_injected_clock_are_accepted(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    frozen = datetime(2020, 2, 3, 4, 5, 6, tzinfo=UTC)  # far from the database's own clock
    monkeypatch.setattr(clock, "now", lambda: frozen)
    user, org, _ = await _org_with_member(db)
    session, token = new_session(user), new_one_time_token(user)
    invitation = new_invitation(org, await system_role(db, "member"))
    await add(db, session, token, invitation, log := new_audit_log())
    for row in (user, org, session, token, invitation, log):
        assert row.created_at == frozen
    assert session.expires_at == frozen + timedelta(days=1)
