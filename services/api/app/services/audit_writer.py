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
        # The audit log is the source of truth — persist first.
        self.repo.save(event)
        # Task 94: best-effort local event fan-out AFTER the durable
        # write. Off by default; a publish/handler failure must never
        # affect the audit write or the caller.
        from .. import config

        if config.EVENT_BUS_PUBLISH_ENABLED:
            try:
                from .event_bus import get_event_bus

                get_event_bus().publish(
                    action,
                    {
                        "target_type": target_type,
                        "target_id": target_id,
                        "actor_type": actor_type,
                    },
                    project_id=project_id,
                )
            except Exception:
                pass
