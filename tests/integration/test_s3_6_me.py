"""Section 3.6: the signed-in user's profile, sessions and password."""

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.models import AuditLog, RevokeReason, User, UserSession
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
        response = await http.delete(f"/api/v1/me/sessions/{phone_id}", headers=_bearer(laptop))
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
        response = await http.delete(f"/api/v1/me/sessions/{session_id}", headers=_bearer(mine))
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
        response = await http.post("/api/v1/me/sessions/revoke-others", headers=_bearer(devices[1]))
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


async def test_s3_6_07_wrong_current_password_counts_toward_lockout(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    async with api_client(db_connection) as http:
        email, (tokens,) = await _account(http)
        wrong = {"current_password": "Not-My-Password-1", "new_password": NEW_PASSWORD}
        response = await http.post("/api/v1/me/password", json=wrong, headers=_bearer(tokens))
    assert (response.status_code, response.json()["code"]) == (401, "auth.invalid_credentials")
    db.expunge_all()
    user = (await db.execute(select(User).where(User.email == email))).scalar_one()
    assert user.failed_login_count == 1


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"current_password": PASSWORD, "new_password": "short"}, "user.password_weak"),
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
        ("DELETE", f"/api/v1/me/sessions/{uuid.uuid4()}"),
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
        first = await http.post("/api/v1/me/sessions/revoke-others", headers=_bearer(devices[0]))
        before = await _reasons(db, email)
        second = await http.post("/api/v1/me/sessions/revoke-others", headers=_bearer(devices[0]))
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
        response = await http.delete(f"/api/v1/me/sessions/{this_one}", headers=_bearer(laptop))
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
