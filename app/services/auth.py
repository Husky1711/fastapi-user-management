"""Authentication: who is calling, and the flows that create and end sessions."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.client import ClientInfo
from app.core.config import AuthSettings, JwtSettings, SessionStrategy, Settings
from app.core.emails import InvalidEmail, normalize_email
from app.core.errors import Unauthorized
from app.core.security import (
    InvalidToken,
    check_password_rules,
    decode_access_token,
    hash_password,
    hash_token,
    issue_access_token,
    new_opaque_token,
    password_needs_rehash,
    verify_dummy_password,
    verify_password,
)
from app.infra.database import end_read, is_unique_violation, transaction
from app.models import RevokeReason, User, UserSession, UserStatus
from app.repositories import SessionRepository, UserRepository
from app.services import audit


class InvalidCredentials(Unauthorized):
    """Wrong email or password, or an account that can't log in now (locked, disabled).
    One answer for all of them, so it can't be used to discover accounts."""

    default_code = "auth.invalid_credentials"
    default_detail = "The email or password is incorrect."


@dataclass(frozen=True, slots=True)
class IssuedTokens:
    access_token: str
    refresh_token: str
    access_expires_in: int
    refresh_expires_in: int


@dataclass(frozen=True, slots=True)
class Verified:
    """The stored hash a password was checked against, and its replacement if the hash
    parameters were raised since it was made."""

    hash: str
    rehash: str | None


@dataclass(frozen=True, slots=True)
class CurrentUser:
    user: User
    session_id: UUID  # the session family the access token belongs to


async def authenticate(
    session: AsyncSession, settings: JwtSettings, token: str, *, now: datetime
) -> CurrentUser:
    """The user behind an access token, if the token is valid, the user active and the
    session (family) still live. One query. Raises `InvalidToken` for every failure."""
    claims = decode_access_token(settings, token, now=now)
    users = UserRepository(session)
    user = await users.get_authenticated(claims.user_id, claims.session_id, now=now)
    if user is None:
        raise InvalidToken
    return CurrentUser(user=user, session_id=claims.session_id)


async def signup(
    session: AsyncSession, *, email: str, password: str, full_name: str | None, client: ClientInfo
) -> None:
    """Create an account, or do nothing if the email is taken. The caller can't tell which:
    both paths validate, hash the password and return the same answer."""
    email = normalize_email(email)
    check_password_rules(password)
    await end_read(session)
    password_hash = await hash_password(password)
    users = UserRepository(session)
    try:
        async with transaction(session):
            if await users.get_by_email(email) is not None:
                audit.record(session, action="auth.signup_existing_email", client=client)
                return
            user = User(
                id=uuid.uuid4(), email=email, password_hash=password_hash, full_name=full_name
            )
            users.add(user)
            await session.flush()  # the audit row refers to the user: insert the user first
            audit.record(session, action="auth.signed_up", client=client, actor_user_id=user.id)
    except IntegrityError as error:
        if not is_unique_violation(error, "uq_users_email"):
            raise  # any other integrity problem is a bug, never "email taken"
        # The same email signed up concurrently, or a deleted account still holds it.


async def login(
    session: AsyncSession,
    settings: Settings,
    *,
    email: str,
    password: str,
    client: ClientInfo,
    now: datetime,
) -> IssuedTokens:
    user = await _user_by_email(session, email)
    await end_read(session)  # no pool connection is held while Argon2 runs
    if user is None:
        await verify_dummy_password(password)
        raise InvalidCredentials
    if not await verify_password(user.password_hash, password):
        await count_failed_login(session, settings.auth, user.id, client, now, LOGIN_FAILED)
        raise InvalidCredentials
    verified = Verified(hash=user.password_hash, rehash=None)
    if password_needs_rehash(user.password_hash):
        verified = Verified(hash=user.password_hash, rehash=await hash_password(password))
    tokens = await _complete_login(session, settings, user.id, verified, client, now)
    if tokens is None:  # raised after the commit, so the "refused" audit entry is kept
        raise InvalidCredentials
    return tokens


