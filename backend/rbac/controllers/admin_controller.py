import json

from django.contrib.auth.models import Group
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
    create_admin_role,
    create_admin_user,
    delete_admin_role,
    delete_admin_user,
    get_admin_role_detail,
    list_admin_role_rows,
    list_rbac_permissions,
    list_admin_user_rows,
    list_assignable_groups,
    replace_user_groups,
    restore_admin_role_permissions,
    update_admin_role,
    update_admin_user,
)
from systemcheck.models import AuditRecord
from systemcheck.services.audit_service import record_audit_event


def _parse_json_body(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None


def _forbidden_response():
    return JsonResponse({"message": "无权限。"}, status=403)


def _build_admin_user_audit_payload(*, user=None, user_row=None, groups=None):
    if user_row is None and user is not None:
        user_row = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "groups": sorted(user.groups.values_list("name", flat=True)),
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
        }

    if user_row is None:
        return {"groups": sorted(groups or [])}

    return {
        "username": user_row.get("username", ""),
        "email": user_row.get("email", ""),
        "groups": sorted(groups if groups is not None else user_row.get("groups", [])),
        "is_staff": bool(user_row.get("is_staff", False)),
        "is_superuser": bool(user_row.get("is_superuser", False)),
    }


def _build_role_audit_payload(*, role=None, role_row=None):
    if role_row is None and role is not None:
        role_row = get_admin_role_detail(role.id)

    if role_row is None:
        return {}

    return {
        "name": role_row.get("name", ""),
        "role_type": role_row.get("role_type", "custom"),
        "is_system": bool(role_row.get("is_system", False)),
        "member_count": int(role_row.get("member_count", 0)),
        "permissions": sorted(role_row.get("permissions", [])),
        "default_permissions": sorted(role_row.get("default_permissions", [])),
    }


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


def _normalize_permission_codenames(payload):
    if "permissions" not in payload:
        return None

    permission_codenames = payload.get("permissions")
    if not isinstance(permission_codenames, list) or any(
        not isinstance(permission_codename, str) or not permission_codename.strip()
        for permission_codename in permission_codenames
    ):
        raise ValueError("permissions 必须是字符串数组。")

    return permission_codenames


