from app.models import AuditLog
from app.repositories.base import Repository


class AuditRepository(Repository):
    # An entry names its organization (if any) itself; nothing here is read back by tenant yet.
    unscoped = frozenset({"add"})

    def add(self, entry: AuditLog) -> None:
        self.session.add(entry)
