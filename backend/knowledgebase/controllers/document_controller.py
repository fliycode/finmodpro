from django.db import DatabaseError, OperationalError, ProgrammingError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from knowledgebase.models import Document
from knowledgebase.services.document_service import (
    build_document_list_response,
    build_document_response,
    create_document_from_upload,
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
        return JsonResponse({"message": "file 为必填项。"}, status=400)

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
    except ValueError as exc:
        return JsonResponse({"message": str(exc)}, status=400)

    return JsonResponse(build_document_response(document), status=201)


@require_GET
@permission_required("auth.view_document")
def document_detail_view(request, document_id):
    try:
        document = get_document_for_user(request.user, document_id)
    except Document.DoesNotExist:
        return JsonResponse({"message": "文档不存在。"}, status=404)
    except (OperationalError, ProgrammingError, DatabaseError) as exc:
        return _build_schema_not_ready_response(exc)

    try:
        return JsonResponse(
            build_document_response(document, include_content_preview=True)
        )
    except (OperationalError, ProgrammingError, DatabaseError) as exc:
        return _build_schema_not_ready_response(exc)
