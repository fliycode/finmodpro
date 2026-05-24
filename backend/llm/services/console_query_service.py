"""
控制台查询服务（类比 SpringBoot 中 @Service 的查询层）。
该模块负责组装 LLM 管理控制台的三个概览页面数据：
- 总览（供应商状态、活跃模型、最近活动）
- 可观测性（对话统计、检索命中、失败详情）
- 知识库（解析器能力、摄入队列状态）
"""
from collections import Counter
from datetime import timedelta

from django.db.models import Avg
from django.utils import timezone

from common.exceptions import ModelNotConfiguredError
from knowledgebase.models import Document, IngestionTask
from llm.models import FineTuneRun, ModelConfig
from llm.services.model_config_service import get_active_model_config
from rag.models import RetrievalLog

# 供应商标签映射
_PROVIDER_LABELS = {
    ModelConfig.PROVIDER_DEEPSEEK: "DeepSeek",
    ModelConfig.PROVIDER_DASHSCOPE: "DashScope",
    ModelConfig.PROVIDER_OLLAMA: "Ollama",
    ModelConfig.PROVIDER_OPENAI_COMPATIBLE: "OpenAI Compatible",
}


def _build_provider_status():
    """构建各 LLM 供应商及辅助服务的连接状态列表。

    返回:
        list[dict]，每个元素包含 key、label、status（connected/configured/missing/idle）和 active_count。
        也包含非 LLM 供应商的辅助组件：pymupdf4llm（文档解析）和 llamafactory（微调框架）。
    """
    all_configs = list(ModelConfig.objects.exclude(provider=ModelConfig.PROVIDER_LITELLM))
    active_configs = [config for config in all_configs if config.is_active]
    configured_by_provider = Counter(config.provider for config in all_configs)
    active_by_provider = Counter(config.provider for config in active_configs)
    running_fine_tunes = FineTuneRun.objects.filter(status=FineTuneRun.STATUS_RUNNING).count()
    has_fine_tune_runs = FineTuneRun.objects.exists()

    providers = [
        {
            "key": key,
            "label": label,
            "status": (
                "connected"
                if active_by_provider.get(key)
                else "configured"
                if configured_by_provider.get(key)
                else "missing"
            ),
            "active_count": active_by_provider.get(key, 0),
        }
        for key, label in _PROVIDER_LABELS.items()
    ]
    providers.extend(
        [
            {
                "key": "pymupdf4llm",
                "label": "pymupdf4llm",
                "status": "configured",
                "active_count": 0,
            },
            {
                "key": "llamafactory",
                "label": "LLaMA-Factory",
                "status": "connected" if running_fine_tunes else "configured" if has_fine_tune_runs else "idle",
                "active_count": running_fine_tunes,
            },
        ]
    )
    return providers


def _serialize_model(model_config):
    """将模型配置序列化为简洁的字典格式。

    参数:
        model_config: ModelConfig 实例或 None。
    返回:
        dict，包含 provider、model_name、endpoint、name 字段。
    """
    if model_config is None:
        return {
            "provider": "",
            "model_name": "",
            "endpoint": "",
            "name": "",
        }
    return {
        "provider": model_config.provider,
        "model_name": model_config.model_name,
        "endpoint": model_config.endpoint,
        "name": model_config.name,
    }


def _serialize_failed_ingestion(task):
    """将失败的摄入任务序列化为字典格式。

    参数:
        task: IngestionTask 实例。
    返回:
        dict，包含 document_id、document_title、message、current_step、updated_at。
    """
    return {
        "document_id": task.document_id,
        "document_title": task.document.title,
        "document_type": task.document.doc_type,
        # 优先使用任务级错误信息，否则回退到文档级错误（用于旧版本失败的记录）
        "message": task.error_message or task.document.error_message,
        "current_step": task.current_step,
        "updated_at": task.updated_at.isoformat(),
    }


def _recent_failed_ingestions(limit=5):
    """获取最近失败的摄入任务列表。

    参数:
        limit: int，返回的最大记录数，默认 5。
    返回:
        list[IngestionTask]，按更新时间倒序排列。
    """
    return list(
        IngestionTask.objects.filter(status=IngestionTask.STATUS_FAILED)
        .select_related("document")
        .order_by("-updated_at", "-id")[:limit]
    )


