"""
文档分块查询控制器。

类比 SpringBoot: 相当于 @RestController 中处理分块查询的 GET 端点。
提供文档所有分块内容的只读查询接口。
"""
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
    """
    构建"数据库未就绪"的统一错误响应。

    类比 SpringBoot: 相当于 @ControllerAdvice 中针对数据库异常的全局处理逻辑。

    参数:
        exc: 捕获到的数据库异常对象

    返回:
        JsonResponse: 状态码 503，包含中文错误提示。
    """
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
    """
    文档分块列表端点 —— GET documents/{document_id}/chunks。

    类比 SpringBoot: 相当于
        @GetMapping("/documents/{documentId}/chunks")
        @PreAuthorize("hasAuthority('auth.view_document')")
        public ResponseEntity<?> getChunks(@PathVariable Long documentId)

    返回指定文档的所有分块（DocumentChunk）信息。

    参数:
        request:     Django HttpRequest 对象
        document_id: URL 路径中的文档 ID（整数）

    返回:
        JsonResponse: 包含文档所有分块详细信息的 JSON 响应。
                      文档不存在返回 404，数据库未就绪返回 503。
    """
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
