import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from authentication.models import User
from authentication.services.jwt_service import generate_access_token
from knowledgebase.models import Document
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
        self.assertEqual(
            payload["data"],
            {
                "knowledgebase_count": 1,
                "document_count": 2,
                "risk_event_count": 2,
                "pending_risk_event_count": 1,
            },
        )
