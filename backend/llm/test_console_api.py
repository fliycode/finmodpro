from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from authentication.models import User
from authentication.services.jwt_service import generate_access_token
from knowledgebase.models import Document, IngestionTask
from llm.models import LiteLLMSyncEvent, ModelConfig, ModelInvocationLog
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


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class GatewayApiTests(TestCase):
    """Endpoint / auth tests for /api/ops/llm/gateway/* routes."""

    GATEWAY_ENDPOINTS = [
        "/api/ops/llm/gateway/summary/",
        "/api/ops/llm/gateway/logs/",
        "/api/ops/llm/gateway/logs/summary/",
        "/api/ops/llm/gateway/errors/",
        "/api/ops/llm/gateway/costs/summary/",
        "/api/ops/llm/gateway/costs/timeseries/",
        "/api/ops/llm/gateway/costs/models/",
    ]

    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()

        self.admin = User.objects.create_user(
            username="gw-admin",
            password="secret123",
            email="gw-admin@example.com",
        )
        self.admin.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.access_token = generate_access_token(self.admin)

        self.member = User.objects.create_user(
            username="gw-member",
            password="secret123",
            email="gw-member@example.com",
        )
        self.member.groups.add(Group.objects.get(name=ROLE_MEMBER))
        self.member_token = generate_access_token(self.member)

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

    def test_gateway_endpoints_require_authentication(self):
        for endpoint in self.GATEWAY_ENDPOINTS:
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, 401, f"Expected 401 for {endpoint}")
            self.assertEqual(response.json()["code"], 401)

    def test_gateway_endpoints_require_manage_permission(self):
        for endpoint in self.GATEWAY_ENDPOINTS:
            response = self.client.get(
                endpoint,
                HTTP_AUTHORIZATION=f"Bearer {self.member_token}",
            )
            self.assertEqual(response.status_code, 403, f"Expected 403 for {endpoint}")
            self.assertEqual(response.json()["code"], 403)

    def test_gateway_summary_returns_expected_keys(self):
        LiteLLMSyncEvent.objects.create(status=LiteLLMSyncEvent.STATUS_SUCCESS, message="ok")
        self._make_log()

        response = self.client.get(
            "/api/ops/llm/gateway/summary/",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        for key in ("gateway", "recent_sync", "traffic", "top_models", "recent_errors"):
            self.assertIn(key, data, f"Missing key: {key}")

    def test_gateway_logs_returns_rows(self):
        self._make_log()

        response = self.client.get(
            "/api/ops/llm/gateway/logs/",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("logs", data)
        self.assertIn("total", data)
        self.assertGreater(data["total"], 0)

    def test_gateway_logs_supports_model_filter(self):
        self._make_log(alias="model-a")
        self._make_log(alias="model-b")

        response = self.client.get(
            "/api/ops/llm/gateway/logs/?model=model-a",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["logs"][0]["alias"], "model-a")

    def test_gateway_logs_summary_returns_aggregates(self):
        self._make_log(latency_ms=100)
        self._make_log(latency_ms=300, status=ModelInvocationLog.STATUS_FAILED, error_code="500")

        response = self.client.get(
            "/api/ops/llm/gateway/logs/summary/",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["total_requests"], 2)
        self.assertIn("error_rate_pct", data)
        self.assertIn("avg_latency_ms", data)
        self.assertIn("error_breakdown", data)
        self.assertIn("latency_buckets", data)

    def test_gateway_trace_returns_trace_view(self):
        tid = "trace-api-test"
        self._make_log(trace_id=tid)

        response = self.client.get(
            f"/api/ops/llm/gateway/traces/{tid}/",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["trace_id"], tid)
        self.assertEqual(len(data["logs"]), 1)

    def test_gateway_trace_returns_404_for_unknown(self):
        response = self.client.get(
            "/api/ops/llm/gateway/traces/no-such-trace/",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 404)

    def test_gateway_errors_returns_aggregated_types(self):
        self._make_log(status=ModelInvocationLog.STATUS_FAILED, error_code="500")
        self._make_log(status=ModelInvocationLog.STATUS_FAILED, error_code="503")

        response = self.client.get(
            "/api/ops/llm/gateway/errors/",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("total_failed_requests", data)
        self.assertIn("error_types", data)
        self.assertIn("recent_errors", data)

    def test_gateway_costs_summary_returns_cost_fields(self):
        self._make_log(request_tokens=1_000, response_tokens=500)

        response = self.client.get(
            "/api/ops/llm/gateway/costs/summary/",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        for key in ("total_requests", "total_request_tokens", "total_response_tokens",
                    "estimated_input_cost", "estimated_output_cost", "estimated_total_cost"):
            self.assertIn(key, data, f"Missing key: {key}")

    def test_gateway_costs_timeseries_returns_points(self):
        self._make_log()

        response = self.client.get(
            "/api/ops/llm/gateway/costs/timeseries/",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("points", data)

    def test_gateway_costs_models_returns_model_breakdown(self):
        self._make_log(request_tokens=1_000, response_tokens=500)

        response = self.client.get(
            "/api/ops/llm/gateway/costs/models/",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertIn("models", data)
        self.assertTrue(len(data["models"]) > 0)
        for m in data["models"]:
            self.assertIn("alias", m)
            self.assertIn("request_share_pct", m)
            self.assertIn("estimated_total_cost", m)

    def test_gateway_legacy_urls_also_work(self):
        """Non-trailing-slash variants must resolve (APPEND_SLASH behavior)."""
        # We just check that they're registered (status != 404) for the auth guard.
        no_slash_endpoints = [e.rstrip("/") for e in self.GATEWAY_ENDPOINTS]
        for endpoint in no_slash_endpoints:
            response = self.client.get(endpoint)
            self.assertNotEqual(response.status_code, 404, f"Route not found: {endpoint}")
