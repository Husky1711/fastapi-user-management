"""
ORM models package.

Split layout (readiness 5.3):
  models/identity.py    — Organization, User, RefreshToken
  models/session.py     — sessions, tokens, invitations, login attempts
  models/compliance.py  — audit, permissions, groups, api keys, retention
  models/rbac_model.py  — catalog roles / permissions

``models.user_model`` re-exports the historical surface for import compatibility.
"""

from models.compliance import (  # noqa: F401
    ApiKey,
    AuditLog,
    ConsentRecord,
    DataRetentionPolicy,
    OrganizationSetting,
    SecurityIncident,
    UserGroup,
    UserGroupMembership,
    UserPermission,
)
from models.identity import Organization, OrganizationMembership, RefreshToken, User  # noqa: F401
from models.rbac_model import (  # noqa: F401 — User.role_assignments -> UserRole
    GroupPermission,
    Permission,
    Role,
    RolePermission,
    UserRole,
)
from models.units import OrgUnit, OrgUnitMember  # noqa: F401,E402
import models.role_events  # noqa: F401,E402 — persists user.role into user_roles
from models.session import (  # noqa: F401
    EmailVerificationToken,
    LoginAttempt,
    PasswordHistory,
    PasswordResetToken,
    UserInvitation,
    UserSession,
)

__all__ = [
    "Organization",
    "RefreshToken",
    "User",
    "UserSession",
    "PasswordHistory",
    "PasswordResetToken",
    "EmailVerificationToken",
    "UserInvitation",
    "LoginAttempt",
    "AuditLog",
    "UserPermission",
    "UserGroup",
    "UserGroupMembership",
    "ApiKey",
    "OrganizationSetting",
    "ConsentRecord",
    "SecurityIncident",
    "DataRetentionPolicy",
]
