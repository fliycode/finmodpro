from rest_framework.views import APIView

from common.api_response import error_response, success_response
from rbac.services.authz_service import get_authenticated_user, user_has_permission
from risk.serializers import RiskEventListQuerySerializer
from risk.services.analytics_service import build_risk_analytics_overview


class RiskAnalyticsOverviewView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.view_document"):
            return error_response(code=403, message="无权限。", status_code=403)

        serializer = RiskEventListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        return success_response(data=build_risk_analytics_overview(filters=serializer.validated_data))
