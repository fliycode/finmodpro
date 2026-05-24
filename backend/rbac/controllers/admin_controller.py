"""
RBAC 管理员控制器 — 用户/角色/权限管理的 HTTP 端点。

作用：提供管理员视角下的用户 CRUD、角色 CRUD、权限查询、用户分组替换等 RESTful 接口。
      所有接口均受 JWT 认证和细粒度权限校验保护，操作审计日志由 AuditRecord 记录。

类比 Spring Boot：
  - 本模块相当于一个 `@RestController`（AdminController），其中每个视图函数
    对应一个 `@RequestMapping` / `@PostMapping` / `@GetMapping` 等注解方法。
  - `jwt_login_required` 装饰器类似 `@PreAuthorize` + JWT Filter，
    `permission_required` 装饰器类似 `@PreAuthorize("hasAuthority('xxx')")`。
"""

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


# =============================================================================
# 内部辅助函数 — 类似于 Spring Boot Controller 中的 private 工具方法
# =============================================================================


def _parse_json_body(request):
    """
    解析请求体为 JSON 字典。

    参数:
        request: Django HttpRequest 对象。

    返回:
        dict: 解析成功时返回 JSON 字典；
        None: JSON 格式非法时返回 None。

    类比 Spring Boot: `@RequestBody` 自动反序列化，此处手动完成该步骤。
    """
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None


def _forbidden_response():
    """
    快速构建 403 Forbidden 响应。

    返回:
        JsonResponse: HTTP 403，附带中文提示消息。

    类比 Spring Boot: `throw new AccessDeniedException("无权限。")` 后由全局异常处理器
    统一返回 403。
    """
    return JsonResponse({"message": "无权限。"}, status=403)


def _build_admin_user_audit_payload(*, user=None, user_row=None, groups=None):
    """
    从用户对象或已序列化的用户行构建审计日志负载（payload）。

    参数:
        user:   Django User 模型实例（可选），优先级低于 user_row。
        user_row:  dict，已经序列化的用户数据（可选）。
        groups:    list[str]，直接指定的分组列表（可选），与 user/groups 二选一。

    返回:
        dict: 包含 username、email、groups、is_staff、is_superuser 的字典。

    类比 Spring Boot: 构建审计 DTO，用于 AuditEvent 记录。
    """
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
    """
    从角色对象或已序列化的角色行构建审计日志负载。

    参数:
        role:     Django Group 模型实例（可选），优先级低于 role_row。
        role_row: dict，已经序列化的角色数据（可选）。

    返回:
        dict: 包含 name、role_type、is_system、member_count、permissions 等的字典。

    类比 Spring Boot: 构建审计 DTO，用于 AuditEvent 记录。
    """
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
    """
    从请求体中提取并规范化分组名称列表。

    参数:
        payload: dict，请求体 JSON。

    返回:
        list[str] | None: 去重排序后的分组名称列表；若 payload 中不含 "groups" 字段则返回 None。

    异常:
        ValueError: 当 groups 不是非空字符串列表时抛出。

    类比 Spring Boot: Controller 层的 `@Valid` + 自定义校验逻辑。
    """
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
    """
    从请求体中提取并规范化用户字段（username、email、password）。

    参数:
        payload:         dict，请求体 JSON。
        require_password: bool，是否强制要求提供 password（创建用户时为 True）。

    返回:
        dict: {"username": str, "email": str, "password": str}

    异常:
        ValueError: 当必填字段缺失时抛出。

    类比 Spring Boot: Controller 层的 `@Valid UserDTO` 参数校验。
    """
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
    """
    从请求体中提取并规范化权限 codename 列表。

    参数:
        payload: dict，请求体 JSON。

    返回:
        list[str] | None: 权限 codename 列表；若 payload 中不含 "permissions" 字段则返回 None。

    异常:
        ValueError: 当 permissions 不是字符串列表时抛出。

    类比 Spring Boot: 校验并转换请求中的权限列表 DTO。
    """
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
    """
    从请求体中提取并规范化角色字段（name、permissions）。

    参数:
        payload:      dict，请求体 JSON。
        require_name: bool，是否强制要求提供 name（创建角色时为 True）。

    返回:
        dict: {"name": str | None, "permissions": list[str] | None}

    异常:
        ValueError: 当 name 必填但缺失或格式非法时抛出。

    类比 Spring Boot: 校验并转换请求中的角色 DTO。
    """
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


# =============================================================================
# 管理员视图函数 — 类似于 Spring Boot @RestController 中的公开端点
# =============================================================================


@csrf_exempt
@require_http_methods(["GET", "POST"])
@jwt_login_required
def admin_user_collection_view(request):
    """
    管理员用户集合视图。

    GET   — 列表查询：返回所有用户列表（需要 auth.view_user 权限）。
    POST  — 创建用户：创建新用户并可选分配分组（需要 auth.add_user 权限，
             若同时指定了 groups 还需要 auth.assign_role 权限）。

    参数:
        request: Django HttpRequest 对象。

    返回:
        GET:  JsonResponse, 用户列表（数组）。
        POST: JsonResponse, 新创建的用户对象，状态码 201。

    类比 Spring Boot: `@GetMapping("/admin/users")` + `@PostMapping("/admin/users")`
    合并到一个方法中，由 `request.method` 区分。
    """
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
    """
    管理员分组列表视图（仅 GET）。

    返回所有可分配的分组（Django Group）列表，供管理员为用户分配角色时参照。

    权限要求:
        auth.view_role

    参数:
        request: Django HttpRequest 对象。

    返回:
        JsonResponse: 分组列表（id + name），数组格式。

    类比 Spring Boot: `@GetMapping("/admin/groups")`，类似查询所有 `Role` 实体。
    """
    return JsonResponse(list_assignable_groups(), safe=False)


