"""Relationships between people (and later other resources) inside an organization.

Drives "own" permission scopes: a role permission with ``scope='own'`` reaches only
objects the holder is related to, e.g. ``teacher —teaches→ student`` or
``doctor —attends→ patient``. Relation keys come from the org's sector template.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, Index
from sqlalchemy.sql import func

from utils.database import Base


class ResourceRelation(Base):
    __tablename__ = "resource_relations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "subject_user_id", "relation", "object_type", "object_id",
            name="uq_resource_relations",
        ),
        Index("ix_resource_relations_object", "organization_id", "object_type", "object_id"),
    )

    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    subject_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relation = Column(String(50), nullable=False)
    object_type = Column(String(50), nullable=False, default="user")
    object_id = Column(Integer, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
