"""
文档管理控制器 —— 知识库最核心的 CRUD 端点。

类比 SpringBoot: 相当于 @RestController 中处理文档资源的核心端点集合。
提供文档的上传（创建）、列表查询（分页/过滤）、详情查看、删除和统计功能。
文档上传支持文件去重（SHA256 哈希）、文件大小限制和多级权限控制。
"""
from django.db import DatabaseError, OperationalError, ProgrammingError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from django.conf import settings

from common.exceptions import DuplicateDocumentError
from knowledgebase.controllers.audit_utils import (
    build_document_audit_payload,
    safe_record_audit_event,
)
from knowledgebase.models import Document
from knowledgebase.services.document_service import (
    build_document_list_response,
    build_document_response,
    build_stats_response,
    create_document_from_upload,
    delete_document_with_vectors,
    get_document_for_user,
)
from rbac.services.authz_service import permission_required
from systemcheck.models import AuditRecord

_MAX_UPLOAD_BYTES = getattr(settings, "DATA_UPLOAD_MAX_MEMORY_SIZE", 50 * 1024 * 1024)


def _build_schema_not_ready_response(exc):
    """
    构建"数据库未就绪"的统一错误响应。

    类比 SpringBoot: 相当于 @ControllerAdvice 中的全局数据库异常处理器。

    参数:
        exc: 捕获到的数据库异常对象

    返回:
        JsonResponse: 状态码 503。
    """
    return JsonResponse(
        {
            "message": "知识库数据表尚未初始化，请先执行后端迁移与 RBAC 初始化。",
            "detail": str(exc),
        },
        status=503,
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
@permission_required("auth.view_document")
def document_list_create_view(request):
    """
    文档列表/上传端点 —— GET/POST documents。

    类比 SpringBoot: 相当于
        @RequestMapping(value="/documents", method={GET, POST})
        @PreAuthorize("hasAuthority('auth.view_document')")

    GET:  分页查询文档列表，支持多种过滤条件：
          - q:          全文搜索关键词
          - status:     按状态过滤（all/uploaded/parsed/indexed/failed 等）
          - time_range: 按时间范围过滤（today/week/month/year/all）
          - dataset_id: 按所属数据集过滤
          - page/page_size: 分页参数（不传则返回全量）

    POST: 上传新文档（multipart/form-data），需额外具备 auth.upload_document 权限。
          支持的字段：
          - file:         文件本身（必填）
          - title:        文档标题
          - source_date:  来源日期
          - owner_id:     所有者 ID
          - visibility:   可见性（private/internal/public）
          - dataset_id:   所属数据集 ID
          上传前会进行 SHA256 去重检测和文件大小校验。

    参数:
        request: Django HttpRequest 对象

    返回:
        GET  -> 200: {"documents": [...], "total": N, "page": ..., "page_size": ..., "total_pages": ...}
        POST -> 201: 文档详情 JSON（上传成功）
        POST -> 400: 参数校验失败
        POST -> 409: 重复文档（SHA256 哈希冲突）
        POST -> 413: 文件超出大小限制
        无权限 -> 403
        数据库未就绪 -> 503
    """
    if request.method == "GET":
        page_requested = "page" in request.GET or "page_size" in request.GET
        try:
            return JsonResponse(
                build_document_list_response(
                    request.user,
                    q=request.GET.get("q", ""),
                    status=request.GET.get("status", "all"),
                    time_range=request.GET.get("time_range", "all"),
                    dataset_id=request.GET.get("dataset_id"),
                    page=request.GET.get("page") if page_requested else None,
                    page_size=request.GET.get("page_size") if page_requested else None,
                )
            )
        except (OperationalError, ProgrammingError, DatabaseError) as exc:
            return _build_schema_not_ready_response(exc)

    if not request.user.has_perm("auth.upload_document"):
        return JsonResponse({"message": "无权限。"}, status=403)

    uploaded_file = request.FILES.get("file")
    title = (request.POST.get("title") or "").strip()
    source_date = (request.POST.get("source_date") or "").strip()
    if uploaded_file is None:
        safe_record_audit_event(
            actor=request.user,
            action="knowledgebase.document.upload",
            target_type="document",
            status=AuditRecord.STATUS_FAILED,
            detail_payload={
                **build_document_audit_payload(
                    title=title,
                    source_date=source_date,
                ),
                "error": "file 为必填项。",
            },
        )
        return JsonResponse({"message": "file 为必填项。"}, status=400)

    max_mb = _MAX_UPLOAD_BYTES // (1024 * 1024)
    if uploaded_file.size > _MAX_UPLOAD_BYTES:
        safe_record_audit_event(
            actor=request.user,
            action="knowledgebase.document.upload",
            target_type="document",
            target_id=uploaded_file.name,
            status=AuditRecord.STATUS_FAILED,
            detail_payload={
                **build_document_audit_payload(
                    title=title,
                    filename=uploaded_file.name,
                    doc_type=uploaded_file.content_type,
                    visibility=request.POST.get("visibility"),
                    source_date=source_date,
                    file_size=uploaded_file.size,
                ),
                "error": f"文件大小超出限制（最大 {max_mb} MB）。",
            },
        )
        return JsonResponse(
            {"message": f"文件大小超出限制（最大 {max_mb} MB）。"},
            status=413,
        )

    try:
        document = create_document_from_upload(
            uploaded_file=uploaded_file,
            title=title,
            source_date=source_date,
            uploaded_by=request.user,
            owner_id=request.POST.get("owner_id"),
            visibility=request.POST.get("visibility"),
            dataset_id=request.POST.get("dataset_id"),
        )
    except DuplicateDocumentError as exc:
        safe_record_audit_event(
            actor=request.user,
            action="knowledgebase.document.upload",
            target_type="document",
            target_id=uploaded_file.name,
            status=AuditRecord.STATUS_FAILED,
            detail_payload={
                **build_document_audit_payload(
                    title=title,
                    filename=uploaded_file.name,
                    doc_type=uploaded_file.content_type,
                    visibility=request.POST.get("visibility"),
                    source_date=source_date,
                    file_size=uploaded_file.size,
                ),
                "error": str(exc),
                "existing_document_id": exc.existing_document.get("id"),
            },
        )
        return JsonResponse(
            {"message": str(exc), "existing_document": exc.existing_document},
            status=409,
        )
    except ValueError as exc:
        safe_record_audit_event(
            actor=request.user,
            action="knowledgebase.document.upload",
            target_type="document",
            target_id=uploaded_file.name,
            status=AuditRecord.STATUS_FAILED,
            detail_payload={
                **build_document_audit_payload(
                    title=title,
                    filename=uploaded_file.name,
                    doc_type=uploaded_file.content_type,
                    visibility=request.POST.get("visibility"),
                    source_date=source_date,
                    file_size=uploaded_file.size,
                ),
                "error": str(exc),
            },
        )
        return JsonResponse({"message": str(exc)}, status=400)

    safe_record_audit_event(
        actor=request.user,
        action="knowledgebase.document.upload",
        target_type="document",
        target_id=document.id,
        status=AuditRecord.STATUS_SUCCEEDED,
        detail_payload=build_document_audit_payload(document=document),
    )
    return JsonResponse(build_document_response(document), status=201)


@csrf_exempt
@require_http_methods(["GET", "DELETE"])
@permission_required("auth.view_document")
def document_detail_view(request, document_id):
    """
    文档详情/删除端点 —— GET/DELETE documents/{document_id}。

    类比 SpringBoot: 相当于
        @RequestMapping(value="/documents/{documentId}", method={GET, DELETE})
        @PreAuthorize("hasAuthority('auth.view_document')")
        public ResponseEntity<?> getOrDelete(@PathVariable Long documentId)

    GET:    返回文档完整详情（含内容预览，原始文本截取前 2000 字符）。
    DELETE: 删除文档及其关联的向量数据库条目（需额外具备 auth.delete_document 权限）。

    参数:
        request:     Django HttpRequest 对象
        document_id: URL 路径中的文档 ID

    返回:
        GET    -> 200: 文档详情 JSON
        DELETE -> 200: {"message": "文档已删除。"}
        文档不存在 -> 404
        无删除权限 -> 403
        数据库未就绪 -> 503
    """
    try:
        document = get_document_for_user(request.user, document_id)
    except Document.DoesNotExist:
        if request.method == "DELETE":
            safe_record_audit_event(
                actor=request.user,
                action="knowledgebase.document.delete",
                target_type="document",
                target_id=document_id,
                status=AuditRecord.STATUS_FAILED,
                detail_payload={"error": "文档不存在。"},
            )
        return JsonResponse({"message": "文档不存在。"}, status=404)
    except (OperationalError, ProgrammingError, DatabaseError) as exc:
        return _build_schema_not_ready_response(exc)

    if request.method == "DELETE":
        if not request.user.has_perm("auth.delete_document"):
            return JsonResponse({"message": "无权限。"}, status=403)
        try:
            document_payload = build_document_audit_payload(document=document)
            delete_document_with_vectors(document)
            safe_record_audit_event(
                actor=request.user,
                action="knowledgebase.document.delete",
                target_type="document",
                target_id=document_id,
                status=AuditRecord.STATUS_SUCCEEDED,
                detail_payload=document_payload,
            )
            return JsonResponse({"message": "文档已删除。"})
        except (OperationalError, ProgrammingError, DatabaseError) as exc:
            return _build_schema_not_ready_response(exc)

    try:
        return JsonResponse(
            build_document_response(document, include_content_preview=True)
        )
    except (OperationalError, ProgrammingError, DatabaseError) as exc:
        return _build_schema_not_ready_response(exc)


@require_GET
@permission_required("auth.view_document")
def document_stats_view(request):
    """
    文档统计端点 —— GET documents/stats。

    类比 SpringBoot: 相当于
        @GetMapping("/documents/stats")
        @PreAuthorize("hasAuthority('auth.view_document')")

    返回当前用户可见文档的汇总统计数据，包括按状态、时间、数据集等维度的分布。

    参数:
        request: Django HttpRequest 对象

    返回:
        JsonResponse: 包含多维度统计数据的 JSON 响应。
    """
    try:
        return JsonResponse(build_stats_response(request.user))
    except (OperationalError, ProgrammingError, DatabaseError) as exc:
        return _build_schema_not_ready_response(exc)
