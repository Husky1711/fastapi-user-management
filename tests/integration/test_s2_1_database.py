"""Section 2.1: sessions and transactions against the real PostgreSQL."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import APIRouter, FastAPI
from httpx import AsyncClient
from sqlalchemy import Column, MetaData, Table, Text, func, insert, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.deps import DbSession
from app.main import create_app
from app.models.base import NAMING_CONVENTION, Base, Timestamps, UUIDPrimaryKey
from tests.db import SERVICES, service_database_settings
from tests.helpers import check_ok, client_for, make_settings

pytestmark = SERVICES
CONCURRENT_REQUESTS = 10  # equals pool_size + max_overflow below, so all run at once


def _probe_router(table: Table, barrier: asyncio.Barrier | None = None) -> APIRouter:
    """Test-only routes that write notes through `get_db`, the way a service will."""
    router = APIRouter()

    @router.post("/_test/notes/{note}")
    async def add_note(
        note: str, session: DbSession, fail: bool = False, twice: bool = False
    ) -> str:
        async with session.begin():
            await session.execute(insert(table).values(note=note))
            if twice:  # violates the unique constraint inside the same transaction
                await session.execute(insert(table).values(note=note))
            if barrier is not None:  # every request holds an open transaction at the same time
                await barrier.wait()
            if fail:
                raise RuntimeError("failed after writing")
        return str(id(session))

    return router


@pytest.fixture
async def probe(db_engine: AsyncEngine) -> AsyncIterator[Table]:
    table = Table(f"s2_1_probe_{uuid.uuid4().hex}", MetaData(), Column("note", Text, unique=True))
    async with db_engine.begin() as connection:
        await connection.run_sync(table.create)
    try:
        yield table
    finally:
        async with db_engine.begin() as connection:
            await connection.run_sync(table.drop)


async def _notes(engine: AsyncEngine, table: Table) -> list[str]:
    async with engine.connect() as connection:
        result = await connection.execute(select(table.c.note).order_by(table.c.note))
        return list(result.scalars())


@asynccontextmanager
async def _probe_client(router: APIRouter) -> AsyncIterator[AsyncClient]:
    settings = make_settings(database=service_database_settings(pool_size=5, max_overflow=5))
    app: FastAPI = create_app(settings, health_checks={"database": check_ok}, api_routers=[router])
    async with (
        app.router.lifespan_context(app),
        client_for(app, raise_app_exceptions=False) as http,
    ):
        yield http


async def test_s2_1_01_successful_request_commits(db_engine: AsyncEngine, probe: Table) -> None:
    async with _probe_client(_probe_router(probe)) as http:
        response = await http.post("/api/v1/_test/notes/kept")
    assert response.status_code == 200
    assert await _notes(db_engine, probe) == ["kept"]


async def test_s2_1_02_failed_request_commits_nothing(db_engine: AsyncEngine, probe: Table) -> None:
    async with _probe_client(_probe_router(probe)) as http:
        response = await http.post("/api/v1/_test/notes/lost", params={"fail": "true"})
    assert response.status_code == 500
    assert await _notes(db_engine, probe) == []


async def test_s2_1_03_constraint_failure_rolls_back_earlier_writes(
    db_engine: AsyncEngine, probe: Table
) -> None:
    async with _probe_client(_probe_router(probe)) as http:
        response = await http.post("/api/v1/_test/notes/dup", params={"twice": "true"})
        assert response.status_code == 500
        assert response.json()["code"] == "server.internal_error"
        assert (await http.post("/api/v1/_test/notes/after")).status_code == 200
    assert await _notes(db_engine, probe) == ["after"]


async def test_s2_1_04_concurrent_requests_use_separate_sessions(
    db_engine: AsyncEngine, probe: Table
) -> None:
    router = _probe_router(probe, asyncio.Barrier(CONCURRENT_REQUESTS))
    async with _probe_client(router) as http:
        responses = await asyncio.gather(
            *(http.post(f"/api/v1/_test/notes/n{i:02}") for i in range(CONCURRENT_REQUESTS))
        )
    assert {r.status_code for r in responses} == {200}
    # All sessions were alive at the same moment (barrier), so equal ids would mean sharing.
    assert len({r.json() for r in responses}) == CONCURRENT_REQUESTS
    assert len(await _notes(db_engine, probe)) == CONCURRENT_REQUESTS


class _ProbeBase(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = Base.type_annotation_map


class _Thing(UUIDPrimaryKey, Timestamps, _ProbeBase):
    __tablename__ = "s2_1_things"
    name: Mapped[str] = mapped_column(Text)


async def test_s2_1_05_model_base_fills_ids_and_aware_timestamps(
    db_connection: AsyncConnection,
) -> None:
    await db_connection.run_sync(_ProbeBase.metadata.create_all)
    db_now = (await db_connection.execute(select(func.now()))).scalar_one()
    session = AsyncSession(bind=db_connection, join_transaction_mode="create_savepoint")
    first, second = _Thing(name="a"), _Thing(name="b")
    session.add_all([first, second])
    await session.flush()
    assert first.id.version == 4
    assert first.id != second.id
    assert first.created_at.tzinfo is not None
    assert first.created_at.utcoffset() == timedelta(0)
    assert first.created_at == db_now  # set by the database, in the same transaction
    assert first.updated_at == first.created_at
    await session.close()
    assert datetime.now(UTC) - db_now < timedelta(minutes=5)
