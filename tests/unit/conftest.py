"""Unit-test fixtures: role rules come from the seed defaults, not a live database."""

import pytest

from services.permissions import role_catalog


@pytest.fixture(autouse=True)
def default_role_catalog(monkeypatch):
    monkeypatch.setattr(role_catalog, "_load_from_db", lambda: {})
    role_catalog.invalidate_cache()
    yield
    role_catalog.invalidate_cache()
