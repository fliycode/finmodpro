"""
数据集管理控制器。

类比 SpringBoot: 相当于 @RestController 中处理数据集 CRUD 的端点。
提供数据集的列表查询和详情查看功能。
"""
import json

from django.db import DatabaseError, OperationalError, ProgrammingError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from knowledgebase.controllers.audit_utils import (
    build_dataset_audit_payload,
    safe_record_audit_event,
)
from knowledgebase.models import Dataset
from knowledgebase.services.dataset_service import (
    create_dataset,
    get_dataset,
    list_datasets,
    serialize_dataset,
)
from rbac.services.authz_service import permission_required
from systemcheck.models import AuditRecord


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


@csrf_exempt
@require_http_methods(["GET", "POST"])
@permission_required("auth.view_document")
def dataset_list_create_view(request):
    """
    数据集列表/创建端点 —— GET/POST datasets。

    类比 SpringBoot: 相当于
        @RequestMapping(value="/datasets", method={GET, POST})
        @PreAuthorize("hasAuthority('auth.view_document')")
        public ResponseEntity<?> listOrCreate()

    GET:  返回所有数据集列表。
    POST: 创建新数据集（需额外拥有 auth.upload_document 权限）。

    参数:
        request: Django HttpRequest 对象，POST 时 body 需包含 name 和 description。

    返回:
        GET  -> 200: {"datasets": [...], "total": N}
        POST -> 201: {"dataset": {...}}  (创建成功)
        POST -> 400: {"message": str(exc)}  (参数校验失败)
        无权限 -> 403
        数据库未就绪 -> 503
    """
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
        safe_record_audit_event(
            actor=request.user,
            action="knowledgebase.dataset.create",
            target_type="dataset",
            status=AuditRecord.STATUS_FAILED,
            detail_payload={
                **build_dataset_audit_payload(
                    name=payload.get("name", ""),
                    description=payload.get("description", ""),
                    owner=request.user,
                ),
                "error": str(exc),
            },
        )
        return JsonResponse({"message": str(exc)}, status=400)
    safe_record_audit_event(
        actor=request.user,
        action="knowledgebase.dataset.create",
        target_type="dataset",
        target_id=dataset.id,
        status=AuditRecord.STATUS_SUCCEEDED,
        detail_payload=build_dataset_audit_payload(dataset=dataset),
    )
    return JsonResponse({"dataset": serialize_dataset(dataset)}, status=201)


@require_GET
@permission_required("auth.view_document")
def dataset_detail_view(request, dataset_id):
    """
    数据集详情端点 —— GET datasets/{dataset_id}。

    类比 SpringBoot: 相当于
        @GetMapping("/datasets/{datasetId}")
        @PreAuthorize("hasAuthority('auth.view_document')")

    返回单个数据集的详细信息，包括其包含的文档统计。

    参数:
        request:    Django HttpRequest 对象
        dataset_id: URL 路径中的数据集 ID

    返回:
        200: {"dataset": {...}}  包含数据集详情及文档统计
        404: {"message": "数据集不存在。"}
        503: 数据库未就绪
    """
    try:
        dataset = get_dataset(dataset_id)
    except Dataset.DoesNotExist:
        return JsonResponse({"message": "数据集不存在。"}, status=404)
    except (OperationalError, ProgrammingError, DatabaseError) as exc:
        return _build_schema_not_ready_response(exc)

    return JsonResponse({"dataset": serialize_dataset(dataset)})
