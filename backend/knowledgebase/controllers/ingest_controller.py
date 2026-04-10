from django.db import DatabaseError, OperationalError, ProgrammingError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from knowledgebase.models import Document
from knowledgebase.services.document_service import (
    build_document_response,
    enqueue_document_ingestion,
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


@csrf_exempt
@require_POST
@permission_required("auth.trigger_ingest")
def document_ingest_view(request, document_id):
    try:
        document = get_document_for_user(request.user, document_id)
    except Document.DoesNotExist:
        return JsonResponse({"message": "文档不存在。"}, status=404)
    except (OperationalError, ProgrammingError, DatabaseError) as exc:
        return _build_schema_not_ready_response(exc)

    try:
        ingestion_task, created = enqueue_document_ingestion(document)
        document.refresh_from_db()

        return JsonResponse(
            build_document_response(
                document,
                include_content_preview=True,
                message="摄取任务已提交。" if created else "已有进行中的摄取任务。",
            )
        )
    except (OperationalError, ProgrammingError, DatabaseError) as exc:
        return _build_schema_not_ready_response(exc)
