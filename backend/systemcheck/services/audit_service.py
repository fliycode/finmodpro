from systemcheck.models import AuditRecord


def _serialize_actor(actor):
    if actor is None:
        return None
    return {
        "id": actor.id,
        "username": actor.username,
        "email": actor.email,
    }


def serialize_audit_record(record):
    return {
        "id": record.id,
        "actor": _serialize_actor(getattr(record, "actor", None)),
        "actor_name": getattr(record.actor, "username", "") if getattr(record, "actor", None) else "",
        "action": record.action,
        "target_type": record.target_type,
        "target_id": record.target_id or "",
        "status": record.status,
        "detail_payload": record.detail_payload or {},
        "summary": f"{record.action} -> {record.status}",
        "created_at": record.created_at.isoformat(),
    }


def record_audit_event(*, actor=None, action, target_type, target_id="", status, detail_payload=None):
    return AuditRecord.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id="" if target_id is None else str(target_id),
        status=status,
        detail_payload=detail_payload or {},
    )


def list_audit_records(*, limit=10):
    safe_limit = max(int(limit or 10), 1)
    records = AuditRecord.objects.select_related("actor").order_by("-created_at", "-id")[:safe_limit]
    return [serialize_audit_record(record) for record in records]
