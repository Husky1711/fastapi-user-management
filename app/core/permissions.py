"""The permission catalogue and the system roles, as code.

Routes check permissions, never role names (ARCHITECTURE §5). The seed migration copies these
values into the database; a test keeps the two in step. To add a permission: add it here, add
a migration that inserts it (and grants it), and the test will confirm they match.
"""

from types import MappingProxyType

PERMISSIONS = MappingProxyType(
    {
        "org:read": "View the organization",
        "org:update": "Change the organization's name and settings",
        "org:delete": "Delete the organization",
        "org:transfer": "Transfer ownership of the organization",
        "members:read": "List members and their roles",
        "members:invite": "Invite people to the organization",
        "members:update": "Change members' roles",
        "members:remove": "Remove members from the organization",
        "invitations:read": "List the organization's invitations",
        "invitations:revoke": "Revoke pending invitations",
        "roles:read": "List roles and their permissions",
        "roles:manage": "Create, change and delete custom roles",
        "audit:read": "Read the organization's audit log",
    }
)

OWNER_ONLY = frozenset({"org:delete", "org:transfer", "roles:manage"})
MEMBER_PERMISSIONS = frozenset({"org:read", "members:read"})

# key -> (display name, permissions)
SYSTEM_ROLES = MappingProxyType(
    {
        "owner": ("Owner", frozenset(PERMISSIONS)),
        "admin": ("Admin", frozenset(PERMISSIONS) - OWNER_ONLY),
        "member": ("Member", MEMBER_PERMISSIONS),
    }
)
