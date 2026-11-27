"""Sign-up, login, refresh and logout. Each route calls one service function.

Rate-limit policies for these routes are added in roadmap step 4.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.core import clock
from app.core.config import Settings
from app.core.deps import Client, DbSession
from app.core.errors import NotFound
from app.schemas.auth import LoginIn, SignupAcceptedOut, SignupIn, TokenOut
from app.schemas.errors import NOT_FOUND_RESPONSE, UNAUTHORIZED_RESPONSE
from app.services import auth
from app.services.auth import IssuedTokens

router = APIRouter(prefix="/auth", tags=["auth"])


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


AppSettings = Annotated[Settings, Depends(_settings)]


def _signup_enabled(settings: AppSettings) -> None:
    if not settings.auth.signup_enabled:  # invite-only products: the route behaves as absent
        raise NotFound


def token_out(tokens: IssuedTokens) -> TokenOut:
    return TokenOut(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.access_expires_in,
        refresh_expires_in=tokens.refresh_expires_in,
    )


@router.post(
    "/signup",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=SignupAcceptedOut,
    dependencies=[Depends(_signup_enabled)],
    responses=NOT_FOUND_RESPONSE,
    summary="Create an account (the answer is the same whether or not the email is taken)",
)
async def signup(body: SignupIn, session: DbSession, client: Client) -> SignupAcceptedOut:
    await auth.signup(
        session, email=body.email, password=body.password, full_name=body.full_name, client=client
    )
    return SignupAcceptedOut()


@router.post(
    "/login",
    response_model=TokenOut,
    responses=UNAUTHORIZED_RESPONSE,
    summary="Exchange email and password for an access token and a refresh token",
)
async def login(
    body: LoginIn, session: DbSession, client: Client, settings: AppSettings
) -> TokenOut:
    tokens = await auth.login(
        session,
        settings,
        email=body.email,
        password=body.password,
        client=client,
        now=clock.now(),
    )
    return token_out(tokens)
