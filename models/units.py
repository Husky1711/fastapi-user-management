"""Organization units: a tree of any depth inside an organization.

Sector-neutral: the *type* of each level is data (``unit_type``), e.g.
education ``campus > department > class``, medical ``hospital > ward > team``,
pharma ``site > study > lab``. Roles can be granted on a unit (``user_roles.unit_id``)
and then apply to that unit and everything below it.

``path`` is the materialised ancestry ``/<root id>/.../<own id>/`` so "is X under Y"
is ``x.path.startswith(y.path)`` (indexed prefix match in SQL).
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from utils.database import Base


class OrgUnit(Base):
    __tablename__ = "org_units"

    id = Column(Integer, primary_key=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id = Column(
        Integer, ForeignKey("org_units.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    unit_type = Column(String(50), nullable=False)
    name = Column(String(150), nullable=False)
    path = Column(String(500), nullable=False, index=True)
    depth = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    parent = relationship("OrgUnit", remote_side=[id], backref="children")


class OrgUnitMember(Base):
    """A person placed in a unit (e.g. a student in a class, a nurse on a ward)."""

    __tablename__ = "org_unit_members"
    __table_args__ = (UniqueConstraint("unit_id", "user_id", name="uq_org_unit_members"),)

    id = Column(Integer, primary_key=True)
    unit_id = Column(
        Integer, ForeignKey("org_units.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    unit = relationship("OrgUnit", lazy="joined")
