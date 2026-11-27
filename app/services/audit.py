"""Writing audit entries. Details are redacted here, so no caller can leak a secret into the
audit trail by accident."""

from collections.abc import Mapping
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.client import ClientInfo
from app.core.logging import request_id_var
from app.core.redaction import redact_fields
from app.models import AuditLog
from app.repositories import AuditRepository


def record(
    session: AsyncSession,
    *,
    action: str,
    client: ClientInfo,
    actor_user_id: UUID | None = None,
    organization_id: UUID | None = None,
    target: tuple[str, UUID] | None = None,
    details: Mapping[str, object] | None = None,
) -> AuditLog:
    """Add an entry to the caller's unit of work (it commits with the change it describes).

    The unit of work orders inserts only by `relationship()`s, not by foreign keys: flush a
    new row before recording an entry that refers to it.
    """
    entry = AuditLog(
        action=action,
        actor_user_id=actor_user_id,
        organization_id=organization_id,
        target_type=target[0] if target else None,
        target_id=str(target[1]) if target else None,
        details=redact_fields(details or {}),
        ip=client.ip,
        request_id=request_id_var.get(),
    )
    AuditRepository(session).add(entry)
    return entry