async def _complete_login(
    session: AsyncSession,
    settings: Settings,
    user_id: UUID,
    verified: Verified,
    client: ClientInfo,
    now: datetime,
) -> IssuedTokens | None:
    """Re-check the user under the row lock, then start the session. None if the account
    can't log in now: locked or disabled meanwhile, or the password changed meanwhile (the
    password that was checked is no longer the account's password)."""
    async with transaction(session):
        user = await lock_user(session, user_id)
        if user is None or not can_log_in(user, now) or user.password_hash != verified.hash:
            actor = user_id if user is not None else None  # a removed user can't be referenced
            audit.record(session, action="auth.login_refused", client=client, actor_user_id=actor)
            return None
        _mark_login(user, now, verified.rehash)
        await _apply_session_strategy(session, settings.auth, user.id, client, now)
        tokens = _start_session(session, settings, user.id, client, now)
        audit.record(session, action="auth.logged_in", client=client, actor_user_id=user.id)
    return tokens


async def _user_by_email(session: AsyncSession, email: str) -> User | None:
    try:
        return await UserRepository(session).get_by_email(normalize_email(email))
    except InvalidEmail:  # not an address: no such account (no different error to probe)
        return None


def is_locked(user: User, now: datetime) -> bool:
    return user.locked_until is not None and user.locked_until > now


def can_log_in(user: User, now: datetime) -> bool:
    """Active, not deleted and not locked: what login and password change both require."""
    return user.status == UserStatus.ACTIVE and user.deleted_at is None and not is_locked(user, now)


def _mark_login(user: User, now: datetime, new_hash: str | None) -> None:
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    if new_hash is not None:  # parameters were raised since this hash was made
        user.password_hash = new_hash


LOGIN_FAILED = "auth.login_failed"


async def count_failed_login(
    session: AsyncSession,
    policy: AuthSettings,
    user_id: UUID,
    client: ClientInfo,
    now: datetime,
    action: str,
) -> None:
    """Count a wrong password toward the lockout and audit it as `action`."""
    async with transaction(session):
        failures = await UserRepository(session).record_failed_login(
            user_id,
            now=now,
            threshold=policy.lockout_threshold,
            lock_for=timedelta(minutes=policy.lockout_minutes),
        )
        if failures is None:  # the user was removed meanwhile: nothing to count
            return
        details = {"failed_count": failures.count}
        audit.record(
            session,
            action=action,
            client=client,
            actor_user_id=user_id,
            details=details,
        )
        if failures.count == policy.lockout_threshold:
            audit.record(
                session,
                action="auth.account_locked",
                client=client,
                actor_user_id=user_id,
                details=details,
            )


async def _apply_session_strategy(
    session: AsyncSession, policy: AuthSettings, user_id: UUID, client: ClientInfo, now: datetime
) -> None:
    sessions = SessionRepository(session)
    reason = RevokeReason.REPLACED
    if policy.session_strategy == SessionStrategy.REPLACE_ALL:
        await sessions.revoke_all(user_id=user_id, reason=reason, now=now)
    elif policy.session_strategy == SessionStrategy.LIMIT_SESSIONS:
        for family_id in await sessions.oldest_active_families(
            user_id=user_id, now=now, keep=policy.max_sessions - 1
        ):
            await sessions.revoke_family(
                user_id=user_id, family_id=family_id, reason=reason, now=now
            )
    elif policy.session_strategy == SessionStrategy.REPLACE_SAME_DEVICE and client.user_agent:
        await sessions.revoke_same_device(
            user_id=user_id, user_agent=client.user_agent, reason=reason, now=now
        )


def _start_session(
    session: AsyncSession, settings: Settings, user_id: UUID, client: ClientInfo, now: datetime
) -> IssuedTokens:
    """A new family with its first refresh token."""
    return _add_refresh_token(session, settings, user_id, uuid.uuid4(), now, now, client)