@require_GET
@permission_required("auth.view_role")
def admin_role_collection_view(request):
    """
    管理员角色列表视图（仅 GET）。

    返回所有角色（含自定义和系统角色）的摘要列表。

    权限要求:
        auth.view_role

    参数:
        request: Django HttpRequest 对象。

    返回:
        JsonResponse: 角色列表，数组格式。

    类比 Spring Boot: `@GetMapping("/admin/roles")`，返回 `List<RoleDTO>`。
    """
    return JsonResponse(list_admin_role_rows(), safe=False)


@require_GET
@permission_required("auth.view_role")
def admin_permission_list_view(request):
    """
    管理员权限列表视图（仅 GET）。

    返回平台中所有可分配权限的完整清单，包含每个权限默认被分配给哪些系统角色。

    权限要求:
        auth.view_role

    参数:
        request: Django HttpRequest 对象。

    返回:
        JsonResponse: 权限列表，数组格式。

    类比 Spring Boot: `@GetMapping("/admin/permissions")`，查询所有 `GrantedAuthority`。
    """
    return JsonResponse(list_rbac_permissions(), safe=False)


@csrf_exempt
@require_http_methods(["POST"])
@permission_required("auth.assign_role")
def admin_role_create_view(request):
    """
    管理员创建角色视图（仅 POST）。

    创建一个新的自定义角色，并可指定其初始权限集合。

    权限要求:
        auth.assign_role

    参数:
        request: Django HttpRequest 对象，body 中包含 name（必填）和 permissions（可选）。

    返回:
        JsonResponse: 新创建的角色详情，状态码 201。

    异常:
        400: 请求体非法。
        409: 角色名称已存在。

    类比 Spring Boot: `@PostMapping("/admin/roles")`，创建新的 Role 实体。
    """
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
    """
    管理员角色详情视图 — 单个角色的增删改查。

    GET    — 查看角色详情（含已分配用户列表，需要 auth.view_role 权限）。
    PATCH  — 更新角色名称和/或权限（需要 auth.assign_role 权限）。
    DELETE — 删除角色（需要 auth.assign_role 权限，系统角色不可删除）。

    参数:
        request: Django HttpRequest 对象。
        role_id: int，角色 ID（URL 路径参数）。

    返回:
        GET:    角色详情对象。
        PATCH:  更新后的角色详情。
        DELETE: {"message": "角色已删除。"}

    异常:
        404: 角色不存在。
        400/409: 参数校验失败或业务逻辑冲突。

    类比 Spring Boot: `@RequestMapping("/admin/roles/{roleId}")`，
    由 `@GetMapping` / `@PatchMapping` / `@DeleteMapping` 分别处理。
    """
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
    """
    管理员角色恢复默认权限视图（仅 POST）。

    将指定系统角色的权限集合重置为 ROLE_PERMISSION_MAP 中定义的默认值。
    自定义角色不可恢复默认。

    权限要求:
        auth.assign_role

    参数:
        request: Django HttpRequest 对象。
        role_id: int，角色 ID（URL 路径参数）。

    返回:
        JsonResponse: 恢复默认后的角色详情。

    异常:
        404: 角色不存在。
        400: 非系统角色（不支持恢复默认）。

    类比 Spring Boot: `@PostMapping("/admin/roles/{roleId}/restore-defaults")`，
    类似"重置为出厂设置"操作。
    """
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
    """
    管理员替换用户分组视图（仅 PUT）。

    将指定用户的分组（角色）整体替换为新的分组列表。

    权限要求:
        auth.assign_role

    参数:
        request: Django HttpRequest 对象，body 中需包含 groups 数组。
        user_id: int，目标用户 ID（URL 路径参数）。

    返回:
        JsonResponse: 更新后的用户对象（含新分组）。

    异常:
        400: 请求体非法或分组名无效。
        404: 用户不存在。

    类比 Spring Boot: `@PutMapping("/admin/users/{userId}/groups")`，
    执行 User 与 Role 的 ManyToMany 关系替换。
    """
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
    """
    管理员用户详情视图 — 单个用户的修改和删除。

    PATCH  — 更新用户信息（username、email、password）和/或分组。
             需要 auth.change_user 权限；
             若同时指定了 groups 还需要 auth.assign_role 权限。
    DELETE — 删除用户。需要 auth.delete_user 权限；不允许删除当前登录用户。
             使用 permission_required 装饰器已完成权限前置校验。

    参数:
        request: Django HttpRequest 对象。
        user_id: int，目标用户 ID（URL 路径参数）。

    返回:
        PATCH:  更新后的用户对象。
        DELETE: {"message": "用户已删除。"}

    异常:
        404: 用户不存在。
        400: 尝试删除自己 / 参数校验失败。
        409: 用户名冲突。

    类比 Spring Boot: `@RequestMapping("/admin/users/{userId}")`，
    由 `@PatchMapping` 和 `@DeleteMapping` 分别处理。
    """
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
