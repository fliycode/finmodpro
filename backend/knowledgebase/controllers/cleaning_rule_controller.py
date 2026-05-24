"""
清洗规则管理控制器。

类比 SpringBoot: 相当于 @RestController 中处理清洗规则 CRUD 的端点集合。
提供清洗规则的完整生命周期管理：列表查询、创建、详情查看、更新、删除、
一键初始化默认规则，以及清洗结果汇总查询。
"""
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from knowledgebase.controllers.audit_utils import (
    build_cleaning_rule_audit_payload,
    safe_record_audit_event,
)
from knowledgebase.services.cleaning_rule_service import (
    bootstrap_default_cleaning_rules,
    create_cleaning_rule,
    delete_cleaning_rule,
    get_cleaning_summary,
    get_cleaning_rule,
    list_cleaning_rules,
    update_cleaning_rule,
    _serialize_rule,
)
from rbac.services.authz_service import permission_required
from systemcheck.models import AuditRecord


@csrf_exempt
@require_http_methods(["GET", "POST"])
@permission_required("auth.manage_cleaning_rules")
def cleaning_rule_list_create_view(request):
    """
    清洗规则列表/创建端点 —— GET/POST cleaning/rules。

    类比 SpringBoot: 相当于
        @RequestMapping(value="/cleaning/rules", method={GET, POST})
        @PreAuthorize("hasAuthority('auth.manage_cleaning_rules')")
        public ResponseEntity<?> listOrCreate()

    GET:  返回所有已配置的清洗规则列表。
    POST: 创建一条新的清洗规则（JSON body 中提供 name、rule_type、config 等）。

    参数:
        request: Django HttpRequest 对象

    返回:
        GET  -> 200: {"rules": [...], "total": N}
        POST -> 201: {"rule": {...}}  (创建成功)
        POST -> 400: {"message": str(exc)}  (创建失败)
    """
    if request.method == "GET":
        rules = list_cleaning_rules()
        return JsonResponse({"rules": rules, "total": len(rules)})

    payload = json.loads(request.body or "{}")
    try:
        rule = create_cleaning_rule(
            name=payload.get("name", ""),
            rule_type=payload.get("rule_type", ""),
            config=payload.get("config", {}),
            enabled=payload.get("enabled", True),
            priority=payload.get("priority", 100),
            created_by=request.user,
        )
    except Exception as exc:
        safe_record_audit_event(
            actor=request.user,
            action="knowledgebase.cleaning_rule.create",
            target_type="cleaning_rule",
            status=AuditRecord.STATUS_FAILED,
            detail_payload={
                **build_cleaning_rule_audit_payload(
                    name=payload.get("name", ""),
                    rule_type=payload.get("rule_type", ""),
                    enabled=payload.get("enabled", True),
                    priority=payload.get("priority", 100),
                    config=payload.get("config", {}),
                ),
                "error": str(exc),
            },
        )
        return JsonResponse({"message": str(exc)}, status=400)
    safe_record_audit_event(
        actor=request.user,
        action="knowledgebase.cleaning_rule.create",
        target_type="cleaning_rule",
        target_id=rule.id,
        status=AuditRecord.STATUS_SUCCEEDED,
        detail_payload=build_cleaning_rule_audit_payload(rule=rule),
    )
    return JsonResponse({"rule": _serialize_rule(rule)}, status=201)


