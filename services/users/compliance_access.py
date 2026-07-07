"""Access control helpers for compliance / production API endpoints."""

from __future__ import annotations

from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.user_model import User, UserGroup
from services.users.role_scope import can_view_user, filter_users_for_viewer


def manageable_user_ids(
    db: Session,
    viewer_role: str,
    org_id: Optional[int],
    viewer_id: Optional[int] = None,
) -> Optional[List[int]]:
    """User IDs the viewer may access. None means unrestricted (super_admin)."""
    if viewer_role == "super_admin":
        return None
    if viewer_role == "user":
        return [viewer_id] if viewer_id is not None else []
    return [
        row[0]
        for row in filter_users_for_viewer(db.query(User.id), viewer_role, org_id).all()
    ]


def resolve_organization_filter(viewer: User, organization_id: Optional[int]) -> Optional[int]:
    if viewer.role == "super_admin":
        return organization_id
    return viewer.organization_id


def require_user_data_access(db: Session, viewer: User, target_user_id: int) -> User:
    """Ensure viewer may read compliance data for target_user_id."""
    if viewer.role == "super_admin":
        target = db.query(User).filter(User.id == target_user_id).first()
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return target

    if viewer.role == "user":
        if target_user_id != viewer.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot access data for other users",
            )
        return viewer

    target = db.query(User).filter(User.id == target_user_id).first()
    if not target or target.organization_id != viewer.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access data for users outside your organization",
        )
    if not can_view_user(viewer.role, target.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access data for this user",
        )
    return target


def require_group_access(db: Session, viewer: User, group_id: int) -> UserGroup:
    """Ensure the group exists and belongs to the viewer's organization."""
    group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    if viewer.role != "super_admin" and group.organization_id != viewer.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return group


def scope_user_ids_for_query(
    db: Session,
    viewer: User,
    requested_user_id: Optional[int],
) -> Optional[List[int]]:
    """Resolve user_id filters for list/statistics queries."""
    if requested_user_id is not None:
        require_user_data_access(db, viewer, requested_user_id)
        return [requested_user_id]

    return manageable_user_ids(db, viewer.role, viewer.organization_id, viewer.id)


def filter_members_by_scope(
    members: List[dict],
    manageable_ids: Optional[List[int]],
) -> List[dict]:
    if manageable_ids is None:
        return members
    allowed = set(manageable_ids)
    return [member for member in members if member.get("user_id") in allowed]
