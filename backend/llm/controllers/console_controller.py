"""
LLM 控制台视图控制器（类比 SpringBoot 中 @RestController 类）。
提供三个概览端点：
- LlmConsoleSummaryView: 总览页（供应商状态、活跃模型、最近活动、快捷链接）
- LlmConsoleObservabilityView: 可观测性页（24 小时内请求统计、失败详情）
- LlmConsoleKnowledgeView: 知识库页（解析器能力、摄入队列统计）
"""
from rest_framework.views import APIView

from common.api_response import success_response
from llm.controllers.model_config_controller import _require_manage_permission
from llm.services.console_query_service import (
    build_llm_console_summary,
    build_llm_knowledge_summary,
    build_llm_observability_summary,
)


class LlmConsoleSummaryView(APIView):
    """LLM 控制台总览视图。

    GET /api/llm/summary/ — 返回供应商连接状态、活跃模型、最近活动和快捷链接。
    需要 auth.manage_model_config 权限。
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """获取 LLM 控制台总览数据。

        参数:
            request: Django REST Framework 的 Request 对象，携带认证信息。
        返回:
            JSON 响应，包含 providers, active_models, recent_activity, quick_links 等概览信息。
        """
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error
        return success_response(data=build_llm_console_summary())


class LlmConsoleObservabilityView(APIView):
    """LLM 可观测性视图。

    GET /api/llm/observability/ — 返回 24 小时内的对话请求统计、检索命中、平均延迟和失败详情。
    需要 auth.manage_model_config 权限。
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """获取 LLM 可观测性数据。

        参数:
            request: Django REST Framework 的 Request 对象。
        返回:
            JSON 响应，包含 overview（请求量/命中/延迟）和 recent_failures（最近失败详情）。
        """
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error
        return success_response(data=build_llm_observability_summary())


class LlmConsoleKnowledgeView(APIView):
    """LLM 知识库视图。

    GET /api/llm/knowledge/ — 返回文档解析器能力、摄入队列各状态计数和最近失败详情。
    需要 auth.manage_model_config 权限。
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """获取 LLM 知识库状态数据。

        参数:
            request: Django REST Framework 的 Request 对象。
        返回:
            JSON 响应，包含 parser_capabilities（解析器能力）、ingestion_summary（摄入统计）、pipeline_steps 等。
        """
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error
        return success_response(data=build_llm_knowledge_summary())
