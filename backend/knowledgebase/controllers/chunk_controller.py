from django.db import DatabaseError, OperationalError, ProgrammingError
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from knowledgebase.models import Document
from knowledgebase.services.document_service import (
    build_document_chunks_response,
    get_document_for_user,
)
from rbac.services.authz_service import permission_required


def _build_schema_not_ready_response(exc):
    return JsonResponse(
        {
            "message": "知识库数据表尚未初始化，请先执行后端迁移与 RBAC 初始化。",
            "detail": str(exc),
        },
        status=503,
    )


@require_GET
@permission_required("auth.view_document")
def document_chunks_view(request, document_id):
    try:
        document = get_document_for_user(request.user, document_id)
    except Document.DoesNotExist:
        return JsonResponse({"message": "文档不存在。"}, status=404)
    except (OperationalError, ProgrammingError, DatabaseError) as exc:
        return _build_schema_not_ready_response(exc)

    try:
        return JsonResponse(build_document_chunks_response(document))
    except (OperationalError, ProgrammingError, DatabaseError) as exc:
        return _build_schema_not_ready_response(exc)
