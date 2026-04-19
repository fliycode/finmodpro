from collections import Counter
from datetime import timedelta

from django.conf import settings
from django.db.models import Avg
from django.utils import timezone

from knowledgebase.models import Document, IngestionTask
from llm.models import FineTuneRun, ModelConfig
from rag.models import RetrievalLog


def _langfuse_config():
    host = getattr(settings, "LANGFUSE_HOST", "")
    public_key = getattr(settings, "LANGFUSE_PUBLIC_KEY", "")
    secret_key = getattr(settings, "LANGFUSE_SECRET_KEY", "")
    return {
        "configured": all([host, public_key, secret_key]),
        "host": host,
        "has_public_key": bool(public_key),
        "has_secret_key": bool(secret_key),
    }


def _build_provider_status():
    all_configs = list(ModelConfig.objects.all())
    active_configs = [config for config in all_configs if config.is_active]
    configured_by_provider = Counter(config.provider for config in all_configs)
    active_by_provider = Counter(config.provider for config in active_configs)
    running_fine_tunes = FineTuneRun.objects.filter(status=FineTuneRun.STATUS_RUNNING).count()
    has_fine_tune_runs = FineTuneRun.objects.exists()
    langfuse = _langfuse_config()
    unstructured_configured = bool(getattr(settings, "UNSTRUCTURED_API_URL", ""))

    providers = [
        {
            "key": "litellm",
            "label": "LiteLLM",
            "status": (
                "connected"
                if active_by_provider.get(ModelConfig.PROVIDER_LITELLM)
                else "configured"
                if configured_by_provider.get(ModelConfig.PROVIDER_LITELLM)
                else "missing"
            ),
            "active_count": active_by_provider.get(ModelConfig.PROVIDER_LITELLM, 0),
        },
    ]
    for provider_key, provider_label in ModelConfig.PROVIDER_CHOICES:
        if provider_key == ModelConfig.PROVIDER_LITELLM:
            continue
        providers.append(
            {
                "key": provider_key,
                "label": provider_label,
                "status": (
                    "connected"
                    if active_by_provider.get(provider_key)
                    else "configured"
                    if configured_by_provider.get(provider_key)
                    else "missing"
                ),
                "active_count": active_by_provider.get(provider_key, 0),
            }
        )
    providers.extend(
        [
            {
                "key": "langfuse",
                "label": "Langfuse",
                "status": "configured" if langfuse["configured"] else "missing",
                "active_count": 0,
            },
            {
                "key": "unstructured",
                "label": "Unstructured",
                "status": "configured" if unstructured_configured else "missing",
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
    return {
        "document_id": task.document_id,
        "document_title": task.document.title,
        "document_type": task.document.doc_type,
        "message": task.error_message or task.document.error_message,
        "current_step": task.current_step,
        "updated_at": task.updated_at.isoformat(),
    }


def _recent_failed_ingestions(limit=5):
    return list(
        IngestionTask.objects.filter(status=IngestionTask.STATUS_FAILED)
        .select_related("document")
        .order_by("-updated_at", "-id")[:limit]
    )


def build_llm_console_summary():
    active_chat = (
        ModelConfig.objects.filter(capability=ModelConfig.CAPABILITY_CHAT, is_active=True)
        .order_by("id")
        .first()
    )
    active_embedding = (
        ModelConfig.objects.filter(capability=ModelConfig.CAPABILITY_EMBEDDING, is_active=True)
        .order_by("id")
        .first()
    )
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
    window_start = timezone.now() - timedelta(hours=24)
    recent_chat_logs = RetrievalLog.objects.filter(
        source=RetrievalLog.SOURCE_CHAT_ASK,
        created_at__gte=window_start,
    )
    recent_failures = _recent_failed_ingestions()
    langfuse = _langfuse_config()

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
        "langfuse": langfuse,
    }


def build_llm_knowledge_summary():
    recent_failures = _recent_failed_ingestions()
    return {
        "parser_capabilities": {
            "txt": {"parser": "local", "fallback": False},
            "pdf": {
                "parser": "unstructured",
                "fallback": True,
            },
            "docx": {"parser": "unstructured", "fallback": False},
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
