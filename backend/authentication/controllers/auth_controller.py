"""
认证 Controller — HTTP 请求处理层

接收 HTTP 请求 → 解析请求体 → 调用 Service → 构建并返回 JSON 响应。

Django 的 Controller（也叫 View）是处理 HTTP 请求的入口函数。
@require_POST 装饰器限制只接受 POST 方法（类似 SpringBoot 的 @PostMapping）。

SpringBoot 类比: @RestController 中的 @PostMapping / @GetMapping 方法。
"""

import json

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_GET

from authentication.services.auth_service import (
    authenticate_user,
    build_user_auth_profile,
    build_user_summary,
    get_user_by_id,
    register_user,
    username_exists,
)
from authentication.services.jwt_service import generate_access_token
from authentication.services.refresh_session_service import (
    RefreshSessionError,
    create_refresh_session,
    get_refresh_cookie_max_age,
    revoke_refresh_session,
    rotate_refresh_session,
)
from authentication.services.password_reset_service import (
    PasswordResetError,
    create_reset_token,
    reset_password,
)


def _parse_json_body(request):
    """解析请求体为 JSON 字典。

    如果请求体为空或格式错误返回 None。

    参数:
        request: Django HttpRequest
    返回:
        dict 或 None
    """
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None


def _build_auth_response(message, user, status_code):
    """构建完整的认证响应（含 JWT Token + 用户资料）。

    使用默认的 JWT Access Token 有效期 (15分钟)。
    """
    return _build_auth_response_with_lifetime(
        message, user, status_code, settings.JWT_ACCESS_TOKEN_LIFETIME_SECONDS,
    )


def _build_auth_response_with_lifetime(message, user, status_code, lifetime_seconds):
    """构建含 Token 的认证响应 JSON。

    响应包含:
      - access_token: JWT Token 字符串
      - access_token_type: "Bearer"
      - expires_in: Token 有效期秒数
      - user: 用户摘要
      - profile: 用户完整资料（含角色和权限）
    """
    user_summary = build_user_summary(user)
    return JsonResponse(
        {
            "message": message,
            "access_token": generate_access_token(user, lifetime_seconds=lifetime_seconds),
            "access_token_type": "Bearer",
            "expires_in": lifetime_seconds,
            "user": user_summary,
            "profile": build_user_auth_profile(user, summary=user_summary),
        },
        status=status_code,
    )


def _refresh_cookie_settings(remember_me):
    """构建 Refresh Cookie 的配置项字典。

    httponly=True: 防止 JavaScript 访问 Cookie（防 XSS）
    samesite=Lax: 同站请求携带 Cookie（防 CSRF）
    """
    max_age = get_refresh_cookie_max_age(remember_me)
    settings_map = {
        "httponly": True,
        "secure": settings.AUTH_REFRESH_COOKIE_SECURE,
        "samesite": settings.AUTH_REFRESH_COOKIE_SAMESITE,
        "path": settings.AUTH_REFRESH_COOKIE_PATH,
    }
    if settings.AUTH_REFRESH_COOKIE_DOMAIN:
        settings_map["domain"] = settings.AUTH_REFRESH_COOKIE_DOMAIN
    if max_age is not None:
        settings_map["max_age"] = max_age  # 会话 Cookie (None) vs 持久化 Cookie (秒数)
    return settings_map


def _set_refresh_cookie(response, refresh_cookie_value, remember_me):
    """在 HTTP 响应中设置 Refresh Cookie。"""
    response.set_cookie(
        settings.AUTH_REFRESH_COOKIE_NAME,
        refresh_cookie_value,
        **_refresh_cookie_settings(remember_me),
    )
    return response


def _clear_refresh_cookie(response):
    """从 HTTP 响应中清除 Refresh Cookie（登出 / Token 吊销时调用）。"""
    response.delete_cookie(
        settings.AUTH_REFRESH_COOKIE_NAME,
        path=settings.AUTH_REFRESH_COOKIE_PATH,
        domain=settings.AUTH_REFRESH_COOKIE_DOMAIN or None,
    )
    return response


def _parse_remember_me(payload):
    """从请求体中解析 remember_me 布尔值。

    兼容多种前端传值方式: bool / "true" / "1" / "yes" / "on" / 1。
    """
    remember_me = payload.get("remember_me")

    if isinstance(remember_me, bool):
        return remember_me
    if isinstance(remember_me, str):
        return remember_me.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(remember_me, (int, float)):
        return remember_me == 1
    return False


# ==================== API 端点 ====================

@ensure_csrf_cookie
@require_GET
def csrf_view(request):
    """获取 CSRF Cookie。

    前端在首次加载时调用此端点获取 CSRF Cookie。
    SpringBoot 类比: CsrfTokenRepository 的 /csrf 端点。
    """
    return JsonResponse({"message": "CSRF cookie ready。"})


