"""Request dependencies shared by routers."""

import ipaddress
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core import clock
from app.core.client import USER_AGENT_MAX_LENGTH, ClientInfo
from app.core.config import Settings
from app.core.errors import Unauthorized
from app.services.auth import CurrentUser, authenticate


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """One database session per request.

    The service commits through `app.infra.database.transaction(session)`, so the commit
    happens before the response is built and a failed commit becomes an error response, never
    a success. Anything left uncommitted is rolled back when the session closes.
    """
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


# auto_error=False: a missing or non-Bearer header becomes our own problem+json 401.
_bearer = HTTPBearer(auto_error=False, description="Access token from POST /auth/login")


async def get_current_user(
    request: Request,
    session: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CurrentUser:
    """The only place an access token is read (CLAUDE.md, "one way to do each thing")."""
    if credentials is None:
        raise Unauthorized(headers={"WWW-Authenticate": "Bearer"})
    settings = app_settings(request).jwt
    return await authenticate(session, settings, credentials.credentials, now=clock.now())


def client_info(request: Request) -> ClientInfo:
    """The caller's address and user agent.

    `request.client` is already the real client when uvicorn trusts the proxy in front of it
    (`FORWARDED_ALLOW_IPS`); `X-Forwarded-For` is never read here, so a client can't spoof it.
    """
    agent = request.headers.get("user-agent") or None
    return ClientInfo(
        ip=_ip_or_none(request.client.host if request.client else None),
        user_agent=agent[:USER_AGENT_MAX_LENGTH] if agent else None,
    )


def _ip_or_none(host: str | None) -> str | None:
    """Only real addresses are recorded (some servers and test clients report a name). An
    IPv6 zone id (`fe80::1%eth0`) is local to the server and `inet` refuses it: dropped."""
    if not host:
        return None
    try:
        address = ipaddress.ip_address(host.partition("%")[0])
    except ValueError:
        return None
    return str(address)


def no_store(response: Response) -> None:
    """API answers hold tokens or personal data: no browser or proxy may keep a copy
    (RFC 6749 §5.1 for token responses; ASVS V8.2.1)."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


Authenticated = Annotated[CurrentUser, Depends(get_current_user)]
Client = Annotated[ClientInfo, Depends(client_info)]


def app_settings(request: Request) -> Settings:
    """The settings this app was created with (tests create apps with their own)."""
    settings: Settings = request.app.state.settings
    return settings


AppSettings = Annotated[Settings, Depends(app_settings)]
