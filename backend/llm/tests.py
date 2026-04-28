import json
import os
import shutil
import subprocess
import sys
import tempfile
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from django.conf import settings
from django.contrib.auth.models import Group
from django.test import TestCase
from django.test import Client, override_settings

from common.exceptions import ServiceConfigurationError, UpstreamRateLimitError, UpstreamServiceError
from authentication.models import User
from authentication.services.jwt_service import generate_access_token
from llm.models import EvalRecord, FineTuneRun, LiteLLMSyncEvent, ModelConfig, ModelInvocationLog
from llm.services import model_config_command_service
from llm.services.model_config_command_service import migrate_active_configs_to_litellm
from llm.services.model_config_service import get_active_model_config
from llm.services.fine_tune_service import create_fine_tune_run
from llm.services.prompt_service import load_prompt_template, render_prompt
from llm.services.litellm_alias_service import sync_litellm_route_for_config
from llm.services.litellm_config_render_service import build_rendered_litellm_config
from llm.services.providers.litellm_provider import LiteLLMChatProvider, LiteLLMEmbeddingProvider
from llm.services.runtime_service import (
    get_chat_provider,
    get_embedding_provider,
    get_rerank_provider,
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
        self.assertEqual(payload["data"]["total"], 5)
        self.assertEqual(
            [item["name"] for item in payload["data"]["model_configs"]],
            [
                "default-chat",
                "qwen-chat",
                "default-embedding",
                "default-dashscope-embedding",
                "default-dashscope-rerank",
            ],
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
                "alias",
                "upstream_provider",
                "upstream_model",
                "fallback_aliases",
                "weight",
                "input_price_per_million",
                "output_price_per_million",
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
                "alias",
                "upstream_provider",
                "upstream_model",
                "fallback_aliases",
                "weight",
                "input_price_per_million",
                "output_price_per_million",
            },
        )

    def test_delete_requires_authentication(self):
        model_config = ModelConfig.objects.create(
            name="litellm-delete-unauth",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="chat-delete-unauth",
            endpoint="http://localhost:4000",
            options={},
            is_active=False,
        )

        response = self.client.delete(f"/api/ops/model-configs/{model_config.id}/")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {"code": 401, "message": "未认证。", "data": {}},
        )

    def test_delete_rejects_active_model_config(self):
        active_model = get_active_model_config(ModelConfig.CAPABILITY_CHAT)

        response = self.client.delete(
            f"/api/ops/model-configs/{active_model.id}/",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "启用中的模型配置不能删除。")

    def test_delete_removes_inactive_model_config(self):
        model_config = ModelConfig.objects.create(
            name="litellm-delete-inactive",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="chat-delete-inactive",
            endpoint="http://localhost:4000",
            options={"litellm": {"upstream_provider": "openai", "upstream_model": "gpt-4o"}},
            is_active=False,
        )

        response = self.client.delete(
            f"/api/ops/model-configs/{model_config.id}/",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"code": 0, "message": "ok", "data": {"deleted": True}})
        self.assertFalse(ModelConfig.objects.filter(id=model_config.id).exists())

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
                "runner_server_id",
                "runner_server_name",
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

    def test_admin_can_configure_remote_runner_server_and_bind_it_to_fine_tune_runs(self):
        create_server_response = self.client.post(
            "/api/ops/fine-tune-servers/",
            data=json.dumps(
                {
                    "name": "gpu-runner-a",
                    "base_url": "https://gpu-runner.example",
                    "auth_token": "runner-secret-token",
                    "default_work_dir": "/srv/llamafactory/jobs",
                    "is_enabled": True,
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(create_server_response.status_code, 201)
        server_payload = create_server_response.json()["data"]["fine_tune_server"]
        self.assertEqual(server_payload["name"], "gpu-runner-a")
        self.assertEqual(server_payload["base_url"], "https://gpu-runner.example")
        self.assertTrue(server_payload["has_auth_token"])
        self.assertEqual(server_payload["auth_token_masked"], "runner******oken")

        base_model = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
        create_run_response = self.client.post(
            "/api/ops/fine-tunes/",
            data=json.dumps(
                {
                    "base_model_id": base_model.id,
                    "dataset_name": "财报基准集",
                    "dataset_version": "2026Q3",
                    "strategy": "lora",
                    "runner_server_id": server_payload["id"],
                    "training_config": {"epochs": 2},
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(create_run_response.status_code, 201)
        run_payload = create_run_response.json()["data"]["fine_tune_run"]
        self.assertEqual(run_payload["runner_server_id"], server_payload["id"])
        self.assertEqual(run_payload["runner_server_name"], "gpu-runner-a")

        runner_spec_response = self.client.get(
            f"/api/ops/fine-tunes/{run_payload['id']}/runner-spec/",
            HTTP_X_FINE_TUNE_TOKEN=run_payload["callback_token"],
        )
        self.assertEqual(runner_spec_response.status_code, 200)
        runner_spec = runner_spec_response.json()["data"]
        self.assertEqual(runner_spec["runner_target"]["server_id"], server_payload["id"])
        self.assertEqual(runner_spec["runner_target"]["name"], "gpu-runner-a")
        self.assertEqual(runner_spec["runner_target"]["base_url"], "https://gpu-runner.example")
        self.assertEqual(runner_spec["runner_target"]["default_work_dir"], "/srv/llamafactory/jobs")

    @patch("urllib.request.urlopen")
    def test_dispatch_endpoint_submits_job_spec_to_remote_runner(self, mock_urlopen):
        mock_urlopen.return_value = _FakeHttpResponse(
            {
                "code": 0,
                "data": {
                    "job_id": "gpu-job-001",
                    "status": "queued",
                    "runner_name": "gpu-runner-a",
                },
            }
        )
        create_server_response = self.client.post(
            "/api/ops/fine-tune-servers/",
            data=json.dumps(
                {
                    "name": "gpu-runner-a",
                    "base_url": "https://gpu-runner.example",
                    "auth_token": "runner-secret-token",
                    "default_work_dir": "/srv/llamafactory/jobs",
                    "is_enabled": True,
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )
        server_id = create_server_response.json()["data"]["fine_tune_server"]["id"]
        base_model = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
        create_run_response = self.client.post(
            "/api/ops/fine-tunes/",
            data=json.dumps(
                {
                    "base_model_id": base_model.id,
                    "dataset_name": "财报基准集",
                    "dataset_version": "2026Q3",
                    "strategy": "lora",
                    "runner_server_id": server_id,
                    "training_config": {"epochs": 2, "learning_rate": 0.0001},
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )
        run_id = create_run_response.json()["data"]["fine_tune_run"]["id"]

        dispatch_response = self.client.post(
            f"/api/ops/fine-tunes/{run_id}/dispatch/",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(dispatch_response.status_code, 200)
        payload = dispatch_response.json()["data"]
        self.assertEqual(payload["dispatch"]["job_id"], "gpu-job-001")
        self.assertEqual(payload["fine_tune_run"]["external_job_id"], "gpu-job-001")
        self.assertEqual(payload["fine_tune_run"]["runner_name"], "gpu-runner-a")

        request_obj = mock_urlopen.call_args.args[0]
        self.assertEqual(request_obj.full_url, "https://gpu-runner.example/api/v1/fine-tune-jobs")
        self.assertEqual(request_obj.headers["Authorization"], "Bearer runner-secret-token")
        remote_payload = json.loads(request_obj.data.decode("utf-8"))
        self.assertEqual(remote_payload["run_key"], payload["fine_tune_run"]["run_key"])
        self.assertTrue(remote_payload["platform"]["api_base_url"].startswith("http://testserver"))
        self.assertEqual(remote_payload["runner_target"]["default_work_dir"], "/srv/llamafactory/jobs")
        self.assertEqual(remote_payload["training_job"]["framework"], "llamafactory")
        self.assertEqual(remote_payload["callback"]["token_header"], "X-Fine-Tune-Token")
        self.assertTrue(remote_payload["callback"]["token"].startswith("ftcb_"))


class LiteLLMGatewayAuditModelTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()

        self.admin_user = User.objects.create_user(
            username="audit-admin",
            password="secret123",
            email="audit-admin@example.com",
        )
        self.admin_user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.admin_access_token = generate_access_token(self.admin_user)

    def test_model_config_list_includes_litellm_route_fields(self):
        model = ModelConfig.objects.create(
            name="chat-default",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="chat-default",
            endpoint="http://localhost:4000",
            options={
                "litellm": {
                    "upstream_provider": "openai",
                    "upstream_model": "gpt-4o",
                    "fallback_aliases": ["chat-backup"],
                    "weight": 1,
                }
            },
            is_active=True,
        )

        response = self.client.get(
            "/api/ops/model-configs/",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        row = next(
            (item for item in response.json()["data"]["model_configs"] if item["id"] == model.id),
            None,
        )
        self.assertIsNotNone(row, "Expected LiteLLM model config row not found in response")
        self.assertEqual(row["alias"], "chat-default")
        self.assertEqual(row["upstream_provider"], "openai")
        self.assertEqual(row["upstream_model"], "gpt-4o")
        self.assertEqual(row["fallback_aliases"], ["chat-backup"])
        self.assertEqual(row["weight"], 1)
        self.assertEqual(row["input_price_per_million"], 0)
        self.assertEqual(row["output_price_per_million"], 0)

    def test_model_config_list_includes_litellm_pricing_fields(self):
        model = ModelConfig.objects.create(
            name="chat-priced",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="chat-priced",
            endpoint="http://localhost:4000",
            options={
                "litellm": {
                    "upstream_provider": "openai",
                    "upstream_model": "gpt-4o-mini",
                    "input_price_per_million": 0.15,
                    "output_price_per_million": 0.6,
                }
            },
            is_active=False,
        )

        response = self.client.get(
            "/api/ops/model-configs/",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        row = next(
            (item for item in response.json()["data"]["model_configs"] if item["id"] == model.id),
            None,
        )
        self.assertIsNotNone(row, "Expected LiteLLM model config row not found in response")
        self.assertEqual(row["input_price_per_million"], 0.15)
        self.assertEqual(row["output_price_per_million"], 0.6)

    def test_model_invocation_log_stage_constants_and_choices(self):
        """STAGE_* constants must match their string values and STAGE_CHOICES must list all three."""
        self.assertEqual(ModelInvocationLog.STAGE_ROUTING, "routing")
        self.assertEqual(ModelInvocationLog.STAGE_FALLBACK, "fallback")
        self.assertEqual(ModelInvocationLog.STAGE_DIRECT, "direct")

        choice_values = [v for v, _ in ModelInvocationLog.STAGE_CHOICES]
        self.assertIn("routing", choice_values)
        self.assertIn("fallback", choice_values)
        self.assertIn("direct", choice_values)
        self.assertEqual(len(choice_values), 3)

    def test_model_invocation_log_stage_stored_and_retrieved(self):
        """A log created with a known stage constant round-trips correctly."""
        model = ModelConfig.objects.create(
            name="chat-stage-test",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="gpt-4o",
            endpoint="http://localhost:4000",
        )
        log = ModelInvocationLog.objects.create(
            model_config=model,
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_LITELLM,
            alias="chat-stage-test",
            stage=ModelInvocationLog.STAGE_FALLBACK,
            status=ModelInvocationLog.STATUS_SUCCESS,
            latency_ms=50,
            request_tokens=5,
            response_tokens=10,
        )

        fetched = ModelInvocationLog.objects.get(pk=log.pk)
        self.assertEqual(fetched.stage, ModelInvocationLog.STAGE_FALLBACK)

    def test_model_invocation_log_stage_defaults_to_blank(self):
        """Omitting stage should produce an empty string (unclassified)."""
        model = ModelConfig.objects.create(
            name="chat-stage-blank",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="gpt-4o",
            endpoint="http://localhost:4000",
        )
        log = ModelInvocationLog.objects.create(
            model_config=model,
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_LITELLM,
            alias="chat-stage-blank",
            status=ModelInvocationLog.STATUS_SUCCESS,
            latency_ms=10,
            request_tokens=1,
            response_tokens=2,
        )
        self.assertEqual(log.stage, "")

    def test_model_invocation_log_ordering_most_recent_first(self):
        """ModelInvocationLog Meta ordering must return newer records before older ones."""
        model = ModelConfig.objects.create(
            name="chat-order-test",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="gpt-4o",
            endpoint="http://localhost:4000",
        )
        first = ModelInvocationLog.objects.create(
            model_config=model,
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_LITELLM,
            alias="order-a",
            status=ModelInvocationLog.STATUS_SUCCESS,
            latency_ms=10,
            request_tokens=1,
            response_tokens=1,
        )
        second = ModelInvocationLog.objects.create(
            model_config=model,
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_LITELLM,
            alias="order-b",
            status=ModelInvocationLog.STATUS_SUCCESS,
            latency_ms=10,
            request_tokens=1,
            response_tokens=1,
        )

        ids = list(
            ModelInvocationLog.objects.filter(pk__in=[first.pk, second.pk]).values_list("pk", flat=True)
        )
        self.assertEqual(ids[0], second.pk, "Most recent log should appear first")
        self.assertEqual(ids[1], first.pk, "Oldest log should appear last")

    def test_model_invocation_log_persists_trace_and_tokens(self):
        model = ModelConfig.objects.create(
            name="chat-invocation-test",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="gpt-4o",
            endpoint="http://localhost:4000",
            is_active=True,
        )
        log = ModelInvocationLog.objects.create(
            model_config=model,
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_LITELLM,
            alias="chat-default",
            upstream_model="gpt-4o",
            status=ModelInvocationLog.STATUS_SUCCESS,
            latency_ms=420,
            request_tokens=120,
            response_tokens=220,
            trace_id="trace-1",
            request_id="request-1",
        )

        fetched = ModelInvocationLog.objects.get(pk=log.pk)
        self.assertEqual(fetched.alias, "chat-default")
        self.assertEqual(fetched.trace_id, "trace-1")
        self.assertEqual(fetched.request_id, "request-1")
        self.assertEqual(fetched.request_tokens, 120)
        self.assertEqual(fetched.response_tokens, 220)
        self.assertEqual(fetched.latency_ms, 420)
        self.assertEqual(fetched.status, ModelInvocationLog.STATUS_SUCCESS)
        self.assertEqual(fetched.capability, ModelConfig.CAPABILITY_CHAT)
        self.assertEqual(fetched.provider, ModelConfig.PROVIDER_LITELLM)
        self.assertEqual(fetched.upstream_model, "gpt-4o")
        self.assertIsNotNone(fetched.created_at)

    def test_model_invocation_log_survives_model_config_deletion(self):
        model = ModelConfig.objects.create(
            name="chat-to-delete",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="gpt-4o",
            endpoint="http://localhost:4000",
            is_active=False,
        )
        log = ModelInvocationLog.objects.create(
            model_config=model,
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_LITELLM,
            alias="chat-to-delete",
            status=ModelInvocationLog.STATUS_SUCCESS,
            latency_ms=100,
            request_tokens=10,
            response_tokens=20,
            trace_id="trace-del",
        )

        model.delete()

        log.refresh_from_db()
        self.assertIsNone(log.model_config)
        self.assertEqual(log.trace_id, "trace-del")
        self.assertEqual(log.alias, "chat-to-delete")

    def test_litellm_sync_event_status_constants(self):
        self.assertEqual(LiteLLMSyncEvent.STATUS_SUCCESS, "success")
        self.assertEqual(LiteLLMSyncEvent.STATUS_FAILED, "failed")

    def test_litellm_sync_event_creates_with_defaults(self):
        event = LiteLLMSyncEvent.objects.create(status=LiteLLMSyncEvent.STATUS_SUCCESS)

        self.assertEqual(event.status, "success")
        self.assertEqual(event.message, "")
        self.assertEqual(event.checksum, "")
        self.assertIsNone(event.triggered_by)
        self.assertIsNotNone(event.created_at)

    def test_litellm_sync_event_persists_all_fields(self):
        event = LiteLLMSyncEvent.objects.create(
            status=LiteLLMSyncEvent.STATUS_FAILED,
            triggered_by=self.admin_user,
            message="upstream timeout",
            checksum="abc123def456",
        )

        fetched = LiteLLMSyncEvent.objects.get(pk=event.pk)
        self.assertEqual(fetched.status, "failed")
        self.assertEqual(fetched.triggered_by, self.admin_user)
        self.assertEqual(fetched.message, "upstream timeout")
        self.assertEqual(fetched.checksum, "abc123def456")

    def test_litellm_sync_event_ordering_most_recent_first(self):
        first = LiteLLMSyncEvent.objects.create(status=LiteLLMSyncEvent.STATUS_SUCCESS)
        second = LiteLLMSyncEvent.objects.create(status=LiteLLMSyncEvent.STATUS_FAILED)

        ids = list(LiteLLMSyncEvent.objects.filter(pk__in=[first.pk, second.pk]).values_list("pk", flat=True))
        self.assertEqual(ids[0], second.pk)
        self.assertEqual(ids[1], first.pk)

    def test_litellm_sync_event_triggered_by_null_on_user_delete(self):
        temp_user = User.objects.create_user(
            username="temp-sync-user",
            password="secret",
            email="temp-sync@example.com",
        )
        event = LiteLLMSyncEvent.objects.create(
            status=LiteLLMSyncEvent.STATUS_SUCCESS,
            triggered_by=temp_user,
        )

        temp_user.delete()

        event.refresh_from_db()
        self.assertIsNone(event.triggered_by)

    def test_fallback_aliases_non_list_stored_value_serializes_as_empty_list(self):
        """A non-list value stored in options.litellm.fallback_aliases must be coerced to []."""
        model = ModelConfig.objects.create(
            name="chat-bad-aliases",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="chat-bad-aliases",
            endpoint="http://localhost:4000",
            options={"litellm": {"fallback_aliases": "not-a-list"}},
            is_active=False,
        )

        response = self.client.get(
            "/api/ops/model-configs/",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        row = next(
            (item for item in response.json()["data"]["model_configs"] if item["id"] == model.id),
            None,
        )
        self.assertIsNotNone(row, "Expected model config row not found in response")
        self.assertEqual(row["fallback_aliases"], [])

    def test_non_litellm_model_serializer_compat_fields_have_defaults(self):
        """Non-LiteLLM configs expose empty/default values for the LiteLLM compat fields."""
        model = ModelConfig.objects.create(
            name="ollama-compat-defaults",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_OLLAMA,
            model_name="qwen2.5:7b",
            endpoint="http://localhost:11434",
            options={},
            is_active=False,
        )

        response = self.client.get(
            "/api/ops/model-configs/",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        row = next(
            (item for item in response.json()["data"]["model_configs"] if item["id"] == model.id),
            None,
        )
        self.assertIsNotNone(row, "Expected model config row not found in response")
        self.assertEqual(row["alias"], "qwen2.5:7b")
        self.assertEqual(row["upstream_provider"], "")
        self.assertEqual(row["upstream_model"], "")
        self.assertEqual(row["fallback_aliases"], [])
        self.assertEqual(row["weight"], 1)


class ModelInvocationLogIndexTests(TestCase):
    """Pin the composite indexes declared on ModelInvocationLog.Meta."""

    def _index_names(self):
        return {idx.name for idx in ModelInvocationLog._meta.indexes}

    def test_provider_created_at_composite_index_exists(self):
        self.assertIn(
            "llm_invlog_prov_created_idx",
            self._index_names(),
            "Composite index (provider, -created_at) must be declared on ModelInvocationLog",
        )

    def test_provider_created_at_index_fields(self):
        idx = next(
            (i for i in ModelInvocationLog._meta.indexes if i.name == "llm_invlog_prov_created_idx"),
            None,
        )
        self.assertIsNotNone(idx, "Index llm_invlog_prov_created_idx not found")
        self.assertEqual(list(idx.fields), ["provider", "-created_at"])

    def test_all_expected_indexes_present(self):
        expected = {
            "llm_invlog_prov_created_idx",
            "llm_invoclog_cfg_created_idx",
            "llm_invoclog_trace_created_idx",
            "llm_invoclog_reqid_created_idx",
        }
        self.assertTrue(
            expected.issubset(self._index_names()),
            f"Missing indexes: {expected - self._index_names()}",
        )


class LiteLLMGatewayCommandServiceTests(TestCase):
    def setUp(self):
        seed_roles_and_permissions()
        self.admin_user = User.objects.create_user(
            username="cmd-admin",
            password="secret123",
            email="cmd-admin@example.com",
        )
        self.admin_user.groups.add(Group.objects.get(name=ROLE_ADMIN))

    def test_migrate_to_litellm_creates_active_chat_and_embedding_routes(self):
        # Seed data (from migration 0001) provides default-chat (Ollama, active)
        # and default-embedding (Ollama, active).
        result = migrate_active_configs_to_litellm(triggered_by=self.admin_user)

        self.assertEqual(result["migrated_capabilities"], ["chat", "embedding", "rerank"])
        self.assertTrue(ModelConfig.objects.filter(provider="litellm", capability="chat", is_active=True).exists())
        self.assertTrue(ModelConfig.objects.filter(provider="litellm", capability="rerank", is_active=True).exists())
        self.assertTrue(LiteLLMSyncEvent.objects.filter(status="success").exists())

    def test_migrate_to_litellm_copies_source_chat_options_and_upstream_metadata(self):
        active_chat = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
        active_chat.provider = ModelConfig.PROVIDER_DEEPSEEK
        active_chat.name = "deepseek-primary"
        active_chat.model_name = "deepseek-chat"
        active_chat.endpoint = "https://api.deepseek.com/v1"
        active_chat.options = {
            "api_key": "sk-deepseek",
            "temperature": 0.2,
            "max_tokens": 512,
        }
        active_chat.save()

        migrate_active_configs_to_litellm(triggered_by=self.admin_user)

        route = ModelConfig.objects.get(provider="litellm", capability="chat", is_active=True)
        self.assertEqual(route.endpoint, settings.LITELLM_GATEWAY_URL)
        self.assertEqual(route.options["api_key"], "sk-deepseek")
        self.assertEqual(route.options["temperature"], 0.2)
        self.assertEqual(route.options["max_tokens"], 512)
        self.assertEqual(route.options["api_base"], "https://api.deepseek.com/v1")
        self.assertEqual(route.options["litellm"]["upstream_provider"], "deepseek")
        self.assertEqual(route.options["litellm"]["upstream_model"], "deepseek/deepseek-chat")

    def test_migrate_to_litellm_reuses_existing_active_litellm_route_without_double_wrapping(self):
        route = ModelConfig.objects.create(
            name="litellm-existing-chat",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="deepseek-chat",
            endpoint=settings.LITELLM_GATEWAY_URL,
            options={
                "api_key": "sk-deepseek",
                "api_base": "https://api.deepseek.com/v1",
                "litellm": {
                    "upstream_provider": "deepseek",
                    "upstream_model": "deepseek/deepseek-chat",
                },
            },
            is_active=True,
        )

        migrate_active_configs_to_litellm(triggered_by=self.admin_user)

        route.refresh_from_db()
        self.assertTrue(route.is_active)
        self.assertFalse(
            ModelConfig.objects.filter(
                capability=ModelConfig.CAPABILITY_CHAT,
                provider=ModelConfig.PROVIDER_LITELLM,
                name="litellm-litellm-existing-chat",
            ).exists()
        )

    def test_migrate_to_litellm_repairs_incomplete_active_litellm_route_from_original_source(self):
        source_chat = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
        source_chat.provider = ModelConfig.PROVIDER_DEEPSEEK
        source_chat.name = "deepseek-primary"
        source_chat.model_name = "deepseek-chat"
        source_chat.endpoint = "https://api.deepseek.com/v1"
        source_chat.options = {
            "api_key": "sk-deepseek",
            "temperature": 0.2,
        }
        source_chat.save()

        broken_route = ModelConfig.objects.create(
            name="litellm-deepseek-primary",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="deepseek-chat",
            endpoint=settings.LITELLM_GATEWAY_URL,
            options={},
            is_active=True,
        )

        migrate_active_configs_to_litellm(triggered_by=self.admin_user)

        broken_route.refresh_from_db()
        self.assertTrue(broken_route.is_active)
        self.assertEqual(broken_route.options["api_key"], "sk-deepseek")
        self.assertFalse(
            ModelConfig.objects.filter(
                capability=ModelConfig.CAPABILITY_CHAT,
                provider=ModelConfig.PROVIDER_LITELLM,
                name="litellm-litellm-deepseek-primary",
            ).exists()
        )

    def test_migrate_to_litellm_maps_dashscope_embedding_to_openai_compatible_upstream(self):
        active_embedding = get_active_model_config(ModelConfig.CAPABILITY_EMBEDDING)
        active_embedding.provider = ModelConfig.PROVIDER_DASHSCOPE
        active_embedding.name = "dashscope-embed"
        active_embedding.model_name = "text-embedding-v4"
        active_embedding.endpoint = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        active_embedding.options = {"api_key": "sk-dashscope"}
        active_embedding.save()

        migrate_active_configs_to_litellm(triggered_by=self.admin_user)

        route = ModelConfig.objects.get(provider="litellm", capability="embedding", is_active=True)
        self.assertEqual(route.options["litellm"]["upstream_provider"], "dashscope")
        self.assertEqual(route.options["litellm"]["upstream_model"], "openai/text-embedding-v4")

    def test_migrate_to_litellm_repairs_stale_dashscope_embedding_prefix_on_existing_route(self):
        route = ModelConfig.objects.create(
            name="litellm-existing-embed",
            capability=ModelConfig.CAPABILITY_EMBEDDING,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="text-embedding-v4",
            endpoint=settings.LITELLM_GATEWAY_URL,
            options={
                "api_key": "sk-dashscope",
                "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "litellm": {
                    "upstream_provider": "dashscope",
                    "upstream_model": "dashscope/text-embedding-v4",
                },
            },
            is_active=True,
        )

        migrate_active_configs_to_litellm(triggered_by=self.admin_user)

        route.refresh_from_db()
        self.assertEqual(
            route.options["litellm"]["upstream_model"],
            "openai/text-embedding-v4",
        )

    def test_migrate_to_litellm_creates_active_rerank_route(self):
        active_rerank = get_active_model_config(ModelConfig.CAPABILITY_RERANK)
        active_rerank.provider = ModelConfig.PROVIDER_DASHSCOPE
        active_rerank.name = "dashscope-rerank"
        active_rerank.model_name = "qwen3-vl-rerank"
        active_rerank.endpoint = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
        active_rerank.options = {"api_key": "sk-dashscope"}
        active_rerank.save()

        result = migrate_active_configs_to_litellm(triggered_by=self.admin_user)

        self.assertIn(ModelConfig.CAPABILITY_RERANK, result["migrated_capabilities"])
        route = ModelConfig.objects.get(
            provider=ModelConfig.PROVIDER_LITELLM,
            capability=ModelConfig.CAPABILITY_RERANK,
            is_active=True,
        )
        self.assertEqual(route.model_name, "qwen3-vl-rerank")
        self.assertEqual(
            route.options["litellm"]["upstream_model"],
            "openai/qwen3-vl-rerank",
        )

    def test_migrate_to_litellm_prunes_stale_nested_routes_when_canonical_route_exists(self):
        active_embedding = get_active_model_config(ModelConfig.CAPABILITY_EMBEDDING)
        active_embedding.provider = ModelConfig.PROVIDER_DASHSCOPE
        active_embedding.name = "dashscope-embed-primary"
        active_embedding.model_name = "text-embedding-v4"
        active_embedding.endpoint = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        active_embedding.options = {"api_key": "sk-dashscope"}
        active_embedding.save()

        canonical_route = ModelConfig.objects.create(
            name="litellm-dashscope-embed-primary",
            capability=ModelConfig.CAPABILITY_EMBEDDING,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="text-embedding-v4",
            endpoint=settings.LITELLM_GATEWAY_URL,
            options={
                "api_key": "sk-dashscope",
                "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "litellm": {
                    "upstream_provider": "dashscope",
                    "upstream_model": "openai/text-embedding-v4",
                },
            },
            is_active=True,
        )
        stale_nested_route = ModelConfig.objects.create(
            name="litellm-litellm-dashscope-embed-primary",
            capability=ModelConfig.CAPABILITY_EMBEDDING,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="text-embedding-v4",
            endpoint=settings.LITELLM_GATEWAY_URL,
            options={},
            is_active=False,
        )

        migrate_active_configs_to_litellm(triggered_by=self.admin_user)

        canonical_route.refresh_from_db()
        self.assertTrue(canonical_route.is_active)
        self.assertFalse(ModelConfig.objects.filter(id=stale_nested_route.id).exists())

    @patch("urllib.request.urlopen")
    def test_litellm_provider_records_successful_chat_invocation(self, mock_urlopen):
        mock_urlopen.return_value = _FakeHttpResponse({
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7},
        })
        model_config = ModelConfig.objects.create(
            name="litellm-chat-test",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="chat-default",
            endpoint="http://localhost:4000",
            options={"api_key": "sk-test"},
            is_active=True,
        )
        provider = LiteLLMChatProvider(
            endpoint="http://localhost:4000",
            model_name="chat-default",
            options={"api_key": "sk-test"},
            model_config=model_config,
        )

        provider.chat(messages=[{"role": "user", "content": "hi"}], trace_id="trace-1", request_id="request-1")

        log = ModelInvocationLog.objects.get(trace_id="trace-1")
        self.assertEqual(log.request_tokens, 11)
        self.assertEqual(log.response_tokens, 7)
        self.assertEqual(log.status, "success")
        self.assertEqual(log.request_id, "request-1")
        self.assertEqual(log.model_config, model_config)

    @patch("urllib.request.urlopen")
    @override_settings(LITELLM_MASTER_KEY="master-key")
    def test_litellm_provider_uses_configured_gateway_master_key(self, mock_urlopen):
        mock_urlopen.return_value = _FakeHttpResponse({
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        })
        provider = LiteLLMChatProvider(
            endpoint="http://localhost:4000",
            model_name="chat-default",
            options={"api_key": "upstream-key"},
        )

        provider.chat(messages=[{"role": "user", "content": "hi"}])

        request_obj = mock_urlopen.call_args.args[0]
        self.assertEqual(request_obj.headers["Authorization"], "Bearer master-key")

    @patch("urllib.request.urlopen")
    def test_litellm_provider_records_failed_chat_invocation(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            url="http://localhost:4000/v1/chat/completions",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=BytesIO(b"server error"),
        )
        model_config = ModelConfig.objects.create(
            name="litellm-chat-fail-test",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="chat-fail",
            endpoint="http://localhost:4000",
            options={"api_key": "sk-test"},
            is_active=False,
        )
        provider = LiteLLMChatProvider(
            endpoint="http://localhost:4000",
            model_name="chat-fail",
            options={"api_key": "sk-test"},
            model_config=model_config,
        )

        with self.assertRaises(Exception):
            provider.chat(messages=[{"role": "user", "content": "hi"}], trace_id="trace-fail", request_id="req-fail")

        log = ModelInvocationLog.objects.get(trace_id="trace-fail")
        self.assertEqual(log.status, "failed")
        self.assertEqual(log.model_config, model_config)

    @patch("urllib.request.urlopen")
    def test_litellm_embedding_provider_records_successful_invocation(self, mock_urlopen):
        mock_urlopen.return_value = _FakeHttpResponse({
            "data": [{"embedding": [0.1, 0.2, 0.3]}],
            "usage": {"prompt_tokens": 5, "total_tokens": 5},
        })
        model_config = ModelConfig.objects.create(
            name="litellm-embed-test",
            capability=ModelConfig.CAPABILITY_EMBEDDING,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="embed-default",
            endpoint="http://localhost:4000",
            options={"api_key": "sk-test"},
            is_active=True,
        )
        provider = LiteLLMEmbeddingProvider(
            endpoint="http://localhost:4000",
            model_name="embed-default",
            options={"api_key": "sk-test"},
            model_config=model_config,
        )

        provider.embed(texts=["hello world"], trace_id="embed-trace-1", request_id="embed-req-1")

        log = ModelInvocationLog.objects.get(trace_id="embed-trace-1")
        self.assertEqual(log.capability, "embedding")
        self.assertEqual(log.request_tokens, 5)
        self.assertEqual(log.response_tokens, 0)
        self.assertEqual(log.status, "success")
        self.assertEqual(log.request_id, "embed-req-1")
        self.assertEqual(log.model_config, model_config)

    @patch("urllib.request.urlopen")
    def test_litellm_embedding_provider_sends_float_encoding_format(self, mock_urlopen):
        mock_urlopen.return_value = _FakeHttpResponse({
            "data": [{"embedding": [0.1, 0.2, 0.3]}],
            "usage": {"prompt_tokens": 5, "total_tokens": 5},
        })
        provider = LiteLLMEmbeddingProvider(
            endpoint="http://localhost:4000",
            model_name="embed-default",
            options={"api_key": "sk-test"},
        )

        provider.embed(texts=["hello world"])

        request_obj = mock_urlopen.call_args.args[0]
        payload = json.loads(request_obj.data.decode("utf-8"))
        self.assertEqual(payload["encoding_format"], "float")

    @patch("urllib.request.urlopen")
    def test_litellm_embedding_provider_posts_multiple_texts_in_single_request(self, mock_urlopen):
        mock_urlopen.return_value = _FakeHttpResponse({
            "data": [
                {"embedding": [0.1, 0.2, 0.3]},
                {"embedding": [0.4, 0.5, 0.6]},
            ],
            "usage": {"prompt_tokens": 8, "total_tokens": 8},
        })
        provider = LiteLLMEmbeddingProvider(
            endpoint="http://localhost:4000",
            model_name="embed-default",
            options={"api_key": "sk-test"},
        )

        vectors = provider.embed(texts=["hello", "world"])

        self.assertEqual(mock_urlopen.call_count, 1)
        request_obj = mock_urlopen.call_args.args[0]
        payload = json.loads(request_obj.data.decode("utf-8"))
        self.assertEqual(payload["input"], ["hello", "world"])
        self.assertEqual(vectors, [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])

    @patch("urllib.request.urlopen")
    def test_litellm_embedding_provider_records_failed_invocation(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            url="http://localhost:4000/v1/embeddings",
            code=429,
            msg="Too Many Requests",
            hdrs={"Retry-After": "5"},
            fp=BytesIO(b"rate limited"),
        )
        model_config = ModelConfig.objects.create(
            name="litellm-embed-fail-test",
            capability=ModelConfig.CAPABILITY_EMBEDDING,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="embed-fail",
            endpoint="http://localhost:4000",
            options={"api_key": "sk-test"},
            is_active=False,
        )
        provider = LiteLLMEmbeddingProvider(
            endpoint="http://localhost:4000",
            model_name="embed-fail",
            options={"api_key": "sk-test"},
            model_config=model_config,
        )

        with self.assertRaises(Exception):
            provider.embed(texts=["hi"], trace_id="embed-fail-trace", request_id="embed-fail-req")

        log = ModelInvocationLog.objects.get(trace_id="embed-fail-trace")
        self.assertEqual(log.status, "failed")
        self.assertEqual(log.model_config, model_config)

    @patch("urllib.request.urlopen")
    def test_get_rerank_provider_supports_active_litellm_route(self, mock_urlopen):
        mock_urlopen.return_value = _FakeHttpResponse({
            "results": [
                {"index": 1, "relevance_score": 0.91},
                {"index": 0, "relevance_score": 0.55},
            ],
        })
        ModelConfig.objects.filter(capability=ModelConfig.CAPABILITY_RERANK).update(is_active=False)
        ModelConfig.objects.create(
            name="litellm-rerank-test",
            capability=ModelConfig.CAPABILITY_RERANK,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="rerank-default",
            endpoint="http://localhost:4000",
            options={
                "api_key": "sk-test",
                "litellm": {"upstream_model": "openai/qwen-rerank"},
            },
            is_active=True,
        )

        provider = get_rerank_provider()
        result = provider.rerank(
            query="capital of france",
            documents=["Berlin is in Germany.", "Paris is in France."],
            top_n=1,
        )

        self.assertEqual(result, [{"index": 1, "relevance_score": 0.91}, {"index": 0, "relevance_score": 0.55}])
        request_obj = mock_urlopen.call_args.args[0]
        self.assertTrue(request_obj.full_url.endswith("/v1/rerank"))

    @patch("urllib.request.urlopen")
    def test_litellm_chat_provider_records_distinct_alias_and_upstream_model(self, mock_urlopen):
        """alias is the route name; upstream_model is resolved from options.litellm.upstream_model."""
        mock_urlopen.return_value = _FakeHttpResponse({
            "choices": [{"message": {"content": "hello"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3},
        })
        model_config = ModelConfig.objects.create(
            name="litellm-route-alias-test",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="my-route-alias",
            endpoint="http://localhost:4000",
            options={
                "api_key": "sk-test",
                "litellm": {"upstream_model": "gpt-4o"},
            },
            is_active=True,
        )
        provider = LiteLLMChatProvider(
            endpoint="http://localhost:4000",
            model_name="my-route-alias",
            options={"api_key": "sk-test", "litellm": {"upstream_model": "gpt-4o"}},
            model_config=model_config,
        )

        provider.chat(messages=[{"role": "user", "content": "hi"}], trace_id="alias-trace", request_id="alias-req")

        log = ModelInvocationLog.objects.get(trace_id="alias-trace")
        self.assertEqual(log.alias, "my-route-alias")
        self.assertEqual(log.upstream_model, "gpt-4o")
        self.assertEqual(log.status, "success")

    @patch("urllib.request.urlopen")
    def test_litellm_embedding_provider_records_distinct_alias_and_upstream_model(self, mock_urlopen):
        """alias is the route name; upstream_model is resolved from options.litellm.upstream_model for embeddings."""
        mock_urlopen.return_value = _FakeHttpResponse({
            "data": [{"embedding": [0.1, 0.2, 0.3]}],
            "usage": {"prompt_tokens": 4, "total_tokens": 4},
        })
        model_config = ModelConfig.objects.create(
            name="litellm-embed-alias-test",
            capability=ModelConfig.CAPABILITY_EMBEDDING,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="my-embed-alias",
            endpoint="http://localhost:4000",
            options={
                "api_key": "sk-test",
                "litellm": {"upstream_model": "text-embedding-3-small"},
            },
            is_active=True,
        )
        provider = LiteLLMEmbeddingProvider(
            endpoint="http://localhost:4000",
            model_name="my-embed-alias",
            options={"api_key": "sk-test", "litellm": {"upstream_model": "text-embedding-3-small"}},
            model_config=model_config,
        )

        provider.embed(texts=["hello"], trace_id="embed-alias-trace", request_id="embed-alias-req")

        log = ModelInvocationLog.objects.get(trace_id="embed-alias-trace")
        self.assertEqual(log.alias, "my-embed-alias")
        self.assertEqual(log.upstream_model, "text-embedding-3-small")
        self.assertEqual(log.capability, "embedding")
        self.assertEqual(log.status, "success")

    @patch("urllib.request.urlopen")
    def test_litellm_chat_provider_does_not_break_on_logging_failure(self, mock_urlopen):
        """A DB error during invocation logging must not break the successful response."""
        mock_urlopen.return_value = _FakeHttpResponse({
            "choices": [{"message": {"content": "fine"}}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 1},
        })
        model_config = ModelConfig.objects.create(
            name="litellm-log-guard-test",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="guard-route",
            endpoint="http://localhost:4000",
            options={"api_key": "sk-test"},
            is_active=True,
        )
        provider = LiteLLMChatProvider(
            endpoint="http://localhost:4000",
            model_name="guard-route",
            options={"api_key": "sk-test"},
            model_config=model_config,
        )

        with patch("llm.services.providers.litellm_provider.record_model_invocation", side_effect=Exception("db error")):
            result = provider.chat(messages=[{"role": "user", "content": "hi"}])

        self.assertEqual(result, "fine")

    @patch("urllib.request.urlopen")
    def test_unsaved_model_config_skips_invocation_logging_entirely(self, mock_urlopen):
        """An unsaved ModelConfig (pk=None) must never call record_model_invocation."""
        mock_urlopen.return_value = _FakeHttpResponse({
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3},
        })
        unsaved_config = ModelConfig(
            name="connection-test-unsaved",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="test-route",
            endpoint="http://localhost:4000",
            options={"api_key": "sk-test"},
        )
        self.assertIsNone(unsaved_config.pk, "ModelConfig must be unsaved (no pk)")
        provider = LiteLLMChatProvider(
            endpoint="http://localhost:4000",
            model_name="test-route",
            options={"api_key": "sk-test"},
            model_config=unsaved_config,
        )

        with patch("llm.services.providers.litellm_provider.record_model_invocation") as mock_log:
            provider.chat(messages=[{"role": "user", "content": "ping"}])

        mock_log.assert_not_called()


# ---------------------------------------------------------------------------
# LiteLLM Gateway Query Service Tests
# ---------------------------------------------------------------------------

class GatewayQueryServiceTests(TestCase):
    """Service-level tests for litellm_gateway_query_service."""

    def setUp(self):
        self.model_config = ModelConfig.objects.create(
            name="gw-chat",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="gw-chat",
            endpoint="http://localhost:4000",
            is_active=True,
            options={
                "api_key": "sk-test",
                "litellm": {
                    "upstream_provider": "openai",
                    "upstream_model": "gpt-4o",
                    "input_price_per_million": 5.0,
                    "output_price_per_million": 15.0,
                },
            },
        )

    def _make_log(self, **kwargs):
        defaults = dict(
            model_config=self.model_config,
            capability="chat",
            alias="gw-chat",
            upstream_model="gpt-4o",
            status=ModelInvocationLog.STATUS_SUCCESS,
            latency_ms=200,
            request_tokens=10,
            response_tokens=5,
        )
        defaults.update(kwargs)
        return ModelInvocationLog.objects.create(**defaults)

    def test_summary_returns_gateway_health_and_traffic(self):
        from llm.services.litellm_gateway_query_service import get_gateway_summary

        self._make_log()
        self._make_log(status=ModelInvocationLog.STATUS_FAILED, error_code="500")

        result = get_gateway_summary()

        self.assertIn("gateway", result)
        self.assertIn("status", result["gateway"])
        self.assertIn("recent_sync", result)
        self.assertIn("traffic", result)
        self.assertGreaterEqual(result["traffic"]["request_count"], 2)
        self.assertGreaterEqual(result["traffic"]["failed_count"], 1)
        self.assertIn("error_rate_pct", result["traffic"])
        self.assertIn("top_models", result)
        self.assertIn("recent_errors", result)

    def test_summary_includes_recent_sync_info(self):
        from llm.services.litellm_gateway_query_service import get_gateway_summary

        LiteLLMSyncEvent.objects.create(status=LiteLLMSyncEvent.STATUS_SUCCESS, message="ok")

        result = get_gateway_summary()

        self.assertIsNotNone(result["recent_sync"])
        self.assertEqual(result["recent_sync"]["status"], "success")

    def test_summary_recent_sync_is_none_when_no_events(self):
        from llm.services.litellm_gateway_query_service import get_gateway_summary

        result = get_gateway_summary()

        self.assertIsNone(result["recent_sync"])

    def test_summary_top_models_ordered_by_count(self):
        from llm.services.litellm_gateway_query_service import get_gateway_summary

        for _ in range(3):
            self._make_log(alias="model-a")
        self._make_log(alias="model-b")

        result = get_gateway_summary()

        aliases = [m["alias"] for m in result["top_models"]]
        self.assertEqual(aliases[0], "model-a")

    def test_get_logs_returns_filtered_rows(self):
        from llm.services.litellm_gateway_query_service import get_logs

        self._make_log(alias="chat-model", status=ModelInvocationLog.STATUS_SUCCESS)
        self._make_log(alias="embed-model", status=ModelInvocationLog.STATUS_FAILED, error_code="503")

        result = get_logs({"model": "chat-model", "status": None, "time": "24h"})

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["logs"][0]["alias"], "chat-model")
        # No raw prompt/response data
        for log in result["logs"]:
            self.assertNotIn("prompt", log)
            self.assertNotIn("response", log)

    def test_get_logs_status_filter(self):
        from llm.services.litellm_gateway_query_service import get_logs

        self._make_log(status=ModelInvocationLog.STATUS_SUCCESS)
        self._make_log(status=ModelInvocationLog.STATUS_FAILED, error_code="503")

        result = get_logs({"model": None, "status": "failed", "time": "24h"})

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["logs"][0]["status"], "failed")

    def test_get_logs_includes_required_fields(self):
        from llm.services.litellm_gateway_query_service import get_logs

        self._make_log(
            alias="gw-chat",
            upstream_model="gpt-4o",
            stage=ModelInvocationLog.STAGE_ROUTING,
            latency_ms=250,
            request_tokens=20,
            response_tokens=10,
            trace_id="trace-123",
            request_id="req-abc",
        )

        result = get_logs({"model": None, "status": None, "time": "24h"})

        log = result["logs"][0]
        for field in ("time", "alias", "upstream_model", "capability", "stage",
                      "latency_ms", "request_tokens", "response_tokens",
                      "status", "error_code", "trace_id", "request_id"):
            self.assertIn(field, log, f"Missing field: {field}")

    def test_get_logs_summary_aggregates_correctly(self):
        from llm.services.litellm_gateway_query_service import get_logs_summary

        self._make_log(latency_ms=100, status=ModelInvocationLog.STATUS_SUCCESS)
        self._make_log(latency_ms=300, status=ModelInvocationLog.STATUS_FAILED, error_code="500")

        result = get_logs_summary({"model": None, "status": None, "time": "24h"})

        self.assertEqual(result["total_requests"], 2)
        self.assertAlmostEqual(result["avg_latency_ms"], 200.0, delta=1.0)
        self.assertAlmostEqual(result["error_rate_pct"], 50.0, delta=0.1)
        self.assertIn("error_breakdown", result)
        self.assertIn("latency_buckets", result)

    def test_get_logs_summary_latency_buckets_structure(self):
        from llm.services.litellm_gateway_query_service import get_logs_summary

        for ms in [50, 150, 600, 1500]:
            self._make_log(latency_ms=ms)

        result = get_logs_summary({"model": None, "status": None, "time": "24h"})

        buckets = result["latency_buckets"]
        self.assertIsInstance(buckets, list)
        self.assertTrue(len(buckets) > 0)
        for bucket in buckets:
            self.assertIn("label", bucket)
            self.assertIn("count", bucket)

    def test_get_trace_returns_ordered_logs(self):
        from llm.services.litellm_gateway_query_service import get_trace

        tid = "trace-xyz"
        self._make_log(trace_id=tid, alias="first-model")
        self._make_log(trace_id=tid, alias="second-model")

        result = get_trace(tid)

        self.assertEqual(result["trace_id"], tid)
        self.assertIsNotNone(result["started_at"])
        self.assertIsNotNone(result["ended_at"])
        self.assertEqual(len(result["logs"]), 2)

    def test_get_trace_returns_none_for_unknown_trace(self):
        from llm.services.litellm_gateway_query_service import get_trace

        result = get_trace("does-not-exist")

        self.assertIsNone(result)

    def test_get_errors_returns_aggregated_types(self):
        from llm.services.litellm_gateway_query_service import get_errors

        self._make_log(status=ModelInvocationLog.STATUS_FAILED, error_code="500")
        self._make_log(status=ModelInvocationLog.STATUS_FAILED, error_code="500")
        self._make_log(status=ModelInvocationLog.STATUS_FAILED, error_code="503")

        result = get_errors()

        self.assertEqual(result["total_failed_requests"], 3)
        self.assertIn("error_types", result)
        codes = {e["error_code"] for e in result["error_types"]}
        self.assertIn("500", codes)
        self.assertIn("503", codes)
        self.assertIn("recent_errors", result)

    def test_get_costs_summary_uses_model_pricing(self):
        from llm.services.litellm_gateway_query_service import get_costs_summary

        self._make_log(request_tokens=1_000_000, response_tokens=500_000)

        result = get_costs_summary({"time": "24h"})

        self.assertIn("total_requests", result)
        self.assertIn("total_request_tokens", result)
        self.assertIn("total_response_tokens", result)
        self.assertIn("estimated_input_cost", result)
        self.assertIn("estimated_output_cost", result)
        self.assertIn("estimated_total_cost", result)
        # 1M input tokens × $5/M = $5.00; 0.5M output × $15/M = $7.50
        self.assertAlmostEqual(result["estimated_input_cost"], 5.0, delta=0.01)
        self.assertAlmostEqual(result["estimated_output_cost"], 7.5, delta=0.01)

    def test_get_costs_summary_no_pricing_yields_zero_cost(self):
        from llm.services.litellm_gateway_query_service import get_costs_summary

        model_no_price = ModelConfig.objects.create(
            name="no-price",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="no-price",
            endpoint="http://localhost:4000",
            options={},
        )
        ModelInvocationLog.objects.create(
            model_config=model_no_price,
            capability="chat",
            alias="no-price",
            upstream_model="cheap-model",
            request_tokens=1_000,
            response_tokens=500,
        )

        result = get_costs_summary({"time": "24h"})

        self.assertEqual(result["estimated_total_cost"], 0.0)

    def test_get_costs_timeseries_returns_points(self):
        from llm.services.litellm_gateway_query_service import get_costs_timeseries

        self._make_log(request_tokens=100, response_tokens=50)

        result = get_costs_timeseries({"time": "24h"})

        self.assertIn("points", result)
        self.assertIsInstance(result["points"], list)
        if result["points"]:
            point = result["points"][0]
            self.assertIn("bucket", point)
            self.assertIn("request_count", point)
            self.assertIn("estimated_cost", point)

    def test_get_costs_models_returns_per_model_breakdown(self):
        from llm.services.litellm_gateway_query_service import get_costs_models

        self._make_log(request_tokens=500_000, response_tokens=250_000)
        other_config = ModelConfig.objects.create(
            name="gw-embed",
            capability=ModelConfig.CAPABILITY_EMBEDDING,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="gw-embed",
            endpoint="http://localhost:4000",
            options={"api_key": "sk-test"},
        )
        ModelInvocationLog.objects.create(
            model_config=other_config,
            capability="embedding",
            alias="gw-embed",
            upstream_model="text-ada-002",
            request_tokens=100_000,
            response_tokens=0,
        )

        result = get_costs_models({"time": "24h"})

        self.assertIn("models", result)
        aliases = [m["alias"] for m in result["models"]]
        self.assertIn("gw-chat", aliases)
        for m in result["models"]:
            self.assertIn("request_share_pct", m)
            self.assertIn("estimated_total_cost", m)

    # ------------------------------------------------------------------
    # Provider-scope regression: non-LiteLLM logs must be excluded
    # ------------------------------------------------------------------

    def _make_non_litellm_log(self, **kwargs):
        """Create an invocation log for a non-LiteLLM provider (e.g. Ollama).

        Uses get_or_create for the ModelConfig so the helper is safe to call
        multiple times within a single test without hitting the
        (capability, name) unique constraint.
        """
        ollama_config, _ = ModelConfig.objects.get_or_create(
            capability=ModelConfig.CAPABILITY_CHAT,
            name="ollama-chat",
            defaults=dict(
                provider=ModelConfig.PROVIDER_OLLAMA,
                model_name="llama3",
                endpoint="http://localhost:11434",
                is_active=False,
            ),
        )
        defaults = dict(
            model_config=ollama_config,
            provider=ModelConfig.PROVIDER_OLLAMA,
            capability="chat",
            alias="ollama-chat",
            upstream_model="llama3",
            status=ModelInvocationLog.STATUS_SUCCESS,
            latency_ms=50,
            request_tokens=5,
            response_tokens=3,
        )
        defaults.update(kwargs)
        return ModelInvocationLog.objects.create(**defaults)

    def test_provider_scope_get_logs_excludes_non_litellm(self):
        """Non-LiteLLM invocation logs must not appear in gateway log results."""
        from llm.services.litellm_gateway_query_service import get_logs

        self._make_log(alias="gw-chat")
        self._make_non_litellm_log()

        result = get_logs({"model": None, "status": None, "time": "24h"})

        aliases = [log["alias"] for log in result["logs"]]
        self.assertNotIn("ollama-chat", aliases)
        self.assertEqual(result["total"], 1)

    def test_provider_scope_get_logs_summary_excludes_non_litellm(self):
        """Non-LiteLLM logs must not inflate gateway aggregate metrics."""
        from llm.services.litellm_gateway_query_service import get_logs_summary

        self._make_log(latency_ms=100)
        self._make_non_litellm_log(latency_ms=9000)

        result = get_logs_summary({"model": None, "status": None, "time": "24h"})

        self.assertEqual(result["total_requests"], 1)
        # avg latency should reflect only the LiteLLM log
        self.assertAlmostEqual(result["avg_latency_ms"], 100.0, delta=1.0)

    def test_provider_scope_get_errors_excludes_non_litellm(self):
        """Non-LiteLLM failed logs must not appear in gateway error totals."""
        from llm.services.litellm_gateway_query_service import get_errors

        self._make_log(status=ModelInvocationLog.STATUS_FAILED, error_code="500")
        self._make_non_litellm_log(status=ModelInvocationLog.STATUS_FAILED, error_code="503")

        result = get_errors()

        self.assertEqual(result["total_failed_requests"], 1)
        codes = {e["error_code"] for e in result["error_types"]}
        self.assertNotIn("503", codes)

    def test_provider_scope_get_costs_summary_excludes_non_litellm(self):
        """Non-LiteLLM logs must not contribute to gateway cost summaries."""
        from llm.services.litellm_gateway_query_service import get_costs_summary

        self._make_log(request_tokens=1_000_000, response_tokens=0)
        self._make_non_litellm_log(request_tokens=999_000_000, response_tokens=999_000_000)

        result = get_costs_summary({"time": "24h"})

        self.assertEqual(result["total_requests"], 1)
        self.assertEqual(result["total_request_tokens"], 1_000_000)

    def test_provider_scope_get_costs_models_excludes_non_litellm(self):
        """Non-LiteLLM logs must not appear in the per-model cost breakdown."""
        from llm.services.litellm_gateway_query_service import get_costs_models

        self._make_log()
        self._make_non_litellm_log()

        result = get_costs_models({"time": "24h"})

        aliases = [m["alias"] for m in result["models"]]
        self.assertNotIn("ollama-chat", aliases)
        self.assertEqual(result["total_requests"], 1)

    def test_provider_scope_get_gateway_summary_excludes_non_litellm(self):
        """Non-LiteLLM logs must not inflate gateway dashboard traffic counts."""
        from llm.services.litellm_gateway_query_service import get_gateway_summary

        self._make_log()
        self._make_non_litellm_log()

        result = get_gateway_summary()

        self.assertEqual(result["traffic"]["request_count"], 1)

    def test_provider_scope_get_trace_excludes_non_litellm(self):
        """A trace lookup must not return logs from non-LiteLLM providers."""
        from llm.services.litellm_gateway_query_service import get_trace

        tid = "shared-trace-001"
        self._make_log(trace_id=tid, alias="gw-chat")
        # Same trace_id, but belongs to a non-LiteLLM provider.
        self._make_non_litellm_log(trace_id=tid)

        result = get_trace(tid)

        self.assertIsNotNone(result, "Trace must be found via its LiteLLM log")
        aliases = [log["alias"] for log in result["logs"]]
        self.assertIn("gw-chat", aliases)
        self.assertNotIn("ollama-chat", aliases)
        self.assertEqual(len(result["logs"]), 1)

    def test_provider_scope_get_costs_timeseries_excludes_non_litellm(self):
        """Non-LiteLLM logs must not appear in the costs time-series points."""
        from llm.services.litellm_gateway_query_service import get_costs_timeseries

        self._make_log(request_tokens=1_000, response_tokens=500)
        # Non-LiteLLM log with huge token counts — must not pollute the series.
        self._make_non_litellm_log(request_tokens=999_000_000, response_tokens=999_000_000)

        result = get_costs_timeseries({"time": "24h"})

        self.assertIn("points", result)
        total_requests = sum(p["request_count"] for p in result["points"])
        self.assertEqual(total_requests, 1, "Only the LiteLLM log should be counted")

    def test_1h_timeseries_distinct_minute_buckets(self):
        """Two logs in the same hour but different minutes must produce
        distinct time-series points when time=1h.

        Regression: the old implementation used TruncHour for the 1h window,
        collapsing all traffic within an hour into a single coarse bucket.
        """
        from datetime import datetime, timedelta, timezone as dt_tz
        from llm.services.litellm_gateway_query_service import get_costs_timeseries

        now = datetime.now(tz=dt_tz.utc)
        t0 = now.replace(second=0, microsecond=0)
        t1 = t0 - timedelta(minutes=10)  # 10 minutes earlier, still within the 1h window

        log0 = self._make_log(request_tokens=100, response_tokens=50)
        ModelInvocationLog.objects.filter(pk=log0.pk).update(created_at=t0)

        log1 = self._make_log(request_tokens=200, response_tokens=100)
        ModelInvocationLog.objects.filter(pk=log1.pk).update(created_at=t1)

        result = get_costs_timeseries({"time": "1h"})

        self.assertIn("points", result)
        self.assertGreaterEqual(
            len(result["points"]),
            2,
            "Two logs 10 minutes apart within the same hour must produce at "
            "least 2 distinct 1h timeseries points (not collapse into one hourly bucket).",
        )

    def test_1h_timeseries_reports_minute_granularity_metadata(self):
        from llm.services.litellm_gateway_query_service import get_costs_timeseries

        self._make_log(request_tokens=100, response_tokens=50)

        result = get_costs_timeseries({"time": "1h"})

        self.assertEqual(result["granularity_minutes"], 1)
        self.assertIsNone(result["granularity_hours"])

    def test_non_litellm_helper_does_not_deactivate_active_litellm_config(self):
        self.assertTrue(self.model_config.is_active)

        self._make_non_litellm_log()
        self.model_config.refresh_from_db()

        self.assertTrue(self.model_config.is_active)

@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class ModelConfigConnectionApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()

        self.admin_user = User.objects.create_user(
            username="conn-admin",
            password="secret123",
            email="conn-admin@example.com",
        )
        self.admin_user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.admin_access_token = generate_access_token(self.admin_user)

        self.member_user = User.objects.create_user(
            username="conn-member",
            password="secret123",
            email="conn-member@example.com",
        )
        self.member_user.groups.add(Group.objects.get(name=ROLE_MEMBER))
        self.member_access_token = generate_access_token(self.member_user)

    def test_connection_test_requires_authentication(self):
        response = self.client.post(
            "/api/ops/model-configs/test-connection/",
            content_type="application/json",
            data=json.dumps({}),
        )
        self.assertEqual(response.status_code, 401)

    def test_connection_test_requires_manage_permission(self):
        response = self.client.post(
            "/api/ops/model-configs/test-connection/",
            content_type="application/json",
            data=json.dumps({}),
            HTTP_AUTHORIZATION=f"Bearer {self.member_access_token}",
        )
        self.assertEqual(response.status_code, 403)

    @patch("urllib.request.urlopen")
    def test_connection_test_litellm_chat_success(self, mock_urlopen):
        mock_urlopen.return_value = _FakeHttpResponse({
            "choices": [{"message": {"content": "pong"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        })
        response = self.client.post(
            "/api/ops/model-configs/test-connection/",
            content_type="application/json",
            data=json.dumps({
                "capability": "chat",
                "provider": "litellm",
                "model_name": "test-route",
                "endpoint": "http://localhost:4000",
                "options": {"api_key": "sk-test"},
            }),
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["ok"], True)

    @patch("urllib.request.urlopen")
    def test_connection_test_does_not_write_invocation_log(self, mock_urlopen):
        """Connection tests use an unsaved ModelConfig; no log should be written."""
        mock_urlopen.return_value = _FakeHttpResponse({
            "choices": [{"message": {"content": "pong"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        })
        before = ModelInvocationLog.objects.count()
        self.client.post(
            "/api/ops/model-configs/test-connection/",
            content_type="application/json",
            data=json.dumps({
                "capability": "chat",
                "provider": "litellm",
                "model_name": "test-route",
                "endpoint": "http://localhost:4000",
                "options": {"api_key": "sk-test"},
            }),
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )
        self.assertEqual(ModelInvocationLog.objects.count(), before)


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class ModelConfigMigrationApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()
        self.temp_dir = Path(tempfile.mkdtemp(dir=Path.cwd()))
        self.litellm_root_patch = override_settings(LITELLM_GENERATED_CONFIG_ROOT=self.temp_dir)
        self.litellm_root_patch.enable()

        self.admin_user = User.objects.create_user(
            username="migration-admin",
            password="secret123",
            email="migration-admin@example.com",
        )
        self.admin_user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.admin_access_token = generate_access_token(self.admin_user)

        self.member_user = User.objects.create_user(
            username="migration-member",
            password="secret123",
            email="migration-member@example.com",
        )
        self.member_user.groups.add(Group.objects.get(name=ROLE_MEMBER))
        self.member_access_token = generate_access_token(self.member_user)

    def tearDown(self):
        self.litellm_root_patch.disable()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # --- POST /api/ops/model-configs/migrate-to-litellm/ ---

    def test_migrate_requires_authentication(self):
        response = self.client.post("/api/ops/model-configs/migrate-to-litellm/")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {"code": 401, "message": "未认证。", "data": {}},
        )

    def test_migrate_requires_manage_model_config_permission(self):
        response = self.client.post(
            "/api/ops/model-configs/migrate-to-litellm/",
            HTTP_AUTHORIZATION=f"Bearer {self.member_access_token}",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {"code": 403, "message": "无权限。", "data": {}},
        )

    def test_migrate_success_response_shape(self):
        response = self.client.post(
            "/api/ops/model-configs/migrate-to-litellm/",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["message"], "ok")
        data = payload["data"]
        self.assertIn("migrated_capabilities", data)
        self.assertIn("chat", data["migrated_capabilities"])
        self.assertIn("embedding", data["migrated_capabilities"])
        sync_result = data["sync_result"]
        self.assertIn("status", sync_result)
        self.assertIn("sync_event_id", sync_result)
        self.assertIn("route_count", sync_result)
        self.assertEqual(sync_result["status"], "success")

    @patch("llm.controllers.model_config_controller.migrate_active_configs_to_litellm")
    def test_migrate_returns_503_when_no_active_config(self, mock_migrate):
        mock_migrate.side_effect = ServiceConfigurationError(
            "未配置启用中的 chat 模型。", code="model_not_configured"
        )

        response = self.client.post(
            "/api/ops/model-configs/migrate-to-litellm/",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["code"], 503)
        self.assertEqual(payload["message"], "未配置启用中的 chat 模型。")
        self.assertEqual(payload["data"], {"error": "model_not_configured"})

    # --- POST /api/ops/model-configs/<id>/sync-litellm/ ---

    def test_sync_requires_authentication(self):
        model_config = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
        response = self.client.post(f"/api/ops/model-configs/{model_config.id}/sync-litellm/")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {"code": 401, "message": "未认证。", "data": {}},
        )

    def test_sync_requires_manage_model_config_permission(self):
        model_config = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
        response = self.client.post(
            f"/api/ops/model-configs/{model_config.id}/sync-litellm/",
            HTTP_AUTHORIZATION=f"Bearer {self.member_access_token}",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {"code": 403, "message": "无权限。", "data": {}},
        )

    def test_sync_returns_404_for_unknown_model_config(self):
        response = self.client.post(
            "/api/ops/model-configs/999999/sync-litellm/",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {"code": 404, "message": "模型配置不存在。", "data": {}},
        )

    def test_sync_writes_rendered_config_when_base_config_exists(self):
        """sync_litellm_route_for_config rebuilds the rendered config when the base exists."""
        model_config = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
        base_config_path = self.temp_dir / "litellm_config.yaml"
        rendered_config_path = self.temp_dir / "litellm_config_rendered.yaml"
        base_config_path.write_text(
            "model_list:\n"
            "  - model_name: placeholder\n"
            "    litellm_params:\n"
            "      model: openai/placeholder\n"
            "      api_base: http://placeholder\n"
            "litellm_settings:\n"
            "  drop_params: true\n",
            encoding="utf-8",
        )

        with override_settings(
            LITELLM_BASE_CONFIG_PATH=str(base_config_path),
            LITELLM_RENDERED_CONFIG_PATH=str(rendered_config_path),
        ):
            response = self.client.post(
                f"/api/ops/model-configs/{model_config.id}/sync-litellm/",
                HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(rendered_config_path.exists(), "Rendered config should have been written")

    def test_migrate_db_writes_are_atomic(self):
        """If one capability's route activation fails, no LiteLLM routes are activated."""
        original_ensure = model_config_command_service.ensure_litellm_route_from_model_config

        def _fail_on_embedding(active):
            if active.capability == ModelConfig.CAPABILITY_EMBEDDING:
                raise ValueError("boom")
            return original_ensure(active)

        before_count = ModelConfig.objects.filter(provider="litellm", is_active=True).count()
        with patch("llm.services.model_config_command_service.ensure_litellm_route_from_model_config", side_effect=_fail_on_embedding):
            with self.assertRaises(ValueError):
                migrate_active_configs_to_litellm(triggered_by=self.admin_user)

        after_count = ModelConfig.objects.filter(provider="litellm", is_active=True).count()
        self.assertEqual(after_count, before_count, "Atomic transaction must roll back on failure")


class LiteLLMAliasYamlRegressionTests(TestCase):
    """Regression tests for YAML generation in litellm_alias_service."""

    def setUp(self):
        seed_roles_and_permissions()
        self.sync_litellm_route_for_config = sync_litellm_route_for_config
        self.temp_dir = Path(tempfile.mkdtemp(dir=Path.cwd()))
        self.admin_user = User.objects.create_user(
            username="alias-test-admin",
            password="secret",
            email="alias-test@example.com",
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_litellm_model_config(self, upstream_model=None, model_name="my-route"):
        options = {"api_base": "http://localhost:8001"}
        if upstream_model is not None:
            options["litellm"] = {"upstream_model": upstream_model}
        return ModelConfig.objects.create(
            name="Test Route",
            model_name=model_name,
            provider=ModelConfig.PROVIDER_LITELLM,
            capability=ModelConfig.CAPABILITY_CHAT,
            endpoint="http://localhost:8001",
            is_active=True,
            options=options,
        )

    def _sync_and_read_yaml(self, model_config):
        with override_settings(
            LITELLM_GENERATED_CONFIG_ROOT=str(self.temp_dir),
            LITELLM_BASE_CONFIG_PATH=str(self.temp_dir / "base.yaml"),
            LITELLM_RENDERED_CONFIG_PATH=str(self.temp_dir / "rendered.yaml"),
        ):
            self.sync_litellm_route_for_config(model_config, triggered_by=self.admin_user)
        route_key = f"route-{model_config.capability}-{model_config.id}"
        config_path = self.temp_dir / f"{route_key}.yaml"
        return config_path.read_text(encoding="utf-8")

    def test_prefixed_upstream_model_is_not_double_prefixed(self):
        """options.litellm.upstream_model='openai/gpt-4o' must produce model: openai/gpt-4o."""
        model_config = self._make_litellm_model_config(upstream_model="openai/gpt-4o")
        yaml_text = self._sync_and_read_yaml(model_config)

        self.assertIn("model: openai/gpt-4o", yaml_text,
                      "Already-prefixed upstream model must appear exactly once")
        self.assertNotIn("model: openai/openai/", yaml_text,
                         "Double prefix openai/openai/ must not appear in YAML")

    def test_bare_upstream_model_gets_openai_prefix(self):
        """options.litellm.upstream_model='gpt-4o' must produce model: openai/gpt-4o."""
        model_config = self._make_litellm_model_config(upstream_model="gpt-4o")
        yaml_text = self._sync_and_read_yaml(model_config)

        self.assertIn("model: openai/gpt-4o", yaml_text,
                      "Bare model name must be prefixed with openai/")

    def test_dashscope_embedding_upstream_is_rendered_as_openai_compatible_model(self):
        model_config = self._make_litellm_model_config(
            upstream_model="dashscope/text-embedding-v4",
            model_name="text-embedding-v4",
        )
        model_config.capability = ModelConfig.CAPABILITY_EMBEDDING
        model_config.save(update_fields=["capability", "updated_at"])

        yaml_text = self._sync_and_read_yaml(model_config)

        self.assertIn("model: openai/text-embedding-v4", yaml_text)
        self.assertNotIn("model: dashscope/text-embedding-v4", yaml_text)

    def test_absent_upstream_model_falls_back_to_model_name(self):
        """When options.litellm.upstream_model is absent, model_name is used as the upstream."""
        model_config = self._make_litellm_model_config(upstream_model=None, model_name="my-fallback-route")
        yaml_text = self._sync_and_read_yaml(model_config)

        self.assertIn("model: openai/my-fallback-route", yaml_text,
                      "Absent upstream_model must fall back to openai/<model_name>")

    def test_yaml_includes_api_key_when_present(self):
        model_config = self._make_litellm_model_config(upstream_model="deepseek/deepseek-chat")
        model_config.options["api_key"] = "sk-upstream"
        model_config.save(update_fields=["options", "updated_at"])

        yaml_text = self._sync_and_read_yaml(model_config)

        self.assertIn("api_key: sk-upstream", yaml_text)


class LiteLLMGatewaySettingsTests(TestCase):
    def test_litellm_render_defaults_match_deploy_paths(self):
        self.assertTrue(str(settings.LITELLM_BASE_CONFIG_PATH).endswith("deploy/litellm/config.yaml"))
        self.assertTrue(str(settings.LITELLM_RENDERED_CONFIG_PATH).endswith("deploy/litellm/rendered.config.yaml"))


class LiteLLMConfigRenderRegressionTests(TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(dir=Path.cwd()))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_render_normalizes_stale_dashscope_embedding_snippet(self):
        base_config_path = self.temp_dir / "base.yaml"
        generated_root = self.temp_dir / "generated"
        output_path = self.temp_dir / "rendered.yaml"
        generated_root.mkdir(parents=True, exist_ok=True)
        base_config_path.write_text(
            "model_list:\n"
            "litellm_settings:\n"
            "  drop_params: true\n",
            encoding="utf-8",
        )
        (generated_root / "route-embedding-7.yaml").write_text(
            "model_list:\n"
            "  - model_name: text-embedding-v4\n"
            "    litellm_params:\n"
            "      model: dashscope/text-embedding-v4\n"
            "      api_base: https://dashscope.aliyuncs.com/compatible-mode/v1\n",
            encoding="utf-8",
        )

        build_rendered_litellm_config(
            base_config_path=str(base_config_path),
            generated_root=str(generated_root),
            output_path=str(output_path),
        )

        rendered = output_path.read_text(encoding="utf-8")
        self.assertIn("model: openai/text-embedding-v4", rendered)
        self.assertNotIn("model: dashscope/text-embedding-v4", rendered)

    def test_render_service_imports_without_django_settings(self):
        env = os.environ.copy()
        env.pop("DJANGO_SETTINGS_MODULE", None)
        python_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            f"{Path.cwd()}:{python_path}" if python_path else str(Path.cwd())
        )

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import llm.services.litellm_config_render_service",
            ],
            cwd=Path.cwd(),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
