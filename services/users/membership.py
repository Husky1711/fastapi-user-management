"""Organization memberships and the per-request *active organization*.

A user may belong to several organizations (``organization_memberships``);
``users.organization_id`` is their home org. Each request acts in one org:

* clients send ``X-Organization-Id`` (``ORG_HEADER``) to pick it; without the header
  the home org is used, so single-org clients need no change;
* ``activate_organization`` checks membership (platform roles may act in any existing
  org), then sets ``current_user.organization_id`` to the active org for this request
  only (``set_committed_value``: never written back) and records it on the session so
  every user loaded in the request reports their role *in that org*.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import List, Optional

from fastapi import status
from sqlalchemy import and_, exists
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from models.identity import Organization, OrganizationMembership, User
from utils.api_errors import APIHTTPException

ORG_HEADER = "X-Organization-Id"

# Raw header value for the current request (set by OrganizationContextMiddleware).
requested_org_var: ContextVar[Optional[str]] = ContextVar("requested_org", default=None)


class OrganizationContextMiddleware:
    """Pure ASGI: capture X-Organization-Id into a contextvar (validated later)."""

    def __init__(self, app) -> None:
        self.app = app
        self._header = ORG_HEADER.lower().encode()

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        value = next(
            (v.decode("latin-1") for k, v in scope.get("headers", []) if k == self._header),
            None,
        )
        token = requested_org_var.set(value)
        try:
            await self.app(scope, receive, send)
        finally:
            requested_org_var.reset(token)


def _parse_requested_org() -> Optional[int]:
    raw = requested_org_var.get()
    if raw is None or raw.strip() == "":
        return None
    try:
        return int(raw)
    except ValueError:
        raise APIHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{ORG_HEADER} must be an organization id",
            error_code="INVALID_ORGANIZATION",
        )


def activate_organization(db: Session, user: User) -> int:
    """Validate the requested org and make it the active org for this request."""
    from services.permissions.role_catalog import is_platform_role

    requested = _parse_requested_org()
    home = user.__dict__.setdefault("_home_org_id", user.organization_id)
    active = home
    if requested is not None and requested != home:
        db.info["active_org_id"] = requested  # evaluate roles in the requested org
        allowed = requested in user.member_org_ids() or (
            is_platform_role(user.role)
            and db.query(Organization.id).filter(Organization.id == requested).first()
            is not None
        )
        if not allowed:
            db.info.pop("active_org_id", None)
            raise APIHTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this organization",
                error_code="NOT_ORGANIZATION_MEMBER",
            )
        active = requested
        set_committed_value(user, "organization_id", requested)
    db.info["active_org_id"] = active
    return active


# --- membership queries -------------------------------------------------------

def is_member(user: User, organization_id: Optional[int]) -> bool:
    return organization_id is not None and organization_id in user.member_org_ids()


def member_of(organization_id: int):
    """SQL condition: ``User`` is an active member (or home member) of the org."""
    return (User.organization_id == organization_id) | exists().where(
        and_(
            OrganizationMembership.user_id == User.id,
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.status == "active",
        )
    )


def list_memberships(user: User) -> List[dict]:
    """The user's organizations with their role in each (for org switchers)."""
    from services.permissions.role_catalog import highest, DEFAULT_ROLE_NAME

    rows = []
    for m in sorted(user.memberships, key=lambda m: m.organization_id):
        if m.status != "active":
            continue
        org = m.organization
        rows.append(
            {
                "organization_id": m.organization_id,
                "organization_name": org.name if org else None,
                "organization_slug": org.slug if org else None,
                "role": highest(user.roles_in(m.organization_id)) or DEFAULT_ROLE_NAME,
                "is_home": m.organization_id == user.__dict__.get("_home_org_id", user.organization_id),
            }
        )
    return rows
