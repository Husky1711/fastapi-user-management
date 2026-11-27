"""Request dependencies shared by routers."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """One database session per request.

    The service opens the transaction (`async with session.begin():`), so the commit happens
    before the response is built and a failed commit becomes an error response, never a
    success. Anything left uncommitted is rolled back when the session closes.
    """
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]
