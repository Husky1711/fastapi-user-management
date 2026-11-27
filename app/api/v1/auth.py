"""Sign-up, login, refresh and logout. Each route calls one service function.

Rate-limit policies for these routes are added in roadmap step 4.
"""

from fastapi import APIRouter, Depends, status

from app.core import clock
from app.core.deps import AppSettings, Authenticated, Client, DbSession
from app.core.errors import NotFound
from app.schemas.auth import (
    LoginIn,
    ReauthIn,
    RefreshIn,
    SignupAcceptedOut,
    SignupIn,
    TokenOut,
    password_of,
)
from app.schemas.errors import NOT_FOUND_RESPONSE, UNAUTHORIZED_RESPONSE
from app.services import auth
from app.services.auth import IssuedTokens

router = APIRouter(prefix="/auth", tags=["auth"])


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


@router.post(
    "/refresh",
    response_model=TokenOut,
    responses=UNAUTHORIZED_RESPONSE,
    summary="Exchange a refresh token for new tokens (the old refresh token stops working)",
)
async def refresh(
    body: RefreshIn, session: DbSession, client: Client, settings: AppSettings
) -> TokenOut:
    tokens = await auth.refresh(
        session, settings, refresh_token=body.refresh_token, client=client, now=clock.now()
    )
    return token_out(tokens)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=UNAUTHORIZED_RESPONSE,
    summary="End the current session (its access and refresh tokens stop working at once)",
)
async def logout(
    current: Authenticated, session: DbSession, client: Client, settings: AppSettings
) -> None:
    await auth.logout(
        session,
        settings,
        current,
        everywhere=False,
        current_password=None,
        client=client,
        now=clock.now(),
    )


@router.post(
    "/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=UNAUTHORIZED_RESPONSE,
    summary="End every session of the current user, on every device (needs your password)",
)
async def logout_all(
    current: Authenticated,
    session: DbSession,
    client: Client,
    settings: AppSettings,
    body: ReauthIn | None = None,
) -> None:
    await auth.logout(
        session,
        settings,
        current,
        everywhere=True,
        current_password=password_of(body),
        client=client,
        now=clock.now(),
    )
