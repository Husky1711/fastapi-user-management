"""Sector template files are valid and wording merges in the right order."""

from types import SimpleNamespace

import pytest

from services.sector import template_service as ts


def test_all_templates_load_and_reference_known_permissions():
    from services.permissions.user_permission_service import UserPermissionService

    known = set(UserPermissionService.STANDARD_PERMISSIONS)
    templates = ts.templates()
    assert {"generic", "education", "medical", "pharma"} <= set(templates)
    for t in templates.values():
        for role in t["roles"]:
            for entry in role["permissions"]:
                if entry != "*":
                    name, _, scope = entry.partition("@")
                    assert name in known, f"{t['key']}:{role['name']} -> {name}"
                    assert scope in ("", "own")


def test_role_levels_do_not_clash_across_templates():
    seen = {}
    for t in ts.templates().values():
        for role in t["roles"]:
            assert seen.setdefault(role["name"], role["level"]) == role["level"], role["name"]


def test_vocabulary_merges_generic_template_and_overrides():
    org = SimpleNamespace(
        id=1, sector_template="education",
        vocabulary_overrides={"terms": {"member": "Learner"}, "role_labels": {"teacher": "Tutor"}},
    )
    v = ts.vocabulary(org)
    assert v["terms"]["member"] == "Learner"          # org override
    assert v["terms"]["organization"] == "Institution"  # template
    assert v["role_labels"]["teacher"] == "Tutor"
    assert v["role_labels"]["organization_admin"] == "Principal"
    assert [u["key"] for u in v["unit_types"]] == ["campus", "department", "class"]


def test_orgs_without_a_template_are_unrestricted(monkeypatch):
    monkeypatch.setattr(ts, "chosen_template_key", lambda org_id: None)
    assert ts.allowed_role_names(1) is None
    ts.validate_unit_type(1, "anything", None)  # no error
    ts.validate_relation(1, "anything")


def test_template_rules_enforced_when_chosen(monkeypatch):
    monkeypatch.setattr(ts, "chosen_template_key", lambda org_id: "medical")
    assert "doctor" in ts.allowed_role_names(1) and "teacher" not in ts.allowed_role_names(1)
    ts.validate_unit_type(1, "ward", "hospital")
    with pytest.raises(ts.TemplateError):
        ts.validate_unit_type(1, "ward", None)
    with pytest.raises(ts.TemplateError):
        ts.validate_relation(1, "teaches")
