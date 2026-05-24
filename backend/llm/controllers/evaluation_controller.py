"""
评测控制器（类比 SpringBoot 中 @RestController）。
提供评测记录的列表查询（GET）和创建/运行（POST）。
评测是对模型在 QA 问答和风险抽取任务上的准确性、延迟等指标的自动化测量。
"""
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
    """评测记录列表与创建视图。

    GET  /api/evaluations/ — 列出所有评测记录及对比分组。
    POST /api/evaluations/ — 运行一次评测并记录结果。
    需要 auth.view_evaluation（GET）或 auth.run_evaluation（POST）权限。
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """列出所有评测记录及对比分组。

        参数:
            request: Django REST Framework 的 Request 对象。
        返回:
            JSON 响应，包含 total（总数）、eval_records（记录列表）、comparison_groups（按评测模式分组对比）。
        """
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
        """运行一次评测并创建记录。

        参数:
            request: Django REST Framework 的 Request 对象，body 中包含 task_type（任务类型）、
                     model_config_id（模型配置 ID）、evaluation_mode（评测模式）等。
        返回:
            201 Created JSON 响应，包含新创建的 EvalRecord。若模型配置不存在则返回 404。
        """
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
