from django.core.paginator import Paginator
from django.db import DatabaseError, OperationalError, ProgrammingError
from rest_framework.views import APIView

from common.api_response import error_response, success_response
from rbac.services.authz_service import get_authenticated_user, user_has_permission
from systemcheck.models import AuditRecord
from systemcheck.services.audit_service import serialize_audit_record


def _build_schema_not_ready_response(exc):
    return error_response(
        code=503,
        message="系统审计数据表尚未初始化，请先执行后端迁移。",
        data={"detail": str(exc)},
        status_code=503,
    )


class AuditLogListView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
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
