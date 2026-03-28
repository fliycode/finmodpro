from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from knowledgebase.models import Document
from knowledgebase.services.document_service import build_document_response, ingest_document
from rbac.services.authz_service import permission_required


@csrf_exempt
@require_POST
@permission_required("auth.trigger_ingest")
def document_ingest_view(request, document_id):
    try:
        document = Document.objects.get(id=document_id)
    except Document.DoesNotExist:
        return JsonResponse({"message": "文档不存在。"}, status=404)

    try:
        document = ingest_document(document)
    except ValueError as exc:
        return JsonResponse({"message": str(exc)}, status=400)

    return JsonResponse(
        build_document_response(
            document,
            include_content_preview=True,
            message="摄取完成。",
        )
    )
