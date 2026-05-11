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
    return JsonResponse({"summary": get_cleaning_summary()})


@csrf_exempt
@require_POST
@permission_required("auth.manage_cleaning_rules")
def cleaning_rule_bootstrap_view(request):
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
