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
    try:
        return JsonResponse(build_stats_response(request.user))
    except (OperationalError, ProgrammingError, DatabaseError) as exc:
        return _build_schema_not_ready_response(exc)
