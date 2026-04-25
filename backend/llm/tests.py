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
from llm.models import EvalRecord, FineTuneRun, LiteLLMSyncEvent, ModelConfig, ModelInvocationLog
from llm.services.model_config_service import get_active_model_config
from llm.services.fine_tune_service import create_fine_tune_run
from llm.services.prompt_service import load_prompt_template, render_prompt
from llm.services.providers.deepseek_provider import DeepSeekChatProvider
from llm.services.runtime_service import (
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

        row = next(item for item in response.json()["data"]["model_configs"] if item["id"] == model.id)
        self.assertEqual(row["alias"], "chat-default")
        self.assertEqual(row["upstream_provider"], "openai")
        self.assertEqual(row["upstream_model"], "gpt-4o")
        self.assertEqual(row["fallback_aliases"], ["chat-backup"])
        self.assertEqual(row["weight"], 1)

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
            status="success",
            latency_ms=420,
            request_tokens=120,
            response_tokens=220,
            trace_id="trace-1",
            request_id="request-1",
        )

        self.assertEqual(log.alias, "chat-default")
        self.assertEqual(log.trace_id, "trace-1")
        self.assertEqual(log.response_tokens, 220)

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
        temp_user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        event = LiteLLMSyncEvent.objects.create(
            status=LiteLLMSyncEvent.STATUS_SUCCESS,
            triggered_by=temp_user,
        )

        temp_user.delete()

        event.refresh_from_db()
        self.assertIsNone(event.triggered_by)
