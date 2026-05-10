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
    ensure_user_role_bindings(request.user)

    if request.method == "PATCH":
        return _patch_current_user(request)

    return JsonResponse(serialize_user_rbac_profile(request.user))


def _patch_current_user(request):
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