def _add_refresh_token(
    session: AsyncSession,
    settings: Settings,
    user_id: UUID,
    family_id: UUID,
    family_started_at: datetime,
    now: datetime,
    client: ClientInfo,
) -> IssuedTokens:
    """Store the next refresh token of a family and issue both tokens. The refresh token's
    life is capped by the family's maximum age."""
    policy = settings.auth
    max_end = family_started_at + policy.session_max_age
    expires_at = min(now + policy.refresh_ttl, max_end)
    refresh = new_opaque_token()
    SessionRepository(session).add(
        UserSession(
            id=uuid.uuid4(),
            user_id=user_id,
            family_id=family_id,
            family_started_at=family_started_at,
            # This instance's clock may be a little behind the one that started the family;
            # never record the row as older than its family (CHECK family_started_first).
            created_at=max(now, family_started_at),
            token_hash=hash_token(refresh),
            expires_at=expires_at,
            last_used_at=now,
            ip=client.ip,
            user_agent=client.user_agent,
        )
    )
    access, _ = issue_access_token(settings.jwt, user_id=user_id, session_id=family_id, now=now)
    return IssuedTokens(
        access_token=access,
        refresh_token=refresh,
        access_expires_in=settings.jwt.access_ttl_seconds,
        refresh_expires_in=int((expires_at - now).total_seconds()),
    )


async def refresh(
    session: AsyncSession,
    settings: Settings,
    *,
    refresh_token: str,
    client: ClientInfo,
    now: datetime,
) -> IssuedTokens:
    """Rotate a refresh token. A token that was already rotated is being replayed (it was
    copied): the whole family is revoked and the attempt audited. Raises `InvalidToken`.

    The owner's row is locked before the token's row is re-read, the same order every
    revocation uses, so a logout or password change never misses the successor token."""
    sessions = SessionRepository(session)
    token_hash = hash_token(refresh_token)
    async with transaction(session):
        found = await sessions.get_by_token_hash(token_hash)
        tokens = None
        if found is not None:
            user = await lock_user(session, found.user_id)
            row = await sessions.get_by_token_hash(token_hash, for_update=True)
            if user is not None and row is not None:
                tokens = await _rotate(session, settings, user, row, client, now)
    if tokens is None:  # raised after the commit, so a reuse revocation is kept
        raise InvalidToken
    return tokens


async def _rotate(
    session: AsyncSession,
    settings: Settings,
    user: User,
    row: UserSession,
    client: ClientInfo,
    now: datetime,
) -> IssuedTokens | None:
    sessions = SessionRepository(session)
    if row.revoked_reason == RevokeReason.ROTATED:
        await sessions.revoke_family(
            user_id=row.user_id,
            family_id=row.family_id,
            reason=RevokeReason.REUSE_DETECTED,
            now=now,
        )
        audit.record(
            session,
            action="auth.refresh_token_reused",
            client=client,
            actor_user_id=row.user_id,
            target=("session", row.family_id),
        )
        return None
    max_age_end = row.family_started_at + settings.auth.session_max_age
    if row.revoked_at is not None or row.expires_at <= now or max_age_end <= now:
        return None
    if user.deleted_at is not None or user.status != UserStatus.ACTIVE:
        return None
    await sessions.revoke_family(
        user_id=row.user_id, family_id=row.family_id, reason=RevokeReason.ROTATED, now=now
    )
    return _add_refresh_token(
        session, settings, row.user_id, row.family_id, row.family_started_at, now, client
    )


async def lock_user(session: AsyncSession, user_id: UUID) -> User | None:
    """Take the per-user lock every session or credential change takes first (the only
    entry point). Returns the row deleted or not: callers check what they need."""
    return await UserRepository(session).get_for_update(user_id)


async def logout(
    session: AsyncSession,
    current: CurrentUser,
    *,
    everywhere: bool,
    client: ClientInfo,
    now: datetime,
) -> None:
    """End this session (its whole family), or every session of the user."""
    sessions = SessionRepository(session)
    user_id = current.user.id
    async with transaction(session):
        await lock_user(session, user_id)
        if everywhere:
            await sessions.revoke_all(user_id=user_id, reason=RevokeReason.LOGOUT_ALL, now=now)
        else:
            await sessions.revoke_family(
                user_id=user_id, family_id=current.session_id, reason=RevokeReason.LOGOUT, now=now
            )
        action = "auth.logged_out_everywhere" if everywhere else "auth.logged_out"
        audit.record(session, action=action, client=client, actor_user_id=user_id)
