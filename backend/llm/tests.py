import json
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from django.contrib.auth.models import Group
from django.test import TestCase
from django.test import Client, override_settings

from common.exceptions import UpstreamRateLimitError, UpstreamServiceError
from authentication.models import User
from authentication.services.jwt_service import generate_access_token
from llm.models import EvalRecord, ModelConfig
from llm.services.model_config_service import get_active_model_config
from llm.services.prompt_service import render_prompt
from llm.services.providers.ollama_provider import (
    OllamaChatProvider,
    OllamaEmbeddingProvider,
)
from llm.services.runtime_service import get_chat_provider, get_embedding_provider
from rbac.services.rbac_service import ROLE_ADMIN, ROLE_MEMBER, seed_roles_and_permissions


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
                "is_active",
                "created_at",
                "updated_at",
            },
        )
        self.assertEqual(first_row["id"], get_active_model_config(ModelConfig.CAPABILITY_CHAT).id)
        self.assertTrue(first_row["is_active"])
        self.assertEqual(payload["data"]["model_configs"][1]["id"], replacement.id)


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
                "is_active",
                "created_at",
                "updated_at",
            },
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