def _normalize_role_payload(payload, *, require_name=False):
    has_name = "name" in payload
    name = payload.get("name")
    if require_name and (not isinstance(name, str) or not name.strip()):
        raise ValueError("name 为必填项。")
    if has_name and not isinstance(name, str):
        raise ValueError("name 必须是字符串。")

    return {
        "name": name.strip() if isinstance(name, str) else None,
        "permissions": _normalize_permission_codenames(payload),
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
        record_audit_event(
            actor=request.user,
            action="rbac.user.create",
            target_type="user",
            target_id=user_fields["username"],
            status=AuditRecord.STATUS_FAILED,
            detail_payload={
                **_build_admin_user_audit_payload(groups=group_names or []),
                "username": user_fields["username"],
                "email": user_fields["email"],
                "error": str(exc),
            },
        )
        status_code = 409 if "已存在" in str(exc) else 400
        return JsonResponse({"message": str(exc)}, status=status_code)

    record_audit_event(
        actor=request.user,
        action="rbac.user.create",
        target_type="user",
        target_id=created_user["id"],
        status=AuditRecord.STATUS_SUCCEEDED,
        detail_payload=_build_admin_user_audit_payload(user_row=created_user),
    )
    return JsonResponse(created_user, status=201)


@require_GET
@permission_required("auth.view_role")
def admin_group_list_view(request):
    return JsonResponse(list_assignable_groups(), safe=False)


@require_GET
@permission_required("auth.view_role")
def admin_role_collection_view(request):
    return JsonResponse(list_admin_role_rows(), safe=False)


@require_GET
@permission_required("auth.view_role")
def admin_permission_list_view(request):
    return JsonResponse(list_rbac_permissions(), safe=False)


@csrf_exempt
@require_http_methods(["POST"])
@permission_required("auth.assign_role")
def admin_role_create_view(request):
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({"message": "请求体必须是合法 JSON。"}, status=400)

    try:
        role_fields = _normalize_role_payload(payload, require_name=True)
        created_role = create_admin_role(
            name=role_fields["name"],
            permission_codenames=role_fields["permissions"],
        )
    except ValueError as exc:
        record_audit_event(
            actor=request.user,
            action="rbac.role.create",
            target_type="role",
            target_id=(payload.get("name") or "").strip(),
            status=AuditRecord.STATUS_FAILED,
            detail_payload={
                "name": (payload.get("name") or "").strip(),
                "permissions": sorted(payload.get("permissions") or []),
                "error": str(exc),
            },
        )
        status_code = 409 if "已存在" in str(exc) else 400
        return JsonResponse({"message": str(exc)}, status=status_code)

    record_audit_event(
        actor=request.user,
        action="rbac.role.create",
        target_type="role",
        target_id=created_role["id"],
        status=AuditRecord.STATUS_SUCCEEDED,
        detail_payload=_build_role_audit_payload(role_row=created_role),
    )
    return JsonResponse(created_role, status=201)


@csrf_exempt
@require_http_methods(["GET", "PATCH", "DELETE"])
@jwt_login_required
def admin_role_detail_view(request, role_id):
    if request.method == "GET":
        if not user_has_permission(request.user, "auth.view_role"):
            return _forbidden_response()
        try:
            return JsonResponse(get_admin_role_detail(role_id))
        except Group.DoesNotExist:
            return JsonResponse({"message": "角色不存在。"}, status=404)

    if not user_has_permission(request.user, "auth.assign_role"):
        return _forbidden_response()

    try:
        role_before = get_admin_role_detail(role_id)
    except Group.DoesNotExist:
        record_audit_event(
            actor=request.user,
            action="rbac.role.update" if request.method == "PATCH" else "rbac.role.delete",
            target_type="role",
            target_id=role_id,
            status=AuditRecord.STATUS_FAILED,
            detail_payload={"error": "角色不存在。"},
        )
        return JsonResponse({"message": "角色不存在。"}, status=404)

    if request.method == "DELETE":
        try:
            delete_admin_role(role_id)
        except ValueError as exc:
            record_audit_event(
                actor=request.user,
                action="rbac.role.delete",
                target_type="role",
                target_id=role_id,
                status=AuditRecord.STATUS_FAILED,
                detail_payload={**_build_role_audit_payload(role_row=role_before), "error": str(exc)},
            )
            return JsonResponse({"message": str(exc)}, status=400)

        record_audit_event(
            actor=request.user,
            action="rbac.role.delete",
            target_type="role",
            target_id=role_id,
            status=AuditRecord.STATUS_SUCCEEDED,
            detail_payload=_build_role_audit_payload(role_row=role_before),
        )
        return JsonResponse({"message": "角色已删除。"})

    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({"message": "请求体必须是合法 JSON。"}, status=400)

    try:
        role_fields = _normalize_role_payload(payload, require_name=False)
        updated_role = update_admin_role(
            role_id,
            name=role_fields["name"] if "name" in payload else None,
            permission_codenames=role_fields["permissions"],
        )
    except ValueError as exc:
        record_audit_event(
            actor=request.user,
            action="rbac.role.update",
            target_type="role",
            target_id=role_id,
            status=AuditRecord.STATUS_FAILED,
            detail_payload={
                **_build_role_audit_payload(role_row=role_before),
                "requested_name": payload.get("name"),
                "requested_permissions": sorted(payload.get("permissions") or []),
                "error": str(exc),
            },
        )
        status_code = 409 if "已存在" in str(exc) else 400
        return JsonResponse({"message": str(exc)}, status=status_code)

    record_audit_event(
        actor=request.user,
        action="rbac.role.update",
        target_type="role",
        target_id=role_id,
        status=AuditRecord.STATUS_SUCCEEDED,
        detail_payload={
            **_build_role_audit_payload(role_row=updated_role),
            "previous_name": role_before["name"],
            "previous_permissions": role_before["permissions"],
        },
    )
    return JsonResponse(updated_role)


@csrf_exempt
@require_http_methods(["POST"])
@permission_required("auth.assign_role")
def admin_role_restore_defaults_view(request, role_id):
    try:
        role_before = get_admin_role_detail(role_id)
    except Group.DoesNotExist:
        record_audit_event(
            actor=request.user,
            action="rbac.role.restore_defaults",
            target_type="role",
            target_id=role_id,
            status=AuditRecord.STATUS_FAILED,
            detail_payload={"error": "角色不存在。"},
        )
        return JsonResponse({"message": "角色不存在。"}, status=404)

    try:
        updated_role = restore_admin_role_permissions(role_id)
    except ValueError as exc:
        record_audit_event(
            actor=request.user,
            action="rbac.role.restore_defaults",
            target_type="role",
            target_id=role_id,
            status=AuditRecord.STATUS_FAILED,
            detail_payload={**_build_role_audit_payload(role_row=role_before), "error": str(exc)},
        )
        return JsonResponse({"message": str(exc)}, status=400)

    record_audit_event(
        actor=request.user,
        action="rbac.role.restore_defaults",
        target_type="role",
        target_id=role_id,
        status=AuditRecord.STATUS_SUCCEEDED,
        detail_payload={
            **_build_role_audit_payload(role_row=updated_role),
            "previous_permissions": role_before["permissions"],
        },
    )
    return JsonResponse(updated_role)


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
        record_audit_event(
            actor=request.user,
            action="rbac.user.groups.replace",
            target_type="user",
            target_id=user_id,
            status=AuditRecord.STATUS_FAILED,
            detail_payload={"groups": sorted({group_name.strip() for group_name in group_names}), "error": "用户不存在。"},
        )
        return JsonResponse({"message": "用户不存在。"}, status=404)

    normalized_group_names = sorted({group_name.strip() for group_name in group_names})
    previous_groups = sorted(user.groups.values_list("name", flat=True))
    try:
        updated_user = replace_user_groups(user, normalized_group_names)
    except ValueError as exc:
        record_audit_event(
            actor=request.user,
            action="rbac.user.groups.replace",
            target_type="user",
            target_id=user.id,
            status=AuditRecord.STATUS_FAILED,
            detail_payload={
                **_build_admin_user_audit_payload(user=user, groups=normalized_group_names),
                "previous_groups": previous_groups,
                "error": str(exc),
            },
        )
        return JsonResponse({"message": str(exc)}, status=400)

    record_audit_event(
        actor=request.user,
        action="rbac.user.groups.replace",
        target_type="user",
        target_id=user.id,
        status=AuditRecord.STATUS_SUCCEEDED,
        detail_payload={
            **_build_admin_user_audit_payload(user_row=updated_user),
            "previous_groups": previous_groups,
        },
    )
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
        record_audit_event(
            actor=request.user,
            action="rbac.user.update" if request.method == "PATCH" else "rbac.user.delete",
            target_type="user",
            target_id=user_id,
            status=AuditRecord.STATUS_FAILED,
            detail_payload={"error": "用户不存在。"},
        )
        return JsonResponse({"message": "用户不存在。"}, status=404)

    if request.method == "DELETE":
        user_snapshot = _build_admin_user_audit_payload(user=user)
        if request.user.id == user.id:
            record_audit_event(
                actor=request.user,
                action="rbac.user.delete",
                target_type="user",
                target_id=user.id,
                status=AuditRecord.STATUS_FAILED,
                detail_payload={**user_snapshot, "error": "不能删除当前登录用户。"},
            )
            return JsonResponse({"message": "不能删除当前登录用户。"}, status=400)

        delete_admin_user(user)
        record_audit_event(
            actor=request.user,
            action="rbac.user.delete",
            target_type="user",
            target_id=user_id,
            status=AuditRecord.STATUS_SUCCEEDED,
            detail_payload=user_snapshot,
        )
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
        record_audit_event(
            actor=request.user,
            action="rbac.user.update",
            target_type="user",
            target_id=user.id,
            status=AuditRecord.STATUS_FAILED,
            detail_payload={
                **_build_admin_user_audit_payload(user=user, groups=group_names),
                "username": user_fields["username"],
                "email": user_fields["email"],
                "error": str(exc),
            },
        )
        status_code = 409 if "已存在" in str(exc) else 400
        return JsonResponse({"message": str(exc)}, status=status_code)

    record_audit_event(
        actor=request.user,
        action="rbac.user.update",
        target_type="user",
        target_id=user.id,
        status=AuditRecord.STATUS_SUCCEEDED,
        detail_payload=_build_admin_user_audit_payload(user_row=updated_user),
    )
    return JsonResponse(updated_user)
