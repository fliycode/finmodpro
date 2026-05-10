import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from knowledgebase.services.cleaning_rule_service import (
    create_cleaning_rule,
    delete_cleaning_rule,
    get_cleaning_rule,
    list_cleaning_rules,
    update_cleaning_rule,
    _serialize_rule,
)
from rbac.services.authz_service import permission_required


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
        return JsonResponse({"message": str(exc)}, status=400)
    return JsonResponse({"rule": _serialize_rule(rule)}, status=201)


@csrf_exempt
@require_http_methods(["GET", "PATCH", "DELETE"])
@permission_required("auth.manage_cleaning_rules")
def cleaning_rule_detail_view(request, rule_id):
    try:
        rule = get_cleaning_rule(rule_id=rule_id)
    except Exception:
        return JsonResponse({"message": "规则不存在。"}, status=404)

    if request.method == "DELETE":
        delete_cleaning_rule(rule=rule)
        return JsonResponse({"message": "ok"})

    if request.method == "GET":
        return JsonResponse({"rule": _serialize_rule(rule)})

    payload = json.loads(request.body or "{}")
    try:
        rule = update_cleaning_rule(rule=rule, **payload)
    except Exception as exc:
        return JsonResponse({"message": str(exc)}, status=400)
    return JsonResponse({"rule": _serialize_rule(rule)})
