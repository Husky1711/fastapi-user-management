"""Tests for Option B role dual-write invariant helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from services.permissions.rbac_catalog_service import RbacCatalogService


def test_apply_effective_role_prefers_catalog():
    user = SimpleNamespace(id=7, role="user")
    db = MagicMock()
    with patch.object(
        RbacCatalogService, "get_effective_system_role", return_value="admin"
    ):
        with patch(
            "sqlalchemy.orm.attributes.set_committed_value"
        ) as set_committed:
            effective = RbacCatalogService.apply_effective_role(db, user)
    assert effective == "admin"
    set_committed.assert_called_once()


def test_find_role_drifts_when_catalog_diverges():
    user = SimpleNamespace(id=1, username="alice", role="admin", deleted_at=None)

    user_q = MagicMock()
    user_q.filter.return_value.all.return_value = [user]

    membership_q = MagicMock()
    membership_q.join.return_value.filter.return_value.first.return_value = (1,)

    db = MagicMock()

    def query_side_effect(entity):
        # First: User list; later: UserRole.id membership check
        label = getattr(entity, "key", None) or getattr(entity, "name", None)
        if label == "id" or str(entity).endswith(".id"):
            return membership_q
        return user_q

    db.query.side_effect = query_side_effect

    with patch.object(
        RbacCatalogService, "get_effective_system_role", return_value="user"
    ):
        drifts = RbacCatalogService.find_role_drifts(db)

    assert len(drifts) == 1
    assert drifts[0]["users_role"] == "admin"
    assert drifts[0]["catalog_role"] == "user"
