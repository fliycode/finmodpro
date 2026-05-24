"""
文档版本管理控制器。

类比 SpringBoot: 相当于 @RestController 中处理文档版本资源的核心端点。
支持两种操作：
- GET:  查询文档的所有历史版本列表
- POST: 为现有文档上传一个新版本（创建 Document + DocumentVersion 关联记录）

文档版本是基于同一逻辑文档的上传历史管理机制：每个新版本创建一个独立的
Document 实例，通过 DocumentVersion 表的 root_document 外键将其与原始文档
关联起来，is_current 标记最新版本。
"""
from django.conf import settings
from django.db import DatabaseError, OperationalError, ProgrammingError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from knowledgebase.controllers.audit_utils import (
    build_document_version_audit_payload,
    safe_record_audit_event,
)
from knowledgebase.models import Document
from knowledgebase.services.document_service import build_document_response, get_document_for_user
from knowledgebase.services.version_service import (
    build_document_versions_response,
    create_new_document_version,
    parse_source_metadata,
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
        JsonResponse: 状态码 503，包含中文错误提示。
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
def document_versions_view(request, document_id):
    """
    文档版本列表/上传端点 —— GET/POST documents/{document_id}/versions。

    类比 SpringBoot: 相当于
        @RequestMapping(value="/documents/{documentId}/versions", method={GET, POST})
        @PreAuthorize("hasAuthority('auth.view_document')")
        public ResponseEntity<?> handleVersions(@PathVariable Long documentId)

    GET:  返回文档所有历史版本的列表，包含每个版本的元数据摘要。
    POST: 为该文档上传一份新版本文件（需额外拥有 auth.upload_document 权限）。
          系统会自动：
          1. 创建新的 Document 实例
          2. 创建对应的 DocumentVersion 记录
          3. 将旧的 is_current 标记设为 False
          4. 新版本的 is_current 设为 True

          支持的字段（multipart/form-data）：
          - file:             文件本身（必填）
          - title:            版本标题
          - source_date:      来源日期
          - source_type:      来源类型
          - source_label:     来源标签
          - source_metadata:  来源元数据（JSON 字符串）
          - processing_notes: 处理备注

    参数:
        request:     Django HttpRequest 对象
        document_id: URL 路径中的根文档 ID

    返回:
        GET  -> 200: {"root_document": {...}, "versions": [...], "current_version": {...}}
        POST -> 201: 新版本 Document 详情 JSON（含 message: "新版本已上传。"）
        POST -> 400: 参数校验失败
        POST -> 413: 文件超出大小限制
        文档不存在 -> 404
        无上传权限 -> 403
        数据库未就绪 -> 503
    """
    try:
        document = get_document_for_user(request.user, document_id)
    except Document.DoesNotExist:
        if request.method == "POST":
            safe_record_audit_event(
                actor=request.user,
                action="knowledgebase.document_version.upload",
                target_type="document",
                target_id=document_id,
                status=AuditRecord.STATUS_FAILED,
                detail_payload={"error": "文档不存在。"},
            )
        return JsonResponse({"message": "文档不存在。"}, status=404)
    except (OperationalError, ProgrammingError, DatabaseError) as exc:
        return _build_schema_not_ready_response(exc)

    if request.method == "GET":
        try:
            return JsonResponse(build_document_versions_response(document))
        except (OperationalError, ProgrammingError, DatabaseError) as exc:
            return _build_schema_not_ready_response(exc)

    if not request.user.has_perm("auth.upload_document"):
        return JsonResponse({"message": "无权限。"}, status=403)

    uploaded_file = request.FILES.get("file")
    if uploaded_file is None:
        safe_record_audit_event(
            actor=request.user,
            action="knowledgebase.document_version.upload",
            target_type="document",
            target_id=document.id,
            status=AuditRecord.STATUS_FAILED,
            detail_payload={
                **build_document_version_audit_payload(root_document=document),
                "error": "file 为必填项。",
            },
        )
        return JsonResponse({"message": "file 为必填项。"}, status=400)

    max_mb = _MAX_UPLOAD_BYTES // (1024 * 1024)
    if uploaded_file.size > _MAX_UPLOAD_BYTES:
        safe_record_audit_event(
            actor=request.user,
            action="knowledgebase.document_version.upload",
            target_type="document",
            target_id=document.id,
            status=AuditRecord.STATUS_FAILED,
            detail_payload={
                **build_document_version_audit_payload(
                    root_document=document,
                    title=(request.POST.get("title") or "").strip(),
                    file_size=uploaded_file.size,
                    source_type=(request.POST.get("source_type") or "").strip(),
                    source_label=(request.POST.get("source_label") or "").strip(),
                ),
                "error": f"文件大小超出限制（最大 {max_mb} MB）。",
            },
        )
        return JsonResponse(
            {"message": f"文件大小超出限制（最大 {max_mb} MB）。"},
            status=413,
        )

    source_metadata = request.POST.get("source_metadata")
    try:
        new_document = create_new_document_version(
            document=document,
            uploaded_file=uploaded_file,
            uploaded_by=request.user,
            title=(request.POST.get("title") or "").strip(),
            source_date=(request.POST.get("source_date") or "").strip(),
            source_type=(request.POST.get("source_type") or "").strip(),
            source_label=(request.POST.get("source_label") or "").strip(),
            source_metadata=parse_source_metadata(source_metadata),
            processing_notes=(request.POST.get("processing_notes") or "").strip(),
        )
    except ValueError as exc:
        safe_record_audit_event(
            actor=request.user,
            action="knowledgebase.document_version.upload",
            target_type="document",
            target_id=document.id,
            status=AuditRecord.STATUS_FAILED,
            detail_payload={
                **build_document_version_audit_payload(
                    root_document=document,
                    title=(request.POST.get("title") or "").strip(),
                    file_size=uploaded_file.size,
                    source_type=(request.POST.get("source_type") or "").strip(),
                    source_label=(request.POST.get("source_label") or "").strip(),
                    source_metadata=source_metadata,
                    processing_notes=(request.POST.get("processing_notes") or "").strip(),
                ),
                "error": str(exc),
            },
        )
        return JsonResponse({"message": str(exc)}, status=400)
    except (OperationalError, ProgrammingError, DatabaseError) as exc:
        return _build_schema_not_ready_response(exc)

    safe_record_audit_event(
        actor=request.user,
        action="knowledgebase.document_version.upload",
        target_type="document",
        target_id=document.id,
        status=AuditRecord.STATUS_SUCCEEDED,
        detail_payload=build_document_version_audit_payload(
            root_document=document,
            new_document=new_document,
        ),
    )
    return JsonResponse(
        build_document_response(new_document, message="新版本已上传。"),
        status=201,
    )
