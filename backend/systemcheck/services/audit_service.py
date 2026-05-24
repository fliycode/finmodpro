"""
审计日志服务 —— 提供审计事件的记录、查询和序列化功能。

类比 SpringBoot: 相当于 @Service 中的审计层，负责:
- 记录操作审计事件 (record_audit_event)
- 序列化审计记录为前端可用的 JSON 格式 (serialize_audit_record)
- 敏感信息脱敏 (sanitize_audit_detail_payload)
- 查询审计记录列表 (list_audit_records)
"""

from systemcheck.models import AuditRecord

# 敏感字段键名集合 —— 这些字段的值在审计日志中会被替换为 [REDACTED]
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
# 单个字符串字段的最大保留长度
_MAX_DETAIL_STRING_LENGTH = 500


def _sanitize_detail_value(value, *, key=""):
    """
    递归地对审计详情值进行安全脱敏处理。

    脱敏规则:
    - 键名在敏感字段集合中的值 <- 替换为 [REDACTED]
    - 字符串超过最大长度 <- 截断并添加 "..."
    - 嵌套字典/列表 <- 递归处理

    参数:
        value: 要脱敏的原始值。
        key (str): 当前字段的键名，用于匹配敏感字段列表。

    返回:
        任何类型: 脱敏后的值。
    """
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
    """
    对审计详情的整个 payload 进行脱敏处理。

    类比 SpringBoot: 相当于审计拦截器中的掩码/脱敏逻辑。

    参数:
        detail_payload (dict): 原始的审计详情字典。

    返回:
        dict: 脱敏后的审计详情字典。
    """
    if not isinstance(detail_payload, dict):
        return {}
    return _sanitize_detail_value(detail_payload)


def _serialize_actor(actor):
    """
    序列化用户 (actor) 信息为精简的字典。

    参数:
        actor: Django User 实例。

    返回:
        dict | None: 包含 id, username, email 的字典，actor 为 None 时返回 None。
    """
    if actor is None:
        return None
    return {
        "id": actor.id,
        "username": actor.username,
        "email": actor.email,
    }


def serialize_audit_record(record):
    """
    将 AuditRecord 模型实例序列化为前端可用的 JSON 字典。

    类比 SpringBoot: 相当于 Jackson @JsonSerialize 或 DTO 转换方法。

    参数:
        record (AuditRecord): 审计记录模型实例。

    返回:
        dict: 包含 id, actor, action, target, status, detail_payload 等字段的字典。
    """
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
    """
    记录一条审计事件到数据库。

    类比 SpringBoot: 相当于 @Service 中的审计日志写入方法，
    类似于 CQRS 中 Command 的审计记录。

    参数:
        actor:          执行操作的用户实例 (必须提供关键字参数)。
        action (str):   操作名称 (如 "risk.extract") (必须提供关键字参数)。
        target_type (str): 操作目标类型 (如 "document") (必须提供关键字参数)。
        target_id (str, 可选, 默认 ""): 操作目标 ID。
        status (str):   操作状态 (必须提供关键字参数)。
        detail_payload (dict, 可选): 操作详情 (会自动脱敏)。

    返回:
        AuditRecord: 新创建的审计记录实例。
    """
    return AuditRecord.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id="" if target_id is None else str(target_id),
        status=status,
        detail_payload=sanitize_audit_detail_payload(detail_payload),
    )


def list_audit_records(*, limit=10):
    """
    查询最近 N 条审计记录。

    参数:
        limit (int): 返回的最大记录数，必须 >= 1。默认 10。

    返回:
        list[dict]: 序列化后的审计记录列表，按时间降序排列。
    """
    safe_limit = max(int(limit or 10), 1)
    records = AuditRecord.objects.select_related("actor").order_by("-created_at", "-id")[:safe_limit]
    return [serialize_audit_record(record) for record in records]
