import shutil
import tempfile
from decimal import Decimal
from datetime import timedelta

from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from authentication.models import User
from authentication.services.jwt_service import generate_access_token
from knowledgebase.models import Document, IngestionTask
from llm.models import EvalRecord, ModelConfig
from rag.models import RetrievalLog
from rbac.services.rbac_service import ROLE_ADMIN, seed_roles_and_permissions
from risk.models import RiskEvent


class HealthApiTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_health_returns_unified_response_payload(self):
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["message"], "ok")
        self.assertEqual(payload["data"]["status"], "ok")
        self.assertEqual(payload["data"]["service"], "finmodpro-backend")
        self.assertIn("environment", payload["data"])
        self.assertIn("timestamp", payload["data"])


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class DashboardStatsApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()

        self.admin_user = User.objects.create_user(
            username="dashboard-admin",
            password="secret123",
            email="dashboard-admin@example.com",
        )
        self.admin_user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.admin_access_token = generate_access_token(self.admin_user)

        self.basic_user = User.objects.create_user(
            username="dashboard-basic",
            password="secret123",
            email="dashboard-basic@example.com",
        )
        self.basic_access_token = generate_access_token(self.basic_user)

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def create_document(self, *, title, filename):
        return Document.objects.create(
            title=title,
            file=SimpleUploadedFile(filename, b"stats-content", content_type="application/pdf"),
            filename=filename,
            doc_type="pdf",
        )

    def create_risk_event(self, *, document, review_status):
        return RiskEvent.objects.create(
            company_name="FinModPro Holdings",
            risk_type="liquidity",
            risk_level=RiskEvent.LEVEL_MEDIUM,
            summary="流动性承压。",
            evidence_text="公司出现短期流动性承压迹象。",
            confidence_score=Decimal("0.800"),
            review_status=review_status,
            document=document,
        )

    def test_dashboard_stats_returns_real_admin_aggregate_payload(self):
        indexed_document = self.create_document(title="已索引文档", filename="indexed.pdf")
        indexed_document.status = Document.STATUS_INDEXED
        indexed_document.save(update_fields=["status", "updated_at"])

        processing_document = self.create_document(title="处理中文档", filename="processing.pdf")
        processing_document.status = Document.STATUS_CHUNKED
        processing_document.save(update_fields=["status", "updated_at"])

        failed_document = self.create_document(title="失败文档", filename="failed.pdf")
        failed_document.status = Document.STATUS_FAILED
        failed_document.error_message = "vector insert failed"
        failed_document.save(update_fields=["status", "error_message", "updated_at"])

        pending_risk = self.create_risk_event(
            document=indexed_document,
            review_status=RiskEvent.STATUS_PENDING,
        )
        pending_risk.risk_level = RiskEvent.LEVEL_HIGH
        pending_risk.save(update_fields=["risk_level", "updated_at"])

        approved_risk = self.create_risk_event(
            document=failed_document,
            review_status=RiskEvent.STATUS_APPROVED,
        )
        approved_risk.risk_level = RiskEvent.LEVEL_CRITICAL
        approved_risk.save(update_fields=["risk_level", "updated_at"])

        ModelConfig.objects.create(
            name="chat-active",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_DEEPSEEK,
            model_name="deepseek-chat",
            endpoint="https://api.deepseek.com",
            is_active=True,
        )
        ModelConfig.objects.create(
            name="embedding-active",
            capability=ModelConfig.CAPABILITY_EMBEDDING,
            provider=ModelConfig.PROVIDER_OLLAMA,
            model_name="mxbai-embed-large",
            endpoint="http://localhost:11434",
            is_active=True,
        )
        ModelConfig.objects.create(
            name="chat-inactive",
            capability=ModelConfig.CAPABILITY_CHAT,
            provider=ModelConfig.PROVIDER_OLLAMA,
            model_name="llama3.2",
            endpoint="http://localhost:11434",
            is_active=False,
        )

        now = timezone.now()
        for days_ago, result_count in [
            (0, 2),
            (1, 1),
            (2, 0),
            (3, 3),
            (6, 0),
        ]:
            log = RetrievalLog.objects.create(
                query=f"query-{days_ago}",
                top_k=5,
                result_count=result_count,
                source=RetrievalLog.SOURCE_CHAT_ASK,
                duration_ms=120,
            )
            RetrievalLog.objects.filter(id=log.id).update(created_at=now - timedelta(days=days_ago))

        stale_log = RetrievalLog.objects.create(
            query="stale-query",
            top_k=5,
            result_count=1,
            source=RetrievalLog.SOURCE_CHAT_ASK,
            duration_ms=120,
        )
        RetrievalLog.objects.filter(id=stale_log.id).update(created_at=now - timedelta(days=10))

        task = IngestionTask.objects.create(
            document=failed_document,
            status=IngestionTask.STATUS_FAILED,
            current_step=IngestionTask.STEP_FAILED,
            error_message="vector insert failed",
            finished_at=now,
        )
        IngestionTask.objects.filter(id=task.id).update(created_at=now - timedelta(minutes=10))

        eval_record = EvalRecord.objects.create(
            task_type=EvalRecord.TASK_QA,
            target_name="deepseek-chat",
            status=EvalRecord.STATUS_SUCCEEDED,
            average_latency_ms=Decimal("98.50"),
        )
        EvalRecord.objects.filter(id=eval_record.id).update(created_at=now - timedelta(minutes=5))

        response = self.client.get(
            "/api/dashboard/stats",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["message"], "ok")

        data = payload["data"]
        self.assertEqual(data["knowledgebase_count"], 1)
        self.assertEqual(data["document_count"], 3)
        self.assertEqual(data["indexed_document_count"], 1)
        self.assertEqual(data["processing_document_count"], 1)
        self.assertEqual(data["failed_document_count"], 1)
        self.assertEqual(data["risk_event_count"], 2)
        self.assertEqual(data["pending_risk_event_count"], 1)
        self.assertEqual(data["high_risk_event_count"], 2)
        self.assertEqual(data["active_model_count"], 2)
        self.assertEqual(data["chat_request_count_24h"], 1)
        self.assertEqual(data["retrieval_hit_rate_7d"], "60.0%")
        self.assertEqual(len(data["chat_requests_7d"]), 7)
        self.assertEqual(len(data["retrieval_hits_7d"]), 7)
        self.assertEqual(
            data["risk_level_distribution"],
            {"low": 0, "medium": 0, "high": 1, "critical": 1},
        )
        self.assertEqual(
            data["document_status_distribution"],
            {
                "uploaded": 0,
                "parsed": 0,
                "chunked": 1,
                "indexed": 1,
                "failed": 1,
            },
        )
        self.assertGreaterEqual(len(data["recent_activity"]), 3)
        self.assertIn("type", data["recent_activity"][0])
        self.assertIn("message", data["recent_activity"][0])
        self.assertIn("timestamp", data["recent_activity"][0])

    def test_dashboard_stats_requires_authentication(self):
        response = self.client.get("/api/dashboard/stats")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {"code": 401, "message": "未认证。", "data": {}},
        )

    def test_dashboard_stats_requires_permission(self):
        response = self.client.get(
            "/api/dashboard/stats",
            HTTP_AUTHORIZATION=f"Bearer {self.basic_access_token}",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {"code": 403, "message": "无权限。", "data": {}},
        )

    def test_dashboard_stats_returns_unified_counts(self):
        first_document = self.create_document(title="一季报", filename="q1.pdf")
        second_document = self.create_document(title="二季报", filename="q2.pdf")
        self.create_risk_event(document=first_document, review_status=RiskEvent.STATUS_PENDING)
        self.create_risk_event(document=second_document, review_status=RiskEvent.STATUS_APPROVED)

        response = self.client.get(
            "/api/dashboard/stats",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["message"], "ok")
        data = payload["data"]
        self.assertEqual(data["knowledgebase_count"], 1)
        self.assertEqual(data["document_count"], 2)
        self.assertEqual(data["risk_event_count"], 2)
        self.assertEqual(data["pending_risk_event_count"], 1)
