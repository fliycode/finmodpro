from rest_framework.views import APIView

from common.api_response import error_response, success_response
from rbac.services.authz_service import get_authenticated_user, user_has_permission
from risk.serializers import RiskEventListQuerySerializer, RiskEventSummarySerializer
from risk.services.query_service import list_risk_events


class RiskEventListView(APIView):
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

        risk_events = list_risk_events(filters=serializer.validated_data)
        return success_response(
            data={
                "total": risk_events.count(),
                "risk_events": RiskEventSummarySerializer(risk_events, many=True).data,
            }
        )
