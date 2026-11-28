"""The signed-in user's own account. Each route calls one service function."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.core import clock
from app.core.deps import AppSettings, Authenticated, Client, DbSession
from app.core.pagination import Page, PaginationParams
from app.schemas.auth import ReauthIn, password_of
from app.schemas.errors import NOT_FOUND_RESPONSE, UNAUTHORIZED_RESPONSE
from app.schemas.me import MeOut, PasswordChangeIn, SessionOut
from app.services import me

router = APIRouter(prefix="/me", tags=["me"], responses=UNAUTHORIZED_RESPONSE)


@router.get("", response_model=MeOut, summary="Your profile")
async def profile(current: Authenticated) -> MeOut:
    return MeOut.model_validate(current.user)


@router.get(
    "/sessions", response_model=Page[SessionOut], summary="Devices signed in to your account"
)
async def sessions(
    current: Authenticated, session: DbSession, page: Annotated[PaginationParams, Query()]
) -> Page[SessionOut]:
    found = await me.list_sessions(session, current, page=page, now=clock.now())
    items = [SessionOut.of(row, current_family=current.session_id) for row in found.items]
    return Page(items=items, total=found.total, limit=page.limit, offset=page.offset)


@router.post(
    "/sessions/{session_id}/revoke",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=NOT_FOUND_RESPONSE,
    summary="Sign out one device (another device needs your current password)",
)
async def end_session(
    session_id: UUID,
    current: Authenticated,
    session: DbSession,
    client: Client,
    settings: AppSettings,
    body: ReauthIn | None = None,
) -> None:
    await me.end_session(
        session,
        settings,
        current,
        session_id,
        current_password=password_of(body),
        client=client,
        now=clock.now(),
    )


@router.post(
    "/sessions/revoke-others",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Sign out every other device (needs your current password; this one stays)",
)
async def end_other_sessions(
    current: Authenticated,
    session: DbSession,
    client: Client,
    settings: AppSettings,
    body: ReauthIn | None = None,
) -> None:
    await me.end_other_sessions(
        session,
        settings,
        current,
        current_password=password_of(body),
        client=client,
        now=clock.now(),
    )


@router.post(
    "/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change your password (other devices are signed out)",
)
async def change_password(
    body: PasswordChangeIn,
    current: Authenticated,
    session: DbSession,
    client: Client,
    settings: AppSettings,
) -> None:
    await me.change_password(
        session,
        settings,
        current,
        current_password=body.current_password,
        new_password=body.new_password,
        client=client,
        now=clock.now(),
    )
