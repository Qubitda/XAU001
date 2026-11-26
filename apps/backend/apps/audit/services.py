from typing import Any
from .models import AuditLog


def record_audit(
    *,
    action: str,
    entity_type: str,
    entity_id: str,
    actor=None,
    organization=None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    return AuditLog.objects.create(
        actor=actor if (actor and getattr(actor, "is_authenticated", False)) else None,
        organization=organization,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        metadata=metadata or {},
    )
