"""
RBAC 个人资料控制器 — 当前用户个人信息与密码管理端点。

作用：提供登录用户查看/修改个人资料、修改密码、上传头像等面向普通用户的接口。
      所有接口均受 JWT 认证保护，无需角色权限即可访问（因为是个人操作）。

类比 Spring Boot：
  - 本模块相当于一个 `@RestController("/profile")` 控制器，
    专门处理当前认证用户（Principal）的个人操作请求。
  - `jwt_login_required` 装饰器类似 `SecurityContextHolder` 获取当前认证用户。
"""

import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from authentication.models import User, UserProfile
from rbac.services.authz_service import jwt_login_required
from rbac.services.rbac_service import ensure_user_role_bindings, serialize_user_rbac_profile


@csrf_exempt
@require_http_methods(["GET", "PATCH"])
@jwt_login_required
def current_user_profile_view(request):
    """
    当前用户个人资料视图。

    GET   — 返回当前登录用户的完整 RBAC 资料（含分组、权限、头像、统计信息）。
    PATCH — 更新当前用户的 username 和 email。

    在执行任何操作之前，会先调用 `ensure_user_role_bindings` 确保用户已绑定
    至少一个默认角色（如 member），防止无角色用户出现。

    参数:
        request: Django HttpRequest 对象。

    返回:
        GET:   JsonResponse, 用户 RBAC 资料对象。
        PATCH: JsonResponse, 更新后的用户 RBAC 资料对象。

    类比 Spring Boot:
        `@GetMapping("/profile")` + `@PatchMapping("/profile")`，
        从 `SecurityContextHolder.getContext().getAuthentication()` 获取当前用户。
    """
    ensure_user_role_bindings(request.user)

    if request.method == "PATCH":
        return _patch_current_user(request)

    return JsonResponse(serialize_user_rbac_profile(request.user))


def _patch_current_user(request):
    """
    内部函数 — 处理当前用户个人资料更新（PATCH）。

    仅允许修改 username 和 email，不允许修改密码（密码有独立接口）。

    参数:
        request: Django HttpRequest 对象，body 中包含 username 和 email。

    返回:
        JsonResponse: 更新后的用户 RBAC 资料对象。

    异常:
        400: 请求体非法或字段为空。
        409: 用户名已被其他用户占用。

    类比 Spring Boot: Controller 中的 private 方法，被 @PatchMapping 端点内部调用。
    """
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"message": "请求体必须是合法 JSON。"}, status=400)

    username = (payload.get("username") or "").strip()
    email = (payload.get("email") or "").strip()

    if not username or not email:
        return JsonResponse({"message": "用户名和邮箱不能为空。"}, status=400)

    user = request.user

    if User.objects.filter(username=username).exclude(id=user.id).exists():
        return JsonResponse({"message": "用户名已存在。"}, status=409)

    user.username = username
    user.email = email
    user.save()

    return JsonResponse(serialize_user_rbac_profile(user))


@csrf_exempt
@require_POST
@jwt_login_required
def change_password_view(request):
    """
    修改密码视图（仅 POST）。

    验证旧密码正确后，将用户密码更新为新密码并保存。

    参数:
        request: Django HttpRequest 对象，body 中包含 old_password 和 new_password。

    返回:
        JsonResponse: {"message": "密码已修改。"}

    异常:
        400: 请求体非法、字段为空、或旧密码不正确。

    类比 Spring Boot: `@PostMapping("/profile/change-password")`，
    调用 `passwordEncoder.matches()` 验证旧密码后 `passwordEncoder.encode()` 更新。
    """
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"message": "请求体必须是合法 JSON。"}, status=400)

    old_password = payload.get("old_password") or ""
    new_password = payload.get("new_password") or ""

    if not old_password or not new_password:
        return JsonResponse({"message": "旧密码和新密码不能为空。"}, status=400)

    user = request.user
    if not user.check_password(old_password):
        return JsonResponse({"message": "旧密码不正确。"}, status=400)

    user.set_password(new_password)
    user.save()

    return JsonResponse({"message": "密码已修改。"})


@require_POST
@jwt_login_required
def upload_avatar_view(request):
    """
    上传头像视图（仅 POST）。

    接收 multipart 上传的图片文件，校验格式和大小后存储到 UserProfile 模型。

    校验规则:
        - 文件大小不超过 2MB。
        - 仅支持 JPEG、PNG、GIF、WebP 格式。

    参数:
        request: Django HttpRequest 对象，FILES 中需包含 avatar 字段。

    返回:
        JsonResponse: 包含更新后用户 RBAC 资料的 JSON 对象（含新头像 URL）。

    异常:
        400: 未选择文件、文件超限、格式不支持。

    类比 Spring Boot: `@PostMapping("/profile/avatar")` + `@RequestParam("avatar") MultipartFile`，
    上传后更新 UserProfile 实体的 avatar 字段。
    """
    file = request.FILES.get("avatar")
    if not file:
        return JsonResponse({"error": "请选择头像文件"}, status=400)

    if file.size > 2 * 1024 * 1024:
        return JsonResponse({"error": "头像文件不能超过 2MB"}, status=400)

    allowed_types = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    if file.content_type not in allowed_types:
        return JsonResponse({"error": "仅支持 JPG、PNG、GIF、WebP 格式"}, status=400)

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.avatar = file
    profile.save()

    return JsonResponse(serialize_user_rbac_profile(request.user))
