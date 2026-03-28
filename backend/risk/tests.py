import shutil
import tempfile
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from knowledgebase.models import Document, DocumentChunk
from risk.models import RiskEvent


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
