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
                    "status": "running",
                    "artifact_path": "/artifacts/runs/ft-20260413",
                    "metrics": {"loss": 0.12, "f1_score": 0.91},
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
        self.assertEqual(payload["data"]["fine_tune_run"]["status"], "running")
        self.assertEqual(payload["data"]["fine_tune_run"]["metrics"]["f1_score"], 0.91)
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
                "artifact_path",
                "metrics",
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
