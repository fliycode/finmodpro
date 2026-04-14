from django.db import DatabaseError, OperationalError, ProgrammingError
from rest_framework.views import APIView

from common.api_response import error_response, success_response
from rbac.services.authz_service import get_authenticated_user, user_has_permission
from systemcheck.models import AuditRecord
from systemcheck.services.audit_service import list_audit_records


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

        try:
            limit = int(request.query_params.get("limit", 10))
        except (TypeError, ValueError):
            limit = 10
        limit = min(max(limit, 1), 50)

        try:
            audits = list_audit_records(limit=limit)
            return success_response(
                data={
                    "total": AuditRecord.objects.count(),
                    "audits": audits,
                }
            )
        except (OperationalError, ProgrammingError, DatabaseError) as exc:
            return _build_schema_not_ready_response(exc)
