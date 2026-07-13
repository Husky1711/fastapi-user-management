"""Unit tests for backup DATABASE_URL parsing (no mysqldump required)."""

import pytest

from scripts.backup_database import _mysql_dump_config


@pytest.mark.unit
def test_mysql_dump_config_parses_sqlalchemy_url():
    cfg = _mysql_dump_config(
        "mysql+pymysql://backup_user:s%40cret@db.example:3307/fastapi_users"
    )
    assert cfg["user"] == "backup_user"
    assert cfg["password"] == "s@cret"
    assert cfg["host"] == "db.example"
    assert cfg["port"] == "3307"
    assert cfg["database"] == "fastapi_users"


@pytest.mark.unit
def test_mysql_dump_config_rejects_non_mysql():
    with pytest.raises(ValueError, match="MySQL"):
        _mysql_dump_config("postgresql+psycopg://u:p@localhost/db")
