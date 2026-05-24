"""
Prompt 模板配置控制器（类比 SpringBoot 中 @RestController）。
提供 Prompt 模板的列表查询（GET）和内容更新（PATCH）。
Prompt 模板以 .txt 文件形式存储在文件系统中，通过 key 路径来索引。
"""
from rest_framework.views import APIView

from common.api_response import error_response, success_response
from llm.serializers import PromptConfigSummarySerializer, PromptConfigUpdateSerializer
from llm.services.prompt_command_service import update_prompt_config
from llm.services.prompt_query_service import list_prompt_configs
from rbac.services.authz_service import get_authenticated_user, user_has_permission
from systemcheck.models import AuditRecord
from systemcheck.services.audit_service import record_audit_event


class PromptConfigListView(APIView):
    """Prompt 模板配置列表视图。

    GET /api/prompt-configs/ — 返回所有 Prompt 模板文件的配置列表。
    需要 auth.manage_model_config 权限。
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """列出所有 Prompt 模板配置。

        参数:
            request: Django REST Framework 的 Request 对象。
        返回:
            JSON 响应，包含 total（总数）和 prompt_configs（模板列表，含 key、category、variables 等）。
        """
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.manage_model_config"):
            return error_response(code=403, message="无权限。", status_code=403)

        prompt_configs = list_prompt_configs()
        return success_response(
            data={
                "total": len(prompt_configs),
                "prompt_configs": PromptConfigSummarySerializer(prompt_configs, many=True).data,
            }
        )


class PromptConfigUpdateView(APIView):
    """Prompt 模板配置更新视图。

    PATCH /api/prompt-configs/<key>/ — 更新指定 key 对应模板文件的内容。
    需要 auth.manage_model_config 权限。
    """
    authentication_classes = []
    permission_classes = []

    def patch(self, request, key):
        """更新指定 Prompt 模板的内容。

        参数:
            request: Django REST Framework 的 Request 对象，body 中包含 template（新模板内容）。
            key: URL 路径参数，指向要更新的 Prompt 模板文件路径。
        返回:
            JSON 响应，包含更新后的 prompt_config 对象。
            若 key 非法则返回 400，模板文件不存在则返回 404。
        """
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.manage_model_config"):
            return error_response(code=403, message="无权限。", status_code=403)

        serializer = PromptConfigUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            prompt_config = update_prompt_config(
                key=key,
                template=serializer.validated_data["template"],
            )
        except ValueError:
            record_audit_event(
                actor=user,
                action="llm.prompt_config.update",
                target_type="prompt_config",
                target_id=key,
                status=AuditRecord.STATUS_FAILED,
                detail_payload={"error": "非法的 prompt key。"},
            )
            return error_response(code=400, message="非法的 prompt key。", status_code=400)
        except FileNotFoundError:
            record_audit_event(
                actor=user,
                action="llm.prompt_config.update",
                target_type="prompt_config",
                target_id=key,
                status=AuditRecord.STATUS_FAILED,
                detail_payload={"error": "Prompt 模板不存在。"},
            )
            return error_response(code=404, message="Prompt 模板不存在。", status_code=404)

        record_audit_event(
            actor=user,
            action="llm.prompt_config.update",
            target_type="prompt_config",
            target_id=key,
            status=AuditRecord.STATUS_SUCCEEDED,
            detail_payload={
                "category": prompt_config["category"],
                "variable_names": prompt_config["variables"],
                "template_length": len(serializer.validated_data["template"]),
            },
        )
        return success_response(
            data={"prompt_config": PromptConfigSummarySerializer(prompt_config).data}
        )
