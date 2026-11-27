"""Section 3.2: auth columns (migration 0003), session and audit repositories."""

import logging
from datetime import timedelta

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock
from app.core.client import ClientInfo
from app.core.logging import JsonFormatter, request_id_var
from app.core.pagination import PaginationParams
from app.core.redaction import REDACTED
from app.infra.database import transaction
from app.models import AuditLog, RevokeReason, User, UserSession
from app.repositories import SessionRepository
from app.services.audit import record
from tests.db import SERVICES, rejected
from tests.factories import add, new_session, new_user

pytestmark = SERVICES
CLIENT = ClientInfo(ip="203.0.113.9", user_agent="pytest")


async def _user_with_sessions(db: AsyncSession, count: int) -> tuple[User, list[UserSession]]:
    user = new_user()
    await add(db, user)
    sessions = [new_session(user, user_agent=f"device-{i}") for i in range(count)]
    await add(db, *sessions)
    return user, sessions


async def test_s3_2_01_auth_columns_exist(db: AsyncSession) -> None:
    rows = await db.execute(
        text(
            "SELECT table_name || '.' || column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND column_name IN "
            "('last_login_at', 'revoked_reason', 'family_started_at')"
        )
    )
    assert set(rows.scalars()) == {
        "users.last_login_at",
        "sessions.revoked_reason",
        "sessions.family_started_at",
    }


async def test_s3_2_02_revocation_reason_and_family_rules(db: AsyncSession) -> None:
    user, (session,) = await _user_with_sessions(db, 1)
    async with rejected(db, "ck_sessions_revoked_reason_set"):
        await db.execute(
            update(UserSession).where(UserSession.id == session.id).values(revoked_at=clock.now())
        )
    async with rejected(db, "ck_sessions_revoked_reason_set"):
        await db.execute(
            update(UserSession)
            .where(UserSession.id == session.id)
            .values(revoked_reason=RevokeReason.LOGOUT)
        )
    async with rejected(db, "ck_sessions_revoked_reason"):
        await db.execute(text("UPDATE sessions SET revoked_at = now(), revoked_reason = 'bored'"))
    async with rejected(db, "ck_sessions_family_started_first"):
        db.add(new_session(user, family_started_at=clock.now() + timedelta(hours=1)))
    async with rejected(db, "uq_sessions_family_id_active"):  # one usable token per family
        db.add(new_session(user, family_id=session.family_id))
    await db.execute(
        update(UserSession)
        .where(UserSession.id == session.id)
        .values(revoked_at=clock.now(), revoked_reason=RevokeReason.ROTATED)
    )
    await add(db, new_session(user, family_id=session.family_id))  # the next one in the family


async def test_s3_2_03_lookups_skip_revoked_and_expired_rows(db: AsyncSession) -> None:
    user, (live, revoked, expired) = await _user_with_sessions(db, 3)
    now = clock.now()
    repo = SessionRepository(db)
    await repo.revoke_family(
        user_id=user.id, family_id=revoked.family_id, reason=RevokeReason.LOGOUT, now=now
    )
    later = now + timedelta(days=1, seconds=1)  # past every factory session's expiry...
    await db.execute(
        update(UserSession)
        .where(UserSession.id != expired.id, UserSession.user_id == user.id)
        .values(expires_at=later + timedelta(days=1))  # ...except `expired`
    )
    assert await repo.get_by_token_hash(revoked.token_hash) is not None  # found, even revoked
    assert await repo.get_by_token_hash(b"\x00" * 32) is None
    family = await repo.active_in_family(user_id=user.id, family_id=live.family_id, now=later)
    assert family is not None
    assert family.id == live.id
    for gone in (revoked, expired):
        found = await repo.active_in_family(user_id=user.id, family_id=gone.family_id, now=later)
        assert found is None
    page = await repo.list_active(user_id=user.id, now=later, page=PaginationParams(limit=1))
    assert (page.total, [s.id for s in page.items]) == (1, [live.id])


async def test_s3_2_04_bulk_revocation_counts_and_keeps_first_reason(db: AsyncSession) -> None:
    user, sessions = await _user_with_sessions(db, 4)
    repo = SessionRepository(db)
    now = clock.now()
    first, keep = sessions[0], sessions[3]
    assert (
        await repo.revoke_family(
            user_id=user.id, family_id=first.family_id, reason=RevokeReason.REVOKED, now=now
        )
        == 1
    )
    revoked = await repo.revoke_all(
        user_id=user.id, reason=RevokeReason.LOGOUT_ALL, now=now, except_family=keep.family_id
    )
    assert revoked == 2  # the first was already revoked
    rows = await db.execute(select(UserSession.id, UserSession.revoked_reason))
    reasons = {row.id: row.revoked_reason for row in rows}
    assert reasons[first.id] == RevokeReason.REVOKED
    assert reasons[sessions[1].id] == RevokeReason.LOGOUT_ALL
    assert reasons[keep.id] is None
    same_device = await repo.revoke_same_device(
        user_id=user.id, user_agent="device-3", reason=RevokeReason.REPLACED, now=now
    )
    assert same_device == 1
    assert await repo.revoke_all(user_id=user.id, reason=RevokeReason.LOGOUT_ALL, now=now) == 0


