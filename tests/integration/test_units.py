"""Roles on org units: a department head manages their department only.

CS head = plain user org-wide + 'admin' on the CS department unit.
Requires the CI seed (scripts/ci_bootstrap_db.py) and rate limits off.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

import main
from models.units import OrgUnit, OrgUnitMember
from models.user_model import User
from utils.database import SessionLocal
from utils.jwt_config import get_password_hash

pytestmark = pytest.mark.integration

ORG_ADMIN = ("testorgadmin", "orgadmin123")
PASSWORD = "UnitTest123!"


def _login(client, username, password=PASSWORD):
    r = client.post("/api/v1/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture
def people():
    sfx = uuid.uuid4().hex[:6]
    names = {k: f"{k}_{sfx}" for k in ("hod", "cs_student", "math_student")}
    db = SessionLocal()
    hashed = get_password_hash(PASSWORD)
    for name in names.values():
        db.add(User(username=name, email=f"{name}@unit-example.com", password_hash=hashed,
                    status="active", phone_number="1234567890", role="user", organization_id=1))
    db.commit()
    ids = {k: db.query(User.id).filter(User.username == v).scalar() for k, v in names.items()}
    db.close()
    yield names, ids
    db = SessionLocal()
    uid = list(ids.values())
    db.query(OrgUnitMember).filter(OrgUnitMember.user_id.in_(uid)).delete(synchronize_session=False)
    for u in db.query(User).filter(User.id.in_(uid)):
        db.delete(u)
    db.commit()
    for unit in sorted(db.query(OrgUnit).filter(OrgUnit.name.like(f"%{sfx}%")), key=lambda u: -u.depth):
        db.delete(unit)
        db.commit()
    db.close()


def test_department_head_manages_only_their_department(people):
    names, ids = people
    sfx = names["hod"].split("_")[-1]
    with TestClient(main.app) as c:
        oa = _login(c, *ORG_ADMIN)

        cs = c.post("/api/v1/units", json={"name": f"CS {sfx}", "unit_type": "Department"}, headers=oa)
        assert cs.status_code == 201, cs.text
        cs = cs.json()
        assert cs["unit_type"] == "department" and cs["depth"] == 0
        cls = c.post("/api/v1/units", json={"name": f"Class A {sfx}", "unit_type": "class",
                                            "parent_id": cs["id"]}, headers=oa).json()
        assert cls["depth"] == 1 and cls["path"].startswith(cs["path"])
        math = c.post("/api/v1/units", json={"name": f"Math {sfx}", "unit_type": "department"},
                      headers=oa).json()
        dup = c.post("/api/v1/units", json={"name": f"cs {sfx}", "unit_type": "department"}, headers=oa)
        assert dup.status_code == 409

        assert c.post(f"/api/v1/units/{cls['id']}/members", json={"user_id": ids["cs_student"]},
                      headers=oa).status_code == 201
        assert c.post(f"/api/v1/units/{math['id']}/members", json={"user_id": ids["math_student"]},
                      headers=oa).status_code == 201
        r = c.post(f"/api/v1/units/{cs['id']}/roles", json={"user_id": ids["hod"], "role": "admin"},
                   headers=oa)
        assert r.status_code == 201, r.text

        hod = _login(c, names["hod"])
        # sees people under CS (incl. the class below it), not Math
        listed = c.get("/api/v1/users", headers=hod).json()
        usernames = {u["username"] for u in listed.get("users", [])}
        assert names["cs_student"] in usernames
        assert names["math_student"] not in usernames
        assert c.get(f"/api/v1/users/{ids['cs_student']}", headers=hod).status_code == 200
        assert c.get(f"/api/v1/users/{ids['math_student']}", headers=hod).status_code == 404

        # edits within the department; org-level fields stay off limits
        r = c.patch(f"/api/v1/users/{ids['cs_student']}", json={"phone_number": "5550001111"}, headers=hod)
        assert r.status_code == 200, r.text
        r = c.patch(f"/api/v1/users/{ids['cs_student']}", json={"role": "admin"}, headers=hod)
        assert r.status_code == 400
        r = c.patch(f"/api/v1/users/{ids['math_student']}", json={"phone_number": "5550002222"}, headers=hod)
        assert r.status_code in (400, 403, 404)

        # no org-wide powers
        assert c.get("/api/v1/invitations", headers=hod).status_code == 403
        assert c.post("/api/v1/units", json={"name": "x", "unit_type": "class"}, headers=hod).status_code == 403
        assert c.post(f"/api/v1/units/{math['id']}/members", json={"user_id": ids["cs_student"]},
                      headers=hod).status_code == 403
        # cannot grant a role equal to its own; can see the subtree's members
        r = c.post(f"/api/v1/units/{cls['id']}/roles", json={"user_id": ids["cs_student"], "role": "admin"},
                   headers=hod)
        assert r.status_code == 403
        sub = c.get(f"/api/v1/units/{cs['id']}/members?include_subtree=true", headers=hod).json()
        assert names["cs_student"] in {m["username"] for m in sub["members"]}

        # a unit with people in it cannot be deleted
        assert c.delete(f"/api/v1/units/{cls['id']}", headers=oa).status_code == 409

        # revoking the unit role ends access immediately
        assert c.delete(f"/api/v1/units/{cs['id']}/roles/{ids['hod']}/admin", headers=oa).status_code == 200
        assert c.get(f"/api/v1/users/{ids['cs_student']}", headers=hod).status_code == 404
        assert c.patch(f"/api/v1/users/{ids['cs_student']}", json={"phone_number": "5550003333"},
                       headers=hod).status_code == 403
