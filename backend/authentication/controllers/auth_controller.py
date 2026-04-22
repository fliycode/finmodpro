import json

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_GET

from authentication.services.auth_service import (
    authenticate_user,
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


def _parse_json_body(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None


def _build_auth_response(message, user, status_code):
    return _build_auth_response_with_lifetime(
        message,
        user,
        status_code,
        settings.JWT_ACCESS_TOKEN_LIFETIME_SECONDS,
    )


def _build_auth_response_with_lifetime(message, user, status_code, lifetime_seconds):
    return JsonResponse(
        {
            "message": message,
            "access_token": generate_access_token(user, lifetime_seconds=lifetime_seconds),
            "access_token_type": "Bearer",
            "expires_in": lifetime_seconds,
            "user": build_user_summary(user),
        },
        status=status_code,
    )


def _refresh_cookie_settings(remember_me):
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
        settings_map["max_age"] = max_age
    return settings_map


def _set_refresh_cookie(response, refresh_cookie_value, remember_me):
    response.set_cookie(
        settings.AUTH_REFRESH_COOKIE_NAME,
        refresh_cookie_value,
        **_refresh_cookie_settings(remember_me),
    )
    return response


def _clear_refresh_cookie(response):
    response.delete_cookie(
        settings.AUTH_REFRESH_COOKIE_NAME,
        path=settings.AUTH_REFRESH_COOKIE_PATH,
        domain=settings.AUTH_REFRESH_COOKIE_DOMAIN or None,
    )
    return response


def _parse_remember_me(payload):
    remember_me = payload.get("remember_me")

    if isinstance(remember_me, bool):
        return remember_me

    if isinstance(remember_me, str):
        return remember_me.strip().lower() in {"1", "true", "yes", "on"}

    if isinstance(remember_me, (int, float)):
        return remember_me == 1

    return False


@ensure_csrf_cookie
@require_GET
def csrf_view(request):
    return JsonResponse({"message": "CSRF cookie ready。"})


@require_POST
def register_view(request):
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({"message": "请求体必须是合法 JSON。"}, status=400)

    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    email = (payload.get("email") or "").strip()

    if not username or not password:
        return JsonResponse(
            {"message": "username 和 password 为必填项。"},
            status=400,
        )

    if username_exists(username):
        return JsonResponse({"message": "用户名已存在。"}, status=409)

    user = register_user(
        username=username,
        password=password,
        email=email,
    )
    return _build_auth_response("注册成功。", user, 201)


@require_POST
def login_view(request):
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({"message": "请求体必须是合法 JSON。"}, status=400)

    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""

    if not username or not password:
        return JsonResponse(
            {"message": "username 和 password 为必填项。"},
            status=400,
        )

    user = authenticate_user(username=username, password=password)
    if user is None:
        return JsonResponse({"message": "用户名或密码错误。"}, status=401)

    remember_me = _parse_remember_me(payload)
    refresh_cookie_value, refresh_session = create_refresh_session(
        user_id=user.id,
        remember_me=remember_me,
    )
    token_lifetime_seconds = (
        settings.JWT_ACCESS_TOKEN_LIFETIME_SECONDS
    )
    response = _build_auth_response_with_lifetime(
        "登录成功。",
        user,
        200,
        token_lifetime_seconds,
    )
    return _set_refresh_cookie(
        response,
        refresh_cookie_value,
        refresh_session["remember_me"],
    )


@require_POST
def refresh_view(request):
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
        "刷新成功。",
        user,
        200,
        settings.JWT_ACCESS_TOKEN_LIFETIME_SECONDS,
    )
    return _set_refresh_cookie(
        response,
        rotated_cookie_value,
        refresh_session["remember_me"],
    )


@require_POST
def logout_view(request):
    refresh_cookie_value = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME, "")
    if refresh_cookie_value:
        revoke_refresh_session(refresh_cookie_value)

    response = JsonResponse({"message": "已退出登录。"}, status=200)
    return _clear_refresh_cookie(response)