def build_llm_console_summary():
    """构建 LLM 控制台总览数据。

    返回:
        dict，包含：
        - providers: 供应商及辅助服务连接状态列表
        - active_models: 当前活跃的 chat 和 embedding 模型信息
        - recent_activity: 24h 内的对话请求数、失败摄入数、运行中微调数等
        - quick_links: 管理页面的快捷导航链接
    """
    try:
        active_chat = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
    except ModelNotConfiguredError:
        active_chat = None
    try:
        active_embedding = get_active_model_config(ModelConfig.CAPABILITY_EMBEDDING)
    except ModelNotConfiguredError:
        active_embedding = None
    latest_fine_tune = FineTuneRun.objects.order_by("-updated_at", "-id").first()
    window_start = timezone.now() - timedelta(hours=24)

    return {
        "providers": _build_provider_status(),
        "active_models": {
            "chat": _serialize_model(active_chat),
            "embedding": _serialize_model(active_embedding),
        },
        "recent_activity": {
            "chat_request_count_24h": RetrievalLog.objects.filter(
                source=RetrievalLog.SOURCE_CHAT_ASK,
                created_at__gte=window_start,
            ).count(),
            "failed_ingestion_count": IngestionTask.objects.filter(
                status=IngestionTask.STATUS_FAILED
            ).count(),
            "running_fine_tune_count": FineTuneRun.objects.filter(
                status=FineTuneRun.STATUS_RUNNING
            ).count(),
            "latest_fine_tune_status": getattr(latest_fine_tune, "status", ""),
        },
        "quick_links": [
            {"label": "模型配置", "to": "/admin/llm/models"},
            {"label": "观测", "to": "/admin/llm/observability"},
            {"label": "知识库接入", "to": "/admin/llm/knowledge"},
            {"label": "LLaMA-Factory", "to": "/admin/llm/fine-tunes"},
            {"label": "评测结果", "to": "/admin/evaluation"},
        ],
    }


def build_llm_observability_summary():
    """构建 LLM 可观测性概览数据。

    返回:
        dict，包含：
        - overview: 24h 内对话请求数、检索命中数、平均延迟、失败摄入总数
        - recent_failures: 最近的摄入失败详情列表
    """
    window_start = timezone.now() - timedelta(hours=24)
    recent_chat_logs = RetrievalLog.objects.filter(
        source=RetrievalLog.SOURCE_CHAT_ASK,
        created_at__gte=window_start,
    )
    recent_failures = _recent_failed_ingestions()

    return {
        "overview": {
            "chat_request_count_24h": recent_chat_logs.count(),
            "retrieval_hit_count_24h": recent_chat_logs.filter(result_count__gt=0).count(),
            "avg_duration_ms_24h": round(
                recent_chat_logs.aggregate(value=Avg("duration_ms"))["value"] or 0,
                2,
            ),
            "failed_ingestion_count": IngestionTask.objects.filter(
                status=IngestionTask.STATUS_FAILED
            ).count(),
        },
        "recent_failures": [_serialize_failed_ingestion(task) for task in recent_failures],
    }


def build_llm_knowledge_summary():
    """构建 LLM 知识库概览数据。

    返回:
        dict，包含：
        - parser_capabilities: 各文档格式（txt/pdf/docx）的解析器和回退策略
        - ingestion_summary: 文档摄入队列各状态（queued/running/succeeded/failed）计数
        - recent_failures: 最近摄入失败详情
        - pipeline_steps: 摄入流水线步骤描述
    """
    recent_failures = _recent_failed_ingestions()
    return {
        "parser_capabilities": {
            "txt": {"parser": "local", "fallback": False},
            "pdf": {
                "parser": "pymupdf4llm",
                "fallback": True,
            },
            "docx": {"parser": "python-docx", "fallback": False},
        },
        "ingestion_summary": {
            "total_documents": Document.objects.count(),
            "queued": IngestionTask.objects.filter(status=IngestionTask.STATUS_QUEUED).count(),
            "running": IngestionTask.objects.filter(status=IngestionTask.STATUS_RUNNING).count(),
            "succeeded": IngestionTask.objects.filter(status=IngestionTask.STATUS_SUCCEEDED).count(),
            "failed": IngestionTask.objects.filter(status=IngestionTask.STATUS_FAILED).count(),
        },
        "recent_failures": [_serialize_failed_ingestion(task) for task in recent_failures],
        "pipeline_steps": ["解析", "切块", "向量化", "索引"],
    }
