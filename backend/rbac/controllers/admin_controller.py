import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from authentication.models import User
from rbac.services.authz_service import (
    jwt_login_required,
    permission_required,
    user_has_permission,
)
from rbac.services.rbac_service import (
    create_admin_user,
    delete_admin_user,
    list_admin_user_rows,
    list_assignable_groups,
    replace_user_groups,
    update_admin_user,
)


def _parse_json_body(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None


def _forbidden_response():
    return JsonResponse({"message": "无权限。"}, status=403)


def _normalize_group_names(payload):
    if "groups" not in payload:
        return None

    group_names = payload.get("groups")
    if not isinstance(group_names, list) or any(
        not isinstance(group_name, str) or not group_name.strip()
        for group_name in group_names
    ):
        raise ValueError("groups 必须是非空字符串数组。")

    normalized_group_names = sorted({group_name.strip() for group_name in group_names})
    if not normalized_group_names:
        raise ValueError("groups 必须是非空字符串数组。")
    return normalized_group_names


def _normalize_user_payload(payload, *, require_password=False):
    username = (payload.get("username") or "").strip()
    email = (payload.get("email") or "").strip()
    password = payload.get("password") or ""

    if not username or not email or (require_password and not password):
        raise ValueError("username、email 和 password 为必填项。")

    return {
        "username": username,
        "email": email,
        "password": password,
    }


@csrf_exempt
@require_http_methods(["GET", "POST"])
@jwt_login_required
def admin_user_collection_view(request):
    if request.method == "GET":
        if not user_has_permission(request.user, "auth.view_user"):
            return _forbidden_response()
        return JsonResponse(list_admin_user_rows(), safe=False)

    if not user_has_permission(request.user, "auth.add_user"):
        return _forbidden_response()

    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({"message": "请求体必须是合法 JSON。"}, status=400)

    try:
        user_fields = _normalize_user_payload(payload, require_password=True)
        group_names = _normalize_group_names(payload)
    except ValueError as exc:
        return JsonResponse({"message": str(exc)}, status=400)

    if group_names is not None and not user_has_permission(request.user, "auth.assign_role"):
        return _forbidden_response()

    try:
        created_user = create_admin_user(
            username=user_fields["username"],
            email=user_fields["email"],
            password=user_fields["password"],
            group_names=group_names,
        )
    except ValueError as exc:
        status_code = 409 if "已存在" in str(exc) else 400
        return JsonResponse({"message": str(exc)}, status=status_code)

    return JsonResponse(created_user, status=201)


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


@csrf_exempt
@require_http_methods(["PATCH", "DELETE"])
@jwt_login_required
def admin_user_detail_view(request, user_id):
    if request.method == "PATCH":
        if not user_has_permission(request.user, "auth.change_user"):
            return _forbidden_response()
    elif not user_has_permission(request.user, "auth.delete_user"):
        return _forbidden_response()

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({"message": "用户不存在。"}, status=404)

    if request.method == "DELETE":
        if request.user.id == user.id:
            return JsonResponse({"message": "不能删除当前登录用户。"}, status=400)

        delete_admin_user(user)
        return JsonResponse({"message": "用户已删除。"})

    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({"message": "请求体必须是合法 JSON。"}, status=400)

    try:
        user_fields = _normalize_user_payload(payload, require_password=False)
        group_names = _normalize_group_names(payload)
    except ValueError as exc:
        return JsonResponse({"message": str(exc)}, status=400)

    if group_names is not None and not user_has_permission(request.user, "auth.assign_role"):
        return _forbidden_response()

    try:
        updated_user = update_admin_user(
            user,
            username=user_fields["username"],
            email=user_fields["email"],
            password=user_fields["password"],
            group_names=group_names,
        )
    except ValueError as exc:
        status_code = 409 if "已存在" in str(exc) else 400
        return JsonResponse({"message": str(exc)}, status=status_code)

    return JsonResponse(updated_user)
