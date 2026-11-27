"""Section 3.6: the signed-in user's profile, sessions and password."""

import uuid
from typing import Any, NoReturn

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.core.config import AuthSettings
from app.models import AuditLog, RevokeReason, User, UserSession
from app.repositories import SessionRepository
from tests.api import api_client
from tests.db import SERVICES

pytestmark = SERVICES
SIGNUP, LOGIN, REFRESH = "/api/v1/auth/signup", "/api/v1/auth/login", "/api/v1/auth/refresh"
PASSWORD = "Correct-Horse-Battery-9"
NEW_PASSWORD = "Brand-New-Passphrase-42"


def _bearer(tokens: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _account(http: AsyncClient, devices: int = 1) -> tuple[str, list[dict[str, Any]]]:
    email = f"me-{uuid.uuid4().hex[:12]}@example.com"
    assert (await http.post(SIGNUP, json={"email": email, "password": PASSWORD})).status_code == 202
    logins = []
    for device in range(devices):
        response = await http.post(
            LOGIN,
            json={"email": email, "password": PASSWORD},
            headers={"User-Agent": f"device-{device}"},
        )
        assert response.status_code == 200
        logins.append(response.json())
    return email, logins


REAUTH = {"current_password": PASSWORD}


async def _end(http: AsyncClient, tokens: dict[str, Any], session_id: object) -> Response:
    """End one session; the current password goes along (needed for another device)."""
    path = f"/api/v1/me/sessions/{session_id}/revoke"
    return await http.post(path, json=REAUTH, headers=_bearer(tokens))


async def _revoke_others(http: AsyncClient, tokens: dict[str, Any]) -> Response:
    return await http.post(
        "/api/v1/me/sessions/revoke-others", json=REAUTH, headers=_bearer(tokens)
    )


async def _session_id(http: AsyncClient, tokens: dict[str, Any]) -> str:
    """The id of the session these tokens belong to."""
    page = (await http.get("/api/v1/me/sessions", headers=_bearer(tokens))).json()
    return str(next(item["id"] for item in page["items"] if item["current"]))


async def _reasons(db: AsyncSession, email: str) -> list[RevokeReason | None]:
    db.expunge_all()
    rows = await db.execute(
        select(UserSession.revoked_reason)
        .join(User, User.id == UserSession.user_id)
        .where(User.email == email)
        .order_by(UserSession.created_at)
    )
    return list(rows.scalars())


async def test_s3_6_01_profile_shows_only_safe_fields(db_connection: AsyncConnection) -> None:
    async with api_client(db_connection) as http:
        email, (tokens,) = await _account(http)
        response = await http.get("/api/v1/me", headers=_bearer(tokens))
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "id",
        "email",
        "full_name",
        "email_verified",
        "created_at",
        "last_login_at",
    }
    assert body["email"] == email
    assert body["last_login_at"] is not None
    assert "hash" not in response.text
    assert "argon2" not in response.text


async def test_s3_6_02_sessions_list_marks_the_current_one(db_connection: AsyncConnection) -> None:
    async with api_client(db_connection) as http:
        _, (phone, laptop) = await _account(http, devices=2)
        response = await http.get("/api/v1/me/sessions", headers=_bearer(laptop))
    assert response.status_code == 200
    page = response.json()
    assert (page["total"], page["limit"], page["offset"]) == (2, 20, 0)
    assert [s["current"] for s in page["items"]] == [True, False]  # newest first
    assert [s["user_agent"] for s in page["items"]] == ["device-1", "device-0"]
    assert set(page["items"][0]) == {
        "id",
        "started_at",
        "last_used_at",
        "expires_at",
        "ip",
        "user_agent",
        "current",
    }
    assert phone["refresh_token"] not in response.text


