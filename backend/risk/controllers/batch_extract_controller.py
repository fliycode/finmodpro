from rest_framework.views import APIView

from common.api_response import error_response, success_response
from rbac.services.authz_service import get_authenticated_user, user_has_permission
from risk.serializers import RiskBatchExtractionRequestSerializer
from risk.services import batch_extract_risk_events_for_documents


class RiskDocumentBatchExtractView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.trigger_ingest"):
            return error_response(code=403, message="无权限。", status_code=403)

        serializer = RiskBatchExtractionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        batch_summary = batch_extract_risk_events_for_documents(
            document_ids=serializer.validated_data["document_ids"]
        )
        return success_response(
            message="批量风险抽取完成。",
            data=batch_summary,
        )
