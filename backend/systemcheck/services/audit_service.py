from systemcheck.models import AuditRecord

_SENSITIVE_DETAIL_KEYS = {
    "api_key",
    "auth_token",
    "authorization",
    "callback_token",
    "password",
    "template",
    "token",
}
_REDACTED_VALUE = "[REDACTED]"
_MAX_DETAIL_STRING_LENGTH = 500


def _sanitize_detail_value(value, *, key=""):
    normalized_key = str(key or "").strip().lower()
    if normalized_key in _SENSITIVE_DETAIL_KEYS:
        return _REDACTED_VALUE

    if isinstance(value, dict):
        return {
            str(child_key): _sanitize_detail_value(child_value, key=child_key)
            for child_key, child_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize_detail_value(item, key=key) for item in value]
    if isinstance(value, str):
        if len(value) <= _MAX_DETAIL_STRING_LENGTH:
            return value
        return f"{value[:_MAX_DETAIL_STRING_LENGTH - 3]}..."
    return value


def sanitize_audit_detail_payload(detail_payload):
    if not isinstance(detail_payload, dict):
        return {}
    return _sanitize_detail_value(detail_payload)


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
        detail_payload=sanitize_audit_detail_payload(detail_payload),
    )


def list_audit_records(*, limit=10):
    safe_limit = max(int(limit or 10), 1)
    records = AuditRecord.objects.select_related("actor").order_by("-created_at", "-id")[:safe_limit]
    return [serialize_audit_record(record) for record in records]
