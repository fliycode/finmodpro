from django.http import JsonResponse
from django.views.decorators.http import require_GET

from rbac.services.authz_service import jwt_login_required
from rbac.services.rbac_service import serialize_user_rbac_profile


@require_GET
@jwt_login_required
def current_user_profile_view(request):
    return JsonResponse(serialize_user_rbac_profile(request.user))
