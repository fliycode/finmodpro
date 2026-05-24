"""
llm 应用的 URL 路由配置（类比 SpringBoot 中 @RequestMapping 的组合定义）。
该文件集中管理所有 LLM 相关的 REST API 端点：
- Gateway 分析（概览、日志、追踪、错误、成本）
- 控制台（总览、可观测性、知识库）
- 评测
- 微调（服务器管理、运行记录、回调、导出、派发）
- 模型配置（CRUD、激活、连接测试）
- Prompt 配置（列表、更新）

每个 path 调用定义了一个 URL 模式与对应视图类的映射关系。
"""
from django.urls import path

from llm.controllers.console_controller import (
    LlmConsoleKnowledgeView,
    LlmConsoleObservabilityView,
    LlmConsoleSummaryView,
)
from llm.controllers.fine_tune_controller import (
    FineTuneRunCallbackView,
    FineTuneRunnerServerDetailView,
    FineTuneRunnerServerListCreateView,
    FineTuneRunDispatchView,
    FineTuneRunDetailView,
    FineTuneRunExportDetailView,
    FineTuneRunListCreateView,
    FineTuneRunRunnerSpecView,
)
from llm.controllers.evaluation_controller import EvalRecordListCreateView
from llm.controllers.gateway_controller import (
    GatewayCostsModelsView,
    GatewayCostsSummaryView,
    GatewayCostsTimeseriesView,
    GatewayErrorsView,
    GatewayLogsSummaryView,
    GatewayLogsView,
    GatewaySummaryView,
    GatewayTraceView,
)
from llm.controllers.model_config_controller import (
    ModelConfigActivationView,
    ModelConfigConnectionTestView,
    ModelConfigDetailView,
    ModelConfigListView,
)
from llm.controllers.prompt_config_controller import PromptConfigListView, PromptConfigUpdateView


