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


@csrf_exempt
@require_http_methods(["GET", "POST"])
@permission_required("auth.view_document")
def document_list_create_view(request):
    if request.method == "GET":
        return JsonResponse(build_document_list_response(request.user))

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

    return JsonResponse(
        build_document_response(document, include_content_preview=True)
    )