@csrf_exempt
@require_http_methods(["GET", "PATCH", "DELETE"])
@permission_required("auth.manage_cleaning_rules")
def cleaning_rule_detail_view(request, rule_id):
    """
    清洗规则详情/更新/删除端点 —— GET/PATCH/DELETE cleaning/rules/{rule_id}。

    类比 SpringBoot: 相当于
        @RequestMapping(value="/cleaning/rules/{ruleId}", method={GET, PATCH, DELETE})
        @PreAuthorize("hasAuthority('auth.manage_cleaning_rules')")

    GET:    返回单条规则的详细信息。
    PATCH:  部分更新规则字段（JSON body 中传递要更新的字段）。
    DELETE: 删除指定规则。

    参数:
        request: Django HttpRequest 对象
        rule_id: URL 路径中的规则 ID

    返回:
        GET    -> 200: {"rule": {...}}
        PATCH  -> 200: {"rule": {...}}  (更新成功)
        DELETE -> 200: {"message": "ok"}
        规则不存在 -> 404
    """
    try:
        rule = get_cleaning_rule(rule_id=rule_id)
    except Exception:
        if request.method in {"PATCH", "DELETE"}:
            safe_record_audit_event(
                actor=request.user,
                action="knowledgebase.cleaning_rule.update"
                if request.method == "PATCH"
                else "knowledgebase.cleaning_rule.delete",
                target_type="cleaning_rule",
                target_id=rule_id,
                status=AuditRecord.STATUS_FAILED,
                detail_payload={"error": "规则不存在。"},
            )
        return JsonResponse({"message": "规则不存在。"}, status=404)

    if request.method == "DELETE":
        rule_payload = build_cleaning_rule_audit_payload(rule=rule)
        delete_cleaning_rule(rule=rule)
        safe_record_audit_event(
            actor=request.user,
            action="knowledgebase.cleaning_rule.delete",
            target_type="cleaning_rule",
            target_id=rule_id,
            status=AuditRecord.STATUS_SUCCEEDED,
            detail_payload=rule_payload,
        )
        return JsonResponse({"message": "ok"})

    if request.method == "GET":
        return JsonResponse({"rule": _serialize_rule(rule)})

    payload = json.loads(request.body or "{}")
    try:
        rule = update_cleaning_rule(rule=rule, **payload)
    except Exception as exc:
        safe_record_audit_event(
            actor=request.user,
            action="knowledgebase.cleaning_rule.update",
            target_type="cleaning_rule",
            target_id=rule_id,
            status=AuditRecord.STATUS_FAILED,
            detail_payload={
                **build_cleaning_rule_audit_payload(
                    rule=rule,
                ),
                **build_cleaning_rule_audit_payload(
                    name=payload.get("name", rule.name),
                    rule_type=payload.get("rule_type", rule.rule_type),
                    enabled=payload.get("enabled", rule.enabled),
                    priority=payload.get("priority", rule.priority),
                    config=payload.get("config", rule.config),
                ),
                "error": str(exc),
            },
        )
        return JsonResponse({"message": str(exc)}, status=400)
    safe_record_audit_event(
        actor=request.user,
        action="knowledgebase.cleaning_rule.update",
        target_type="cleaning_rule",
        target_id=rule.id,
        status=AuditRecord.STATUS_SUCCEEDED,
        detail_payload=build_cleaning_rule_audit_payload(rule=rule),
    )
    return JsonResponse({"rule": _serialize_rule(rule)})


@require_GET
@permission_required("auth.manage_cleaning_rules")
def cleaning_summary_view(request):
    """
    清洗汇总信息端点 —— GET cleaning/summary。

    类比 SpringBoot: 相当于
        @GetMapping("/cleaning/summary")
        @PreAuthorize("hasAuthority('auth.manage_cleaning_rules')")

    返回所有文档清洗的汇总统计数据（规则使用情况、质量分数分布等）。

    参数:
        request: Django HttpRequest 对象

    返回:
        JsonResponse: {"summary": {...}} 包含清洗汇总信息。
    """
    return JsonResponse({"summary": get_cleaning_summary()})


@csrf_exempt
@require_POST
@permission_required("auth.manage_cleaning_rules")
def cleaning_rule_bootstrap_view(request):
    """
    一键初始化默认清洗规则端点 —— POST cleaning/rules/bootstrap。

    类比 SpringBoot: 相当于
        @PostMapping("/cleaning/rules/bootstrap")
        @PreAuthorize("hasAuthority('auth.manage_cleaning_rules')")

    批量创建系统预置的默认清洗规则。如果规则已存在（按名称判断）则跳过。
    适合在系统首次启动或重置时调用。

    参数:
        request: Django HttpRequest 对象（用于获取操作者身份）

    返回:
        有新创建时 -> 201: {"rules": [...], "created_count": N, "existing_count": N, "summary": {...}}
        全部已存在 -> 200: 同上，但 created_count 为 0，status 为 SKIPPED
    """
    result = bootstrap_default_cleaning_rules(created_by=request.user)
    audit_status = (
        AuditRecord.STATUS_SUCCEEDED
        if result["created_count"] > 0
        else AuditRecord.STATUS_SKIPPED
    )
    safe_record_audit_event(
        actor=request.user,
        action="knowledgebase.cleaning_rule.bootstrap",
        target_type="cleaning_rule",
        status=audit_status,
        detail_payload={
            "created_count": result["created_count"],
            "existing_count": result["existing_count"],
            "rule_names": [rule["name"] for rule in result["rules"]],
        },
    )
    return JsonResponse(
        {
            **result,
            "summary": get_cleaning_summary(),
        },
        status=201 if result["created_count"] > 0 else 200,
    )
