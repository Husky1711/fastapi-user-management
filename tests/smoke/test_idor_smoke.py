"""
IDOR smoke tests — cross-organization access denials by resource ID.

Staff in org 1 must not read or mutate org 2 users, groups, or API keys.
"""

from __future__ import annotations

import pytest

from models.user_model import ApiKey, User, UserGroup
from conftest import auth_headers, login
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
    ("username", "password", "method", "path_key"),
    [
        ("testorgadmin", "orgadmin123", "GET", "org2_group_id"),
        ("testadmin", "admin123", "PATCH", "org2_group_id"),
        ("testorgadmin", "orgadmin123", "GET", "org2_api_key_id"),
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