@require_POST
def register_view(request):
    """用户注册 API: POST /api/auth/register

    请求体: {"username": "...", "password": "...", "email": "..."}
    成功后返回 JWT Token + 用户资料，状态码 201。
    """
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({"message": "请求体必须是合法 JSON。"}, status=400)

    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    email = (payload.get("email") or "").strip()

    if not username or not password:
        return JsonResponse({"message": "username 和 password 为必填项。"}, status=400)

    if username_exists(username):
        return JsonResponse({"message": "用户名已存在。"}, status=409)

    user = register_user(username=username, password=password, email=email)
    return _build_auth_response("注册成功。", user, 201)


@require_POST
def login_view(request):
    """用户登录 API: POST /api/auth/login

    请求体: {"username": "...", "password": "...", "remember_me": true/false}

    成功后:
      - 返回 JWT Access Token (15分钟有效)
      - 设置 HTTP-only Refresh Cookie (1天或7天有效)
    """
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({"message": "请求体必须是合法 JSON。"}, status=400)

    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""

    if not username or not password:
        return JsonResponse({"message": "username 和 password 为必填项。"}, status=400)

    user = authenticate_user(username=username, password=password)
    if user is None:
        return JsonResponse({"message": "用户名或密码错误。"}, status=401)

    remember_me = _parse_remember_me(payload)

    # 创建 Refresh Session
    refresh_cookie_value, refresh_session = create_refresh_session(
        user_id=user.id, remember_me=remember_me,
    )

    response = _build_auth_response_with_lifetime(
        "登录成功。", user, 200, settings.JWT_ACCESS_TOKEN_LIFETIME_SECONDS,
    )
    return _set_refresh_cookie(response, refresh_cookie_value, refresh_session["remember_me"])


@require_POST
def refresh_view(request):
    """Token 刷新 API: POST /api/auth/refresh

    读取 Cookie 中的 Refresh Token → 验证并轮换 → 返回新的 Access Token + 更新 Cookie。

    如果 Refresh Token 无效或过期，清除 Cookie 并返回 401。
    """
    refresh_cookie_value = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME, "")
    if not refresh_cookie_value:
        response = JsonResponse({"message": "登录已过期，请重新登录。"}, status=401)
        return _clear_refresh_cookie(response)

    try:
        rotated_cookie_value, refresh_session = rotate_refresh_session(refresh_cookie_value)
        user = get_user_by_id(refresh_session["user_id"])
    except (RefreshSessionError, KeyError):
        response = JsonResponse({"message": "登录已过期，请重新登录。"}, status=401)
        return _clear_refresh_cookie(response)

    response = _build_auth_response_with_lifetime(
        "刷新成功。", user, 200, settings.JWT_ACCESS_TOKEN_LIFETIME_SECONDS,
    )
    return _set_refresh_cookie(response, rotated_cookie_value, refresh_session["remember_me"])


@require_POST
def logout_view(request):
    """用户登出 API: POST /api/auth/logout

    吊销 Refresh Session 并清除 Cookie。
    """
    refresh_cookie_value = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME, "")
    if refresh_cookie_value:
        revoke_refresh_session(refresh_cookie_value)

    response = JsonResponse({"message": "已退出登录。"}, status=200)
    return _clear_refresh_cookie(response)


@require_POST
def forgot_password_view(request):
    """忘记密码 API: POST /api/auth/forgot-password

    请求体: {"username": "..."}
    返回: 重置 Token（开发环境直接返回，生产环境应发送邮件）
    """
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({"message": "请求体必须是合法 JSON。"}, status=400)

    username = (payload.get("username") or "").strip()
    if not username:
        return JsonResponse({"message": "username 为必填项。"}, status=400)

    try:
        raw_token, expires_in = create_reset_token(username=username)
    except PasswordResetError as exc:
        return JsonResponse({"message": str(exc)}, status=404)

    return JsonResponse(
        {
            "message": "重置令牌已生成。",
            "reset_token": raw_token,
            "expires_in": expires_in,
        },
        status=200,
    )


@require_POST
def reset_password_view(request):
    """重置密码 API: POST /api/auth/reset-password

    请求体: {"token": "...", "new_password": "..."}
    验证 Token 后更新密码。
    """
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({"message": "请求体必须是合法 JSON。"}, status=400)

    token = (payload.get("token") or "").strip()
    new_password = payload.get("new_password") or ""

    if not token or not new_password:
        return JsonResponse({"message": "token 和 new_password 为必填项。"}, status=400)

    if len(new_password) < 8:
        return JsonResponse({"message": "密码长度至少为8位。"}, status=400)

    try:
        user = reset_password(token=token, new_password=new_password)
    except PasswordResetError as exc:
        return JsonResponse({"message": str(exc)}, status=400)

    return JsonResponse({"message": "密码已重置，请使用新密码登录。"}, status=200)
