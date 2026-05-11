import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from ..models import AuditAction, AuditEvent


@dataclass
class AuditWriter:
    repo: object

    def write(
        self,
        action: AuditAction,
        target_type: str,
        target_id: str,
        project_id: str | None = None,
        actor_email: str | None = None,
        details: dict | None = None,
    ) -> None:
        actor_type = "user" if (actor_email and actor_email != "auth-disabled") else "system"
        event = AuditEvent(
            id=str(uuid.uuid4()),
            project_id=project_id,
            actor_type=actor_type,
            actor_id=actor_email or "system",
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details or {},
            created_at=datetime.now(timezone.utc),
        )
        self.repo.save(event)
