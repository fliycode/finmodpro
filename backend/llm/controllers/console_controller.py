from rest_framework.views import APIView

from common.api_response import success_response
from llm.controllers.model_config_controller import _require_manage_permission
from llm.services.console_query_service import (
    build_llm_console_summary,
    build_llm_knowledge_summary,
    build_llm_observability_summary,
)


class LlmConsoleSummaryView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error
        return success_response(data=build_llm_console_summary())


class LlmConsoleObservabilityView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error
        return success_response(data=build_llm_observability_summary())


class LlmConsoleKnowledgeView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error
        return success_response(data=build_llm_knowledge_summary())
