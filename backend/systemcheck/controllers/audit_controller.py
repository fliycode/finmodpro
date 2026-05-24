"""
审计日志控制器 —— 提供审计日志的分页查询接口。

类比 SpringBoot: 相当于 @RestController 中的审计日志查询端点，
GET /api/systemcheck/audits 支持分页、搜索和按状态/操作过滤。
"""

from django.core.paginator import Paginator
from django.db import DatabaseError, OperationalError, ProgrammingError
from rest_framework.views import APIView

from common.api_response import error_response, success_response
from rbac.services.authz_service import get_authenticated_user, user_has_permission
from systemcheck.models import AuditRecord
from systemcheck.services.audit_service import serialize_audit_record


def _build_schema_not_ready_response(exc):
    """
    构建"数据库表未初始化"的统一错误响应。

    类比 SpringBoot: 相当于 @ControllerAdvice 中的 @ExceptionHandler，
    当数据库表尚未创建（迁移未执行）时返回友好的 503 提示。

    参数:
        exc: 捕获到的数据库异常对象。

    返回:
        JsonResponse: 状态码 503，提示执行迁移。
    """
    return error_response(
        code=503,
        message="系统审计数据表尚未初始化，请先执行后端迁移。",
        data={"detail": str(exc)},
        status_code=503,
    )


class AuditLogListView(APIView):
    """
    审计日志列表视图 —— GET /api/systemcheck/audits

    支持分页、搜索（按操作者或操作名称）和按状态/操作类型过滤。

    类比 SpringBoot: 相当于 @GetMapping("/audits") + @PreAuthorize("hasAuthority('auth.view_audit_log')")。
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """
        获取分页的审计日志列表。

        参数:
            request: Django HttpRequest，查询参数支持:
                     - page   (int, 可选, 默认 1): 页码
                     - page_size (int, 可选, 默认 25, 最大 100): 每页数量
                     - search (str, 可选): 模糊搜索操作者用户名或操作名称
                     - status (str, 可选): 按操作状态过滤
                     - action (str, 可选): 按操作名称过滤

        返回:
            JsonResponse: {total, page, page_size, results: [...]}
                         未认证: 401, 无权限: 403, 数据库未就绪: 503
        """
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.view_audit_log"):
            return error_response(code=403, message="无权限。", status_code=403)

        page = int(request.query_params.get("page", 1))
        page_size = min(max(int(request.query_params.get("page_size", 25)), 1), 100)
        search = (request.query_params.get("search", "") or "").strip()
        status_filter = (request.query_params.get("status", "") or "").strip()
        action_filter = (request.query_params.get("action", "") or "").strip()

        try:
            qs = AuditRecord.objects.select_related("actor").order_by("-created_at", "-id")

            if search:
                qs = qs.filter(actor__username__icontains=search) | qs.filter(action__icontains=search)
            if status_filter:
                qs = qs.filter(status=status_filter)
            if action_filter:
                qs = qs.filter(action=action_filter)

            paginator = Paginator(qs, page_size)
            page_obj = paginator.get_page(page)

            return success_response(
                data={
                    "total": paginator.count,
                    "page": page,
                    "page_size": page_size,
                    "results": [serialize_audit_record(r) for r in page_obj.object_list],
                }
            )
        except (OperationalError, ProgrammingError, DatabaseError) as exc:
            return _build_schema_not_ready_response(exc)
