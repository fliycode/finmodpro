from rest_framework.views import APIView

from common.api_response import error_response, success_response
from llm.serializers import EvalRecordCreateSerializer, EvalRecordSummarySerializer
from llm.services.evaluation_service import (
    build_evaluation_comparison_groups,
    list_eval_records,
    run_basic_evaluation,
)
from rbac.services.authz_service import get_authenticated_user, user_has_permission
from systemcheck.models import AuditRecord
from systemcheck.services.audit_service import record_audit_event


class EvalRecordListCreateView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.view_evaluation"):
            return error_response(code=403, message="无权限。", status_code=403)

        eval_records = list_eval_records()
        serialized_records = EvalRecordSummarySerializer(eval_records, many=True).data
        return success_response(
            data={
                "total": eval_records.count(),
                "eval_records": serialized_records,
                "comparison_groups": build_evaluation_comparison_groups(eval_records),
            }
        )

    def post(self, request):
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.run_evaluation"):
            return error_response(code=403, message="无权限。", status_code=403)

        serializer = EvalRecordCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            eval_record = run_basic_evaluation(**serializer.validated_data)
        except ValueError:
            record_audit_event(
                actor=user,
                action="llm.evaluation.run",
                target_type="evaluation",
                target_id=serializer.validated_data.get("model_config_id") or "",
                status=AuditRecord.STATUS_FAILED,
                detail_payload={
                    "task_type": serializer.validated_data["task_type"],
                    "evaluation_mode": serializer.validated_data.get("evaluation_mode", ""),
                    "dataset_name": serializer.validated_data.get("dataset_name", ""),
                    "dataset_version": serializer.validated_data.get("dataset_version", ""),
                    "version": serializer.validated_data.get("version", ""),
                    "error": "模型配置不存在。",
                },
            )
            return error_response(code=404, message="模型配置不存在。", status_code=404)

        record_audit_event(
            actor=user,
            action="llm.evaluation.run",
            target_type="evaluation",
            target_id=eval_record.id,
            status=AuditRecord.STATUS_SUCCEEDED,
            detail_payload={
                "task_type": eval_record.task_type,
                "evaluation_mode": eval_record.evaluation_mode,
                "target_name": eval_record.target_name,
                "model_config_id": eval_record.model_config_id or "",
                "dataset_name": eval_record.dataset_name,
                "dataset_version": eval_record.dataset_version,
                "version": eval_record.version,
            },
        )
        return success_response(
            data={"eval_record": EvalRecordSummarySerializer(eval_record).data},
            status_code=201,
        )
