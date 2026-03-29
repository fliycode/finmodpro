import json
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from django.test import TestCase

from common.exceptions import UpstreamRateLimitError, UpstreamServiceError
from llm.models import EvalRecord, ModelConfig
from llm.services.model_config_service import get_active_model_config
from llm.services.prompt_service import render_prompt
from llm.services.providers.ollama_provider import (
    OllamaChatProvider,
    OllamaEmbeddingProvider,
)
from llm.services.runtime_service import get_chat_provider, get_embedding_provider


class _FakeHttpResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class ModelConfigServiceTests(TestCase):
    def test_get_active_model_config_returns_enabled_record(self):
        active_chat = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
        active_embedding = get_active_model_config(ModelConfig.CAPABILITY_EMBEDDING)

        self.assertEqual(active_chat.provider, ModelConfig.PROVIDER_OLLAMA)
        self.assertEqual(active_embedding.provider, ModelConfig.PROVIDER_OLLAMA)

    def test_saving_new_active_model_deactivates_previous_config(self):
        previous = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
        replacement = ModelConfig.objects.create(
            name="qwen-chat",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_OLLAMA,
            model_name="qwen2.5:7b",
            endpoint="http://localhost:11434",
            options={"temperature": 0.1},
            is_active=True,
        )

        previous.refresh_from_db()
        replacement.refresh_from_db()
        self.assertFalse(previous.is_active)
        self.assertTrue(replacement.is_active)
        self.assertEqual(get_active_model_config(ModelConfig.CAPABILITY_CHAT).id, replacement.id)


class EvalRecordModelTests(TestCase):
    def test_eval_record_can_be_created_with_metrics_and_version(self):
        model_config = get_active_model_config(ModelConfig.CAPABILITY_CHAT)

        record = EvalRecord.objects.create(
            model_config=model_config,
            target_name="default-chat",
            task_type=EvalRecord.TASK_QA,
            qa_accuracy=Decimal("0.8750"),
            extraction_accuracy=Decimal("0.6500"),
            average_latency_ms=Decimal("245.50"),
            version="v1.0.0",
            status=EvalRecord.STATUS_SUCCEEDED,
            metadata={"dataset": "qa-smoke", "sample_count": 40},
        )

        self.assertEqual(record.model_config_id, model_config.id)
        self.assertEqual(record.target_name, "default-chat")
        self.assertEqual(record.task_type, EvalRecord.TASK_QA)
        self.assertEqual(record.qa_accuracy, Decimal("0.8750"))
        self.assertEqual(record.extraction_accuracy, Decimal("0.6500"))
        self.assertEqual(record.average_latency_ms, Decimal("245.50"))
        self.assertEqual(record.version, "v1.0.0")
        self.assertEqual(record.status, EvalRecord.STATUS_SUCCEEDED)
        self.assertEqual(record.metadata["dataset"], "qa-smoke")
        self.assertIsNotNone(record.created_at)

    def test_eval_record_supports_defaults_for_pending_runs(self):
        record = EvalRecord.objects.create(
            target_name="risk-extractor",
            task_type=EvalRecord.TASK_RISK_EXTRACTION,
        )

        self.assertIsNone(record.model_config)
        self.assertIsNone(record.qa_accuracy)
        self.assertIsNone(record.extraction_accuracy)
        self.assertEqual(record.average_latency_ms, Decimal("0"))
        self.assertEqual(record.version, "")
        self.assertEqual(record.status, EvalRecord.STATUS_PENDING)
        self.assertEqual(record.metadata, {})

    def test_eval_record_orders_newest_first_by_default(self):
        older = EvalRecord.objects.create(
            target_name="baseline-chat",
            task_type=EvalRecord.TASK_QA,
        )
        newer = EvalRecord.objects.create(
            target_name="candidate-chat",
            task_type=EvalRecord.TASK_QA,
        )

        self.assertEqual(
            list(EvalRecord.objects.values_list("id", flat=True)),
            [newer.id, older.id],
        )


class ProviderRuntimeTests(TestCase):
    @patch("urllib.request.urlopen")
    def test_ollama_chat_provider_returns_message_content(self, mocked_urlopen):
        mocked_urlopen.return_value = _FakeHttpResponse(
            {"message": {"content": "基于资料，收入保持增长。"}}
        )

        provider = OllamaChatProvider(
            endpoint="http://localhost:11434",
            model_name="llama3.2",
            options={"temperature": 0.2},
        )

        content = provider.chat(
            messages=[{"role": "user", "content": "请总结收入情况"}],
        )

        self.assertEqual(content, "基于资料，收入保持增长。")

    @patch("urllib.request.urlopen")
    def test_ollama_embedding_provider_returns_dense_vectors(self, mocked_urlopen):
        mocked_urlopen.return_value = _FakeHttpResponse(
            {"embeddings": [[0.1, 0.2, 0.3]]}
        )

        provider = OllamaEmbeddingProvider(
            endpoint="http://localhost:11434",
            model_name="mxbai-embed-large",
        )

        vectors = provider.embed(texts=["cash flow", "margin"])

        self.assertEqual(vectors, [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]])

    @patch("urllib.request.urlopen")
    def test_ollama_provider_maps_rate_limit_to_upstream_rate_limit_error(self, mocked_urlopen):
        mocked_urlopen.side_effect = HTTPError(
            url="http://localhost:11434/api/chat",
            code=429,
            msg="Too Many Requests",
            hdrs={"Retry-After": "12"},
            fp=BytesIO(b'{"error":"busy"}'),
        )

        provider = OllamaChatProvider(
            endpoint="http://localhost:11434",
            model_name="llama3.2",
        )

        with self.assertRaises(UpstreamRateLimitError) as context:
            provider.chat(messages=[{"role": "user", "content": "hello"}])

        self.assertEqual(context.exception.provider, "ollama")
        self.assertEqual(context.exception.retry_after, "12")

    @patch("urllib.request.urlopen")
    def test_ollama_provider_maps_transport_failures_to_upstream_service_error(self, mocked_urlopen):
        mocked_urlopen.side_effect = URLError("connection refused")

        provider = OllamaEmbeddingProvider(
            endpoint="http://localhost:11434",
            model_name="mxbai-embed-large",
        )

        with self.assertRaises(UpstreamServiceError) as context:
            provider.embed(texts=["cash flow"])

        self.assertEqual(context.exception.provider, "ollama")
        self.assertEqual(context.exception.code, "llm_provider_unavailable")

    def test_runtime_service_builds_chat_and_embedding_provider_from_database(self):
        chat_provider = get_chat_provider()
        embedding_provider = get_embedding_provider()

        self.assertIsInstance(chat_provider, OllamaChatProvider)
        self.assertIsInstance(embedding_provider, OllamaEmbeddingProvider)

    def test_prompt_template_is_rendered_from_prompts_directory(self):
        prompt = render_prompt(
            "chat/answer.txt",
            question="净利润情况如何？",
            context="[1] 年报 chunk-1: 净利润同比增长。",
        )

        self.assertIn("净利润情况如何？", prompt)
        self.assertIn("年报 chunk-1", prompt)
