from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from authentication.models import UserProfile
from rbac.services.authz_service import jwt_login_required
from rbac.services.rbac_service import ensure_user_role_bindings, serialize_user_rbac_profile


@require_GET
@jwt_login_required
def current_user_profile_view(request):
    ensure_user_role_bindings(request.user)
    return JsonResponse(serialize_user_rbac_profile(request.user))


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
