import json
import os
import shutil
import tempfile
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from django.contrib.auth.models import Group
from django.test import TestCase
from django.test import Client, override_settings

from common.exceptions import UpstreamRateLimitError, UpstreamServiceError
from authentication.models import User
from authentication.services.jwt_service import generate_access_token
from llm.models import EvalRecord, FineTuneRun, ModelConfig
from llm.services.model_config_service import get_active_model_config
from llm.services.fine_tune_service import create_fine_tune_run
from llm.services.prompt_service import load_prompt_template, render_prompt
from llm.services.providers.ollama_provider import (
    OllamaChatProvider,
    OllamaEmbeddingProvider,
)
from llm.services.providers.deepseek_provider import DeepSeekChatProvider
from llm.services.runtime_service import (
    _normalize_ollama_endpoint,
    get_chat_provider,
    get_embedding_provider,
)
from rbac.services.rbac_service import ROLE_ADMIN, ROLE_MEMBER, ROLE_SUPER_ADMIN, seed_roles_and_permissions


class _FakeHttpResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class _FakeStreamingHttpResponse:
    def __init__(self, lines):
        self._lines = [line.encode("utf-8") for line in lines]

    def __iter__(self):
        return iter(self._lines)


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

    def test_model_config_supports_deepseek_provider(self):
        config = ModelConfig.objects.create(
            name="deepseek-chat",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_DEEPSEEK,
            model_name="deepseek-chat",
            endpoint="https://api.deepseek.com",
            options={"api_key": "sk-test-123456", "temperature": 0.2, "max_tokens": 1024},
            is_active=False,
        )

        self.assertEqual(config.provider, ModelConfig.PROVIDER_DEEPSEEK)
        self.assertEqual(config.options["api_key"], "sk-test-123456")

    def test_model_config_supports_litellm_provider(self):
        config = ModelConfig.objects.create(
            name="litellm-chat",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider="litellm",
            model_name="chat-default",
            endpoint="http://localhost:4000",
            options={"api_key": "sk-litellm", "temperature": 0.2},
            is_active=False,
        )

        self.assertEqual(config.provider, "litellm")


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