async def test_s3_6_03_ending_one_session_signs_that_device_out(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    async with api_client(db_connection) as http:
        email, (phone, laptop) = await _account(http, devices=2)
        listing = (await http.get("/api/v1/me/sessions", headers=_bearer(laptop))).json()
        phone_id = next(s["id"] for s in listing["items"] if not s["current"])
        response = await _end(http, laptop, phone_id)
        phone_after = await http.get("/api/v1/me", headers=_bearer(phone))
        laptop_after = await http.get("/api/v1/me", headers=_bearer(laptop))
    assert response.status_code == 204
    assert (phone_after.status_code, laptop_after.status_code) == (401, 200)
    assert sorted(map(str, await _reasons(db, email))) == ["None", "revoked"]


@pytest.mark.parametrize("target", ["someone_elses", "unknown", "malformed"])
async def test_s3_6_04_other_peoples_and_unknown_sessions_are_not_found(
    db: AsyncSession, db_connection: AsyncConnection, target: str
) -> None:
    async with api_client(db_connection) as http:
        _, (mine,) = await _account(http)
        other_email, (theirs,) = await _account(http)
        their_id = (await http.get("/api/v1/me/sessions", headers=_bearer(theirs))).json()["items"][
            0
        ]["id"]
        session_id = {"someone_elses": their_id, "unknown": str(uuid.uuid4()), "malformed": "abc"}[
            target
        ]
        response = await _end(http, mine, session_id)
    expected = (
        (422, "request.validation_failed") if target == "malformed" else (404, "session.not_found")
    )
    assert (response.status_code, response.json()["code"]) == expected
    assert await _reasons(db, other_email) == [None]


async def test_s3_6_05_revoke_others_keeps_this_device(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    async with api_client(db_connection) as http:
        email, devices = await _account(http, devices=3)
        response = await _revoke_others(http, devices[1])
        results = [(await http.get("/api/v1/me", headers=_bearer(d))).status_code for d in devices]
    assert response.status_code == 204
    assert results == [401, 200, 401]
    assert sorted(map(str, await _reasons(db, email))) == ["None", "revoked", "revoked"]


async def test_s3_6_06_password_change_signs_out_other_devices(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    async with api_client(db_connection) as http:
        email, (phone, laptop) = await _account(http, devices=2)
        change = {"current_password": PASSWORD, "new_password": NEW_PASSWORD}
        response = await http.post("/api/v1/me/password", json=change, headers=_bearer(laptop))
        phone_after = await http.post(REFRESH, json={"refresh_token": phone["refresh_token"]})
        laptop_after = await http.get("/api/v1/me", headers=_bearer(laptop))
        old = await http.post(LOGIN, json={"email": email, "password": PASSWORD})
        new = await http.post(LOGIN, json={"email": email, "password": NEW_PASSWORD})
    assert response.status_code == 204
    assert (phone_after.status_code, laptop_after.status_code) == (401, 200)
    assert (old.status_code, new.status_code) == (401, 200)
    reasons = await _reasons(db, email)
    assert reasons.count(RevokeReason.PASSWORD_CHANGED) == 1
    actions = await db.execute(
        select(AuditLog.action).where(AuditLog.action == "auth.password_changed")
    )
    assert len(actions.scalars().all()) == 1


async def test_s3_6_07_wrong_current_password_uses_the_sessions_budget(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    """ADR-0012: counted against this session's re-entry budget, not the account lockout."""
    async with api_client(db_connection) as http:
        email, (tokens,) = await _account(http)
        wrong = {"current_password": "Not-My-Password-1", "new_password": NEW_PASSWORD}
        response = await http.post("/api/v1/me/password", json=wrong, headers=_bearer(tokens))
    assert (response.status_code, response.json()["code"]) == (401, "auth.invalid_credentials")
    db.expunge_all()
    user = (await db.execute(select(User).where(User.email == email))).scalar_one()
    assert user.failed_login_count == 0
    attempts = await db.execute(
        select(UserSession.reauth_attempts).where(UserSession.user_id == user.id)
    )
    assert list(attempts.scalars()) == [1]


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"current_password": PASSWORD, "new_password": "short"}, "user.password_weak"),
        ({"current_password": PASSWORD, "new_password": "a" + " " * 11}, "user.password_weak"),
        ({"current_password": PASSWORD, "new_password": PASSWORD}, "user.password_unchanged"),
        ({"current_password": PASSWORD}, "request.validation_failed"),
    ],
)
async def test_s3_6_08_invalid_new_passwords_are_422(
    db_connection: AsyncConnection, body: dict[str, str], code: str
) -> None:
    async with api_client(db_connection) as http:
        _, (tokens,) = await _account(http)
        response = await http.post("/api/v1/me/password", json=body, headers=_bearer(tokens))
    assert (response.status_code, response.json()["code"]) == (422, code)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/me"),
        ("GET", "/api/v1/me/sessions"),
        ("POST", f"/api/v1/me/sessions/{uuid.uuid4()}/revoke"),
        ("POST", "/api/v1/me/sessions/revoke-others"),
        ("POST", "/api/v1/me/password"),
    ],
)
async def test_s3_6_09_every_me_route_needs_a_token(
    db_connection: AsyncConnection, method: str, path: str
) -> None:
    async with api_client(db_connection) as http:
        response = await http.request(method, path, json={} if method == "POST" else None)
    assert (response.status_code, response.json()["code"]) == (401, "auth.not_authenticated")


