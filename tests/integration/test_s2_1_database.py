"""Section 2.1: sessions and transactions against the real PostgreSQL."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Annotated

import pytest
from fastapi import APIRouter, Depends, FastAPI
from httpx import AsyncClient
from sqlalchemy import Column, MetaData, Table, Text, func, insert, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core import clock
from app.core.deps import DbSession
from app.core.errors import Conflict
from app.infra.database import NestedUnitOfWork, transaction
from app.main import create_app
from app.models import Organization, User
from app.models.base import NAMING_CONVENTION, Base, Timestamps, UUIDPrimaryKey
from app.repositories import UserRepository
from tests.db import SERVICES, service_database_settings
from tests.factories import add, new_org, new_user
from tests.helpers import check_ok, client_for, make_settings

pytestmark = SERVICES
CONCURRENT_REQUESTS = 10  # equals pool_size + max_overflow below, so all run at once


def _probe_router(table: Table, barrier: asyncio.Barrier | None = None) -> APIRouter:
    """Test-only routes that write notes through `get_db`, the way a service will.

    `count_notes` stands for a dependency such as `get_current_user`: it reads through the
    request's session before the route's unit of work starts.
    """
    router = APIRouter()

    async def count_notes(session: DbSession) -> int:
        return int((await session.execute(select(func.count()).select_from(table))).scalar_one())

    @router.post("/_test/notes/{note}")
    async def add_note(
        note: str,
        session: DbSession,
        seen_before: Annotated[int, Depends(count_notes)],
        fail: bool = False,
        twice: bool = False,
    ) -> str:
        assert session.in_transaction()  # the dependency's read autobegan it
        async with transaction(session):
            await session.execute(insert(table).values(note=note))
            if twice:  # violates the unique constraint inside the same transaction
                await session.execute(insert(table).values(note=note))
            if barrier is not None:  # every request holds an open transaction at the same time
                await barrier.wait()
            if fail:
                raise RuntimeError("failed after writing")
        return f"{id(session)}:{seen_before}"

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
        assert await _notes(db_engine, probe) == ["kept"]  # committed before the response
        second = await http.post("/api/v1/_test/notes/next")
    assert second.json().endswith(":1")  # the next request's dependency read the first write


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
    assert len({r.json().split(":")[0] for r in responses}) == CONCURRENT_REQUESTS
    assert len(await _notes(db_engine, probe)) == CONCURRENT_REQUESTS


class _ProbeBase(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = Base.type_annotation_map


class _Thing(UUIDPrimaryKey, Timestamps, _ProbeBase):
    __tablename__ = "s2_1_things"
    name: Mapped[str] = mapped_column(Text)


async def test_s2_1_05_model_base_fills_ids_and_aware_timestamps(
    db_connection: AsyncConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    frozen = datetime(2031, 5, 6, 7, 8, 9, tzinfo=UTC)
    monkeypatch.setattr(clock, "now", lambda: frozen)  # timestamps come from the app clock
    await db_connection.run_sync(_ProbeBase.metadata.create_all)
    session = AsyncSession(bind=db_connection, join_transaction_mode="create_savepoint")
    first, second = _Thing(name="a"), _Thing(name="b")
    session.add_all([first, second])
    await session.flush()
    assert first.id.version == 4
    assert first.id != second.id
    assert first.created_at.tzinfo is not None
    assert first.created_at.utcoffset() == timedelta(0)
    assert first.created_at == frozen
    assert first.updated_at == first.created_at
    await session.close()


async def test_s2_1_10_failed_unit_of_work_after_a_dependency_read_keeps_nothing(
    db_engine: AsyncEngine, probe: Table
) -> None:
    async with _probe_client(_probe_router(probe)) as http:
        failed = await http.post("/api/v1/_test/notes/lost", params={"fail": "true"})
        kept = await http.post("/api/v1/_test/notes/kept")
    assert (failed.status_code, kept.status_code) == (500, 200)
    assert kept.json().endswith(":0")
    assert await _notes(db_engine, probe) == ["kept"]


def _holding_router(entered: asyncio.Event, release: asyncio.Event) -> APIRouter:
    router = APIRouter()

    @router.get("/_test/hold")
    async def hold(session: DbSession) -> str:
        await session.execute(select(1))  # checks out the pool's only connection
        entered.set()
        await release.wait()
        return "done"

    @router.get("/_test/query")
    async def query(session: DbSession) -> int:
        return int((await session.execute(select(1))).scalar_one())

    return router


async def test_s2_1_11_exhausted_pool_fails_fast_with_a_generic_500() -> None:
    entered, release = asyncio.Event(), asyncio.Event()
    database = service_database_settings(pool_size=1, max_overflow=0)
    settings = make_settings(database=database.model_copy(update={"pool_timeout_seconds": 0.3}))
    app = create_app(
        settings,
        health_checks={"database": check_ok},
        api_routers=[_holding_router(entered, release)],
    )
    async with (
        app.router.lifespan_context(app),
        client_for(app, raise_app_exceptions=False) as http,
    ):
        holder = asyncio.create_task(http.get("/api/v1/_test/hold"))
        await entered.wait()
        starved = await http.get("/api/v1/_test/query")  # waits 0.3 s for a connection
        release.set()
        assert (await holder).status_code == 200
        recovered = await http.get("/api/v1/_test/query")
    assert starved.status_code == 500
    assert starved.json()["code"] == "server.internal_error"
    assert recovered.status_code == 200


async def test_s2_1_12_objects_loaded_before_a_failed_unit_of_work_stay_readable(
    db: AsyncSession,
) -> None:
    await add(db, new_user(email="caller-s2-1-12@example.com"))
    db.expunge_all()
    caller = await UserRepository(db).get_by_email("caller-s2-1-12@example.com")  # dependency
    assert caller is not None
    org = new_org()

    async def service_that_fails() -> None:
        async with transaction(db):
            db.add(org)
            await db.flush()
            raise Conflict

    with pytest.raises(Conflict):
        await service_that_fails()
    assert caller.email == "caller-s2-1-12@example.com"  # not expired: no lazy load, no error
    assert await db.get(Organization, org.id) is None  # the failed block left nothing behind


async def test_s2_1_13_nested_unit_of_work_is_refused(db: AsyncSession) -> None:
    async with transaction(db):
        with pytest.raises(NestedUnitOfWork):
            async with transaction(db):
                pass
        await add(db, user := new_user())
    async with transaction(db):  # the marker is cleared afterwards
        pass
    assert await db.get(User, user.id) is user


async def test_s2_1_14_cancelled_unit_of_work_rolls_back(db_engine: AsyncEngine) -> None:
    email = f"cancelled-{uuid.uuid4().hex[:12]}@example.com"
    inside = asyncio.Event()
    session = AsyncSession(db_engine)

    async def slow_write() -> None:
        async with transaction(session):
            session.add(new_user(email=email))
            await session.flush()
            inside.set()
            await asyncio.Event().wait()  # the client goes away while this waits

    task = asyncio.create_task(slow_write())
    await inside.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not session.in_transaction()
    await session.close()
    async with AsyncSession(db_engine) as reader:
        assert await UserRepository(reader).get_by_email(email) is None
