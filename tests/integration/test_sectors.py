"""Sector templates (wording, unit types, roles) + "own" scopes via relations.

A college adopts the education template; a teacher sees only students they teach.
Requires the CI seed (scripts/ci_bootstrap_db.py) and rate limits off.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

import main
from models.relations import ResourceRelation
from models.units import OrgUnit, OrgUnitMember
from models.user_model import Organization, User
from utils.database import SessionLocal
from utils.jwt_config import get_password_hash

pytestmark = pytest.mark.integration

SUPER = ("test_super_admin", "TestSuperAdminPass123!")
PASSWORD = "SectorTest123!"


def _login(c, username, password=PASSWORD, org=None):
    r = c.post("/api/v1/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    h = {"Authorization": "Bearer " + r.json()["access_token"]}
    if org is not None:
        h["X-Organization-Id"] = str(org)
    return h


@pytest.fixture
def college():
    sfx = uuid.uuid4().hex[:6]
    db = SessionLocal()
    org = Organization(name=f"Sunrise College {sfx}", slug=f"sunrise-{sfx}", status="active")
    other = Organization(name=f"City Hospital {sfx}", slug=f"city-hosp-{sfx}", status="active")
    db.add_all([org, other])
    db.flush()
    hashed = get_password_hash(PASSWORD)
    people = {}
    for key, role in (("principal", "organization_admin"), ("teacher", "user"), ("hod", "user"),
                      ("student_a", "user"), ("student_b", "user"), ("staff_admin", "admin")):
        u = User(username=f"{key}_{sfx}", email=f"{key}_{sfx}@sector-example.com", password_hash=hashed,
                 status="active", phone_number="1234567890", role=role, organization_id=org.id)
        db.add(u)
        people[key] = u
    db.commit()
    ctx = {"org": org.id, "other": other.id, "sfx": sfx,
           "ids": {k: u.id for k, u in people.items()}, "names": {k: u.username for k, u in people.items()}}
    db.close()
    yield ctx
    db = SessionLocal()
    for oid in (ctx["org"], ctx["other"]):
        db.query(ResourceRelation).filter(ResourceRelation.organization_id == oid).delete(synchronize_session=False)
        unit_ids = [u for (u,) in db.query(OrgUnit.id).filter(OrgUnit.organization_id == oid)]
        if unit_ids:
            db.query(OrgUnitMember).filter(OrgUnitMember.unit_id.in_(unit_ids)).delete(synchronize_session=False)
    for u in db.query(User).filter(User.id.in_(list(ctx["ids"].values()))):
        db.delete(u)
    db.commit()
    for oid in (ctx["org"], ctx["other"]):
        for unit in sorted(db.query(OrgUnit).filter(OrgUnit.organization_id == oid), key=lambda u: -u.depth):
            db.delete(unit)
            db.commit()
        db.query(Organization).filter(Organization.id == oid).delete()
        db.commit()
    db.close()


def test_education_template_end_to_end(college):
    org, ids, names = college["org"], college["ids"], college["names"]
    with TestClient(main.app) as c:
        sup = _login(c, *SUPER)
        # super admin: college -> education, another org -> medical (creates doctor role)
        r = c.put(f"/api/v1/organizations/{org}/sector-template", json={"template": "education"},
                  headers={**sup, "X-Organization-Id": str(org)})
        assert r.status_code == 200, r.text
        assert r.json()["vocabulary"]["sector"] == "education"
        assert c.put(f"/api/v1/organizations/{college['other']}/sector-template", json={"template": "medical"},
                     headers={**sup, "X-Organization-Id": str(college["other"])}).status_code == 200
        assert c.get("/api/v1/sector-templates", headers=sup).status_code == 200

        p = _login(c, names["principal"])
        voc = c.get("/api/v1/vocabulary", headers=p).json()
        assert voc["terms"]["member"] == "Student"
        assert voc["role_labels"]["organization_admin"] == "Principal"
        assert voc["role_labels"]["teacher"] == "Teacher"
        assert c.patch("/api/v1/vocabulary", json={"terms": {"member": "Learner"}}, headers=p).json()["terms"]["member"] == "Learner"
        assert c.patch("/api/v1/vocabulary", json={"terms": {"member": None}}, headers=p).json()["terms"]["member"] == "Student"

        # unit types follow the template
        assert c.post("/api/v1/units", json={"name": "Lonely class", "unit_type": "class"}, headers=p).status_code == 400
        assert c.post("/api/v1/units", json={"name": "Ward 1", "unit_type": "ward"}, headers=p).status_code == 400
        sci = c.post("/api/v1/units", json={"name": "Science", "unit_type": "department"}, headers=p).json()
        arts = c.post("/api/v1/units", json={"name": "Arts", "unit_type": "department"}, headers=p).json()
        r = c.post("/api/v1/units", json={"name": "10-A", "unit_type": "class", "parent_id": sci["id"]}, headers=p)
        assert r.status_code == 201, r.text
        cls = r.json()

        # custom roles through the normal user API; other sectors' roles refused
        r = c.patch(f"/api/v1/users/{ids['teacher']}", json={"role": "teacher"}, headers=p)
        assert r.status_code == 200, r.text
        assert r.json()["user"]["role"] == "teacher"
        assert c.patch(f"/api/v1/users/{ids['student_a']}", json={"role": "doctor"}, headers=p).status_code == 400

        # teacher (users:*@own) sees nobody until linked
        t = _login(c, names["teacher"])
        assert c.get("/api/v1/users", headers=t).json().get("users", []) == []
        assert c.post("/api/v1/relations", json={"subject_user_id": ids["teacher"], "relation": "attends",
                                                 "object_user_id": ids["student_a"]}, headers=p).status_code == 400
        rel = c.post("/api/v1/relations", json={"subject_user_id": ids["teacher"], "relation": "teaches",
                                                "object_user_id": ids["student_a"]}, headers=p)
        assert rel.status_code == 201, rel.text
        seen = {u["username"] for u in c.get("/api/v1/users", headers=t).json()["users"]}
        assert seen == {names["student_a"]}
        assert c.get(f"/api/v1/users/{ids['student_a']}", headers=t).status_code == 200
        assert c.get(f"/api/v1/users/{ids['student_b']}", headers=t).status_code == 404
        assert c.patch(f"/api/v1/users/{ids['student_a']}", json={"phone_number": "5551112222"}, headers=t).status_code == 200
        assert c.patch(f"/api/v1/users/{ids['student_b']}", json={"phone_number": "5551113333"}, headers=t).status_code in (400, 403, 404)
        # the teacher cannot link people themselves
        assert c.post("/api/v1/relations", json={"subject_user_id": ids["teacher"], "relation": "teaches",
                                                 "object_user_id": ids["student_b"]}, headers=t).status_code == 403
        own = c.get(f"/api/v1/relations?subject_user_id={ids['teacher']}", headers=t).json()["relations"]
        assert len(own) == 1
        assert c.delete(f"/api/v1/relations/{rel.json()['id']}", headers=p).status_code == 200
        assert c.get(f"/api/v1/users/{ids['student_a']}", headers=t).status_code == 404

        # head of department manages structure below their department
        assert c.post(f"/api/v1/units/{sci['id']}/roles", json={"user_id": ids["hod"], "role": "hod"},
                      headers=p).status_code == 201
        h = _login(c, names["hod"])
        assert c.post("/api/v1/units", json={"name": "10-B", "unit_type": "class", "parent_id": sci["id"]},
                      headers=h).status_code == 201
        assert c.post("/api/v1/units", json={"name": "Music", "unit_type": "department"}, headers=h).status_code == 403
        assert c.patch(f"/api/v1/units/{sci['id']}", json={"name": "Sciences"}, headers=h).status_code == 403
        assert c.patch(f"/api/v1/units/{cls['id']}", json={"name": "10-A Physics"}, headers=h).status_code == 200
        assert c.post(f"/api/v1/units/{cls['id']}/move", json={"parent_id": arts["id"]}, headers=h).status_code == 403

        # moves: invalid type placement refused; principal moves a class across departments
        assert c.post(f"/api/v1/units/{cls['id']}/move", json={"parent_id": None}, headers=p).status_code == 400
        moved = c.post(f"/api/v1/units/{cls['id']}/move", json={"parent_id": arts["id"]}, headers=p)
        assert moved.status_code == 200, moved.text
        assert moved.json()["path"].startswith(arts["path"])
        assert c.post(f"/api/v1/units/{sci['id']}/move", json={"parent_id": sci["id"]}, headers=p).status_code == 400

        # switching the college to the medical template is refused (units do not fit)
        r = c.put(f"/api/v1/organizations/{org}/sector-template", json={"template": "medical"},
                  headers={**sup, "X-Organization-Id": str(org)})
        assert r.status_code == 409


def test_template_switch_guard_permission_sync_and_relation_visibility(college):
    from models.rbac_model import Permission, Role, RolePermission

    org, other, ids = college["org"], college["other"], college["ids"]
    with TestClient(main.app) as c:
        sup = _login(c, *SUPER)
        in_other = {**sup, "X-Organization-Id": str(other)}
        assert c.put(f"/api/v1/organizations/{other}/sector-template", json={"template": "medical"},
                     headers=in_other).status_code == 200

        # someone holds 'nurse' in the hospital -> switching it to education is refused
        r = c.post(f"/api/v1/organizations/{other}/members",
                   json={"user_id": ids["student_b"], "role": "nurse"}, headers=in_other)
        assert r.status_code == 201, r.text
        r = c.put(f"/api/v1/organizations/{other}/sector-template", json={"template": "education"},
                  headers=in_other)
        assert r.status_code == 409 and "nurse (1)" in r.json()["detail"]
        assert c.delete(f"/api/v1/organizations/{other}/members/{ids['student_b']}",
                        headers=in_other).status_code == 200
        assert c.put(f"/api/v1/organizations/{other}/sector-template", json={"template": "education"},
                     headers=in_other).status_code == 200

        # applying a template syncs its roles' permissions exactly (extras removed)
        db = SessionLocal()
        teacher = db.query(Role).filter(Role.name == "teacher", Role.is_system.is_(True)).one()
        extra = db.query(Permission).filter(Permission.name == "audit:export").one()
        db.query(RolePermission).filter(RolePermission.role_id == teacher.id,
                                        RolePermission.permission_id == extra.id).delete()
        db.add(RolePermission(role_id=teacher.id, permission_id=extra.id, scope="all"))
        db.commit()
        db.close()
        r = c.put(f"/api/v1/organizations/{org}/sector-template", json={"template": "education"},
                  headers={**sup, "X-Organization-Id": str(org)})
        assert r.status_code == 200, r.text
        assert "teacher:audit:export" in r.json()["permissions_removed"]

        # relations: a plain admin cannot see one involving the principal (ranks above them)
        r = c.post("/api/v1/relations", json={"subject_user_id": ids["principal"], "relation": "mentors",
                                              "object_user_id": ids["student_a"]},
                   headers={**sup, "X-Organization-Id": str(org)})
        assert r.status_code == 201, r.text
        staff = _login(c, college["names"]["staff_admin"])
        assert all(rel["subject_user_id"] != ids["principal"]
                   for rel in c.get("/api/v1/relations", headers=staff).json()["relations"])
        principal = _login(c, college["names"]["principal"])
        assert any(rel["subject_user_id"] == ids["principal"]
                   for rel in c.get("/api/v1/relations", headers=principal).json()["relations"])
