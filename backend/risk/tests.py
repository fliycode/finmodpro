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
from knowledgebase.models import Dataset, Document, DocumentChunk
from rbac.services.rbac_service import ROLE_ADMIN, seed_roles_and_permissions
from risk.models import RiskEvent, RiskReport
from systemcheck.models import AuditRecord


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

    @patch("risk.services.extraction_service.get_chat_provider")
    def test_extract_document_ignores_events_without_company_name(self, mocked_get_chat_provider):
        document = self.create_document(title="匿名风险纪要", filename="anonymous-risk.pdf")
        DocumentChunk.objects.create(
            document=document,
            chunk_index=0,
            content="再融资延迟导致流动性压力增加。",
            metadata={"page": 1},
        )
        mocked_get_chat_provider.return_value.chat.return_value = json.dumps(
            {
                "events": [
                    {
                        "company_name": "",
                        "risk_type": "liquidity",
                        "risk_level": "medium",
                        "event_time": None,
                        "summary": "再融资延迟导致流动性压力增加。",
                        "evidence_text": "再融资延迟导致流动性压力增加。",
                        "confidence_score": "0.950",
                        "chunk_id": None,
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
        self.assertEqual(payload["data"]["created_count"], 0)
        self.assertEqual(payload["data"]["risk_events"], [])
        self.assertEqual(RiskEvent.objects.count(), 0)

    @patch("risk.services.extraction_service.get_chat_provider")
    def test_extract_document_accepts_markdown_wrapped_json_payload(self, mocked_get_chat_provider):
        document = self.create_document(title="带代码块风险纪要", filename="markdown-risk.pdf")
        chunk = DocumentChunk.objects.create(
            document=document,
            chunk_index=0,
            content="FinModPro Holdings 流动性风险上升，短债覆盖倍数下降。",
            metadata={"page": 2},
        )
        mocked_get_chat_provider.return_value.chat.return_value = (
            "```json\n"
            "{\n"
            '  "events": [\n'
            "    {\n"
            '      "company_name": "FinModPro Holdings",\n'
            '      "risk_type": "liquidity",\n'
            '      "risk_level": "high",\n'
            '      "event_time": "2025-03-01T00:00:00+08:00",\n'
            '      "summary": "流动性风险上升，短债覆盖倍数下降。",\n'
            '      "evidence_text": "FinModPro Holdings 流动性风险上升，短债覆盖倍数下降。",\n'
            '      "confidence_score": 0.910,\n'
            f'      "chunk_id": {chunk.id}\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "```"
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
        self.assertEqual(payload["data"]["risk_events"][0]["company_name"], "FinModPro Holdings")
        self.assertEqual(payload["data"]["risk_events"][0]["chunk_id"], chunk.id)

    @patch("risk.services.extraction_service.get_chat_provider")
    def test_retry_extract_document_records_retry_audit_and_creates_events(self, mocked_get_chat_provider):
        document = self.create_document(title="重试文档", filename="retry-risk.pdf")
        chunk = DocumentChunk.objects.create(
            document=document,
            chunk_index=0,
            content="FinModPro Holdings 流动性承压，需要重新触发提取。",
            metadata={"page": 1},
        )
        mocked_get_chat_provider.return_value.chat.return_value = json.dumps(
            {
                "events": [
                    {
                        "company_name": "FinModPro Holdings",
                        "risk_type": "liquidity",
                        "risk_level": "high",
                        "event_time": "2025-03-02T00:00:00+08:00",
                        "summary": "重试后提取到流动性风险。",
                        "evidence_text": "FinModPro Holdings 流动性承压，需要重新触发提取。",
                        "confidence_score": "0.910",
                        "chunk_id": chunk.id,
                    }
                ]
            }
        )

        response = self.client.post(
            f"/api/risk/documents/{document.id}/extract/retry",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"]["document_id"], document.id)
        self.assertEqual(payload["data"]["created_count"], 1)
        self.assertEqual(RiskEvent.objects.count(), 1)
        self.assertTrue(
            AuditRecord.objects.filter(
                action="risk.extract.retry",
                target_type="document",
                target_id=str(document.id),
                status=AuditRecord.STATUS_RETRIED,
            ).exists()
        )


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

    @patch("risk.services.extraction_service.get_chat_provider")
    def test_retry_batch_extract_records_retry_audit_and_processes_documents(self, mocked_get_chat_provider):
        extractable_document = self.create_document(title="批量重试文档", filename="retry-batch.pdf")
        chunk = DocumentChunk.objects.create(
            document=extractable_document,
            chunk_index=0,
            content="批量重试后抽取信用风险。",
            metadata={"page": 3},
        )
        mocked_get_chat_provider.return_value.chat.return_value = json.dumps(
            {
                "events": [
                    {
                        "company_name": "FinModPro Holdings",
                        "risk_type": "credit",
                        "risk_level": "medium",
                        "event_time": None,
                        "summary": "批量重试成功。",
                        "evidence_text": "批量重试后抽取信用风险。",
                        "confidence_score": "0.780",
                        "chunk_id": chunk.id,
                    }
                ]
            }
        )

        response = self.client.post(
            "/api/risk/documents/extract-batch/retry",
            data=json.dumps({"document_ids": [extractable_document.id]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"]["total_documents"], 1)
        self.assertEqual(payload["data"]["total_created_count"], 1)
        self.assertEqual(RiskEvent.objects.count(), 1)
        self.assertTrue(
            AuditRecord.objects.filter(
                action="risk.batch_extract.retry",
                target_type="documents",
                target_id=str(extractable_document.id),
                status=AuditRecord.STATUS_RETRIED,
            ).exists()
        )


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


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class RiskEventReviewApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()
        self.admin_user = User.objects.create_user(
            username="risk-review-admin",
            password="secret123",
            email="risk-review-admin@example.com",
        )
        self.admin_user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.admin_token = generate_access_token(self.admin_user)

        self.unauthorized_user = User.objects.create_user(
            username="risk-review-member",
            password="secret123",
            email="risk-review-member@example.com",
        )
        self.unauthorized_token = generate_access_token(self.unauthorized_user)

        self.risk_event = RiskEvent.objects.create(
            company_name="FinModPro Holdings",
            risk_type="liquidity",
            risk_level=RiskEvent.LEVEL_HIGH,
            summary="待审核事件",
            evidence_text="证据文本",
            confidence_score=Decimal("0.810"),
            review_status=RiskEvent.STATUS_PENDING,
        )

    def test_review_risk_event_requires_authentication(self):
        response = self.client.post(
            f"/api/risk/events/{self.risk_event.id}/review",
            data=json.dumps({"review_status": RiskEvent.STATUS_APPROVED}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {"code": 401, "message": "未认证。", "data": {}},
        )

    def test_review_risk_event_rejects_user_without_permission(self):
        response = self.client.post(
            f"/api/risk/events/{self.risk_event.id}/review",
            data=json.dumps({"review_status": RiskEvent.STATUS_APPROVED}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.unauthorized_token}",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {"code": 403, "message": "无权限。", "data": {}},
        )

    def test_review_risk_event_validates_review_status(self):
        response = self.client.post(
            f"/api/risk/events/{self.risk_event.id}/review",
            data=json.dumps({"review_status": RiskEvent.STATUS_PENDING}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_token}",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["code"], 400)
        self.assertIn("review_status", payload["data"])

    def test_review_risk_event_returns_404_when_event_missing(self):
        response = self.client.post(
            "/api/risk/events/999999/review",
            data=json.dumps({"review_status": RiskEvent.STATUS_APPROVED}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_token}",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {"code": 404, "message": "风险事件不存在。", "data": {}},
        )

    def test_review_risk_event_updates_review_status(self):
        response = self.client.post(
            f"/api/risk/events/{self.risk_event.id}/review",
            data=json.dumps({"review_status": RiskEvent.STATUS_REJECTED}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"]["risk_event"]["id"], self.risk_event.id)
        self.assertEqual(
            payload["data"]["risk_event"]["review_status"],
            RiskEvent.STATUS_REJECTED,
        )

        self.risk_event.refresh_from_db()
        self.assertEqual(self.risk_event.review_status, RiskEvent.STATUS_REJECTED)


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


class RiskReportModelTests(TestCase):
    def test_risk_report_can_be_created_for_company_scope(self):
        report = RiskReport.objects.create(
            scope_type=RiskReport.SCOPE_COMPANY,
            title="FinModPro Holdings 风险报告",
            company_name="FinModPro Holdings",
            summary="公司维度风险摘要",
            content="公司维度风险正文",
            source_metadata={"event_ids": [1, 2], "document_ids": [3]},
        )

        self.assertEqual(report.scope_type, RiskReport.SCOPE_COMPANY)
        self.assertEqual(report.company_name, "FinModPro Holdings")
        self.assertIsNone(report.period_start)
        self.assertEqual(report.source_metadata, {"event_ids": [1, 2], "document_ids": [3]})

    def test_risk_report_can_be_created_for_time_range_scope(self):
        report = RiskReport.objects.create(
            scope_type=RiskReport.SCOPE_TIME_RANGE,
            title="2025 Q1 风险报告",
            period_start="2025-01-01",
            period_end="2025-03-31",
            content="时间区间风险正文",
        )

        self.assertEqual(report.scope_type, RiskReport.SCOPE_TIME_RANGE)
        self.assertIsNone(report.company_name)
        self.assertEqual(str(report.period_start), "2025-01-01")
        self.assertEqual(str(report.period_end), "2025-03-31")
        self.assertEqual(report.summary, "")
        self.assertEqual(report.source_metadata, {})

    def test_risk_report_orders_by_created_at_desc_then_id_desc(self):
        first = RiskReport.objects.create(
            scope_type=RiskReport.SCOPE_COMPANY,
            title="较早报告",
            company_name="A Corp",
            content="正文 A",
        )
        second = RiskReport.objects.create(
            scope_type=RiskReport.SCOPE_TIME_RANGE,
            title="较新报告",
            period_start="2025-01-01",
            period_end="2025-01-31",
            content="正文 B",
        )

        self.assertEqual(list(RiskReport.objects.values_list("id", flat=True)), [second.id, first.id])


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class CompanyRiskReportApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()
        self.authorized_user = User.objects.create_user(
            username="risk-report-admin",
            password="secret123",
            email="risk-report-admin@example.com",
        )
        self.authorized_user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.authorized_token = generate_access_token(self.authorized_user)

        self.unauthorized_user = User.objects.create_user(
            username="risk-report-member",
            password="secret123",
            email="risk-report-member@example.com",
        )
        self.unauthorized_token = generate_access_token(self.unauthorized_user)

        self.first_document = Document.objects.create(
            title="风险来源文档 A",
            file=SimpleUploadedFile("report-a.pdf", b"risk-content", content_type="application/pdf"),
            filename="report-a.pdf",
            doc_type="pdf",
        )
        self.second_document = Document.objects.create(
            title="风险来源文档 B",
            file=SimpleUploadedFile("report-b.pdf", b"risk-content", content_type="application/pdf"),
            filename="report-b.pdf",
            doc_type="pdf",
        )

    def test_generate_company_report_requires_authentication(self):
        response = self.client.post(
            "/api/risk/reports/company",
            data=json.dumps({"company_name": "FinModPro Holdings"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {"code": 401, "message": "未认证。", "data": {}},
        )

    def test_generate_company_report_rejects_user_without_permission(self):
        response = self.client.post(
            "/api/risk/reports/company",
            data=json.dumps({"company_name": "FinModPro Holdings"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.unauthorized_token}",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {"code": 403, "message": "无权限。", "data": {}},
        )

    def test_generate_company_report_validates_company_name(self):
        response = self.client.post(
            "/api/risk/reports/company",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.authorized_token}",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["code"], 400)
        self.assertIn("company_name", payload["data"])

    def test_generate_company_report_returns_404_when_no_approved_events(self):
        RiskEvent.objects.create(
            company_name="FinModPro Holdings",
            risk_type="liquidity",
            risk_level=RiskEvent.LEVEL_HIGH,
            summary="待审核事件",
            evidence_text="证据 A",
            confidence_score=Decimal("0.810"),
            review_status=RiskEvent.STATUS_PENDING,
            document=self.first_document,
        )

        response = self.client.post(
            "/api/risk/reports/company",
            data=json.dumps({"company_name": "FinModPro Holdings"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.authorized_token}",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {"code": 404, "message": "未找到已审核通过的风险事件。", "data": {}},
        )

    def test_generate_company_report_creates_report_from_approved_events_only(self):
        approved_event = RiskEvent.objects.create(
            company_name="FinModPro Holdings",
            risk_type="liquidity",
            risk_level=RiskEvent.LEVEL_HIGH,
            event_time="2025-02-10T09:00:00+08:00",
            summary="流动性风险上升",
            evidence_text="短债覆盖倍数下降。",
            confidence_score=Decimal("0.920"),
            review_status=RiskEvent.STATUS_APPROVED,
            document=self.first_document,
        )
        second_approved_event = RiskEvent.objects.create(
            company_name="FinModPro Holdings",
            risk_type="credit",
            risk_level=RiskEvent.LEVEL_MEDIUM,
            event_time="2025-02-20T09:00:00+08:00",
            summary="信用风险增加",
            evidence_text="客户回款周期拉长。",
            confidence_score=Decimal("0.760"),
            review_status=RiskEvent.STATUS_APPROVED,
            document=self.second_document,
        )
        RiskEvent.objects.create(
            company_name="FinModPro Holdings",
            risk_type="market",
            risk_level=RiskEvent.LEVEL_LOW,
            summary="未审核事件",
            evidence_text="不应被纳入报告。",
            confidence_score=Decimal("0.450"),
            review_status=RiskEvent.STATUS_PENDING,
            document=self.second_document,
        )

        response = self.client.post(
            "/api/risk/reports/company",
            data=json.dumps({"company_name": "FinModPro Holdings"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.authorized_token}",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        report_payload = payload["data"]["report"]
        self.assertEqual(report_payload["scope_type"], RiskReport.SCOPE_COMPANY)
        self.assertEqual(report_payload["company_name"], "FinModPro Holdings")
        self.assertIn("FinModPro Holdings 风险报告", report_payload["title"])
        self.assertIn("已审核通过风险事件", report_payload["summary"])
        self.assertIn("流动性风险上升", report_payload["content"])
        self.assertIn("信用风险增加", report_payload["content"])
        self.assertEqual(
            report_payload["source_metadata"]["event_ids"],
            [approved_event.id, second_approved_event.id],
        )
        self.assertEqual(
            report_payload["source_metadata"]["document_ids"],
            [self.first_document.id, self.second_document.id],
        )
        self.assertEqual(
            report_payload["source_metadata"]["risk_type_counts"],
            {"credit": 1, "liquidity": 1},
        )
        self.assertEqual(RiskReport.objects.count(), 1)


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class TimeRangeRiskReportApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()
        self.authorized_user = User.objects.create_user(
            username="time-report-admin",
            password="secret123",
            email="time-report-admin@example.com",
        )
        self.authorized_user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.authorized_token = generate_access_token(self.authorized_user)

        self.unauthorized_user = User.objects.create_user(
            username="time-report-member",
            password="secret123",
            email="time-report-member@example.com",
        )
        self.unauthorized_token = generate_access_token(self.unauthorized_user)

        self.first_document = Document.objects.create(
            title="时间区间来源文档 A",
            file=SimpleUploadedFile("time-a.pdf", b"risk-content", content_type="application/pdf"),
            filename="time-a.pdf",
            doc_type="pdf",
        )
        self.second_document = Document.objects.create(
            title="时间区间来源文档 B",
            file=SimpleUploadedFile("time-b.pdf", b"risk-content", content_type="application/pdf"),
            filename="time-b.pdf",
            doc_type="pdf",
        )

    def test_generate_time_range_report_requires_authentication(self):
        response = self.client.post(
            "/api/risk/reports/time-range",
            data=json.dumps({"period_start": "2025-02-01", "period_end": "2025-02-28"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {"code": 401, "message": "未认证。", "data": {}},
        )

    def test_generate_time_range_report_rejects_user_without_permission(self):
        response = self.client.post(
            "/api/risk/reports/time-range",
            data=json.dumps({"period_start": "2025-02-01", "period_end": "2025-02-28"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.unauthorized_token}",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {"code": 403, "message": "无权限。", "data": {}},
        )

    def test_generate_time_range_report_validates_periods(self):
        response = self.client.post(
            "/api/risk/reports/time-range",
            data=json.dumps({"period_start": "2025-03-01", "period_end": "2025-02-01"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.authorized_token}",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["code"], 400)
        self.assertEqual(payload["message"], "period_start 不能晚于 period_end。")

    def test_generate_time_range_report_returns_404_when_no_approved_events(self):
        RiskEvent.objects.create(
            company_name="FinModPro Holdings",
            risk_type="liquidity",
            risk_level=RiskEvent.LEVEL_HIGH,
            event_time="2025-02-10T09:00:00+08:00",
            summary="待审核事件",
            evidence_text="证据 A",
            confidence_score=Decimal("0.810"),
            review_status=RiskEvent.STATUS_PENDING,
            document=self.first_document,
        )

        response = self.client.post(
            "/api/risk/reports/time-range",
            data=json.dumps({"period_start": "2025-02-01", "period_end": "2025-02-28"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.authorized_token}",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {"code": 404, "message": "未找到已审核通过的风险事件。", "data": {}},
        )

    def test_generate_time_range_report_creates_report_from_approved_events_only(self):
        in_range_event = RiskEvent.objects.create(
            company_name="FinModPro Holdings",
            risk_type="liquidity",
            risk_level=RiskEvent.LEVEL_HIGH,
            event_time="2025-02-10T09:00:00+08:00",
            summary="区间内事件 A",
            evidence_text="证据 A",
            confidence_score=Decimal("0.910"),
            review_status=RiskEvent.STATUS_APPROVED,
            document=self.first_document,
        )
        second_in_range_event = RiskEvent.objects.create(
            company_name="Another Corp",
            risk_type="credit",
            risk_level=RiskEvent.LEVEL_MEDIUM,
            event_time="2025-02-18T09:00:00+08:00",
            summary="区间内事件 B",
            evidence_text="证据 B",
            confidence_score=Decimal("0.740"),
            review_status=RiskEvent.STATUS_APPROVED,
            document=self.second_document,
        )
        RiskEvent.objects.create(
            company_name="FinModPro Holdings",
            risk_type="market",
            risk_level=RiskEvent.LEVEL_LOW,
            event_time="2025-03-05T09:00:00+08:00",
            summary="区间外事件",
            evidence_text="不应被纳入。",
            confidence_score=Decimal("0.430"),
            review_status=RiskEvent.STATUS_APPROVED,
            document=self.second_document,
        )
        RiskEvent.objects.create(
            company_name="Another Corp",
            risk_type="operation",
            risk_level=RiskEvent.LEVEL_LOW,
            event_time="2025-02-15T09:00:00+08:00",
            summary="未审核事件",
            evidence_text="也不应被纳入。",
            confidence_score=Decimal("0.520"),
            review_status=RiskEvent.STATUS_PENDING,
            document=self.second_document,
        )

        response = self.client.post(
            "/api/risk/reports/time-range",
            data=json.dumps({"period_start": "2025-02-01", "period_end": "2025-02-28"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.authorized_token}",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        report_payload = payload["data"]["report"]
        self.assertEqual(report_payload["scope_type"], RiskReport.SCOPE_TIME_RANGE)
        self.assertIsNone(report_payload["company_name"])
        self.assertEqual(report_payload["period_start"], "2025-02-01")
        self.assertEqual(report_payload["period_end"], "2025-02-28")
        self.assertIn("时间区间风险报告", report_payload["title"])
        self.assertIn("已审核通过风险事件", report_payload["summary"])
        self.assertIn("区间内事件 A", report_payload["content"])
        self.assertIn("区间内事件 B", report_payload["content"])
        self.assertEqual(
            report_payload["source_metadata"]["event_ids"],
            [in_range_event.id, second_in_range_event.id],
        )
        self.assertEqual(
            report_payload["source_metadata"]["document_ids"],
            [self.first_document.id, self.second_document.id],
        )
        self.assertEqual(
            report_payload["source_metadata"]["risk_type_counts"],
            {"credit": 1, "liquidity": 1},
        )


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class RiskAnalyticsOverviewApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()
        self.authorized_user = User.objects.create_user(
            username="risk-analytics-admin",
            password="secret123",
            email="risk-analytics-admin@example.com",
        )
        self.authorized_user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.authorized_token = generate_access_token(self.authorized_user)

        self.first_document = Document.objects.create(
            title="风险分析文档 A",
            file=SimpleUploadedFile("analytics-a.pdf", b"risk-content", content_type="application/pdf"),
            filename="analytics-a.pdf",
            doc_type="pdf",
        )
        self.second_document = Document.objects.create(
            title="风险分析文档 B",
            file=SimpleUploadedFile("analytics-b.pdf", b"risk-content", content_type="application/pdf"),
            filename="analytics-b.pdf",
            doc_type="pdf",
        )

    def test_get_overview_requires_authentication(self):
        response = self.client.get("/api/risk/analytics/overview")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {"code": 401, "message": "未认证。", "data": {}},
        )

    def test_get_overview_returns_chart_ready_distributions_and_trend(self):
        RiskEvent.objects.create(
            company_name="FinModPro Holdings",
            risk_type="liquidity",
            risk_level=RiskEvent.LEVEL_HIGH,
            event_time="2025-02-10T09:00:00+08:00",
            summary="流动性风险上升",
            evidence_text="短债覆盖倍数下降。",
            confidence_score=Decimal("0.910"),
            review_status=RiskEvent.STATUS_APPROVED,
            document=self.first_document,
        )
        RiskEvent.objects.create(
            company_name="Another Corp",
            risk_type="credit",
            risk_level=RiskEvent.LEVEL_MEDIUM,
            event_time="2025-02-18T09:00:00+08:00",
            summary="信用风险增加",
            evidence_text="客户回款周期拉长。",
            confidence_score=Decimal("0.760"),
            review_status=RiskEvent.STATUS_APPROVED,
            document=self.second_document,
        )
        RiskEvent.objects.create(
            company_name="FinModPro Holdings",
            risk_type="market",
            risk_level=RiskEvent.LEVEL_CRITICAL,
            event_time="2025-03-05T09:00:00+08:00",
            summary="区间外事件",
            evidence_text="不应被纳入。",
            confidence_score=Decimal("0.820"),
            review_status=RiskEvent.STATUS_APPROVED,
            document=self.first_document,
        )
        RiskEvent.objects.create(
            company_name="FinModPro Holdings",
            risk_type="operation",
            risk_level=RiskEvent.LEVEL_LOW,
            event_time="2025-02-15T09:00:00+08:00",
            summary="待审核事件",
            evidence_text="不应被纳入已确认统计。",
            confidence_score=Decimal("0.620"),
            review_status=RiskEvent.STATUS_PENDING,
            document=self.first_document,
        )

        response = self.client.get(
            "/api/risk/analytics/overview?review_status=approved&period_start=2025-02-01&period_end=2025-02-28",
            HTTP_AUTHORIZATION=f"Bearer {self.authorized_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        analytics = payload["data"]
        self.assertEqual(
            analytics["summary"],
            {
                "total_events": 2,
                "high_risk_events": 1,
                "pending_reviews": 0,
                "unique_companies": 2,
                "document_count": 2,
            },
        )
        self.assertEqual(
            analytics["risk_level_distribution"],
            [
                {"key": "high", "value": 1},
                {"key": "medium", "value": 1},
            ],
        )
        self.assertEqual(
            analytics["risk_type_distribution"],
            [
                {"key": "credit", "value": 1},
                {"key": "liquidity", "value": 1},
            ],
        )
        self.assertEqual(
            analytics["trend"],
            [
                {"date": "2025-02-10", "value": 1},
                {"date": "2025-02-18", "value": 1},
            ],
        )
        self.assertEqual(
            analytics["top_companies"],
            [
                {"key": "Another Corp", "value": 1},
                {"key": "FinModPro Holdings", "value": 1},
            ],
        )


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class RiskReportExportApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()
        self.authorized_user = User.objects.create_user(
            username="risk-export-admin",
            password="secret123",
            email="risk-export-admin@example.com",
        )
        self.authorized_user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.authorized_token = generate_access_token(self.authorized_user)

        self.report = RiskReport.objects.create(
            scope_type=RiskReport.SCOPE_COMPANY,
            title="FinModPro Holdings 风险报告",
            company_name="FinModPro Holdings",
            summary="共汇总 2 条已审核通过风险事件。",
            content="报告详情\n- 流动性风险上升",
            source_metadata={
                "event_ids": [1, 2],
                "document_ids": [11, 12],
                "risk_type_counts": {"liquidity": 1, "credit": 1},
            },
        )

    def test_export_report_returns_markdown_attachment(self):
        response = self.client.get(
            f"/api/risk/reports/{self.report.id}/export",
            HTTP_AUTHORIZATION=f"Bearer {self.authorized_token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/markdown; charset=utf-8")
        self.assertIn(
            f'attachment; filename="risk-report-{self.report.id}.md"',
            response["Content-Disposition"],
        )
        body = response.content.decode("utf-8")
        self.assertIn("# FinModPro Holdings 风险报告", body)
        self.assertIn("共汇总 2 条已审核通过风险事件。", body)
        self.assertIn("报告详情", body)


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class RiskSentimentApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()

        self.user = User.objects.create_user(
            username="risk-sentiment-admin",
            password="secret123",
            email="risk-sentiment-admin@example.com",
        )
        self.user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.access_token = generate_access_token(self.user)

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def create_document(self, *, title, filename, parsed_text, dataset=None):
        return Document.objects.create(
            title=title,
            file=SimpleUploadedFile(filename, b"sentiment-content", content_type="application/pdf"),
            filename=filename,
            doc_type="pdf",
            dataset=dataset,
            uploaded_by=self.user,
            owner=self.user,
            visibility=Document.VISIBILITY_INTERNAL,
            status=Document.STATUS_INDEXED,
            parsed_text=parsed_text,
        )

    @patch("risk.services.sentiment_service.get_chat_provider")
    def test_sentiment_analyze_supports_dataset_scope_and_source_groups(self, mocked_get_chat_provider):
        dataset = Dataset.objects.create(name="舆情数据集", description="dataset scope", owner=self.user)
        self.create_document(
            title="公告一",
            filename="doc-1.txt",
            parsed_text="公司现金流改善，利润增长明显。",
            dataset=dataset,
        )
        self.create_document(
            title="公告二",
            filename="doc-2.txt",
            parsed_text="客户投诉增加，交付延迟，盈利承压。",
            dataset=dataset,
        )
        mocked_get_chat_provider.return_value.chat.side_effect = [
            json.dumps(
                {
                    "sentiment": "positive",
                    "risk_tendency": "low",
                    "summary": "公司现金流改善，利润增长明显。",
                    "confidence_score": 0.94,
                    "evidence": ["现金流改善", "利润增长"],
                }
            ),
            json.dumps(
                {
                    "sentiment": "negative",
                    "risk_tendency": "elevated",
                    "summary": "客户投诉增加，交付延迟，盈利承压。",
                    "confidence_score": 0.97,
                    "evidence": ["客户投诉增加", "交付延迟"],
                }
            ),
        ]

        response = self.client.post(
            "/api/risk/sentiment/analyze",
            data=json.dumps({"dataset_id": dataset.id}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"]["summary"]["overall_sentiment"], "negative")
        self.assertEqual(payload["data"]["summary"]["risk_tendency"], "elevated")
        self.assertEqual(len(payload["data"]["distribution"]), 3)
        self.assertEqual(len(payload["data"]["source_groups"]), 2)
        self.assertEqual(
            [item["document_title"] for item in payload["data"]["items"]],
            ["公告一", "公告二"],
        )
        mocked_get_chat_provider.return_value.chat.assert_called()

    @patch("risk.services.sentiment_service.get_chat_provider")
    def test_sentiment_analyze_supports_document_scope(self, mocked_get_chat_provider):
        document = self.create_document(
            title="精选文档",
            filename="doc-3.txt",
            parsed_text="市场反馈中性，整体预期保持稳定。",
        )
        mocked_get_chat_provider.return_value.chat.return_value = json.dumps(
            {
                "sentiment": "neutral",
                "risk_tendency": "moderate",
                "summary": "市场反馈中性，整体预期保持稳定。",
                "confidence_score": 0.82,
                "evidence": ["中性", "稳定"],
            }
        )

        response = self.client.post(
            "/api/risk/sentiment/analyze",
            data=json.dumps({"document_ids": [document.id]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["summary"]["overall_sentiment"], "neutral")
        self.assertEqual(payload["data"]["items"][0]["document_id"], document.id)
        self.assertEqual(payload["data"]["distribution"][1]["key"], "neutral")
