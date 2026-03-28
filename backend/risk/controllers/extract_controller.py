from rest_framework.views import APIView

from common.api_response import error_response, success_response
from common.exceptions import UpstreamServiceError
from knowledgebase.models import Document
from rbac.services.authz_service import get_authenticated_user, user_has_permission
from risk.serializers import RiskEventSummarySerializer
from risk.services import extract_risk_events_for_document, list_document_chunks


class RiskDocumentExtractView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, document_id):
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.trigger_ingest"):
            return error_response(code=403, message="无权限。", status_code=403)

        try:
            document = Document.objects.get(id=document_id)
        except Document.DoesNotExist:
            return error_response(code=404, message="文档不存在。", status_code=404)

        chunks = list_document_chunks(document=document)
        if not chunks:
            return success_response(
                message="文档暂无可抽取内容。",
                data={"document_id": document.id, "created_count": 0, "risk_events": []},
            )

        try:
            created_events = extract_risk_events_for_document(document=document)
        except UpstreamServiceError as exc:
            data = {"error_code": exc.code}
            if exc.provider:
                data["provider"] = exc.provider
            return error_response(
                code=exc.status_code,
                message=exc.message,
                data=data,
                status_code=exc.status_code,
            )

        return success_response(
            message="风险抽取完成。",
            data={
                "document_id": document.id,
                "created_count": len(created_events),
                "risk_events": RiskEventSummarySerializer(created_events, many=True).data,
            },
            status_code=201,
        )
