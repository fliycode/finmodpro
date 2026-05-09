import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import timedelta
from decimal import Decimal
from io import BytesIO, StringIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test import Client, SimpleTestCase, override_settings
from django.utils import timezone

from authentication.models import User
from authentication.services.jwt_service import generate_access_token
from common.exceptions import ServiceConfigurationError, UpstreamRateLimitError, UpstreamServiceError
from knowledgebase.models import Document, IngestionTask
from llm.models import EvalRecord, FineTuneRun, ModelConfig, ModelInvocationLog
from llm.services import model_config_command_service
from llm.services.model_config_service import get_active_model_config
from llm.services.fine_tune_service import create_fine_tune_run
from llm.services.fine_tune_runner_client import build_llamafactory_command
from llm.services.prompt_service import load_prompt_template, render_prompt
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
            name="deepseek-qwen-chat",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_DEEPSEEK,
            model_name="deepseek-chat",
            parameter_scale="32B",
            endpoint="https://api.deepseek.com",
            description="财报问答候选模型",
            options={
                "api_key": "sk-deepseek",
                "temperature": 0.1,
            },
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
        self.assertEqual(payload["data"]["total"], ModelConfig.objects.count())
        self.assertTrue(any(item["name"] == "deepseek-qwen-chat" for item in payload["data"]["model_configs"]))

        first_row = payload["data"]["model_configs"][0]
        self.assertEqual(
            set(first_row.keys()),
            {
                "id",
                "name",
                "capability",
                "provider",
                "model_name",
                "parameter_scale",
                "endpoint",
                "description",
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
                "request_price",
                "price_currency",
                "pricing_notes",
                "invocation_count",
            },
        )
        self.assertEqual(first_row["id"], get_active_model_config(ModelConfig.CAPABILITY_CHAT).id)
        self.assertTrue(first_row["is_active"])
        self.assertEqual(payload["data"]["model_configs"][1]["id"], replacement.id)
        self.assertEqual(payload["data"]["model_configs"][1]["parameter_scale"], "32B")
        self.assertEqual(payload["data"]["model_configs"][1]["description"], "财报问答候选模型")

    def test_list_model_configs_includes_overview_metrics_and_invocation_counts(self):
        model = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
        now = timezone.now()
        today_log = ModelInvocationLog.objects.create(
            model_config=model,
            capability=model.capability,
            provider=model.provider,
            alias=model.model_name,
            upstream_model=model.model_name,
            status=ModelInvocationLog.STATUS_SUCCESS,
            latency_ms=180,
        )
        yesterday_log = ModelInvocationLog.objects.create(
            model_config=model,
            capability=model.capability,
            provider=model.provider,
            alias=model.model_name,
            upstream_model=model.model_name,
            status=ModelInvocationLog.STATUS_SUCCESS,
            latency_ms=220,
        )
        ModelInvocationLog.objects.filter(id=today_log.id).update(created_at=now)
        ModelInvocationLog.objects.filter(id=yesterday_log.id).update(created_at=now - timedelta(days=1))

        response = self.client.get(
            "/api/ops/model-configs",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        overview = payload["overview"]
        self.assertEqual(overview["total_models"], payload["total"])
        self.assertEqual(
            overview["enabled_models"],
            ModelConfig.objects.filter(is_active=True).count(),
        )
        self.assertEqual(overview["total_invocation_count"], 2)
        self.assertEqual(overview["today_invocation_count"], 1)
        self.assertEqual(overview["yesterday_invocation_count"], 1)
        self.assertEqual(overview["invocation_change_pct"], 0.0)

        row = next(item for item in payload["model_configs"] if item["id"] == model.id)
        self.assertEqual(row["invocation_count"], 2)

    def test_list_model_configs_masks_api_key(self):
        ModelConfig.objects.create(
            name="deepseek-chat-mask",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_DEEPSEEK,
            model_name="deepseek-chat",
            endpoint="https://api.deepseek.com",
            options={
                "api_key": "sk-test-123456",
            },
            is_active=False,
        )

        response = self.client.get(
            "/api/ops/model-configs",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        route_row = next(
            item for item in response.json()["data"]["model_configs"] if item["name"] == "deepseek-chat-mask"
        )
        self.assertTrue(route_row["has_api_key"])
        self.assertEqual(route_row["api_key_masked"], "sk-tes******3456")
        self.assertNotIn("sk-test-123456", json.dumps(route_row))

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
            name="deepseek-chat-active",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_DEEPSEEK,
            model_name="deepseek-reasoner",
            endpoint="https://api.deepseek.com",
            options={
                "api_key": "sk-deepseek",
                "temperature": 0.1,
            },
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
                "parameter_scale",
                "endpoint",
                "description",
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
                "request_price",
                "price_currency",
                "pricing_notes",
                "invocation_count",
            },
        )

    def test_delete_requires_authentication(self):
        model_config = ModelConfig.objects.create(
            name="chat-delete-unauth",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_DEEPSEEK,
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
            name="deepseek-delete-inactive",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_DEEPSEEK,
            model_name="deepseek-chat",
            endpoint="https://api.deepseek.com",
            options={"api_key": "sk-deepseek"},
            is_active=False,
        )

        response = self.client.delete(
            f"/api/ops/model-configs/{model_config.id}/",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"code": 0, "message": "ok", "data": {"deleted": True}})
        self.assertFalse(ModelConfig.objects.filter(id=model_config.id).exists())

    def test_admin_can_create_direct_provider_model_config(self):
        response = self.client.post(
            "/api/ops/model-configs/",
            data=json.dumps(
                {
                    "name": "deepseek-chat-prod",
                    "capability": "chat",
                    "provider": "deepseek",
                    "model_name": "deepseek-chat",
                    "endpoint": "https://api.deepseek.com",
                    "options": {
                        "api_key": "sk-test-123456",
                        "temperature": 0.2,
                        "max_tokens": 1024,
                    },
                    "input_price_per_million": "0.500000",
                    "output_price_per_million": "2.000000",
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
    def test_admin_can_test_direct_chat_connection(self, mocked_urlopen):
        mocked_urlopen.return_value = _FakeHttpResponse(
            {"choices": [{"message": {"content": "pong"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
        )

        response = self.client.post(
            "/api/ops/model-configs/test-connection/",
            data=json.dumps(
                {
                    "capability": "chat",
                    "provider": "deepseek",
                    "model_name": "deepseek-chat",
                    "endpoint": "https://api.deepseek.com",
                    "options": {
                        "api_key": "sk-test",
                    },
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["ok"], True)

    @patch("urllib.request.urlopen")
    def test_admin_can_test_direct_embedding_connection(self, mocked_urlopen):
        mocked_urlopen.return_value = _FakeHttpResponse({
            "data": [{"embedding": [0.1, 0.2, 0.3]}],
            "usage": {"prompt_tokens": 1, "total_tokens": 1},
        })

        response = self.client.post(
            "/api/ops/model-configs/test-connection/",
            data=json.dumps(
                {
                    "capability": "embedding",
                    "provider": "openai_compatible",
                    "model_name": "text-embedding-3-small",
                    "endpoint": "https://api.openai.com",
                    "options": {"api_key": "sk-openai"},
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

    def test_update_fine_tune_run_accepts_runner_name_and_training_config(self):
        base_model = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
        run = FineTuneRun.objects.create(
            base_model=base_model,
            dataset_name="财报基准集",
            dataset_version="2026Q1",
            strategy="lora",
            runner_name="legacy-runner",
            training_config={"epochs": 3},
            status=FineTuneRun.STATUS_PENDING,
            notes="等待登记。",
        )

        response = self.client.patch(
            f"/api/ops/fine-tunes/{run.id}",
            data=json.dumps(
                {
                    "runner_name": "llamafactory-runner-a",
                    "training_config": {
                        "template": "llama3",
                        "cutoff_len": 4096,
                        "num_train_epochs": 5,
                        "lora_rank": 16,
                    },
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]["fine_tune_run"]
        self.assertEqual(payload["runner_name"], "llamafactory-runner-a")
        self.assertEqual(payload["training_config"]["template"], "llama3")
        self.assertEqual(payload["training_config"]["cutoff_len"], 4096)
        self.assertEqual(payload["training_config"]["num_train_epochs"], 5)
        self.assertEqual(payload["training_config"]["lora_rank"], 16)


class FineTuneRunnerClientTests(SimpleTestCase):
    def test_build_llamafactory_command_supports_native_sft_lora_fields(self):
        command = build_llamafactory_command(
            spec={
                "run_key": "ft-001",
                "training_job": {
                    "base_model_name": "meta-llama/Meta-Llama-3-8B-Instruct",
                    "strategy": "qlora",
                    "training_config": {
                        "template": "llama3",
                        "cutoff_len": 4096,
                        "max_samples": 2000,
                        "preprocessing_num_workers": 8,
                        "dataloader_num_workers": 2,
                        "overwrite_cache": True,
                        "packing": False,
                        "per_device_train_batch_size": 2,
                        "gradient_accumulation_steps": 8,
                        "learning_rate": 0.0001,
                        "num_train_epochs": 3,
                        "lr_scheduler_type": "cosine",
                        "warmup_ratio": 0.1,
                        "max_grad_norm": 1.0,
                        "logging_steps": 10,
                        "save_steps": 200,
                        "plot_loss": True,
                        "save_only_model": False,
                        "report_to": "none",
                        "bf16": True,
                        "gradient_checkpointing": True,
                        "lora_rank": 16,
                        "lora_alpha": 32,
                        "lora_dropout": 0.05,
                        "lora_target": "all",
                        "quantization_bit": 4,
                    },
                },
            },
            export_dir="/tmp/export",
            output_dir="/tmp/output",
        )

        self.assertEqual(command[:4], ["llamafactory-cli", "train", "--stage", "sft"])
        self.assertIn("--template", command)
        self.assertIn("llama3", command)
        self.assertIn("--cutoff_len", command)
        self.assertIn("4096", command)
        self.assertIn("--max_samples", command)
        self.assertIn("--per_device_train_batch_size", command)
        self.assertIn("--gradient_accumulation_steps", command)
        self.assertIn("--lr_scheduler_type", command)
        self.assertIn("--logging_steps", command)
        self.assertIn("--save_steps", command)
        self.assertIn("--plot_loss", command)
        self.assertIn("--save_only_model", command)
        self.assertIn("--bf16", command)
        self.assertIn("--gradient_checkpointing", command)
        self.assertIn("--lora_rank", command)
        self.assertIn("--lora_alpha", command)
        self.assertIn("--lora_dropout", command)
        self.assertIn("--lora_target", command)
        self.assertIn("--quantization_bit", command)
        self.assertIn("--finetuning_type", command)
        qlora_index = command.index("--finetuning_type")
        self.assertEqual(command[qlora_index + 1], "qlora")

    def test_build_llamafactory_command_keeps_legacy_field_compatibility(self):
        command = build_llamafactory_command(
            spec={
                "run_key": "ft-legacy",
                "training_job": {
                    "base_model_name": "deepseek-ai/deepseek-llm-7b-chat",
                    "strategy": "lora",
                    "training_config": {
                        "epochs": 4,
                        "batch_size": 3,
                    },
                },
            },
            export_dir="/tmp/export",
            output_dir="/tmp/output",
        )

        epochs_index = command.index("--num_train_epochs")
        batch_index = command.index("--per_device_train_batch_size")
        self.assertEqual(command[epochs_index + 1], "4")
        self.assertEqual(command[batch_index + 1], "3")


class FineTuneRunCallbackApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()
        self.export_dir = tempfile.mkdtemp()
        self.override = override_settings(
            FINE_TUNE_EXPORT_ROOT=self.export_dir,
        )
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(shutil.rmtree, self.export_dir, True)

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

    def test_runner_callback_registers_inactive_candidate_model(self):
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
        self.assertEqual(run.registered_model_config.provider, ModelConfig.PROVIDER_OPENAI_COMPATIBLE)
        self.assertFalse(run.registered_model_config.is_active)

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
class GatewayQueryServiceTests(TestCase):
    """Service-level tests for model_usage_query_service."""

    def setUp(self):
        self.model_config = ModelConfig.objects.create(
            name="gw-chat",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_DEEPSEEK,
            model_name="gw-chat",
            endpoint="http://localhost:4000",
            is_active=True,
            input_price_per_million=5.0,
            output_price_per_million=15.0,
            options={
                "api_key": "sk-test",
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
        from llm.services.model_usage_query_service import get_gateway_summary

        self._make_log()
        self._make_log(status=ModelInvocationLog.STATUS_FAILED, error_code="500")

        result = get_gateway_summary()

        self.assertIn("gateway", result)
        self.assertIn("status", result["gateway"])
        self.assertIn("traffic", result)
        self.assertGreaterEqual(result["traffic"]["request_count"], 2)
        self.assertGreaterEqual(result["traffic"]["failed_count"], 1)
        self.assertIn("error_rate_pct", result["traffic"])
        self.assertIn("top_models", result)
        self.assertIn("recent_errors", result)

    def test_summary_top_models_ordered_by_count(self):
        from llm.services.model_usage_query_service import get_gateway_summary

        for _ in range(3):
            self._make_log(alias="model-a")
        self._make_log(alias="model-b")

        result = get_gateway_summary()

        aliases = [m["alias"] for m in result["top_models"]]
        self.assertEqual(aliases[0], "model-a")

    def test_get_logs_returns_filtered_rows(self):
        from llm.services.model_usage_query_service import get_logs

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
        from llm.services.model_usage_query_service import get_logs

        self._make_log(status=ModelInvocationLog.STATUS_SUCCESS)
        self._make_log(status=ModelInvocationLog.STATUS_FAILED, error_code="503")

        result = get_logs({"model": None, "status": "failed", "time": "24h"})

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["logs"][0]["status"], "failed")

    def test_get_logs_includes_required_fields(self):
        from llm.services.model_usage_query_service import get_logs

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
        from llm.services.model_usage_query_service import get_logs_summary

        self._make_log(latency_ms=100, status=ModelInvocationLog.STATUS_SUCCESS)
        self._make_log(latency_ms=300, status=ModelInvocationLog.STATUS_FAILED, error_code="500")

        result = get_logs_summary({"model": None, "status": None, "time": "24h"})

        self.assertEqual(result["total_requests"], 2)
        self.assertAlmostEqual(result["avg_latency_ms"], 200.0, delta=1.0)
        self.assertAlmostEqual(result["error_rate_pct"], 50.0, delta=0.1)
        self.assertIn("error_breakdown", result)
        self.assertIn("latency_buckets", result)

    def test_get_logs_summary_latency_buckets_structure(self):
        from llm.services.model_usage_query_service import get_logs_summary

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
        from llm.services.model_usage_query_service import get_trace

        tid = "trace-xyz"
        self._make_log(trace_id=tid, alias="first-model")
        self._make_log(trace_id=tid, alias="second-model")

        result = get_trace(tid)

        self.assertEqual(result["trace_id"], tid)
        self.assertIsNotNone(result["started_at"])
        self.assertIsNotNone(result["ended_at"])
        self.assertEqual(len(result["logs"]), 2)

    def test_get_trace_returns_none_for_unknown_trace(self):
        from llm.services.model_usage_query_service import get_trace

        result = get_trace("does-not-exist")

        self.assertIsNone(result)

    def test_get_errors_returns_aggregated_types(self):
        from llm.services.model_usage_query_service import get_errors

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
        from llm.services.model_usage_query_service import get_costs_summary

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
        from llm.services.model_usage_query_service import get_costs_summary

        model_no_price = ModelConfig.objects.create(
            name="no-price",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_DEEPSEEK,
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
        from llm.services.model_usage_query_service import get_costs_timeseries

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
        from llm.services.model_usage_query_service import get_costs_models

        self._make_log(request_tokens=500_000, response_tokens=250_000)
        other_config = ModelConfig.objects.create(
            name="gw-embed",
            capability=ModelConfig.CAPABILITY_EMBEDDING,
            provider=ModelConfig.PROVIDER_DEEPSEEK,
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
    # Time-series bucketing regression tests
    # ------------------------------------------------------------------

    def test_1h_timeseries_distinct_minute_buckets(self):
        """Two logs in the same hour but different minutes must produce
        distinct time-series points when time=1h.

        Regression: the old implementation used TruncHour for the 1h window,
        collapsing all traffic within an hour into a single coarse bucket.
        """
        from datetime import datetime, timedelta, timezone as dt_tz
        from llm.services.model_usage_query_service import get_costs_timeseries

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
        from llm.services.model_usage_query_service import get_costs_timeseries

        self._make_log(request_tokens=100, response_tokens=50)

        result = get_costs_timeseries({"time": "1h"})

        self.assertEqual(result["granularity_minutes"], 1)
        self.assertIsNone(result["granularity_hours"])

    def test_log_creation_does_not_deactivate_model_config(self):
        self.assertTrue(self.model_config.is_active)

        self._make_log()
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
    def test_connection_test_deepseek_chat_success(self, mock_urlopen):
        mock_urlopen.return_value = _FakeHttpResponse({
            "choices": [{"message": {"content": "pong"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        })
        response = self.client.post(
            "/api/ops/model-configs/test-connection/",
            content_type="application/json",
            data=json.dumps({
                "capability": "chat",
                "provider": "deepseek",
                "model_name": "deepseek-chat",
                "endpoint": "https://api.deepseek.com",
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
                "provider": "deepseek",
                "model_name": "deepseek-chat",
                "endpoint": "https://api.deepseek.com",
                "options": {"api_key": "sk-test"},
            }),
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )
        self.assertEqual(ModelInvocationLog.objects.count(), before)

    @patch("urllib.request.urlopen")
    def test_connection_test_reuses_saved_api_key_for_existing_model(self, mock_urlopen):
        mock_urlopen.return_value = _FakeHttpResponse({
            "choices": [{"message": {"content": "pong"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        })
        model_config = ModelConfig.objects.create(
            name="saved-deepseek-chat",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_DEEPSEEK,
            model_name="deepseek-chat",
            endpoint="https://api.deepseek.com",
            options={"api_key": "sk-stored"},
            is_active=False,
        )

        response = self.client.post(
            "/api/ops/model-configs/test-connection/",
            content_type="application/json",
            data=json.dumps({
                "model_config_id": model_config.id,
                "capability": "chat",
                "provider": "deepseek",
                "model_name": "deepseek-chat",
                "endpoint": "https://api.deepseek.com",
                "options": {},
            }),
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["ok"], True)

    @patch.dict(os.environ, {"DEEPSEEK_API_KEY": "env-deepseek-key"}, clear=False)
    @patch("urllib.request.urlopen")
    def test_connection_test_uses_provider_env_api_key_when_payload_omits_key(self, mock_urlopen):
        mock_urlopen.return_value = _FakeHttpResponse({
            "choices": [{"message": {"content": "pong"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        })

        response = self.client.post(
            "/api/ops/model-configs/test-connection/",
            content_type="application/json",
            data=json.dumps({
                "capability": "chat",
                "provider": "deepseek",
                "model_name": "deepseek-chat",
                "endpoint": "https://api.deepseek.com",
                "options": {},
            }),
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["ok"], True)
