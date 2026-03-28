from rest_framework.views import APIView

from common.api_response import error_response, success_response
from rbac.services.authz_service import get_authenticated_user, user_has_permission
from risk.models import RiskEvent
from risk.serializers import RiskEventReviewSerializer, RiskEventSummarySerializer
from risk.services.review_service import review_risk_event


class RiskEventReviewView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, event_id):
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.review_risk_event"):
            return error_response(code=403, message="无权限。", status_code=403)

        serializer = RiskEventReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            risk_event = RiskEvent.objects.get(id=event_id)
        except RiskEvent.DoesNotExist:
            return error_response(code=404, message="风险事件不存在。", status_code=404)

        reviewed_event = review_risk_event(
            risk_event=risk_event,
            review_status=serializer.validated_data["review_status"],
        )
        return success_response(
            message="风险事件审核完成。",
            data={"risk_event": RiskEventSummarySerializer(reviewed_event).data},
        )
