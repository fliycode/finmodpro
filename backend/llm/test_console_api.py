from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from authentication.models import User
from authentication.services.jwt_service import generate_access_token
from knowledgebase.models import Document, IngestionTask
from llm.models import ModelConfig
from rag.models import RetrievalLog
from rbac.services.rbac_service import ROLE_ADMIN, ROLE_MEMBER, seed_roles_and_permissions


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class LlmConsoleApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()
        self.admin = User.objects.create_user(
            username="llm-admin",
            password="secret123",
            email="llm-admin@example.com",
        )
        self.admin.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.access_token = generate_access_token(self.admin)

        self.member = User.objects.create_user(
            username="llm-member",
            password="secret123",
            email="llm-member@example.com",
        )
        self.member.groups.add(Group.objects.get(name=ROLE_MEMBER))
        self.member_access_token = generate_access_token(self.member)

    def test_console_endpoints_require_authentication(self):
        for endpoint in (
            "/api/ops/llm/summary/",
            "/api/ops/llm/observability/",
            "/api/ops/llm/knowledge/",
        ):
            response = self.client.get(endpoint)

            self.assertEqual(response.status_code, 401)
            self.assertEqual(
                response.json(),
                {"code": 401, "message": "未认证。", "data": {}},
            )

    def test_console_endpoints_require_manage_model_config_permission(self):
        for endpoint in (
            "/api/ops/llm/summary/",
            "/api/ops/llm/observability/",
            "/api/ops/llm/knowledge/",
        ):
            response = self.client.get(
                endpoint,
                HTTP_AUTHORIZATION=f"Bearer {self.member_access_token}",
            )

            self.assertEqual(response.status_code, 403)
            self.assertEqual(
                response.json(),
                {"code": 403, "message": "无权限。", "data": {}},
            )

    def test_admin_can_fetch_llm_console_summary(self):
        ModelConfig.objects.create(
            name="chat-default",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="chat-default",
            endpoint="http://localhost:4000",
            is_active=True,
            options={"api_key": "sk-litellm"},
        )
        ModelConfig.objects.create(
            name="embed-default",
            capability=ModelConfig.CAPABILITY_EMBEDDING,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="embed-default",
            endpoint="http://localhost:4000",
            is_active=True,
            options={"api_key": "sk-litellm"},
        )

        response = self.client.get(
            "/api/ops/llm/summary/",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["active_models"]["chat"]["provider"], "litellm")
        self.assertEqual(payload["providers"][0]["key"], "litellm")
        self.assertIn("quick_links", payload)

    def test_summary_includes_active_non_litellm_provider_status(self):
        ModelConfig.objects.create(
            name="deepseek-chat",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_DEEPSEEK,
            model_name="deepseek-chat",
            endpoint="https://api.deepseek.com",
            is_active=True,
            options={"api_key": "sk-deepseek"},
        )

        response = self.client.get(
            "/api/ops/llm/summary/",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        provider_keys = [item["key"] for item in payload["providers"]]
        self.assertEqual(payload["active_models"]["chat"]["provider"], "deepseek")
        self.assertIn("deepseek", provider_keys)

    def test_summary_marks_litellm_configured_when_config_exists_but_is_inactive(self):
        ModelConfig.objects.create(
            name="chat-default",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name="chat-default",
            endpoint="http://localhost:4000",
            is_active=False,
            options={"api_key": "sk-litellm"},
        )

        response = self.client.get(
            "/api/ops/llm/summary/",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        litellm = next(item for item in payload["providers"] if item["key"] == "litellm")
        self.assertEqual(litellm["status"], "configured")
        self.assertEqual(litellm["active_count"], 0)

    def test_summary_marks_provider_missing_without_any_configs(self):
        response = self.client.get(
            "/api/ops/llm/summary/",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        deepseek = next(item for item in payload["providers"] if item["key"] == "deepseek")
        self.assertEqual(deepseek["status"], "missing")

    def test_admin_can_fetch_llm_observability_summary(self):
        RetrievalLog.objects.create(
            query="revenue outlook",
            top_k=5,
            result_count=2,
            source=RetrievalLog.SOURCE_CHAT_ASK,
            duration_ms=180,
        )

        response = self.client.get(
            "/api/ops/llm/observability/",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["overview"]["chat_request_count_24h"], 1)
        self.assertEqual(payload["overview"]["retrieval_hit_count_24h"], 1)
        self.assertEqual(payload["overview"]["avg_duration_ms_24h"], 180)
        self.assertIn("langfuse", payload)

    @override_settings(
        UNSTRUCTURED_API_URL="http://unstructured-api:8000",
        UNSTRUCTURED_API_URL_CONFIGURED=False,
    )
    def test_summary_marks_unstructured_missing_when_config_flag_is_false(self):
        Document.objects.create(
            title="未入库文档",
            file=SimpleUploadedFile("report.pdf", b"pdf-content", content_type="application/pdf"),
            filename="report.pdf",
            doc_type="pdf",
            status=Document.STATUS_UPLOADED,
        )

        response = self.client.get(
            "/api/ops/llm/summary/",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        unstructured = next(item for item in payload["providers"] if item["key"] == "unstructured")
        self.assertEqual(unstructured["status"], "missing")

    def test_admin_can_fetch_llm_knowledge_summary(self):
        document = Document.objects.create(
            title="年报",
            file=SimpleUploadedFile("report.pdf", b"pdf-content", content_type="application/pdf"),
            filename="report.pdf",
            doc_type="pdf",
            status=Document.STATUS_FAILED,
        )
        IngestionTask.objects.create(
            document=document,
            status=IngestionTask.STATUS_FAILED,
            current_step=IngestionTask.STEP_FAILED,
            error_message="Unstructured 解析服务不可达。",
        )

        response = self.client.get(
            "/api/ops/llm/knowledge/",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()["data"]
        self.assertEqual(payload["parser_capabilities"]["txt"]["parser"], "local")
        self.assertEqual(payload["parser_capabilities"]["pdf"]["parser"], "unstructured")
        self.assertTrue(payload["parser_capabilities"]["pdf"]["fallback"])
        self.assertFalse(payload["parser_capabilities"]["docx"]["fallback"])
        self.assertEqual(
            payload["ingestion_summary"],
            {
                "total_documents": 1,
                "queued": 0,
                "running": 0,
                "succeeded": 0,
                "failed": 1,
            },
        )
        self.assertEqual(payload["recent_failures"][0]["document_title"], "年报")
