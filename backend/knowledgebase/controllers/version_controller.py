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
