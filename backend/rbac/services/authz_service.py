"""
授权装饰器 — JWT 认证 + 权限校验

提供 DRF 视图使用的认证和鉴权装饰器（Django 的函数式视图不能用 DRF 类装饰器，
因此自定义了 @jwt_login_required 和 @permission_required）。

SpringBoot 类比: @PreAuthorize 注解 + SecurityFilterChain 的结合体。
"""

from functools import wraps

from django.http import JsonResponse

from authentication.models import User
from authentication.services.jwt_service import decode_access_token


def collect_user_permissions(user):
    """获取用户的所有权限名列表（已排序）。

    返回 Django 内置格式: ["auth.view_dashboard", "auth.view_user", ...]
    """
    return sorted(user.get_all_permissions())


def user_has_permission(user, permission_name):
    """检查用户是否拥有指定权限。

    参数:
        user: User 实例
        permission_name: 权限名，支持 "view_dashboard" 或 "auth.view_dashboard" 两种格式
    返回:
        bool
    """
    permissions = collect_user_permissions(user)
    if "." in permission_name:
        return permission_name in permissions
    # 允许传不带 app_label 的短格式（如 "view_dashboard"）
    return permission_name in {value.split(".", 1)[1] for value in permissions}


def _get_bearer_token(request):
    """从 HTTP Authorization header 提取 Bearer Token。

    返回 Token 字符串或 None。
    """
    authorization = request.headers.get("Authorization", "")
    token_type, _, token = authorization.partition(" ")
    if token_type != "Bearer" or not token:
        return None
    return token


def get_authenticated_user(request):
    """从请求中提取 JWT Token 并获取用户。

    返回 User 实例（认证成功）或 None（无效/过期/缺失 Token）。
    """
    token = _get_bearer_token(request)
    if not token:
        return None

    try:
        claims = decode_access_token(token)
        return User.objects.get(id=claims["user_id"])
    except (KeyError, User.DoesNotExist, ValueError):
        return None


def jwt_login_required(view_func):
    """JWT 认证装饰器 — 要求请求携带有效 Bearer Token。

    将解析出的 User 对象注入 request.user，认证失败返回 401。

    使用方式:
        @jwt_login_required
        def my_view(request):
            # request.user 已可用
            ...

    SpringBoot 类比: @PreAuthorize("isAuthenticated()")
    """

    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        user = get_authenticated_user(request)
        if user is None:
            return JsonResponse({"message": "未认证。"}, status=401)

        request.user = user  # 注入用户对象
        return view_func(request, *args, **kwargs)

    return wrapped_view


def permission_required(permission_name):
    """权限校验装饰器 — 要求用户拥有指定权限。

    先执行 JWT 认证，再检查权限。缺少权限返回 403。

    使用方式:
        @permission_required("auth.view_dashboard")
        def my_view(request):
            ...

    SpringBoot 类比: @PreAuthorize("hasAuthority('view_dashboard')")
    """
    def decorator(view_func):
        @wraps(view_func)
        @jwt_login_required  # 先认证
        def wrapped_view(request, *args, **kwargs):
            if not user_has_permission(request.user, permission_name):
                return JsonResponse({"message": "无权限。"}, status=403)
            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator
