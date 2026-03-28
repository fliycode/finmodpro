from functools import wraps

from django.http import JsonResponse

from authentication.models import User
from authentication.services.jwt_service import decode_access_token


def collect_user_permissions(user):
    return sorted(user.get_all_permissions())


def user_has_permission(user, permission_name):
    permissions = collect_user_permissions(user)
    if "." in permission_name:
        return permission_name in permissions
    return permission_name in {value.split(".", 1)[1] for value in permissions}


def _get_bearer_token(request):
    authorization = request.headers.get("Authorization", "")
    token_type, _, token = authorization.partition(" ")
    if token_type != "Bearer" or not token:
        return None
    return token


def get_authenticated_user(request):
    token = _get_bearer_token(request)
    if not token:
        return None

    try:
        claims = decode_access_token(token)
        return User.objects.get(id=claims["user_id"])
    except (KeyError, User.DoesNotExist, ValueError):
        return None


def jwt_login_required(view_func):
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        user = get_authenticated_user(request)
        if user is None:
            return JsonResponse({"message": "未认证。"}, status=401)

        request.user = user
        return view_func(request, *args, **kwargs)

    return wrapped_view


def permission_required(permission_name):
    def decorator(view_func):
        @wraps(view_func)
        @jwt_login_required
        def wrapped_view(request, *args, **kwargs):
            if not user_has_permission(request.user, permission_name):
                return JsonResponse({"message": "无权限。"}, status=403)
            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator
