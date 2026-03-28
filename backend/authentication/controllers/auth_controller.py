import json

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from authentication.services.auth_service import (
    authenticate_user,
    build_user_summary,
    register_user,
    username_exists,
)
from authentication.services.jwt_service import generate_access_token


def _parse_json_body(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None


def _build_auth_response(message, user, status_code):
    return JsonResponse(
        {
            "message": message,
            "access_token": generate_access_token(user),
            "access_token_type": "Bearer",
            "expires_in": settings.JWT_ACCESS_TOKEN_LIFETIME_SECONDS,
            "user": build_user_summary(user),
        },
        status=status_code,
    )


@csrf_exempt
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


@csrf_exempt
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

    return _build_auth_response("登录成功。", user, 200)
