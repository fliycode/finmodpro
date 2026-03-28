import json
import shutil
import tempfile
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from authentication.models import User
from authentication.services.jwt_service import generate_access_token
from knowledgebase.models import Document, DocumentChunk
from rbac.services.rbac_service import ROLE_ADMIN, seed_roles_and_permissions
from risk.models import RiskEvent


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class RiskExtractionApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()

        self.user = User.objects.create_user(
            username="risk-admin",
            password="secret123",
            email="risk-admin@example.com",
        )
        self.user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.access_token = generate_access_token(self.user)

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def create_document(self, *, title="Q4 风险纪要", filename="risk.pdf"):
        return Document.objects.create(
            title=title,
            file=SimpleUploadedFile(filename, b"risk-content", content_type="application/pdf"),
            filename=filename,
            doc_type="pdf",
        )

    @patch("risk.services.extraction_service.get_chat_provider")
    def test_extract_document_creates_risk_events(self, mocked_get_chat_provider):
        document = self.create_document()
        chunk = DocumentChunk.objects.create(
            document=document,
            chunk_index=0,
            content="FinModPro Holdings 流动性风险上升，短债覆盖倍数下降。",
            metadata={"page": 2},
        )
        mocked_get_chat_provider.return_value.chat.return_value = json.dumps(
            {
                "events": [
                    {
                        "company_name": "FinModPro Holdings",
                        "risk_type": "liquidity",
                        "risk_level": "high",
                        "event_time": "2025-03-01T00:00:00+08:00",
                        "summary": "流动性风险上升，短债覆盖倍数下降。",
                        "evidence_text": "FinModPro Holdings 流动性风险上升，短债覆盖倍数下降。",
                        "confidence_score": "0.910",
                        "chunk_id": chunk.id,
                    }
                ]
            }
        )

        response = self.client.post(
            f"/api/risk/documents/{document.id}/extract",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"]["document_id"], document.id)
        self.assertEqual(payload["data"]["created_count"], 1)
        self.assertEqual(len(payload["data"]["risk_events"]), 1)
        self.assertEqual(payload["data"]["risk_events"][0]["company_name"], "FinModPro Holdings")
        self.assertEqual(payload["data"]["risk_events"][0]["chunk_id"], chunk.id)

        risk_event = RiskEvent.objects.get()
        self.assertEqual(risk_event.document_id, document.id)
        self.assertEqual(risk_event.chunk_id, chunk.id)
        self.assertEqual(risk_event.risk_type, "liquidity")

    def test_extract_document_returns_404_when_document_missing(self):
        response = self.client.post(
            "/api/risk/documents/999999/extract",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {"code": 404, "message": "文档不存在。", "data": {}},
        )

    @patch("risk.services.extraction_service.get_chat_provider")
    def test_extract_document_returns_empty_result_when_document_has_no_chunks(self, mocked_get_chat_provider):
        document = self.create_document()

        response = self.client.post(
            f"/api/risk/documents/{document.id}/extract",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["message"], "文档暂无可抽取内容。")
        self.assertEqual(payload["data"]["document_id"], document.id)
        self.assertEqual(payload["data"]["created_count"], 0)
        self.assertEqual(payload["data"]["risk_events"], [])
        self.assertEqual(RiskEvent.objects.count(), 0)
        mocked_get_chat_provider.assert_not_called()


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class RiskBatchExtractionApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()

        self.user = User.objects.create_user(
            username="risk-batch-admin",
            password="secret123",
            email="risk-batch-admin@example.com",
        )
        self.user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.access_token = generate_access_token(self.user)

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def create_document(self, *, title, filename):
        return Document.objects.create(
            title=title,
            file=SimpleUploadedFile(filename, b"risk-content", content_type="application/pdf"),
            filename=filename,
            doc_type="pdf",
        )

    def test_batch_extract_validates_document_ids(self):
        response = self.client.post(
            "/api/risk/documents/extract-batch",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["code"], 400)
        self.assertIn("document_ids", payload["data"])
        self.assertEqual(RiskEvent.objects.count(), 0)

    @patch("risk.services.extraction_service.get_chat_provider")
    def test_batch_extract_returns_mixed_results_summary(self, mocked_get_chat_provider):
        extractable_document = self.create_document(title="可抽取文档", filename="extractable.pdf")
        empty_document = self.create_document(title="无切块文档", filename="empty.pdf")
        chunk = DocumentChunk.objects.create(
            document=extractable_document,
            chunk_index=0,
            content="FinModPro Holdings 信用风险升高，客户回款周期拉长。",
            metadata={"page": 5},
        )
        mocked_get_chat_provider.return_value.chat.return_value = json.dumps(
            {
                "events": [
                    {
                        "company_name": "FinModPro Holdings",
                        "risk_type": "credit",
                        "risk_level": "medium",
                        "event_time": None,
                        "summary": "信用风险升高，客户回款周期拉长。",
                        "evidence_text": "FinModPro Holdings 信用风险升高，客户回款周期拉长。",
                        "confidence_score": "0.780",
                        "chunk_id": chunk.id,
                    }
                ]
            }
        )

        response = self.client.post(
            "/api/risk/documents/extract-batch",
            data=json.dumps({"document_ids": [extractable_document.id, empty_document.id, 999999]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"]["total_documents"], 3)
        self.assertEqual(payload["data"]["processed_documents"], 3)
        self.assertEqual(payload["data"]["total_created_count"], 1)
        self.assertEqual(
            [item["status"] for item in payload["data"]["results"]],
            ["created", "no_chunks", "not_found"],
        )
        self.assertEqual(payload["data"]["results"][0]["document_id"], extractable_document.id)
        self.assertEqual(payload["data"]["results"][0]["created_count"], 1)
        self.assertEqual(payload["data"]["results"][1]["document_id"], empty_document.id)
        self.assertEqual(payload["data"]["results"][2]["document_id"], 999999)
        self.assertEqual(RiskEvent.objects.count(), 1)
        mocked_get_chat_provider.return_value.chat.assert_called_once()


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class RiskEventListApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()

        self.authorized_user = User.objects.create_user(
            username="risk-list-admin",
            password="secret123",
            email="risk-list-admin@example.com",
        )
        self.authorized_user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.authorized_token = generate_access_token(self.authorized_user)

        self.unauthorized_user = User.objects.create_user(
            username="risk-list-member",
            password="secret123",
            email="risk-list-member@example.com",
        )
        self.unauthorized_token = generate_access_token(self.unauthorized_user)

        self.document = Document.objects.create(
            title="筛选文档",
            file=SimpleUploadedFile("filter.pdf", b"risk-content", content_type="application/pdf"),
            filename="filter.pdf",
            doc_type="pdf",
        )
        self.chunk = DocumentChunk.objects.create(
            document=self.document,
            chunk_index=0,
            content="风险切块",
            metadata={},
        )

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_list_risk_events_requires_authentication(self):
        response = self.client.get("/api/risk/events")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {"code": 401, "message": "未认证。", "data": {}},
        )

    def test_list_risk_events_rejects_user_without_permission(self):
        response = self.client.get(
            "/api/risk/events",
            HTTP_AUTHORIZATION=f"Bearer {self.unauthorized_token}",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {"code": 403, "message": "无权限。", "data": {}},
        )

    def test_list_risk_events_supports_multi_condition_filters(self):
        RiskEvent.objects.create(
            company_name="FinModPro Holdings",
            risk_type="liquidity",
            risk_level=RiskEvent.LEVEL_HIGH,
            summary="目标事件",
            evidence_text="证据 A",
            confidence_score=Decimal("0.920"),
            review_status=RiskEvent.STATUS_APPROVED,
            document=self.document,
            chunk=self.chunk,
        )
        RiskEvent.objects.create(
            company_name="FinModPro Holdings",
            risk_type="liquidity",
            risk_level=RiskEvent.LEVEL_HIGH,
            summary="状态不匹配",
            evidence_text="证据 B",
            confidence_score=Decimal("0.820"),
            review_status=RiskEvent.STATUS_PENDING,
            document=self.document,
            chunk=self.chunk,
        )
        RiskEvent.objects.create(
            company_name="Other Corp",
            risk_type="credit",
            risk_level=RiskEvent.LEVEL_MEDIUM,
            summary="公司和类型不匹配",
            evidence_text="证据 C",
            confidence_score=Decimal("0.730"),
            review_status=RiskEvent.STATUS_APPROVED,
        )

        response = self.client.get(
            "/api/risk/events?company_name=FinMod&risk_type=liquid&review_status=approved",
            HTTP_AUTHORIZATION=f"Bearer {self.authorized_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"]["total"], 1)
        self.assertEqual(payload["data"]["risk_events"][0]["summary"], "目标事件")

    def test_list_risk_events_returns_empty_result(self):
        response = self.client.get(
            "/api/risk/events?company_name=missing",
            HTTP_AUTHORIZATION=f"Bearer {self.authorized_token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], {"total": 0, "risk_events": []})

    def test_list_risk_events_returns_expected_structure_and_sorting(self):
        first_event = RiskEvent.objects.create(
            company_name="A Corp",
            risk_type="market",
            risk_level=RiskEvent.LEVEL_LOW,
            summary="较早事件",
            evidence_text="证据 A",
            confidence_score=Decimal("0.410"),
            review_status=RiskEvent.STATUS_PENDING,
            document=self.document,
            chunk=self.chunk,
        )
        second_event = RiskEvent.objects.create(
            company_name="B Corp",
            risk_type="credit",
            risk_level=RiskEvent.LEVEL_HIGH,
            summary="较新事件",
            evidence_text="证据 B",
            confidence_score=Decimal("0.870"),
            review_status=RiskEvent.STATUS_APPROVED,
            document=self.document,
            chunk=self.chunk,
        )

        response = self.client.get(
            "/api/risk/events",
            HTTP_AUTHORIZATION=f"Bearer {self.authorized_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["total"], 2)
        self.assertEqual(
            [item["id"] for item in payload["data"]["risk_events"]],
            [second_event.id, first_event.id],
        )
        first_item = payload["data"]["risk_events"][0]
        self.assertEqual(first_item["document_id"], self.document.id)
        self.assertEqual(first_item["chunk_id"], self.chunk.id)
        self.assertIn("created_at", first_item)
        self.assertIn("updated_at", first_item)
        self.assertIn("review_status", first_item)


class RiskEventModelTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def create_document(self, *, title="Quarterly risk memo", filename="risk.pdf"):
        return Document.objects.create(
            title=title,
            file=SimpleUploadedFile(filename, b"risk-content", content_type="application/pdf"),
            filename=filename,
            doc_type="pdf",
        )

    def test_risk_event_can_be_created_with_required_fields_and_default_review_status(self):
        event = RiskEvent.objects.create(
            company_name="FinModPro Holdings",
            risk_type="liquidity",
            risk_level=RiskEvent.LEVEL_HIGH,
            event_time=timezone.now(),
            summary="流动性风险上升，短债覆盖倍数下降。",
            evidence_text="短期债务增长 18%，现金及等价物下降 9%。",
            confidence_score=Decimal("0.870"),
        )

        self.assertEqual(event.review_status, RiskEvent.STATUS_PENDING)
        self.assertEqual(event.confidence_score, Decimal("0.870"))
        self.assertIsNone(event.document)
        self.assertIsNone(event.chunk)

    def test_risk_event_can_reference_document_and_chunk_for_future_traceability(self):
        document = self.create_document()
        chunk = DocumentChunk.objects.create(
            document=document,
            chunk_index=0,
            content="风险段落内容",
            metadata={"page": 3},
        )

        event = RiskEvent.objects.create(
            company_name="FinModPro Holdings",
            risk_type="credit",
            risk_level=RiskEvent.LEVEL_MEDIUM,
            event_time=timezone.now(),
            summary="应收账款回款周期拉长。",
            evidence_text="核心客户回款周期由 45 天上升到 63 天。",
            confidence_score=Decimal("0.650"),
            document=document,
            chunk=chunk,
        )

        self.assertEqual(event.document_id, document.id)
        self.assertEqual(event.chunk_id, chunk.id)
        self.assertEqual(document.risk_events.get().id, event.id)
        self.assertEqual(chunk.risk_events.get().id, event.id)

    def test_deleting_document_or_chunk_keeps_risk_event_but_clears_source_links(self):
        document = self.create_document()
        chunk = DocumentChunk.objects.create(
            document=document,
            chunk_index=1,
            content="另一个风险段落",
            metadata={},
        )
        event = RiskEvent.objects.create(
            company_name="FinModPro Holdings",
            risk_type="market",
            risk_level=RiskEvent.LEVEL_LOW,
            event_time=timezone.now(),
            summary="汇率波动风险可控。",
            evidence_text="美元敞口下降，套保比例维持在 80%。",
            confidence_score=Decimal("0.520"),
            document=document,
            chunk=chunk,
        )

        chunk.delete()
        document.delete()

        event.refresh_from_db()
        self.assertIsNone(event.document)
        self.assertIsNone(event.chunk)

    def test_risk_event_orders_by_created_at_desc_then_id_desc(self):
        first = RiskEvent.objects.create(
            company_name="A Corp",
            risk_type="liquidity",
            risk_level=RiskEvent.LEVEL_LOW,
            summary="较早事件",
            evidence_text="证据 A",
            confidence_score=Decimal("0.400"),
        )
        second = RiskEvent.objects.create(
            company_name="B Corp",
            risk_type="credit",
            risk_level=RiskEvent.LEVEL_HIGH,
            summary="较新事件",
            evidence_text="证据 B",
            confidence_score=Decimal("0.900"),
        )

        self.assertEqual(list(RiskEvent.objects.values_list("id", flat=True)), [second.id, first.id])