class ObservabilityTests(TestCase):
    @patch.dict(
        os.environ,
        {
            "LANGFUSE_HOST": "https://cloud.langfuse.example",
            "LANGFUSE_PUBLIC_KEY": "pk-lf",
            "LANGFUSE_SECRET_KEY": "sk-lf",
        },
        clear=False,
    )
    @patch("common.observability._build_langfuse_client")
    def test_trace_span_does_not_raise_when_langfuse_client_fails(self, mocked_build_client):
        from common.observability import trace_span

        mocked_build_client.side_effect = RuntimeError("langfuse unavailable")

        with trace_span("chat.ask", metadata={"question": "Q1"}) as observation:
            observation.update(output={"status": "ok"})

        mocked_build_client.assert_called_once()


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

    @patch("urllib.request.urlopen")
    def test_runtime_service_builds_deepseek_chat_provider(self, mocked_urlopen):
        mocked_urlopen.return_value = _FakeHttpResponse(
            {"choices": [{"message": {"content": "pong"}}]}
        )
        ModelConfig.objects.filter(capability=ModelConfig.CAPABILITY_CHAT).update(is_active=False)
        ModelConfig.objects.create(
            name="deepseek-active",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_DEEPSEEK,
            model_name="deepseek-chat",
            endpoint="https://api.deepseek.com",
            options={"api_key": "sk-test", "temperature": 0.3, "max_tokens": 512},
            is_active=True,
        )

        provider = get_chat_provider()
        result = provider.chat(messages=[{"role": "user", "content": "hello"}])

        self.assertIsInstance(provider, DeepSeekChatProvider)
        self.assertEqual(result, "pong")
        mocked_urlopen.assert_called_once()

    @patch("urllib.request.urlopen")
    def test_runtime_service_builds_litellm_chat_provider(self, mocked_urlopen):
        mocked_urlopen.return_value = _FakeHttpResponse(
            {"choices": [{"message": {"content": "pong"}}]}
        )
        ModelConfig.objects.filter(capability=ModelConfig.CAPABILITY_CHAT).update(is_active=False)
        ModelConfig.objects.create(
            name="litellm-active",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider="litellm",
            model_name="chat-default",
            endpoint="http://localhost:4000",
            options={"api_key": "sk-litellm", "temperature": 0.3, "max_tokens": 512},
            is_active=True,
        )

        provider = get_chat_provider()
        result = provider.chat(messages=[{"role": "user", "content": "hello"}])

        self.assertEqual(result, "pong")

    @patch("urllib.request.urlopen")
    def test_litellm_embedding_provider_returns_vectors(self, mocked_urlopen):
        from llm.services.providers.litellm_provider import LiteLLMEmbeddingProvider

        mocked_urlopen.return_value = _FakeHttpResponse({"data": [{"embedding": [0.1, 0.2, 0.3]}]})
        provider = LiteLLMEmbeddingProvider(
            endpoint="http://localhost:4000",
            model_name="embed-default",
            options={"api_key": "sk-litellm"},
        )

        vectors = provider.embed(texts=["cash flow"])

        self.assertEqual(vectors, [[0.1, 0.2, 0.3]])

    @patch.dict(os.environ, {"APP_ENV": "production", "OLLAMA_INTERNAL_URL": "http://ollama:11434"})
    def test_runtime_service_rewrites_localhost_ollama_endpoint_in_production(self):
        provider = get_embedding_provider()

        self.assertIsInstance(provider, OllamaEmbeddingProvider)
        self.assertEqual(provider.endpoint, "http://ollama:11434")

    @patch.dict(os.environ, {"APP_ENV": "production"}, clear=False)
    def test_normalize_ollama_endpoint_keeps_non_local_host(self):
        self.assertEqual(
            _normalize_ollama_endpoint("http://10.0.0.8:11434"),
            "http://10.0.0.8:11434",
        )

    @patch.dict(os.environ, {"APP_ENV": "production", "LITELLM_INTERNAL_URL": "http://litellm:4000"})
    def test_runtime_service_rewrites_localhost_litellm_endpoint_in_production(self):
        ModelConfig.objects.filter(capability=ModelConfig.CAPABILITY_CHAT).update(is_active=False)
        ModelConfig.objects.create(
            name="litellm-prod",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider="litellm",
            model_name="chat-default",
            endpoint="http://localhost:4000",
            options={"api_key": "sk-litellm"},
            is_active=True,
        )

        provider = get_chat_provider()

        self.assertEqual(provider.endpoint, "http://litellm:4000")

    @patch("urllib.request.urlopen")
    def test_deepseek_chat_provider_maps_auth_error(self, mocked_urlopen):
        mocked_urlopen.side_effect = HTTPError(
            url="https://api.deepseek.com/v1/chat/completions",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=BytesIO(b'{"error":"invalid api key"}'),
        )
        provider = DeepSeekChatProvider(
            endpoint="https://api.deepseek.com",
            model_name="deepseek-chat",
            options={"api_key": "sk-test"},
        )

        with self.assertRaises(UpstreamServiceError) as context:
            provider.chat(messages=[{"role": "user", "content": "hello"}])

        self.assertEqual(context.exception.code, "llm_provider_auth_failed")

    @patch("urllib.request.urlopen")
    def test_deepseek_chat_provider_streams_chunks(self, mocked_urlopen):
        mocked_urlopen.return_value = _FakeStreamingHttpResponse(
            [
                'data: {"choices":[{"delta":{"content":"hello"}}]}',
                'data: {"choices":[{"delta":{"content":" world"}}]}',
                "data: [DONE]",
            ]
        )
        provider = DeepSeekChatProvider(
            endpoint="https://api.deepseek.com",
            model_name="deepseek-chat",
            options={"api_key": "sk-test"},
        )

        chunks = list(provider.stream(messages=[{"role": "user", "content": "hello"}]))

        self.assertEqual(chunks, ["hello", " world"])

    def test_prompt_template_is_rendered_from_prompts_directory(self):
        prompt = render_prompt(
            "chat/answer.txt",
            question="净利润情况如何？",
            context="[1] 年报 chunk-1: 净利润同比增长。",
        )

        self.assertIn("净利润情况如何？", prompt)
        self.assertIn("年报 chunk-1", prompt)


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class ModelConfigListApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()

        self.admin_user = User.objects.create_user(
            username="ops-admin",
            password="secret123",
            email="ops-admin@example.com",
        )
        self.admin_user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.admin_access_token = generate_access_token(self.admin_user)

        self.member_user = User.objects.create_user(
            username="ops-member",
            password="secret123",
            email="ops-member@example.com",
        )
        self.member_user.groups.add(Group.objects.get(name=ROLE_MEMBER))
        self.member_access_token = generate_access_token(self.member_user)

    def test_list_model_configs_requires_authentication(self):
        response = self.client.get("/api/ops/model-configs")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {"code": 401, "message": "未认证。", "data": {}},
        )

    def test_list_model_configs_requires_manage_model_config_permission(self):
        response = self.client.get(
            "/api/ops/model-configs",
            HTTP_AUTHORIZATION=f"Bearer {self.member_access_token}",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {"code": 403, "message": "无权限。", "data": {}},
        )

    def test_list_model_configs_returns_serialized_rows(self):
        replacement = ModelConfig.objects.create(
            name="qwen-chat",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_OLLAMA,
            model_name="qwen2.5:7b",
            endpoint="http://localhost:11434",
            options={"temperature": 0.1},
            is_active=False,
        )

        response = self.client.get(
            "/api/ops/model-configs",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["message"], "ok")
        self.assertEqual(payload["data"]["total"], 3)
        self.assertEqual(
            [item["name"] for item in payload["data"]["model_configs"]],
            ["default-chat", "qwen-chat", "default-embedding"],
        )

        first_row = payload["data"]["model_configs"][0]
        self.assertEqual(
            set(first_row.keys()),
            {
                "id",
                "name",
                "capability",
                "provider",
                "model_name",
                "endpoint",
                "options",
                "has_api_key",
                "api_key_masked",
                "fine_tune_run_count",
                "latest_fine_tune_dataset",
                "latest_fine_tune_status",
                "latest_fine_tune_artifact_path",
                "is_active",
                "created_at",
                "updated_at",
            },
        )
        self.assertEqual(first_row["id"], get_active_model_config(ModelConfig.CAPABILITY_CHAT).id)
        self.assertTrue(first_row["is_active"])
        self.assertEqual(payload["data"]["model_configs"][1]["id"], replacement.id)

    def test_list_model_configs_masks_api_key(self):
        ModelConfig.objects.create(
            name="deepseek-chat",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_DEEPSEEK,
            model_name="deepseek-chat",
            endpoint="https://api.deepseek.com",
            options={"api_key": "sk-test-123456"},
            is_active=False,
        )

        response = self.client.get(
            "/api/ops/model-configs",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        deepseek_row = next(
            item for item in response.json()["data"]["model_configs"] if item["provider"] == "deepseek"
        )
        self.assertTrue(deepseek_row["has_api_key"])
        self.assertEqual(deepseek_row["api_key_masked"], "sk-tes******3456")
        self.assertNotIn("sk-test-123456", json.dumps(deepseek_row))

    def test_list_model_configs_exposes_fine_tune_lineage_summary(self):
        base_model = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
        FineTuneRun.objects.create(
            base_model=base_model,
            dataset_name="财报基准集",
            dataset_version="2026Q1",
            strategy="lora",
            status=FineTuneRun.STATUS_SUCCEEDED,
            artifact_path="/artifacts/finmodpro-chat-lora-v1",
            metrics={"f1_score": 0.92},
            notes="外部训练完成后登记。",
        )

        response = self.client.get(
            "/api/ops/model-configs",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        chat_row = next(
            item for item in response.json()["data"]["model_configs"] if item["id"] == base_model.id
        )
        self.assertEqual(chat_row["fine_tune_run_count"], 1)
        self.assertEqual(chat_row["latest_fine_tune_dataset"], "财报基准集")
        self.assertEqual(chat_row["latest_fine_tune_status"], "succeeded")


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class ModelConfigActivationApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()

        self.admin_user = User.objects.create_user(
            username="ops-activation-admin",
            password="secret123",
            email="ops-activation-admin@example.com",
        )
        self.admin_user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.admin_access_token = generate_access_token(self.admin_user)

        self.member_user = User.objects.create_user(
            username="ops-activation-member",
            password="secret123",
            email="ops-activation-member@example.com",
        )
        self.member_user.groups.add(Group.objects.get(name=ROLE_MEMBER))
        self.member_access_token = generate_access_token(self.member_user)

    def test_activation_requires_authentication(self):
        model_config = get_active_model_config(ModelConfig.CAPABILITY_CHAT)

        response = self.client.patch(
            f"/api/ops/model-configs/{model_config.id}/activation",
            data=json.dumps({"is_active": False}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {"code": 401, "message": "未认证。", "data": {}},
        )

    def test_activation_requires_manage_model_config_permission(self):
        model_config = get_active_model_config(ModelConfig.CAPABILITY_CHAT)

        response = self.client.patch(
            f"/api/ops/model-configs/{model_config.id}/activation",
            data=json.dumps({"is_active": False}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.member_access_token}",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {"code": 403, "message": "无权限。", "data": {}},
        )

    def test_activation_enables_target_and_switches_same_capability(self):
        previous = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
        replacement = ModelConfig.objects.create(
            name="qwen-chat-active",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_OLLAMA,
            model_name="qwen2.5:7b",
            endpoint="http://localhost:11434",
            options={"temperature": 0.1},
            is_active=False,
        )

        response = self.client.patch(
            f"/api/ops/model-configs/{replacement.id}/activation",
            data=json.dumps({"is_active": True}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"]["model_config"]["id"], replacement.id)
        self.assertTrue(payload["data"]["model_config"]["is_active"])

        previous.refresh_from_db()
        replacement.refresh_from_db()
        self.assertFalse(previous.is_active)
        self.assertTrue(replacement.is_active)

    def test_activation_can_disable_model_config(self):
        active_model = get_active_model_config(ModelConfig.CAPABILITY_CHAT)

        response = self.client.patch(
            f"/api/ops/model-configs/{active_model.id}/activation",
            data=json.dumps({"is_active": False}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertFalse(payload["data"]["model_config"]["is_active"])

        active_model.refresh_from_db()
        self.assertFalse(active_model.is_active)

    def test_activation_returns_serialized_structure(self):
        active_model = get_active_model_config(ModelConfig.CAPABILITY_EMBEDDING)

        response = self.client.patch(
            f"/api/ops/model-configs/{active_model.id}/activation",
            data=json.dumps({"is_active": True}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.json()["data"]["model_config"].keys()),
            {
                "id",
                "name",
                "capability",
                "provider",
                "model_name",
                "endpoint",
                "options",
                "has_api_key",
                "api_key_masked",
                "fine_tune_run_count",
                "latest_fine_tune_dataset",
                "latest_fine_tune_status",
                "latest_fine_tune_artifact_path",
                "is_active",
                "created_at",
                "updated_at",
            },
        )

    def test_admin_can_create_deepseek_model_config(self):
        response = self.client.post(
            "/api/ops/model-configs/",
            data=json.dumps(
                {
                    "name": "deepseek-prod",
                    "capability": "chat",
                    "provider": "deepseek",
                    "model_name": "deepseek-chat",
                    "endpoint": "https://api.deepseek.com",
                    "options": {
                        "api_key": "sk-test-123456",
                        "temperature": 0.2,
                        "max_tokens": 1024,
                    },
                    "is_active": True,
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["model_config"]["provider"], "deepseek")
        self.assertTrue(payload["data"]["model_config"]["has_api_key"])

    @patch("urllib.request.urlopen")
    def test_admin_can_test_deepseek_connection(self, mocked_urlopen):
        mocked_urlopen.return_value = _FakeHttpResponse(
            {"choices": [{"message": {"content": "pong"}}]}
        )

        response = self.client.post(
            "/api/ops/model-configs/test-connection/",
            data=json.dumps(
                {
                    "capability": "chat",
                    "provider": "deepseek",
                    "model_name": "deepseek-chat",
                    "endpoint": "https://api.deepseek.com",
                    "options": {"api_key": "sk-test"},
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["ok"], True)

    @patch("urllib.request.urlopen")
    def test_admin_can_test_litellm_embedding_connection(self, mocked_urlopen):
        mocked_urlopen.return_value = _FakeHttpResponse({"data": [{"embedding": [0.1, 0.2, 0.3]}]})

        response = self.client.post(
            "/api/ops/model-configs/test-connection/",
            data=json.dumps(
                {
                    "capability": "embedding",
                    "provider": "litellm",
                    "model_name": "embed-default",
                    "endpoint": "http://localhost:4000",
                    "options": {"api_key": "sk-litellm"},
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["ok"], True)

    def test_activation_returns_404_for_unknown_model_config(self):
        response = self.client.patch(
            "/api/ops/model-configs/999999/activation",
            data=json.dumps({"is_active": True}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {"code": 404, "message": "模型配置不存在。", "data": {}},
        )


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class PromptConfigListApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()

        self.admin_user = User.objects.create_user(
            username="ops-prompt-admin",
            password="secret123",
            email="ops-prompt-admin@example.com",
        )
        self.admin_user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.admin_access_token = generate_access_token(self.admin_user)

        self.member_user = User.objects.create_user(
            username="ops-prompt-member",
            password="secret123",
            email="ops-prompt-member@example.com",
        )
        self.member_user.groups.add(Group.objects.get(name=ROLE_MEMBER))
        self.member_access_token = generate_access_token(self.member_user)

    def test_list_prompt_configs_requires_authentication(self):
        response = self.client.get("/api/ops/prompt-configs")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {"code": 401, "message": "未认证。", "data": {}},
        )

    def test_list_prompt_configs_requires_manage_model_config_permission(self):
        response = self.client.get(
            "/api/ops/prompt-configs",
            HTTP_AUTHORIZATION=f"Bearer {self.member_access_token}",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {"code": 403, "message": "无权限。", "data": {}},
        )

    def test_list_prompt_configs_returns_existing_templates_and_variables(self):
        response = self.client.get(
            "/api/ops/prompt-configs",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["message"], "ok")
        self.assertEqual(payload["data"]["total"], 2)
        self.assertEqual(
            [item["key"] for item in payload["data"]["prompt_configs"]],
            ["chat/answer.txt", "risk/extract.txt"],
        )

        first_prompt = payload["data"]["prompt_configs"][0]
        self.assertEqual(
            set(first_prompt.keys()),
            {"key", "category", "name", "template", "variables", "updated_at"},
        )
        self.assertEqual(first_prompt["category"], "chat")
        self.assertEqual(first_prompt["name"], "answer.txt")
        self.assertIn("question", first_prompt["variables"])
        self.assertIn("context", first_prompt["variables"])
        self.assertIn("{question}", first_prompt["template"])


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class PromptConfigUpdateApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()
        self.temp_dir = Path(tempfile.mkdtemp(dir=Path.cwd()))
        self.prompts_dir = self.temp_dir / "prompts"
        (self.prompts_dir / "chat").mkdir(parents=True)
        (self.prompts_dir / "risk").mkdir(parents=True)
        (self.prompts_dir / "chat" / "answer.txt").write_text(
            "问题：{question}\n资料：{context}\n",
            encoding="utf-8",
        )
        (self.prompts_dir / "risk" / "extract.txt").write_text(
            "标题：{document_title}\n切块：{chunk_context}\n",
            encoding="utf-8",
        )
        load_prompt_template.cache_clear()

        self.prompt_service_patch = patch("llm.services.prompt_service.PROMPTS_DIR", self.prompts_dir)
        self.prompt_query_patch = patch("llm.services.prompt_query_service.PROMPTS_DIR", self.prompts_dir)
        self.prompt_service_patch.start()
        self.prompt_query_patch.start()

        self.admin_user = User.objects.create_user(
            username="ops-prompt-update-admin",
            password="secret123",
            email="ops-prompt-update-admin@example.com",
        )
        self.admin_user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.admin_access_token = generate_access_token(self.admin_user)

        self.member_user = User.objects.create_user(
            username="ops-prompt-update-member",
            password="secret123",
            email="ops-prompt-update-member@example.com",
        )
        self.member_user.groups.add(Group.objects.get(name=ROLE_MEMBER))
        self.member_access_token = generate_access_token(self.member_user)

    def tearDown(self):
        self.prompt_query_patch.stop()
        self.prompt_service_patch.stop()
        load_prompt_template.cache_clear()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_update_prompt_config_requires_authentication(self):
        response = self.client.patch(
            "/api/ops/prompt-configs/chat/answer.txt",
            data=json.dumps({"template": "新的模板：{foo}"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"code": 401, "message": "未认证。", "data": {}})

    def test_update_prompt_config_requires_manage_model_config_permission(self):
        response = self.client.patch(
            "/api/ops/prompt-configs/chat/answer.txt",
            data=json.dumps({"template": "新的模板：{foo}"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.member_access_token}",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"code": 403, "message": "无权限。", "data": {}})

    def test_update_prompt_config_returns_404_for_unknown_key(self):
        response = self.client.patch(
            "/api/ops/prompt-configs/chat/missing.txt",
            data=json.dumps({"template": "新的模板：{foo}"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"code": 404, "message": "Prompt 模板不存在。", "data": {}})

    def test_update_prompt_config_rejects_invalid_key(self):
        response = self.client.patch(
            "/api/ops/prompt-configs/../secrets.txt",
            data=json.dumps({"template": "新的模板：{foo}"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"code": 400, "message": "非法的 prompt key。", "data": {}})

    def test_update_prompt_config_persists_template_and_refreshes_render_cache(self):
        original_render = render_prompt("chat/answer.txt", question="Q1", context="C1")
        self.assertIn("Q1", original_render)

        response = self.client.patch(
            "/api/ops/prompt-configs/chat/answer.txt",
            data=json.dumps({"template": "新模板：{company_name} / {quarter}"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"]["prompt_config"]["key"], "chat/answer.txt")
        self.assertEqual(payload["data"]["prompt_config"]["variables"], ["company_name", "quarter"])
        self.assertEqual(
            (self.prompts_dir / "chat" / "answer.txt").read_text(encoding="utf-8"),
            "新模板：{company_name} / {quarter}",
        )
        self.assertEqual(
            render_prompt("chat/answer.txt", company_name="FinModPro", quarter="2025Q1"),
            "新模板：FinModPro / 2025Q1",
        )


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class EvalRecordApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()

        self.admin_user = User.objects.create_user(
            username="ops-eval-admin",
            password="secret123",
            email="ops-eval-admin@example.com",
        )
        self.admin_user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.admin_access_token = generate_access_token(self.admin_user)

        self.super_admin_user = User.objects.create_user(
            username="ops-eval-super-admin",
            password="secret123",
            email="ops-eval-super-admin@example.com",
        )
        self.super_admin_user.groups.add(Group.objects.get(name=ROLE_SUPER_ADMIN))
        self.super_admin_access_token = generate_access_token(self.super_admin_user)

        self.member_user = User.objects.create_user(
            username="ops-eval-member",
            password="secret123",
            email="ops-eval-member@example.com",
        )
        self.member_user.groups.add(Group.objects.get(name=ROLE_MEMBER))
        self.member_access_token = generate_access_token(self.member_user)

    def test_create_evaluation_requires_authentication(self):
        response = self.client.post(
            "/api/ops/evaluations",
            data=json.dumps({"task_type": "qa"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"code": 401, "message": "未认证。", "data": {}})

    def test_create_evaluation_requires_run_evaluation_permission(self):
        response = self.client.post(
            "/api/ops/evaluations",
            data=json.dumps({"task_type": "qa"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"code": 403, "message": "无权限。", "data": {}})

    def test_create_evaluation_returns_404_for_unknown_model_config(self):
        response = self.client.post(
            "/api/ops/evaluations",
            data=json.dumps({"task_type": "qa", "model_config_id": 999999}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.super_admin_access_token}",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {"code": 404, "message": "模型配置不存在。", "data": {}},
        )

    def test_create_evaluation_runs_smoke_suite_and_persists_record(self):
        response = self.client.post(
            "/api/ops/evaluations",
            data=json.dumps(
                {
                    "task_type": "qa",
                    "version": "baseline-v1",
                    "evaluation_mode": "baseline",
                    "dataset_name": "qa-smoke",
                    "dataset_version": "2026Q1",
                    "run_notes": "baseline smoke",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.super_admin_access_token}",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"]["eval_record"]["task_type"], "qa")
        self.assertEqual(payload["data"]["eval_record"]["target_name"], "default-chat")
        self.assertEqual(payload["data"]["eval_record"]["status"], "succeeded")
        self.assertEqual(payload["data"]["eval_record"]["evaluation_mode"], "baseline")
        self.assertEqual(payload["data"]["eval_record"]["qa_accuracy"], "1.0000")
        self.assertEqual(payload["data"]["eval_record"]["extraction_accuracy"], "1.0000")
        self.assertEqual(payload["data"]["eval_record"]["precision"], "1.0000")
        self.assertEqual(payload["data"]["eval_record"]["recall"], "1.0000")
        self.assertEqual(payload["data"]["eval_record"]["f1_score"], "1.0000")
        self.assertEqual(payload["data"]["eval_record"]["dataset_name"], "qa-smoke")
        self.assertEqual(payload["data"]["eval_record"]["dataset_version"], "2026Q1")
        self.assertEqual(payload["data"]["eval_record"]["run_notes"], "baseline smoke")
        self.assertEqual(payload["data"]["eval_record"]["version"], "baseline-v1")
        self.assertEqual(payload["data"]["eval_record"]["metadata"]["evaluator_type"], "smoke")
        self.assertEqual(payload["data"]["eval_record"]["metadata"]["qa_dataset_size"], 2)
        self.assertEqual(payload["data"]["eval_record"]["metadata"]["extraction_dataset_size"], 2)
        self.assertEqual(EvalRecord.objects.count(), 1)

    def test_list_evaluations_requires_view_evaluation_permission(self):
        response = self.client.get(
            "/api/ops/evaluations",
            HTTP_AUTHORIZATION=f"Bearer {self.member_access_token}",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"code": 403, "message": "无权限。", "data": {}})

    def test_list_evaluations_requires_authentication(self):
        response = self.client.get("/api/ops/evaluations")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"code": 401, "message": "未认证。", "data": {}})

    def test_list_evaluations_returns_summary_rows(self):
        first_record = EvalRecord.objects.create(
            model_config=get_active_model_config(ModelConfig.CAPABILITY_CHAT),
            target_name="default-chat",
            task_type=EvalRecord.TASK_QA,
            evaluation_mode=EvalRecord.EVALUATION_MODE_BASELINE,
            qa_accuracy=Decimal("0.9000"),
            extraction_accuracy=Decimal("0.8000"),
            precision=Decimal("0.9000"),
            recall=Decimal("0.9000"),
            f1_score=Decimal("0.9000"),
            average_latency_ms=Decimal("12.50"),
            version="v1",
            status=EvalRecord.STATUS_SUCCEEDED,
            dataset_name="qa-smoke",
            dataset_version="2026Q1",
            run_notes="baseline",
            metadata={"evaluator_type": "smoke"},
        )
        second_record = EvalRecord.objects.create(
            model_config=get_active_model_config(ModelConfig.CAPABILITY_CHAT),
            target_name="default-chat",
            task_type=EvalRecord.TASK_RISK_EXTRACTION,
            evaluation_mode=EvalRecord.EVALUATION_MODE_FINE_TUNED,
            qa_accuracy=Decimal("0.7000"),
            extraction_accuracy=Decimal("0.9500"),
            precision=Decimal("0.9500"),
            recall=Decimal("0.9500"),
            f1_score=Decimal("0.9500"),
            average_latency_ms=Decimal("10.00"),
            version="v2",
            status=EvalRecord.STATUS_SUCCEEDED,
            dataset_name="risk-smoke",
            dataset_version="2026Q1",
            run_notes="fine tuned",
            metadata={"evaluator_type": "smoke"},
        )

        response = self.client.get(
            "/api/ops/evaluations",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"]["total"], 2)
        self.assertEqual(
            [item["id"] for item in payload["data"]["eval_records"]],
            [second_record.id, first_record.id],
        )
        self.assertEqual(
            set(payload["data"]["eval_records"][0].keys()),
            {
                "id",
                "model_config_id",
                "target_name",
                "task_type",
                "evaluation_mode",
                "status",
                "qa_accuracy",
                "extraction_accuracy",
                "precision",
                "recall",
                "f1_score",
                "average_latency_ms",
                "version",
                "dataset_name",
                "dataset_version",
                "run_notes",
                "metadata",
                "created_at",
            },
        )
        self.assertEqual(
            [group["evaluation_mode"] for group in payload["data"]["comparison_groups"]],
            [EvalRecord.EVALUATION_MODE_BASELINE, EvalRecord.EVALUATION_MODE_FINE_TUNED],
        )
        self.assertEqual(payload["data"]["comparison_groups"][0]["records"][0]["id"], first_record.id)
        self.assertEqual(payload["data"]["comparison_groups"][1]["records"][0]["id"], second_record.id)


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class FineTuneRunApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()
        self.export_dir = tempfile.mkdtemp()
        self.override = override_settings(FINE_TUNE_EXPORT_ROOT=self.export_dir)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(shutil.rmtree, self.export_dir, True)

        self.admin_user = User.objects.create_user(
            username="ops-finetune-admin",
            password="secret123",
            email="ops-finetune-admin@example.com",
        )
        self.admin_user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.admin_access_token = generate_access_token(self.admin_user)

        self.member_user = User.objects.create_user(
            username="ops-finetune-member",
            password="secret123",
            email="ops-finetune-member@example.com",
        )
        self.member_user.groups.add(Group.objects.get(name=ROLE_MEMBER))
        self.member_access_token = generate_access_token(self.member_user)

    def test_list_fine_tunes_requires_manage_permission(self):
        response = self.client.get(
            "/api/ops/fine-tunes",
            HTTP_AUTHORIZATION=f"Bearer {self.member_access_token}",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"code": 403, "message": "无权限。", "data": {}})

    def test_create_fine_tune_run_registers_lineage(self):
        base_model = get_active_model_config(ModelConfig.CAPABILITY_CHAT)

        response = self.client.post(
            "/api/ops/fine-tunes",
            data=json.dumps(
                {
                    "base_model_id": base_model.id,
                    "dataset_name": "财报基准集",
                    "dataset_version": "2026Q1",
                    "strategy": "lora",
                    "runner_name": "llamafactory-runner-a",
                    "training_config": {"learning_rate": 1e-4, "epochs": 3},
                    "notes": "外部训练任务登记中。",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"]["fine_tune_run"]["base_model_id"], base_model.id)
        self.assertEqual(payload["data"]["fine_tune_run"]["dataset_name"], "财报基准集")
        self.assertEqual(payload["data"]["fine_tune_run"]["status"], "pending")
        self.assertEqual(payload["data"]["fine_tune_run"]["runner_name"], "llamafactory-runner-a")
        self.assertEqual(payload["data"]["fine_tune_run"]["training_config"]["epochs"], 3)
        self.assertTrue(payload["data"]["fine_tune_run"]["callback_token"].startswith("ftcb_"))
        self.assertEqual(FineTuneRun.objects.count(), 1)

    def test_list_fine_tunes_returns_model_lineage(self):
        base_model = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
        first_run = FineTuneRun.objects.create(
            base_model=base_model,
            dataset_name="财报基准集",
            dataset_version="2026Q1",
            strategy="lora",
            status=FineTuneRun.STATUS_SUCCEEDED,
            artifact_path="/artifacts/runs/ft-20260413",
            metrics={"precision": 0.94, "recall": 0.92, "f1_score": 0.93},
            notes="已完成登记。",
        )
        second_run = FineTuneRun.objects.create(
            base_model=base_model,
            dataset_name="舆情语料集",
            dataset_version="2026Q2",
            strategy="lora",
            status=FineTuneRun.STATUS_PENDING,
            artifact_path="",
            metrics={},
            notes="等待外部训练结果回写。",
        )

        response = self.client.get(
            "/api/ops/fine-tunes",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["total"], 2)
        self.assertEqual(
            [item["id"] for item in payload["data"]["fine_tune_runs"]],
            [second_run.id, first_run.id],
        )
        self.assertEqual(
            set(payload["data"]["fine_tune_runs"][0].keys()),
            {
                "id",
                "base_model_id",
                "base_model_name",
                "base_model_capability",
                "base_model_provider",
                "dataset_name",
                "dataset_version",
                "strategy",
                "status",
                "run_key",
                "external_job_id",
                "runner_name",
                "artifact_path",
                "export_path",
                "deployment_endpoint",
                "deployment_model_name",
                "dataset_manifest",
                "training_config",
                "artifact_manifest",
                "metrics",
                "failure_reason",
                "queued_at",
                "started_at",
                "finished_at",
                "last_heartbeat_at",
                "callback_token",
                "registered_model_config_id",
                "notes",
                "created_at",
                "updated_at",
            },
        )

    def test_update_fine_tune_run_updates_status_and_notes(self):
        base_model = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
        run = FineTuneRun.objects.create(
            base_model=base_model,
            dataset_name="财报基准集",
            dataset_version="2026Q1",
            strategy="lora",
            status=FineTuneRun.STATUS_PENDING,
            artifact_path="",
            metrics={},
            notes="等待登记。",
        )

        response = self.client.patch(
            f"/api/ops/fine-tunes/{run.id}",
            data=json.dumps(
                {
                    "status": "succeeded",
                    "artifact_path": "/artifacts/runs/ft-20260413",
                    "metrics": {"loss": 0.1, "f1_score": 0.95},
                    "notes": "训练结果已回写平台。",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["fine_tune_run"]["status"], "succeeded")
        self.assertEqual(payload["data"]["fine_tune_run"]["artifact_path"], "/artifacts/runs/ft-20260413")
        self.assertEqual(payload["data"]["fine_tune_run"]["metrics"]["f1_score"], 0.95)
        self.assertEqual(payload["data"]["fine_tune_run"]["notes"], "训练结果已回写平台。")
        self.assertEqual(payload["data"]["fine_tune_run"]["artifact_manifest"], {})


class FineTuneRunControlPlaneTests(TestCase):
    def setUp(self):
        self.export_dir = tempfile.mkdtemp()
        self.override = override_settings(FINE_TUNE_EXPORT_ROOT=self.export_dir)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(shutil.rmtree, self.export_dir, True)

    def test_create_fine_tune_run_generates_control_plane_metadata(self):
        base_model = get_active_model_config(ModelConfig.CAPABILITY_CHAT)

        fine_tune_run = create_fine_tune_run(
            payload={
                "base_model_id": base_model.id,
                "dataset_name": "财报基准集",
                "dataset_version": "2026Q2",
                "strategy": "lora",
                "notes": "等待导出训练数据。",
            }
        )

        self.assertTrue(fine_tune_run.run_key.startswith("ft-"))
        self.assertTrue(fine_tune_run.callback_token.startswith("ftcb_"))
        self.assertNotEqual(fine_tune_run.callback_token_hash, fine_tune_run.callback_token)
        self.assertIsNotNone(fine_tune_run.queued_at)
        self.assertEqual(fine_tune_run.status, FineTuneRun.STATUS_PENDING)
        self.assertEqual(fine_tune_run.dataset_manifest["dataset_name"], "财报基准集")
        self.assertIn("export_status", fine_tune_run.dataset_manifest)


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class FineTuneRunCallbackApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()
        self.export_dir = tempfile.mkdtemp()
        self.generated_config_dir = tempfile.mkdtemp()
        self.override = override_settings(
            FINE_TUNE_EXPORT_ROOT=self.export_dir,
            LITELLM_GENERATED_CONFIG_ROOT=self.generated_config_dir,
        )
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(shutil.rmtree, self.export_dir, True)
        self.addCleanup(shutil.rmtree, self.generated_config_dir, True)

        self.admin_user = User.objects.create_user(
            username="ops-finetune-callback-admin",
            password="secret123",
            email="ops-finetune-callback-admin@example.com",
        )
        self.admin_user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.admin_access_token = generate_access_token(self.admin_user)

    def test_list_fine_tunes_exposes_control_plane_fields(self):
        base_model = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
        run = FineTuneRun.objects.create(
            base_model=base_model,
            dataset_name="财报基准集",
            dataset_version="2026Q2",
            strategy="lora",
            status=FineTuneRun.STATUS_PENDING,
            artifact_path="",
            metrics={},
            notes="等待外部训练结果。",
        )

        response = self.client.get(
            "/api/ops/fine-tunes",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        first_run = response.json()["data"]["fine_tune_runs"][0]
        self.assertEqual(first_run["id"], run.id)
        self.assertIn("run_key", first_run)
        self.assertIn("runner_name", first_run)
        self.assertIn("export_path", first_run)
        self.assertIn("deployment_endpoint", first_run)
        self.assertIn("registered_model_config_id", first_run)

    def test_runner_callback_requires_valid_token(self):
        base_model = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
        run = FineTuneRun.objects.create(
            base_model=base_model,
            dataset_name="财报基准集",
            dataset_version="2026Q2",
            strategy="lora",
            status=FineTuneRun.STATUS_PENDING,
            artifact_path="",
            metrics={},
            notes="等待外部训练结果。",
        )

        response = self.client.post(
            f"/api/ops/fine-tunes/{run.id}/callback",
            data=json.dumps({"status": "running"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["message"], "回调令牌无效。")

    def test_runner_callback_updates_status_and_artifact_without_admin_session(self):
        base_model = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
        run = create_fine_tune_run(
            payload={
                "base_model_id": base_model.id,
                "dataset_name": "财报基准集",
                "dataset_version": "2026Q2",
                "strategy": "lora",
                "notes": "等待外部训练回写。",
            }
        )

        response = self.client.post(
            f"/api/ops/fine-tunes/{run.id}/callback",
            data=json.dumps(
                {
                    "status": "succeeded",
                    "metrics": {"f1_score": 0.94},
                    "artifact_manifest": {"adapter_path": "/artifacts/ft-001"},
                }
            ),
            content_type="application/json",
            HTTP_X_FINE_TUNE_TOKEN=run.callback_token,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["fine_tune_run"]["status"], "succeeded")
        self.assertEqual(payload["data"]["fine_tune_run"]["metrics"]["f1_score"], 0.94)
        self.assertEqual(
            payload["data"]["fine_tune_run"]["artifact_manifest"]["adapter_path"],
            "/artifacts/ft-001",
        )

    def test_runner_callback_registers_inactive_litellm_candidate_model(self):
        base_model = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
        run = create_fine_tune_run(
            payload={
                "base_model_id": base_model.id,
                "dataset_name": "财报基准集",
                "dataset_version": "2026Q2",
                "strategy": "lora",
                "notes": "等待外部训练回写。",
            }
        )

        response = self.client.post(
            f"/api/ops/fine-tunes/{run.id}/callback",
            data=json.dumps(
                {
                    "status": "succeeded",
                    "deployment_endpoint": "http://localhost:4000",
                    "deployment_model_name": "finmodpro-ft-chat",
                }
            ),
            content_type="application/json",
            HTTP_X_FINE_TUNE_TOKEN=run.callback_token,
        )

        self.assertEqual(response.status_code, 200)
        run.refresh_from_db()
        self.assertIsNotNone(run.registered_model_config_id)
        self.assertEqual(run.registered_model_config.provider, ModelConfig.PROVIDER_LITELLM)
        self.assertFalse(run.registered_model_config.is_active)

    def test_runner_callback_generates_litellm_alias_config_artifact(self):
        base_model = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
        run = create_fine_tune_run(
            payload={
                "base_model_id": base_model.id,
                "dataset_name": "财报基准集",
                "dataset_version": "2026Q2",
                "strategy": "lora",
                "notes": "等待外部训练回写。",
            }
        )

        response = self.client.post(
            f"/api/ops/fine-tunes/{run.id}/callback",
            data=json.dumps(
                {
                    "status": "succeeded",
                    "deployment_endpoint": "http://127.0.0.1:9000/v1",
                    "deployment_model_name": "finmodpro-ft-chat",
                }
            ),
            content_type="application/json",
            HTTP_X_FINE_TUNE_TOKEN=run.callback_token,
        )

        self.assertEqual(response.status_code, 200)
        run.refresh_from_db()
        artifact_manifest = run.artifact_manifest
        self.assertEqual(artifact_manifest["litellm_alias"], "finmodpro-ft-chat")
        config_path = artifact_manifest["litellm_config_path"]
        self.assertTrue(Path(config_path).exists())
        config_body = Path(config_path).read_text(encoding="utf-8")
        self.assertIn("model_name: finmodpro-ft-chat", config_body)
        self.assertIn("api_base: http://127.0.0.1:9000/v1", config_body)

    def test_runner_callback_is_idempotent_for_candidate_model_registration(self):
        base_model = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
        run = create_fine_tune_run(
            payload={
                "base_model_id": base_model.id,
                "dataset_name": "财报基准集",
                "dataset_version": "2026Q2",
                "strategy": "lora",
                "notes": "等待外部训练回写。",
            }
        )

        callback_payload = {
            "status": "succeeded",
            "deployment_endpoint": "http://localhost:4000",
            "deployment_model_name": "finmodpro-ft-chat",
        }
        first_response = self.client.post(
            f"/api/ops/fine-tunes/{run.id}/callback",
            data=json.dumps(callback_payload),
            content_type="application/json",
            HTTP_X_FINE_TUNE_TOKEN=run.callback_token,
        )
        second_response = self.client.post(
            f"/api/ops/fine-tunes/{run.id}/callback",
            data=json.dumps(callback_payload),
            content_type="application/json",
            HTTP_X_FINE_TUNE_TOKEN=run.callback_token,
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        run.refresh_from_db()
        self.assertEqual(ModelConfig.objects.filter(name__contains=run.run_key).count(), 1)

    def test_failed_runner_callback_does_not_register_candidate_model(self):
        base_model = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
        run = create_fine_tune_run(
            payload={
                "base_model_id": base_model.id,
                "dataset_name": "财报基准集",
                "dataset_version": "2026Q2",
                "strategy": "lora",
                "notes": "等待外部训练回写。",
            }
        )

        response = self.client.post(
            f"/api/ops/fine-tunes/{run.id}/callback",
            data=json.dumps({"status": "failed", "failure_reason": "gpu oom"}),
            content_type="application/json",
            HTTP_X_FINE_TUNE_TOKEN=run.callback_token,
        )

        self.assertEqual(response.status_code, 200)
        run.refresh_from_db()
        self.assertIsNone(run.registered_model_config_id)

    def test_admin_can_fetch_export_bundle_detail(self):
        base_model = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
        run = create_fine_tune_run(
            payload={
                "base_model_id": base_model.id,
                "dataset_name": "财报基准集",
                "dataset_version": "2026Q2",
                "strategy": "lora",
                "notes": "等待外部训练回写。",
            }
        )

        response = self.client.get(
            f"/api/ops/fine-tunes/{run.id}/export",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["fine_tune_run_id"], run.id)
        self.assertEqual(payload["run_key"], run.run_key)
        self.assertEqual(payload["manifest"]["dataset_name"], "财报基准集")
        self.assertIn("train.jsonl", [item["name"] for item in payload["files"]])

    def test_runner_spec_requires_valid_token(self):
        base_model = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
        run = create_fine_tune_run(
            payload={
                "base_model_id": base_model.id,
                "dataset_name": "财报基准集",
                "dataset_version": "2026Q2",
                "strategy": "lora",
                "notes": "等待 runner 拉取执行说明。",
            }
        )

        response = self.client.get(f"/api/ops/fine-tunes/{run.id}/runner-spec")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["message"], "回调令牌无效。")

    @override_settings(FINE_TUNE_EXPORT_BASE_URL="https://runner-downloads.example/exports")
    def test_runner_can_fetch_execution_spec_with_export_and_callback_contract(self):
        base_model = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
        run = create_fine_tune_run(
            payload={
                "base_model_id": base_model.id,
                "dataset_name": "财报基准集",
                "dataset_version": "2026Q2",
                "strategy": "lora",
                "runner_name": "llamafactory-runner-a",
                "notes": "等待 runner 拉取执行说明。",
                "training_config": {"epochs": 3, "learning_rate": 0.0001},
            }
        )

        response = self.client.get(
            f"/api/ops/fine-tunes/{run.id}/runner-spec",
            HTTP_X_FINE_TUNE_TOKEN=run.callback_token,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["fine_tune_run_id"], run.id)
        self.assertEqual(payload["run_key"], run.run_key)
        self.assertEqual(payload["training_job"]["framework"], "llamafactory")
        self.assertEqual(payload["training_job"]["base_model_name"], base_model.model_name)
        self.assertEqual(payload["training_job"]["runner_name"], "llamafactory-runner-a")
        self.assertEqual(payload["training_job"]["training_config"]["epochs"], 3)
        self.assertEqual(payload["callback"]["token_header"], "X-Fine-Tune-Token")
        self.assertTrue(payload["callback"]["url"].endswith(f"/api/ops/fine-tunes/{run.id}/callback/"))
        self.assertEqual(payload["export_bundle"]["manifest"]["dataset_name"], "财报基准集")
        self.assertEqual(payload["export_bundle"]["base_url"], "https://runner-downloads.example/exports")

        file_names = [item["name"] for item in payload["export_bundle"]["files"]]
        self.assertIn("manifest.json", file_names)
        self.assertIn("train.jsonl", file_names)
        manifest_file = next(item for item in payload["export_bundle"]["files"] if item["name"] == "manifest.json")
        self.assertTrue(
            manifest_file["url"].endswith(f"{run.run_key}/manifest.json"),
            msg=manifest_file["url"],
        )


class FineTuneRunnerClientTests(TestCase):
    def test_fetch_runner_spec_uses_token_header_and_unwraps_data(self):
        from llm.services.fine_tune_runner_client import fetch_runner_spec

        captured_request = {}

        def fake_urlopen(req, timeout=30):
            captured_request["url"] = req.full_url
            captured_request["token"] = req.headers.get("X-fine-tune-token")
            return _FakeHttpResponse(
                {
                    "code": 0,
                    "message": "ok",
                    "data": {
                        "fine_tune_run_id": 7,
                        "run_key": "ft-20260416",
                        "export_bundle": {"export_path": "/tmp/ft-20260416", "files": []},
                    },
                }
            )

        with patch("llm.services.fine_tune_runner_client.request.urlopen", side_effect=fake_urlopen):
            payload = fetch_runner_spec(
                api_base_url="http://127.0.0.1:8000",
                fine_tune_run_id=7,
                token="ftcb_test_token",
            )

        self.assertEqual(captured_request["url"], "http://127.0.0.1:8000/api/ops/fine-tunes/7/runner-spec/")
        self.assertEqual(captured_request["token"], "ftcb_test_token")
        self.assertEqual(payload["run_key"], "ft-20260416")

    def test_materialize_export_bundle_downloads_missing_files(self):
        from llm.services.fine_tune_runner_client import materialize_export_bundle

        work_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, work_dir, True)
        requested_urls = []
        spec = {
            "run_key": "ft-20260416",
            "export_bundle": {
                "export_path": "/nonexistent/ft-20260416",
                "files": [
                    {"name": "manifest.json", "url": "https://runner-downloads.example/exports/ft-20260416/manifest.json"},
                    {"name": "train.jsonl", "url": "https://runner-downloads.example/exports/ft-20260416/train.jsonl"},
                ],
            },
        }

        def fake_urlopen(req, timeout=30):
            requested_urls.append(req.full_url if hasattr(req, "full_url") else req)
            if str(requested_urls[-1]).endswith("manifest.json"):
                return _FakeHttpResponse({"dataset_name": "财报基准集"})
            return _FakeHttpResponse({"sample": "ok"})

        with patch("llm.services.fine_tune_runner_client.request.urlopen", side_effect=fake_urlopen):
            export_dir = materialize_export_bundle(spec=spec, work_dir=work_dir)

        manifest_path = Path(export_dir) / "manifest.json"
        train_path = Path(export_dir) / "train.jsonl"
        self.assertTrue(manifest_path.exists())
        self.assertTrue(train_path.exists())
        self.assertEqual(len(requested_urls), 2)
        self.assertIn("dataset_name", manifest_path.read_text(encoding="utf-8"))

    def test_build_llamafactory_command_maps_training_config_to_cli_args(self):
        from llm.services.fine_tune_runner_client import build_llamafactory_command

        command = build_llamafactory_command(
            spec={
                "training_job": {
                    "strategy": "lora",
                    "base_model_name": "Qwen/Qwen2.5-7B-Instruct",
                    "training_config": {
                        "epochs": 3,
                        "learning_rate": 0.0001,
                        "batch_size": 2,
                        "cutoff_len": 1024,
                    },
                }
            },
            export_dir="/tmp/ft-20260416",
            output_dir="/tmp/ft-20260416/output",
        )

        self.assertEqual(command[:2], ["llamafactory-cli", "train"])
        self.assertIn("--model_name_or_path", command)
        self.assertIn("Qwen/Qwen2.5-7B-Instruct", command)
        self.assertIn("--dataset_dir", command)
        self.assertIn("/tmp/ft-20260416", command)
        self.assertIn("--dataset", command)
        self.assertIn("finmodpro_train", command)
        self.assertIn("--finetuning_type", command)
        self.assertIn("lora", command)
        self.assertIn("--num_train_epochs", command)
        self.assertIn("3", command)
        self.assertIn("--learning_rate", command)
        self.assertIn("0.0001", command)
        self.assertIn("--per_device_train_batch_size", command)
        self.assertIn("2", command)

    def test_report_runner_status_posts_callback_payload(self):
        from llm.services.fine_tune_runner_client import report_runner_status

        captured_request = {}

        def fake_urlopen(req, timeout=30):
            captured_request["url"] = req.full_url
            captured_request["token"] = req.headers.get("X-fine-tune-token")
            captured_request["method"] = req.get_method()
            captured_request["payload"] = json.loads(req.data.decode("utf-8"))
            return _FakeHttpResponse({"code": 0, "message": "ok", "data": {"fine_tune_run": {"status": "running"}}})

        with patch("llm.services.fine_tune_runner_client.request.urlopen", side_effect=fake_urlopen):
            response = report_runner_status(
                api_base_url="http://127.0.0.1:8000",
                fine_tune_run_id=7,
                token="ftcb_test_token",
                payload={"status": "running", "external_job_id": "runner-local-7"},
            )

        self.assertEqual(captured_request["url"], "http://127.0.0.1:8000/api/ops/fine-tunes/7/callback/")
        self.assertEqual(captured_request["token"], "ftcb_test_token")
        self.assertEqual(captured_request["method"], "POST")
        self.assertEqual(captured_request["payload"]["status"], "running")
        self.assertEqual(response["fine_tune_run"]["status"], "running")

    def test_run_remote_fine_tune_dry_run_skips_execution_and_callbacks(self):
        from llm.services.fine_tune_runner_client import run_remote_fine_tune

        spec = {
            "run_key": "ft-20260416",
            "training_job": {
                "strategy": "lora",
                "base_model_name": "Qwen/Qwen2.5-7B-Instruct",
                "training_config": {"epochs": 3},
            },
            "export_bundle": {"export_path": "/tmp/ft-20260416", "files": []},
        }

        with patch("llm.services.fine_tune_runner_client.fetch_runner_spec", return_value=spec), \
             patch("llm.services.fine_tune_runner_client.materialize_export_bundle", return_value="/tmp/ft-20260416"), \
             patch("llm.services.fine_tune_runner_client.report_runner_status") as mocked_report, \
             patch("llm.services.fine_tune_runner_client.subprocess.run") as mocked_run:
            result = run_remote_fine_tune(
                api_base_url="http://127.0.0.1:8000",
                fine_tune_run_id=7,
                token="ftcb_test_token",
                work_dir="/tmp/runner-workdir",
                dry_run=True,
            )

        self.assertEqual(result["spec"]["run_key"], "ft-20260416")
        mocked_report.assert_not_called()
        mocked_run.assert_not_called()

    def test_run_remote_fine_tune_reports_deployment_metadata_on_success(self):
        from llm.services.fine_tune_runner_client import run_remote_fine_tune

        spec = {
            "run_key": "ft-20260416",
            "training_job": {
                "strategy": "lora",
                "base_model_name": "Qwen/Qwen2.5-7B-Instruct",
                "training_config": {"epochs": 3},
            },
            "export_bundle": {"export_path": "/tmp/ft-20260416", "files": []},
        }

        with patch("llm.services.fine_tune_runner_client.fetch_runner_spec", return_value=spec), \
             patch("llm.services.fine_tune_runner_client.materialize_export_bundle", return_value="/tmp/ft-20260416"), \
             patch("llm.services.fine_tune_runner_client.report_runner_status") as mocked_report, \
             patch("llm.services.fine_tune_runner_client.subprocess.run") as mocked_run:
            result = run_remote_fine_tune(
                api_base_url="http://127.0.0.1:8000",
                fine_tune_run_id=7,
                token="ftcb_test_token",
                work_dir="/tmp/runner-workdir",
                deployment_endpoint="http://127.0.0.1:9000/v1",
                deployment_model_name="finmodpro-ft-chat",
            )

        mocked_run.assert_called_once()
        self.assertEqual(mocked_report.call_count, 2)
        running_payload = mocked_report.call_args_list[0].kwargs["payload"]
        success_payload = mocked_report.call_args_list[1].kwargs["payload"]
        self.assertEqual(running_payload["status"], "running")
        self.assertEqual(success_payload["status"], "succeeded")
        self.assertEqual(success_payload["deployment_endpoint"], "http://127.0.0.1:9000/v1")
        self.assertEqual(success_payload["deployment_model_name"], "finmodpro-ft-chat")
        self.assertEqual(success_payload["artifact_manifest"]["adapter_path"], "/tmp/runner-workdir/ft-20260416/artifacts")
        self.assertEqual(result["callback_payload"]["deployment_model_name"], "finmodpro-ft-chat")


class LiteLLMConfigRenderTests(TestCase):
    def test_rendered_config_includes_generated_alias_entries_before_settings(self):
        from llm.services.litellm_config_render_service import render_litellm_config

        base_config = (
            "model_list:\n"
            "  - model_name: chat-default\n"
            "    litellm_params:\n"
            "      model: deepseek/deepseek-chat\n"
            "litellm_settings:\n"
            "  success_callback: [\"langfuse\"]\n"
        )
        generated_snippet = (
            "model_list:\n"
            "  - model_name: finmodpro-ft-chat\n"
            "    litellm_params:\n"
            "      model: openai/finmodpro-ft-chat\n"
            "      api_base: http://127.0.0.1:9000/v1\n"
        )

        rendered = render_litellm_config(base_config=base_config, generated_snippets=[generated_snippet])

        self.assertIn("model_name: chat-default", rendered)
        self.assertIn("model_name: finmodpro-ft-chat", rendered)
        self.assertIn("api_base: http://127.0.0.1:9000/v1", rendered)
        self.assertLess(rendered.index("model_name: finmodpro-ft-chat"), rendered.index("litellm_settings:"))

    def test_build_rendered_litellm_config_writes_output_file(self):
        from llm.services.litellm_config_render_service import build_rendered_litellm_config

        temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, temp_dir, True)
        base_path = Path(temp_dir) / "base.yaml"
        generated_root = Path(temp_dir) / "generated"
        output_path = Path(temp_dir) / "rendered.yaml"
        generated_root.mkdir(parents=True, exist_ok=True)

        base_path.write_text(
            "model_list:\n"
            "  - model_name: chat-default\n"
            "    litellm_params:\n"
            "      model: deepseek/deepseek-chat\n"
            "litellm_settings:\n"
            "  success_callback: [\"langfuse\"]\n",
            encoding="utf-8",
        )
        (generated_root / "ft-1.yaml").write_text(
            "model_list:\n"
            "  - model_name: finmodpro-ft-chat\n"
            "    litellm_params:\n"
            "      model: openai/finmodpro-ft-chat\n"
            "      api_base: http://127.0.0.1:9000/v1\n",
            encoding="utf-8",
        )

        result = build_rendered_litellm_config(
            base_config_path=base_path,
            generated_root=generated_root,
            output_path=output_path,
        )

        self.assertEqual(result["generated_count"], 1)
        self.assertTrue(output_path.exists())
        rendered = output_path.read_text(encoding="utf-8")
        self.assertIn("model_name: finmodpro-ft-chat", rendered)
