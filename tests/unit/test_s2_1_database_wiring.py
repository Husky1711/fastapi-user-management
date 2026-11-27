"""Section 2.1: database wiring that needs no running database."""

import json
import logging

import pytest
from fastapi import APIRouter
from pydantic import SecretStr
from sqlalchemy import CheckConstraint, Column, ForeignKey, Integer, MetaData, Table, Text, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.core.config import DatabaseSettings
from app.core.deps import DbSession
from app.core.logging import JsonFormatter
from app.main import create_app
from app.models.base import NAMING_CONVENTION
from tests.helpers import check_ok, client_for, make_settings

UNREACHABLE_PASSWORD = "unreachable-db-s3cret"
UNREACHABLE_DB = DatabaseSettings(
    # Port 1 on loopback: nothing listens there, so the connection is refused at once.
    url=SecretStr(f"postgresql+asyncpg://app:{UNREACHABLE_PASSWORD}@127.0.0.1:1/app"),
    pool_timeout_seconds=2,
)


def test_s2_1_06_naming_convention_names_every_constraint() -> None:
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    Table("parents", metadata, Column("id", Integer, primary_key=True))
    child = Table(
        "children",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("parent_id", ForeignKey("parents.id", ondelete="CASCADE"), index=True),
        Column("code", Text, unique=True),
        CheckConstraint("length(code) > 0", name="code_not_empty"),
    )
    ddl = str(CreateTable(child).compile(dialect=postgresql.dialect()))
    for name in (
        "pk_children",
        "fk_children_parent_id_parents",
        "uq_children_code",
        "ck_children_code_not_empty",
    ):
        assert f"CONSTRAINT {name}" in ddl
    (index,) = child.indexes
    assert "ix_children_parent_id" in str(CreateIndex(index).compile(dialect=postgresql.dialect()))


def _query_router() -> APIRouter:
    router = APIRouter()

    @router.get("/_test/query")
    async def query(session: DbSession) -> int:
        return int((await session.execute(text("SELECT 1"))).scalar_one())

    return router


async def test_s2_1_07_unreachable_database_gives_generic_500(
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = make_settings(database=UNREACHABLE_DB)
    app = create_app(settings, health_checks={"database": check_ok}, api_routers=[_query_router()])
    with caplog.at_level(logging.INFO):
        async with app.router.lifespan_context(app), client_for(app) as http:
            response = await http.get("/api/v1/_test/query")
    assert response.status_code == 500
    assert response.json()["code"] == "server.internal_error"
    assert UNREACHABLE_PASSWORD not in response.text
    logged = "\n".join(JsonFormatter().format(record) for record in caplog.records)
    assert "unhandled exception" in logged
    assert UNREACHABLE_PASSWORD not in logged
    assert all(json.loads(line) for line in logged.splitlines() if line.startswith("{"))


async def test_s2_1_08_each_lifespan_gets_a_fresh_session_factory() -> None:
    app = create_app(make_settings(), health_checks={"database": check_ok})
    factories: list[object] = []
    for _ in range(2):
        async with app.router.lifespan_context(app):
            factories.append(app.state.session_factory)
            assert app.state.session_factory.kw["bind"] is app.state.engine
    assert factories[0] is not factories[1]
    assert factories[0].kw["bind"] is not factories[1].kw["bind"]