async def test_s3_6_10_revoke_others_twice_is_harmless(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    async with api_client(db_connection) as http:
        email, devices = await _account(http, devices=2)
        first = await _revoke_others(http, devices[0])
        before = await _reasons(db, email)
        second = await _revoke_others(http, devices[0])
    assert (first.status_code, second.status_code) == (204, 204)
    assert await _reasons(db, email) == before


async def test_s3_6_11_sessions_list_pages(db_connection: AsyncConnection) -> None:
    async with api_client(db_connection) as http:
        _, devices = await _account(http, devices=3)
        headers = _bearer(devices[0])
        first = (await http.get("/api/v1/me/sessions?limit=2", headers=headers)).json()
        rest = (await http.get("/api/v1/me/sessions?limit=2&offset=2", headers=headers)).json()
        past = (await http.get("/api/v1/me/sessions?offset=10", headers=headers)).json()
        bad = await http.get("/api/v1/me/sessions?limit=0", headers=headers)
        unknown = await http.get("/api/v1/me/sessions?page=2", headers=headers)
    assert (len(first["items"]), first["total"]) == (2, 3)
    assert (len(rest["items"]), rest["total"]) == (1, 3)
    assert {s["id"] for s in first["items"]}.isdisjoint({s["id"] for s in rest["items"]})
    assert (past["items"], past["total"]) == ([], 3)
    assert (bad.status_code, unknown.status_code) == (422, 422)


async def test_s3_6_14_ending_your_own_current_session_signs_you_out(
    db_connection: AsyncConnection,
) -> None:
    async with api_client(db_connection) as http:
        _, (phone, laptop) = await _account(http, devices=2)
        listing = (await http.get("/api/v1/me/sessions", headers=_bearer(laptop))).json()
        this_one = next(s["id"] for s in listing["items"] if s["current"])
        response = await _end(http, laptop, this_one)
        laptop_after = await http.get("/api/v1/me", headers=_bearer(laptop))
        refreshed = await http.post(
            "/api/v1/auth/refresh", json={"refresh_token": laptop["refresh_token"]}
        )
        phone_after = await http.get("/api/v1/me", headers=_bearer(phone))
    assert response.status_code == 204
    assert (laptop_after.status_code, refreshed.status_code, phone_after.status_code) == (
        401,
        401,
        200,
    )


def _lost_connection(*_: object, **__: object) -> NoReturn:
    raise OperationalError("UPDATE sessions", {}, ConnectionResetError("connection lost"))


async def test_s3_6_15_database_failing_inside_a_password_change_changes_nothing(
    db: AsyncSession, db_connection: AsyncConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    new_password = "Brand-New-Passw0rd-1"
    async with api_client(db_connection) as http:
        email, (phone, laptop) = await _account(http, devices=2)
        monkeypatch.setattr(SessionRepository, "revoke_all", _lost_connection)
        change = {"current_password": PASSWORD, "new_password": new_password}
        response = await http.post("/api/v1/me/password", json=change, headers=_bearer(laptop))
        monkeypatch.undo()
        phone_after = await http.get("/api/v1/me", headers=_bearer(phone))
        old_login = await http.post(
            "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
        )
    assert (response.status_code, phone_after.status_code, old_login.status_code) == (
        500,
        200,
        200,
    )  # the whole change rolled back: old password and other devices still work
    assert new_password not in response.text


async def test_s3_6_16_ending_the_same_session_twice_is_404_the_second_time(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    async with api_client(db_connection) as http:
        _, (_phone, laptop) = await _account(http, devices=2)
        listing = (await http.get("/api/v1/me/sessions", headers=_bearer(laptop))).json()
        phone_id = next(s["id"] for s in listing["items"] if not s["current"])
        first = await _end(http, laptop, phone_id)
        second = await _end(http, laptop, phone_id)
    assert (first.status_code, second.status_code) == (204, 404)
    assert second.json()["code"] == "session.not_found"
    ended = await db.execute(select(AuditLog).where(AuditLog.action == "auth.session_ended"))
    assert len(ended.scalars().all()) == 1


@pytest.mark.parametrize("action", ["end_other_device", "revoke_others", "logout_all"])
async def test_s3_6_17_ending_other_sessions_needs_the_current_password(
    db: AsyncSession, db_connection: AsyncConnection, action: str
) -> None:
    """ASVS V3.3.4 (level 2): a stolen access token alone can't sign the owner out
    elsewhere. Missing password: 422; wrong: 401, counted toward the lockout; right: 204."""
    async with api_client(db_connection) as http:
        email, (phone, stolen) = await _account(http, devices=2)
        phone_id = await _session_id(http, phone)
        path, body_key = {
            "end_other_device": (f"/api/v1/me/sessions/{phone_id}/revoke", "current_password"),
            "revoke_others": ("/api/v1/me/sessions/revoke-others", "current_password"),
            "logout_all": ("/api/v1/auth/logout-all", "current_password"),
        }[action]
        missing = await http.post(path, headers=_bearer(stolen))
        wrong = await http.post(path, json={body_key: "Wrong-Guess-123"}, headers=_bearer(stolen))
        phone_still_in = await http.get("/api/v1/me", headers=_bearer(phone))
        right = await http.post(path, json={body_key: PASSWORD}, headers=_bearer(stolen))
        phone_after = await http.get("/api/v1/me", headers=_bearer(phone))
    assert (missing.status_code, missing.json()["code"]) == (422, "auth.current_password_required")
    assert (wrong.status_code, wrong.json()["code"]) == (401, "auth.invalid_credentials")
    assert (phone_still_in.status_code, right.status_code, phone_after.status_code) == (
        200,
        204,
        401,
    )
    db.expunge_all()
    user = (await db.execute(select(User).where(User.email == email))).scalar_one()
    assert user.failed_login_count == 0  # the session's budget, not the account lockout
    failed = await db.execute(select(AuditLog).where(AuditLog.action == "auth.reauth_failed"))
    assert len(failed.scalars().all()) == 1


async def test_s3_6_18_ending_this_session_or_with_reauth_off_needs_no_password(
    db_connection: AsyncConnection,
) -> None:
    async with api_client(db_connection) as http:
        _, (laptop,) = await _account(http)
        this_one = await _session_id(http, laptop)
        own = await http.post(f"/api/v1/me/sessions/{this_one}/revoke", headers=_bearer(laptop))
    async with api_client(db_connection, auth=AuthSettings(reauth_to_end_sessions=False)) as http:
        _, (phone, laptop) = await _account(http, devices=2)
        phone_id = await _session_id(http, phone)
        other = await http.post(f"/api/v1/me/sessions/{phone_id}/revoke", headers=_bearer(laptop))
        others = await http.post("/api/v1/me/sessions/revoke-others", headers=_bearer(laptop))
        everything = await http.post("/api/v1/auth/logout-all", headers=_bearer(laptop))
    assert [r.status_code for r in (own, other, others, everything)] == [204, 204, 204, 204]


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"current_password": ""}, "auth.current_password_required"),
        ({"current_password": None}, "auth.current_password_required"),
        ({}, "auth.current_password_required"),
        ({"current_password": PASSWORD, "extra": 1}, "request.validation_failed"),
        ({"current_password": "x" * 1025}, "request.validation_failed"),
    ],
)
async def test_s3_6_19_the_reentry_body_is_validated(
    db: AsyncSession, db_connection: AsyncConnection, body: dict[str, object], code: str
) -> None:
    async with api_client(db_connection) as http:
        email, (tokens, _other) = await _account(http, devices=2)
        response = await http.post(
            "/api/v1/me/sessions/revoke-others", json=body, headers=_bearer(tokens)
        )
    assert (response.status_code, response.json()["code"]) == (422, code)
    db.expunge_all()
    attempts = await db.execute(
        select(UserSession.reauth_attempts)
        .join(User, User.id == UserSession.user_id)
        .where(User.email == email)
    )
    assert set(attempts.scalars()) == {0}  # nothing verified, nothing counted


async def test_s3_6_20_a_locked_account_can_still_end_a_thiefs_sessions(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    """Review round 5, M1: anonymous wrong logins lock the account, but the owner, signed
    in, can still end every other session with the right password (ADR-0012)."""
    async with api_client(db_connection) as http:
        email, (owner, thief) = await _account(http, devices=2)
        for guess in range(5):
            body = {"email": email, "password": f"Wrong-Guess-Number-{guess}"}
            await http.post("/api/v1/auth/login", json=body, headers={})
        locked_login = await http.post(
            "/api/v1/auth/login", json={"email": email, "password": PASSWORD}
        )
        ended = await _revoke_others(http, owner)
        thief_after = await http.get("/api/v1/me", headers=_bearer(thief))
    assert locked_login.status_code == 401  # the account is locked for logins
    assert (ended.status_code, thief_after.status_code) == (204, 401)
