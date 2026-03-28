import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from authentication.models import User
from rbac.services.authz_service import permission_required
from rbac.services.rbac_service import (
    list_admin_user_rows,
    list_assignable_groups,
    replace_user_groups,
)


def _parse_json_body(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None


@require_GET
@permission_required("auth.view_user")
def admin_user_list_view(request):
    return JsonResponse(list_admin_user_rows(), safe=False)


@require_GET
@permission_required("auth.view_role")
def admin_group_list_view(request):
    return JsonResponse(list_assignable_groups(), safe=False)


@csrf_exempt
@require_http_methods(["PUT"])
@permission_required("auth.assign_role")
def admin_user_groups_update_view(request, user_id):
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({"message": "请求体必须是合法 JSON。"}, status=400)

    group_names = payload.get("groups")
    if not isinstance(group_names, list) or any(
        not isinstance(group_name, str) or not group_name.strip()
        for group_name in group_names
    ):
        return JsonResponse(
            {"message": "groups 必须是非空字符串数组。"},
            status=400,
        )

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({"message": "用户不存在。"}, status=404)

    normalized_group_names = sorted({group_name.strip() for group_name in group_names})
    try:
        updated_user = replace_user_groups(user, normalized_group_names)
    except ValueError as exc:
        return JsonResponse({"message": str(exc)}, status=400)

    return JsonResponse(updated_user)