async def test_s3_2_04_oldest_families_beyond_the_newest_n(db: AsyncSession) -> None:
    user = new_user()
    await add(db, user)
    base = clock.now() - timedelta(hours=5)
    sessions = [
        new_session(
            user, family_started_at=base + timedelta(hours=i), created_at=base + timedelta(hours=i)
        )
        for i in range(4)
    ]
    await add(db, *sessions)
    oldest = await SessionRepository(db).oldest_active_families(
        user_id=user.id, now=clock.now(), keep=2
    )
    assert set(oldest) == {sessions[0].family_id, sessions[1].family_id}


async def test_s3_2_05_one_user_cannot_revoke_another_users_sessions(db: AsyncSession) -> None:
    owner, (session,) = await _user_with_sessions(db, 1)
    intruder, _ = await _user_with_sessions(db, 1)
    repo = SessionRepository(db)
    now = clock.now()
    assert (
        await repo.revoke_family(
            user_id=intruder.id, family_id=session.family_id, reason=RevokeReason.REVOKED, now=now
        )
        == 0
    )
    assert (
        await repo.active_in_family(user_id=intruder.id, family_id=session.family_id, now=now)
        is None
    )
    assert await repo.active_in_family(user_id=owner.id, family_id=session.family_id, now=now)


async def test_s3_2_06_audit_entry_records_who_what_where(db: AsyncSession) -> None:
    user = new_user()
    await add(db, user)
    token = request_id_var.set("req-3-2-06")
    try:
        entry = record(
            db,
            action="auth.login_succeeded",
            client=CLIENT,
            actor_user_id=user.id,
            target=("user", user.id),
            details={"strategy": "allow_multiple"},
        )
        await db.flush()
    finally:
        request_id_var.reset(token)
    db.expunge_all()  # read the stored row back, not the object we built
    stored = (await db.execute(select(AuditLog).where(AuditLog.id == entry.id))).scalar_one()
    assert (stored.action, stored.actor_user_id, stored.target_type) == (
        "auth.login_succeeded",
        user.id,
        "user",
    )
    assert (stored.target_id, stored.ip, stored.request_id) == (
        str(user.id),
        "203.0.113.9",
        "req-3-2-06",
    )
    assert stored.details == {"strategy": "allow_multiple"}


async def test_s3_2_07_audit_details_never_hold_secrets_or_full_emails(db: AsyncSession) -> None:
    entry = record(
        db,
        action="auth.login_failed",
        client=ClientInfo.unknown(),
        details={
            "password": "hunter2-hunter2",
            "Refresh_Token": "abc",
            "attempt": {"email": "grace.hopper@example.com", "api_key": 12345},
            "note": "contact grace.hopper@example.com, password=hunter2",
            "codes": ["ok", "x@example.org"],
        },
    )
    await db.flush()
    details = (
        await db.execute(select(AuditLog.details).where(AuditLog.id == entry.id))
    ).scalar_one()
    assert details["password"] == REDACTED
    assert details["Refresh_Token"] == REDACTED
    assert details["attempt"] == {"email": "g***@example.com", "api_key": REDACTED}
    assert details["note"] == "contact g***@example.com, password=***"
    assert details["codes"] == ["ok", "x***@example.org"]
    text_form = str(details)
    for secret in ("hunter2", "grace.hopper", "12345", "abc"):
        assert secret not in text_form


async def test_s3_2_11_a_failing_commit_after_a_failed_block_is_logged_and_the_error_kept(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """If ending the outer transaction fails too, the original error still surfaces and the
    second failure is logged (error type only) before the rollback (review round 4, L3)."""
    await db.execute(text("SELECT 1"))  # a read first, like a request's dependencies

    async def lost(*_: object, **__: object) -> None:
        raise ConnectionResetError("db-password=hunter2 connection lost")

    monkeypatch.setattr(db, "commit", lost)
    with caplog.at_level(logging.WARNING), pytest.raises(ValueError, match="the block's own"):
        async with transaction(db):
            raise ValueError("the block's own error")
    warnings = [r for r in caplog.records if "failed unit of work" in r.getMessage()]
    assert len(warnings) == 1
    logged = JsonFormatter().format(warnings[0])
    assert "ConnectionResetError" in logged
    assert "hunter2" not in logged
