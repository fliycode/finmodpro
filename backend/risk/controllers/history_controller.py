"""
提取历史列表控制器 —— GET /api/risk/extractions
返回最近的风险提取任务历史，包含文档信息。
"""

from rest_framework.views import APIView

from common.api_response import success_response, error_response
from rbac.services.authz_service import get_authenticated_user, user_has_permission
from risk.services.task_service import list_extraction_tasks, serialize_risk_extraction_task
from knowledgebase.models import Document


class RiskExtractionHistoryView(APIView):
    """
    提取历史列表视图 —— 返回最近的风险提取任务记录。

    查询参数:
        - document_id (int, 可选): 按文档过滤
        - status (str, 可选): queued / running / succeeded / failed
        - limit (int, 可选): 返回条数，默认 20
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.view_document"):
            return error_response(code=403, message="无权限。", status_code=403)

        document_id = request.query_params.get("document_id")
        status_filter = request.query_params.get("status")
        try:
            limit = int(request.query_params.get("limit", 20))
            limit = max(1, min(100, limit))
        except (ValueError, TypeError):
            limit = 20

        if document_id is not None:
            try:
                document_id = int(document_id)
            except (ValueError, TypeError):
                return error_response(code=400, message="document_id 必须为整数。")

        tasks = list_extraction_tasks(document_id=document_id, status=status_filter, limit=limit)

        extracted_document_ids = {t.document_id for t in tasks}
        documents = {
            d.id: d
            for d in Document.objects.filter(id__in=extracted_document_ids).only(
                "id", "title", "filename", "file_size", "source_date"
            )
        }

        history = []
        for task in tasks:
            entry = serialize_risk_extraction_task(task)
            doc = documents.get(task.document_id)
            if doc:
                entry["document_title"] = doc.title or ""
                entry["document_filename"] = doc.filename or ""
                entry["document_file_size"] = doc.file_size or 0
                entry["document_source_date"] = doc.source_date.isoformat() if doc.source_date else None
            history.append(entry)

        return success_response(data={"total": len(history), "tasks": history})
