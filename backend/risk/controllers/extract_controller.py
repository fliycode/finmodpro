from rest_framework.views import APIView

from common.api_response import error_response, success_response
from common.exceptions import UpstreamServiceError
from knowledgebase.models import Document
from rbac.services.authz_service import get_authenticated_user, user_has_permission
from systemcheck.services.audit_service import record_audit_event
from risk.serializers import RiskEventSummarySerializer
from risk.services import extract_risk_events_for_document, list_document_chunks


def _handle_document_extract(*, request, document_id, action, retry_action=None):
    user = get_authenticated_user(request)
    if user is None:
        return error_response(code=401, message="未认证。", status_code=401)
    if not user_has_permission(user, "auth.trigger_ingest"):
        return error_response(code=403, message="无权限。", status_code=403)

    try:
        document = Document.objects.get(id=document_id)
    except Document.DoesNotExist:
        return error_response(code=404, message="文档不存在。", status_code=404)

    if retry_action:
        record_audit_event(
            actor=user,
            action=retry_action,
            target_type="document",
            target_id=document.id,
            status="retried",
            detail_payload={"retry_from_action": action},
        )

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
        record_audit_event(
            actor=user,
            action=action,
            target_type="document",
            target_id=document.id,
            status="failed",
            detail_payload={
                "error_code": exc.code,
                "message": exc.message,
            },
        )
        return error_response(
            code=exc.status_code,
            message=exc.message,
            data=data,
            status_code=exc.status_code,
        )

    record_audit_event(
        actor=user,
        action=action,
        target_type="document",
        target_id=document.id,
        status="succeeded",
        detail_payload={
            "created_count": len(created_events),
        },
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


class RiskDocumentExtractView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, document_id):
        return _handle_document_extract(
            request=request,
            document_id=document_id,
            action="risk.extract",
        )


class RiskDocumentExtractRetryView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, document_id):
        return _handle_document_extract(
            request=request,
            document_id=document_id,
            action="risk.extract",
            retry_action="risk.extract.retry",
        )
