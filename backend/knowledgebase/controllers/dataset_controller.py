import json

from django.db import DatabaseError, OperationalError, ProgrammingError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from knowledgebase.models import Dataset
from knowledgebase.services.dataset_service import (
    create_dataset,
    get_dataset,
    list_datasets,
    serialize_dataset,
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
def dataset_list_create_view(request):
    if request.method == "GET":
        try:
            datasets = list_datasets()
        except (OperationalError, ProgrammingError, DatabaseError) as exc:
            return _build_schema_not_ready_response(exc)
        return JsonResponse({"datasets": datasets, "total": len(datasets)})

    if not request.user.has_perm("auth.upload_document"):
        return JsonResponse({"message": "无权限。"}, status=403)

    payload = json.loads(request.body or "{}")
    try:
        dataset = create_dataset(
            name=payload.get("name", ""),
            description=payload.get("description", ""),
            owner=request.user,
        )
    except ValueError as exc:
        return JsonResponse({"message": str(exc)}, status=400)
    return JsonResponse({"dataset": serialize_dataset(dataset)}, status=201)


@require_GET
@permission_required("auth.view_document")
def dataset_detail_view(request, dataset_id):
    try:
        dataset = get_dataset(dataset_id)
    except Dataset.DoesNotExist:
        return JsonResponse({"message": "数据集不存在。"}, status=404)
    except (OperationalError, ProgrammingError, DatabaseError) as exc:
        return _build_schema_not_ready_response(exc)

    return JsonResponse({"dataset": serialize_dataset(dataset)})
