"""One person, several organizations, a different role in each.

Scenario: a regular user of org 1 becomes an admin of a second college.
Requires the CI seed (scripts/ci_bootstrap_db.py) and rate limits off.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

import main
from models.user_model import Organization, User
from utils.database import SessionLocal

pytestmark = pytest.mark.integration

SUPER = ("test_super_admin", "TestSuperAdminPass123!")
MEMBER = ("testuser", "user123")  # plain user in org 1


def _login(client, creds):
    r = client.post("/api/v1/login", json={"username": creds[0], "password": creds[1]})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture
def second_college():
    db = SessionLocal()
    slug = f"college-{uuid.uuid4().hex[:8]}"
    org = Organization(name=f"Second College {slug}", slug=slug, status="active")
    db.add(org)
    db.commit()
    org_id = org.id
    db.close()
    yield org_id
    db = SessionLocal()
    user = db.query(User).filter(User.username == MEMBER[0]).one()
    for m in list(user.memberships):
        if m.organization_id == org_id:
            user.memberships.remove(m)
    for a in list(user.role_assignments):
        if a.organization_id == org_id:
            user.role_assignments.remove(a)
    db.commit()
    db.query(Organization).filter(Organization.id == org_id).delete()
    db.commit()
    db.close()


def test_member_of_two_orgs_has_a_role_per_org(second_college):
    org2 = second_college
    with TestClient(main.app) as c:
        sup = _login(c, SUPER)
        member_id = c.get("/api/v1/profile", headers=_login(c, MEMBER)).json()["id"]

        # platform staff adds the org-1 user to the second college as an admin
        r = c.post(
            f"/api/v1/organizations/{org2}/members",
            json={"user_id": member_id, "role": "admin"},
            headers={**sup, "X-Organization-Id": str(org2)},
        )
        assert r.status_code == 201, r.text
        again = c.post(
            f"/api/v1/organizations/{org2}/members",
            json={"user_id": member_id, "role": "admin"},
            headers={**sup, "X-Organization-Id": str(org2)},
        )
        assert again.status_code == 409

        me = _login(c, MEMBER)
        orgs = c.get("/api/v1/me/organizations", headers=me).json()
        roles = {o["organization_id"]: o["role"] for o in orgs["organizations"]}
        assert roles[org2] == "admin"
        home = orgs["active_organization_id"]
        assert roles[home] == "user"

        # Home org (no header): plain user -> admin-only gate denied
        assert c.get("/api/v1/invitations", headers=me).status_code == 403
        # Acting in the second college: admin there -> allowed
        in_org2 = {**me, "X-Organization-Id": str(org2)}
        assert c.get("/api/v1/invitations", headers=in_org2).status_code == 200
        assert c.get("/api/v1/me/organizations", headers=in_org2).json()[
            "active_organization_id"
        ] == org2
        # Explicitly acting in the home org: still a plain user (no leak)
        in_home = {**me, "X-Organization-Id": str(home)}
        assert c.get("/api/v1/invitations", headers=in_home).status_code == 403

        # Not a member of org 2 (System org) -> refused
        r = c.get("/api/v1/me/organizations", headers={**me, "X-Organization-Id": "2"})
        assert r.status_code == 403
        assert r.json()["error_code"] == "NOT_ORGANIZATION_MEMBER"
        bad = c.get("/api/v1/me/organizations", headers={**me, "X-Organization-Id": "abc"})
        assert bad.status_code == 400

        # Cannot remove a user's home membership
        r = c.delete(
            f"/api/v1/organizations/{home}/members/{member_id}",
            headers={**sup, "X-Organization-Id": str(home)},
        )
        assert r.status_code == 400

        # Remove from the second college: admin rights there end immediately
        r = c.delete(
            f"/api/v1/organizations/{org2}/members/{member_id}",
            headers={**sup, "X-Organization-Id": str(org2)},
        )
        assert r.status_code == 200, r.text
        assert c.get("/api/v1/invitations", headers=in_org2).status_code == 403


def test_tenant_admin_cannot_grant_membership_in_other_org(second_college):
    with TestClient(main.app) as c:
        admin = _login(c, ("testadmin", "admin123"))
        r = c.post(
            f"/api/v1/organizations/{second_college}/members",
            json={"email": "user@test.com", "role": "user"},
            headers=admin,  # acting in its own org, not the target org
        )
        assert r.status_code == 403
        r = c.post(
            f"/api/v1/organizations/{second_college}/members",
            json={"email": "user@test.com", "role": "user"},
            headers={**admin, "X-Organization-Id": str(second_college)},
        )
        assert r.status_code == 403  # not a member of that org


def test_inviting_an_existing_user_adds_a_membership():
    admin_creds = ("testadmin", "admin123")          # admin in org 1
    invitee_creds = ("testuser_org2", "user2123")    # exists, home org 2
    other_creds = ("testuser", "user123")            # someone else
    with TestClient(main.app) as c:
        admin = _login(c, admin_creds)
        home = c.get("/api/v1/me/organizations", headers=admin).json()["active_organization_id"]

        r = c.post(
            "/api/v1/invitations",
            json={"email": "user2@test.com", "role": "user"},
            headers=admin,
        )
        assert r.status_code == 200, r.text
        token = r.json().get("invite_token")
        assert token, "dev mode returns the raw token"

        v = c.get(f"/api/v1/invitations/validate/{token}").json()
        assert v["existing_account"] is True and v["organization_id"] == home

        # Sign-up path refuses an email that already has an account
        r = c.post(
            "/api/v1/invitations/accept",
            json={"token": token, "username": "newname_x", "password": "Password123!"},
        )
        assert r.status_code == 400

        # A different signed-in user cannot use the link
        r = c.post(
            "/api/v1/invitations/accept-existing",
            json={"token": token},
            headers=_login(c, other_creds),
        )
        assert r.status_code == 403

        invitee = _login(c, invitee_creds)
        r = c.post("/api/v1/invitations/accept-existing", json={"token": token}, headers=invitee)
        assert r.status_code == 200, r.text
        roles = {
            o["organization_id"]: o["role"]
            for o in c.get("/api/v1/me/organizations", headers=invitee).json()["organizations"]
        }
        assert roles.get(home) == "user"

        # Token is spent; re-inviting a current member is refused
        r = c.post("/api/v1/invitations/accept-existing", json={"token": token}, headers=invitee)
        assert r.status_code == 400
        r = c.post(
            "/api/v1/invitations", json={"email": "user2@test.com", "role": "user"}, headers=admin
        )
        assert r.status_code == 400

    # cleanup: drop the added membership
    db = SessionLocal()
    user = db.query(User).filter(User.username == invitee_creds[0]).one()
    for m in list(user.memberships):
        if m.organization_id == home:
            user.memberships.remove(m)
    for a in list(user.role_assignments):
        if a.organization_id == home:
            user.role_assignments.remove(a)
    db.commit()
    db.close()