urlpatterns = [
    # Gateway analytics - 网关分析
    path("llm/gateway/summary", GatewaySummaryView.as_view(), name="gateway-summary-legacy"),
    path("llm/gateway/summary/", GatewaySummaryView.as_view(), name="gateway-summary"),
    path("llm/gateway/logs/summary", GatewayLogsSummaryView.as_view(), name="gateway-logs-summary-legacy"),
    path("llm/gateway/logs/summary/", GatewayLogsSummaryView.as_view(), name="gateway-logs-summary"),
    path("llm/gateway/logs", GatewayLogsView.as_view(), name="gateway-logs-legacy"),
    path("llm/gateway/logs/", GatewayLogsView.as_view(), name="gateway-logs"),
    path("llm/gateway/traces/<str:trace_id>", GatewayTraceView.as_view(), name="gateway-trace-legacy"),
    path("llm/gateway/traces/<str:trace_id>/", GatewayTraceView.as_view(), name="gateway-trace"),
    path("llm/gateway/errors", GatewayErrorsView.as_view(), name="gateway-errors-legacy"),
    path("llm/gateway/errors/", GatewayErrorsView.as_view(), name="gateway-errors"),
    path("llm/gateway/costs/summary", GatewayCostsSummaryView.as_view(), name="gateway-costs-summary-legacy"),
    path("llm/gateway/costs/summary/", GatewayCostsSummaryView.as_view(), name="gateway-costs-summary"),
    path("llm/gateway/costs/timeseries", GatewayCostsTimeseriesView.as_view(), name="gateway-costs-timeseries-legacy"),
    path("llm/gateway/costs/timeseries/", GatewayCostsTimeseriesView.as_view(), name="gateway-costs-timeseries"),
    path("llm/gateway/costs/models", GatewayCostsModelsView.as_view(), name="gateway-costs-models-legacy"),
    path("llm/gateway/costs/models/", GatewayCostsModelsView.as_view(), name="gateway-costs-models"),
    # Console - LLM 控制台
    path("llm/summary", LlmConsoleSummaryView.as_view(), name="llm-console-summary-legacy"),
    path("llm/summary/", LlmConsoleSummaryView.as_view(), name="llm-console-summary"),
    path("llm/observability", LlmConsoleObservabilityView.as_view(), name="llm-console-observability-legacy"),
    path("llm/observability/", LlmConsoleObservabilityView.as_view(), name="llm-console-observability"),
    path("llm/knowledge", LlmConsoleKnowledgeView.as_view(), name="llm-console-knowledge-legacy"),
    path("llm/knowledge/", LlmConsoleKnowledgeView.as_view(), name="llm-console-knowledge"),
    # Evaluations - 评测
    path("evaluations", EvalRecordListCreateView.as_view(), name="evaluation-list-create-legacy"),
    path("evaluations/", EvalRecordListCreateView.as_view(), name="evaluation-list-create"),
    # Fine-tune runner servers - 微调训练服务器管理
    path("fine-tune-servers", FineTuneRunnerServerListCreateView.as_view(), name="fine-tune-server-list-create-legacy"),
    path("fine-tune-servers/", FineTuneRunnerServerListCreateView.as_view(), name="fine-tune-server-list-create"),
    path("fine-tune-servers/<int:runner_server_id>", FineTuneRunnerServerDetailView.as_view(), name="fine-tune-server-detail-legacy"),
    path("fine-tune-servers/<int:runner_server_id>/", FineTuneRunnerServerDetailView.as_view(), name="fine-tune-server-detail"),
    # Fine-tune runs - 微调运行记录管理
    path("fine-tunes", FineTuneRunListCreateView.as_view(), name="fine-tune-list-create-legacy"),
    path("fine-tunes/", FineTuneRunListCreateView.as_view(), name="fine-tune-list-create"),
    path("fine-tunes/<int:fine_tune_run_id>", FineTuneRunDetailView.as_view(), name="fine-tune-detail-legacy"),
    path("fine-tunes/<int:fine_tune_run_id>/", FineTuneRunDetailView.as_view(), name="fine-tune-detail"),
    path("fine-tunes/<int:fine_tune_run_id>/callback", FineTuneRunCallbackView.as_view(), name="fine-tune-callback-legacy"),
    path("fine-tunes/<int:fine_tune_run_id>/callback/", FineTuneRunCallbackView.as_view(), name="fine-tune-callback"),
    path("fine-tunes/<int:fine_tune_run_id>/export", FineTuneRunExportDetailView.as_view(), name="fine-tune-export-detail-legacy"),
    path("fine-tunes/<int:fine_tune_run_id>/export/", FineTuneRunExportDetailView.as_view(), name="fine-tune-export-detail"),
    path("fine-tunes/<int:fine_tune_run_id>/runner-spec", FineTuneRunRunnerSpecView.as_view(), name="fine-tune-runner-spec-legacy"),
    path("fine-tunes/<int:fine_tune_run_id>/runner-spec/", FineTuneRunRunnerSpecView.as_view(), name="fine-tune-runner-spec"),
    path("fine-tunes/<int:fine_tune_run_id>/dispatch", FineTuneRunDispatchView.as_view(), name="fine-tune-dispatch-legacy"),
    path("fine-tunes/<int:fine_tune_run_id>/dispatch/", FineTuneRunDispatchView.as_view(), name="fine-tune-dispatch"),
    # Model configs - 模型配置管理
    path("model-configs/test-connection", ModelConfigConnectionTestView.as_view(), name="model-config-test-connection-legacy"),
    path("model-configs/test-connection/", ModelConfigConnectionTestView.as_view(), name="model-config-test-connection"),
    path("model-configs/<int:model_config_id>", ModelConfigDetailView.as_view(), name="model-config-detail-legacy"),
    path("model-configs/<int:model_config_id>/", ModelConfigDetailView.as_view(), name="model-config-detail"),
    path("model-configs/<int:model_config_id>/activation", ModelConfigActivationView.as_view(), name="model-config-activation-legacy"),
    path("model-configs/<int:model_config_id>/activation/", ModelConfigActivationView.as_view(), name="model-config-activation"),
    # Prompt configs - Prompt 模板配置管理
    path("prompt-configs/<path:key>", PromptConfigUpdateView.as_view(), name="prompt-config-update-legacy"),
    path("prompt-configs/<path:key>/", PromptConfigUpdateView.as_view(), name="prompt-config-update"),
    path("prompt-configs", PromptConfigListView.as_view(), name="prompt-config-list-legacy"),
    path("prompt-configs/", PromptConfigListView.as_view(), name="prompt-config-list"),
    path("model-configs", ModelConfigListView.as_view(), name="model-config-list-legacy"),
    path("model-configs/", ModelConfigListView.as_view(), name="model-config-list"),
]
