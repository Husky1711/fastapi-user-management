"""Helpers for API tests against the real PostgreSQL, rolled back per test."""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, async_sessionmaker

from app.core import clock
from app.core.security import hash_token, issue_access_token, new_opaque_token
from app.main import create_app
from app.models import User, UserSession
from tests.db import service_database_settings
from tests.factories import add, new_user
from tests.helpers import check_ok, client_for, make_settings


@asynccontextmanager
async def api_client(
    connection: AsyncConnection, *routers: APIRouter, **settings: Any
) -> AsyncIterator[AsyncClient]:
    """The app with its database sessions joined to the test's rolled-back transaction.

    Commits become savepoints, so a test can call the API and then check the database through
    the same connection. (Not for concurrency tests: one connection runs one query at a time.)
    """
    app: FastAPI = create_app(
        make_settings(database=service_database_settings(), **settings),
        health_checks={"database": check_ok},
        api_routers=routers,
    )
    async with app.router.lifespan_context(app):
        app.state.session_factory = async_sessionmaker(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
            autoflush=False,
        )
        async with client_for(app, raise_app_exceptions=False) as http:
            yield http


@dataclass(frozen=True)
class SignedIn:
    user: User
    session: UserSession
    access_token: str
    refresh_token: str

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}


async def signed_in(db: AsyncSession, user: User | None = None, **session_values: Any) -> SignedIn:
    """A user with one live session and tokens for it, written straight to the database."""
    user = user or new_user()
    if user not in db:
        await add(db, user)
    refresh = new_opaque_token()
    now = clock.now()
    row = UserSession(
        id=uuid.uuid4(),
        user_id=user.id,
        family_id=uuid.uuid4(),
        family_started_at=now,
        token_hash=hash_token(refresh),
        expires_at=now + timedelta(days=14),
        **session_values,
    )
    await add(db, row)
    access, _ = issue_access_token(
        make_settings().jwt, user_id=user.id, session_id=row.family_id, now=now
    )
    return SignedIn(user=user, session=row, access_token=access, refresh_token=refresh)
