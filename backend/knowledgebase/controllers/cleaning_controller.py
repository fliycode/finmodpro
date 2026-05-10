import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from knowledgebase.models import Document, DocumentCleaningResult
from knowledgebase.services.cleaning_engine_service import clean_document
from knowledgebase.services.cleaning_quality_service import serialize_cleaning_result
from rbac.services.authz_service import permission_required


@csrf_exempt
@require_http_methods(["GET", "POST"])
@permission_required("auth.view_document")
def document_cleaning_view(request, document_id):
    try:
        document = Document.objects.get(id=document_id)
    except Document.DoesNotExist:
        return JsonResponse({"message": "文档不存在。"}, status=404)

    if request.method == "GET":
        results = DocumentCleaningResult.objects.filter(document=document)
        return JsonResponse({
            "results": [serialize_cleaning_result(r) for r in results],
            "total": results.count(),
        })

    if not request.user.has_perm("auth.trigger_cleaning"):
        return JsonResponse({"message": "无权限。"}, status=403)

    try:
        result = clean_document(document=document)
    except Exception as exc:
        return JsonResponse({"message": f"清洗失败: {exc}"}, status=500)

    return JsonResponse({"result": serialize_cleaning_result(result)}, status=201)
