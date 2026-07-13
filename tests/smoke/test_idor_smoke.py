"""
IDOR smoke tests — cross-organization access denials by resource ID.

Staff in org 1 must not read or mutate org 2 users, groups, API keys,
permissions, or audit rows scoped to another tenant.
"""

from __future__ import annotations

import pytest

from models.user_model import ApiKey, User, UserGroup
from tests.smoke.conftest import auth_headers, login
from utils.database import SessionLocal

pytestmark = pytest.mark.smoke


@pytest.fixture(scope="session")
def cross_org_ids() -> dict[str, int]:
    db = SessionLocal()
    try:
        org2_user = (
            db.query(User).filter(User.username == "testuser_org2").one_or_none()
        )
        assert org2_user is not None, "Seed user testuser_org2 missing (bootstrap failed?)"

        group = (
            db.query(UserGroup)
            .filter(UserGroup.name == "CI Org2 Group", UserGroup.organization_id == 2)
            .one_or_none()
        )
        assert group is not None, "Seed group CI Org2 Group missing (bootstrap failed?)"

        api_key = (
            db.query(ApiKey)
            .filter(ApiKey.key_name == "CI Org2 API Key", ApiKey.organization_id == 2)
            .one_or_none()
        )
        assert api_key is not None, "Seed API key CI Org2 API Key missing (bootstrap failed?)"

        return {
            "org2_user_id": org2_user.id,
            "org2_group_id": group.id,
            "org2_api_key_id": api_key.id,
        }
    finally:
        db.close()


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("testorgadmin", "orgadmin123"),
        ("testadmin", "admin123"),
    ],
)
def test_cannot_read_user_in_other_org(
    client,
    cross_org_ids: dict[str, int],
    username: str,
    password: str,
) -> None:
    tokens = login(client, username, password)
    response = client.get(
        f"/api/v1/users/{cross_org_ids['org2_user_id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code in (403, 404, 405), response.text


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("testorgadmin", "orgadmin123"),
        ("testadmin", "admin123"),
    ],
)
def test_cannot_soft_delete_user_in_other_org(
    client,
    cross_org_ids: dict[str, int],
    username: str,
    password: str,
) -> None:
    tokens = login(client, username, password)
    response = client.delete(
        f"/api/v1/users/{cross_org_ids['org2_user_id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code in (403, 404, 405), response.text


@pytest.mark.parametrize(
    ("username", "password", "method", "path_key"),
    [
        ("testorgadmin", "orgadmin123", "GET", "org2_group_id"),
        ("testadmin", "admin123", "PATCH", "org2_group_id"),
        ("testorgadmin", "orgadmin123", "DELETE", "org2_group_id"),
        ("testorgadmin", "orgadmin123", "GET", "org2_api_key_id"),
        ("testadmin", "admin123", "PATCH", "org2_api_key_id"),
        ("testadmin", "admin123", "DELETE", "org2_api_key_id"),
    ],
)
def test_cannot_access_other_org_compliance_resources(
    client,
    cross_org_ids: dict[str, int],
    username: str,
    password: str,
    method: str,
    path_key: str,
) -> None:
    tokens = login(client, username, password)
    headers = auth_headers(tokens["access_token"])

    if path_key == "org2_group_id":
        resource_id = cross_org_ids["org2_group_id"]
        url = f"/api/v1/groups/{resource_id}"
        body = {"name": "blocked-update"} if method == "PATCH" else None
    else:
        resource_id = cross_org_ids["org2_api_key_id"]
        url = f"/api/v1/api-keys/{resource_id}"
        body = {"key_name": "blocked-update"} if method == "PATCH" else None

    if method == "GET":
        response = client.get(url, headers=headers)
    elif method == "PATCH":
        response = client.patch(url, headers=headers, json=body)
    elif method == "DELETE":
        response = client.delete(url, headers=headers)
    else:
        raise ValueError(f"Unsupported method: {method}")

    assert response.status_code in (403, 404, 405), response.text


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("testorgadmin", "orgadmin123"),
        ("testadmin", "admin123"),
    ],
)
def test_cannot_list_group_members_in_other_org(
    client,
    cross_org_ids: dict[str, int],
    username: str,
    password: str,
) -> None:
    tokens = login(client, username, password)
    response = client.get(
        f"/api/v1/groups/{cross_org_ids['org2_group_id']}/members",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code in (403, 404, 405), response.text


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("testorgadmin", "orgadmin123"),
        ("testadmin", "admin123"),
    ],
)
def test_cannot_read_permissions_for_other_org_user(
    client,
    cross_org_ids: dict[str, int],
    username: str,
    password: str,
) -> None:
    tokens = login(client, username, password)
    response = client.get(
        f"/api/v1/permissions?user_id={cross_org_ids['org2_user_id']}",
        headers=auth_headers(tokens["access_token"]),
    )
    assert response.status_code in (403, 404), response.text


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("testorgadmin", "orgadmin123"),
        ("testadmin", "admin123"),
    ],
)
def test_cannot_filter_audit_logs_to_other_org(
    client,
    cross_org_ids: dict[str, int],
    username: str,
    password: str,
) -> None:
    """Org staff must not pull another tenant's audit stream via organization_id."""
    tokens = login(client, username, password)
    headers = auth_headers(tokens["access_token"])

    by_org = client.get("/api/v1/audit/logs?organization_id=2&limit=5", headers=headers)
    # Forbidden, not found, or empty-success with zero rows / forced self-org — never 200 with org2 data
    if by_org.status_code == 200:
        payload = by_org.json()
        logs = payload.get("logs") or payload.get("data") or []
        for row in logs:
            assert row.get("organization_id") in (None, 1), row
    else:
        assert by_org.status_code in (403, 404), by_org.text

    by_user = client.get(
        f"/api/v1/audit/logs?user_id={cross_org_ids['org2_user_id']}&limit=5",
        headers=headers,
    )
    if by_user.status_code == 200:
        payload = by_user.json()
        logs = payload.get("logs") or payload.get("data") or []
        for row in logs:
            assert row.get("user_id") != cross_org_ids["org2_user_id"], row
    else:
        assert by_user.status_code in (403, 404), by_user.text
