import json
import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from authentication.models import User
from authentication.services.jwt_service import generate_access_token
from common.exceptions import UpstreamRateLimitError
from knowledgebase.models import Document, DocumentChunk
from knowledgebase.services.document_service import create_document_from_upload, ingest_document
from rag.models import RetrievalLog
from rag.services.embedding_service import tokenize
from rag.services.vector_store_service import clear_store, index_document
from rbac.services.rbac_service import ROLE_ADMIN, seed_roles_and_permissions


class FakeEmbeddingProvider:
    def embed(self, *, texts, options=None):
        return [[float(index + 1) for index in range(64)] for _ in texts]


def fake_vector_search(*, query, filters=None, top_k=5):
    query_tokens = set(tokenize(query))
    results = []
    queryset = DocumentChunk.objects.select_related("document").order_by("id")
    for chunk in queryset:
        metadata = chunk.metadata or {}
        document = chunk.document
        document_id = filters.get("document_id") if filters else None
        if document_id not in (None, "") and document.id != int(document_id):
            continue
        doc_type = filters.get("doc_type") if filters else None
        if doc_type and document.doc_type != doc_type:
            continue
        source_date_from = filters.get("source_date_from") if filters else None
        if source_date_from and (
            document.source_date is None or document.source_date.isoformat() < source_date_from
        ):
            continue
        source_date_to = filters.get("source_date_to") if filters else None
        if source_date_to and (
            document.source_date is None or document.source_date.isoformat() > source_date_to
        ):
            continue

        searchable_tokens = set(
            tokenize(f"{metadata.get('document_title') or document.title}\n{chunk.content}")
        )
        overlap = len(query_tokens & searchable_tokens)
        if overlap <= 0:
            continue
        score = overlap / max(len(query_tokens), 1)
        results.append(
            {
                "document_id": document.id,
                "chunk_id": chunk.id,
                "document_title": metadata.get("document_title") or document.title,
                "doc_type": metadata.get("doc_type") or document.doc_type,
                "source_date": metadata.get("source_date")
                or (document.source_date.isoformat() if document.source_date else None),
                "page_label": metadata.get("page_label", f"chunk-{chunk.chunk_index + 1}"),
                "snippet": chunk.content,
                "metadata": metadata,
                "score": score,
                "vector_score": score,
                "keyword_score": 0.0,
            }
        )
    results.sort(key=lambda item: (item["score"], item["chunk_id"]), reverse=True)
    return results[: int(top_k)]


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class RagRetrievalApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()
        clear_store()
        self.embedding_provider_patcher = patch(
            "knowledgebase.services.embedding_service.get_embedding_provider",
            return_value=FakeEmbeddingProvider(),
        )
        self.embedding_provider_patcher.start()
        self.vector_search_patcher = patch(
            "knowledgebase.services.vector_service.VectorService.search",
            side_effect=fake_vector_search,
        )
        self.vector_search_patcher.start()
        self.vector_index_patcher = patch(
            "knowledgebase.services.document_service.index_document_chunks",
            side_effect=index_document,
        )
        self.vector_index_patcher.start()
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(
            MEDIA_ROOT=self.media_root,
            MILVUS_URI=f"{self.media_root}/test-milvus.db",
            MILVUS_COLLECTION_NAME="test_document_chunks",
        )
        self.override.enable()

        self.user = User.objects.create_user(
            username="rag-admin",
            password="secret123",
            email="rag@example.com",
        )
        self.user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.access_token = generate_access_token(self.user)

        first_document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "revenue.txt",
                b"revenue growth stayed resilient and cash flow improved sharply",
                content_type="text/plain",
            ),
            title="Revenue memo",
            source_date="2025-01-15",
        )
        second_document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "risk.txt",
                b"supply chain pressure remained elevated and margin risk increased",
                content_type="text/plain",
            ),
            title="Risk memo",
            source_date="2024-10-31",
        )
        third_document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "treasury.txt",
                b"foreign exchange exposure remained elevated across the quarter",
                content_type="text/plain",
            ),
            title="Treasury hedging note",
            source_date="2025-03-31",
        )
        ingest_document(first_document)
        ingest_document(second_document)
        ingest_document(third_document)
        self.first_document = first_document
        self.second_document = second_document
        self.third_document = third_document

    def tearDown(self):
        self.embedding_provider_patcher.stop()
        self.vector_search_patcher.stop()
        self.override.disable()
        self.vector_index_patcher.stop()
        shutil.rmtree(self.media_root, ignore_errors=True)
        clear_store()

    def test_retrieval_query_returns_filtered_ranked_results(self):
        response = self.client.post(
            "/api/rag/retrieval/query",
            data=json.dumps(
                {
                    "query": "cash flow revenue",
                    "filters": {
                        "document_id": self.first_document.id,
                        "doc_type": "txt",
                        "source_date_from": "2025-01-01",
                        "source_date_to": "2025-12-31",
                    },
                    "top_k": 3,
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["query"], "cash flow revenue")
        self.assertEqual(payload["question"], "cash flow revenue")
        self.assertIn("duration_ms", payload)
        self.assertIsInstance(payload["duration_ms"], int)
        self.assertGreaterEqual(payload["duration_ms"], 0)
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(len(payload["citations"]), 1)
        self.assertEqual(payload["results"], payload["citations"])
        self.assertEqual(payload["results"][0]["document_title"], "Revenue memo")
        self.assertEqual(payload["results"][0]["doc_type"], "txt")
        self.assertEqual(payload["results"][0]["source_date"], "2025-01-15")
        self.assertEqual(payload["results"][0]["page_label"], "chunk-1")
        self.assertIn("cash flow improved sharply", payload["results"][0]["snippet"])
        self.assertIn("score", payload["results"][0])
        self.assertIn("rerank_score", payload["results"][0])
        self.assertEqual(RetrievalLog.objects.count(), 1)
        retrieval_log = RetrievalLog.objects.get()
        self.assertEqual(retrieval_log.query, "cash flow revenue")
        self.assertEqual(retrieval_log.top_k, 3)
        self.assertEqual(
            retrieval_log.filters,
            {
                "document_id": self.first_document.id,
                "doc_type": "txt",
                "source_date_from": "2025-01-01",
                "source_date_to": "2025-12-31",
            },
        )
        self.assertEqual(retrieval_log.result_count, 1)
        self.assertEqual(retrieval_log.source, RetrievalLog.SOURCE_RETRIEVAL_API)
        self.assertIsNotNone(retrieval_log.duration_ms)

    def test_retrieval_query_accepts_question_alias(self):
        response = self.client.post(
            "/api/rag/retrieval/query",
            data=json.dumps({"question": "margin risk"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["query"], "margin risk")
        self.assertEqual(payload["question"], "margin risk")
        self.assertIn("duration_ms", payload)
        self.assertIsInstance(payload["citations"], list)

    def test_retrieval_query_uses_keyword_search_to_match_title_only_hits(self):
        response = self.client.post(
            "/api/rag/retrieval/query",
            data=json.dumps({"query": "treasury hedging note", "top_k": 2}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["document_title"], "Treasury hedging note")
        self.assertIn("foreign exchange exposure", payload["results"][0]["snippet"])

    @patch("knowledgebase.services.vector_service.VectorService.search")
    def test_retrieval_query_uses_milvus_backing_store(self, mocked_search):
        mocked_search.return_value = [
            {
                "document_id": self.first_document.id,
                "chunk_id": self.first_document.chunks.first().id,
                "document_title": "Revenue memo",
                "doc_type": "txt",
                "source_date": "2025-01-15",
                "page_label": "chunk-1",
                "snippet": "cash flow revenue",
                "metadata": {"document_id": self.first_document.id},
                "score": 0.91,
            }
        ]

        response = self.client.post(
            "/api/rag/retrieval/query",
            data=json.dumps({"query": "cash flow revenue"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        mocked_search.assert_called_once()

    def test_retrieval_filters_still_apply_to_keyword_hits(self):
        response = self.client.post(
            "/api/rag/retrieval/query",
            data=json.dumps(
                {
                    "query": "treasury hedging note",
                    "filters": {"document_id": self.first_document.id},
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["results"], [])
        self.assertEqual(payload["citations"], [])

    def test_retrieval_rejects_user_without_ask_financial_qa_permission(self):
        unauthorized_user = User.objects.create_user(
            username="rag-unauthorized",
            password="secret123",
            email="rag-unauthorized@example.com",
        )
        token = generate_access_token(unauthorized_user)

        response = self.client.post(
            "/api/rag/retrieval/query",
            data=json.dumps({"query": "revenue"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"message": "无权限。"})
        self.assertEqual(RetrievalLog.objects.count(), 0)

    def test_retrieval_rejects_invalid_top_k(self):
        response = self.client.post(
            "/api/rag/retrieval/query",
            data=json.dumps({"query": "revenue", "top_k": 0}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"message": "top_k 必须是正整数。"})
        self.assertEqual(RetrievalLog.objects.count(), 0)

    def test_retrieval_requires_query_or_question(self):
        response = self.client.post(
            "/api/rag/retrieval/query",
            data=json.dumps({"query": "   "}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"message": "query 或 question 为必填项。"})
        self.assertEqual(RetrievalLog.objects.count(), 0)

    def test_retrieval_maps_upstream_rate_limit_to_429_without_audit_log(self):
        with patch(
            "rag.controllers.retrieval_controller.retrieve",
            side_effect=UpstreamRateLimitError(provider="openai", retry_after=15),
        ):
            response = self.client.post(
                "/api/rag/retrieval/query",
                data=json.dumps({"query": "revenue"}),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
            )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(
            response.json(),
            {
                "message": "上游模型服务触发限流，请稍后重试。",
                "code": "upstream_rate_limited",
                "provider": "openai",
            },
        )
        self.assertEqual(response["Retry-After"], "15")
        self.assertEqual(RetrievalLog.objects.count(), 0)


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class ChatSessionBoundaryTests(TestCase):
    def test_chat_session_model_is_not_defined_in_rag_domain(self):
        from rag import models as rag_models

        self.assertFalse(hasattr(rag_models, "ChatSession"))


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class KnowledgebaseIngestFailureStateTests(TestCase):
    def setUp(self):
        clear_store()
        self.embedding_provider_patcher = patch(
            "knowledgebase.services.embedding_service.get_embedding_provider",
            return_value=FakeEmbeddingProvider(),
        )
        self.embedding_provider_patcher.start()
        self.vector_search_patcher = patch(
            "knowledgebase.services.vector_service.VectorService.search",
            side_effect=fake_vector_search,
        )
        self.vector_search_patcher.start()
        self.vector_index_patcher = patch(
            "knowledgebase.services.document_service.index_document_chunks",
            side_effect=index_document,
        )
        self.vector_index_patcher.start()
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(
            MEDIA_ROOT=self.media_root,
            MILVUS_URI=f"{self.media_root}/test-milvus.db",
            MILVUS_COLLECTION_NAME="test_document_chunks",
        )
        self.override.enable()

    def tearDown(self):
        self.embedding_provider_patcher.stop()
        self.vector_search_patcher.stop()
        self.override.disable()
        self.vector_index_patcher.stop()
        shutil.rmtree(self.media_root, ignore_errors=True)
        clear_store()

    def test_ingest_marks_document_failed_when_parsing_raises(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "broken.txt",
                b"placeholder",
                content_type="text/plain",
            ),
            title="Broken doc",
            source_date="2025-02-01",
        )

        with patch(
            "knowledgebase.services.document_service.parse_document_file",
            side_effect=ValueError("解析失败"),
        ):
            with self.assertRaisesMessage(ValueError, "解析失败"):
                ingest_document(document)

        document.refresh_from_db()
        self.assertEqual(document.status, Document.STATUS_FAILED)
        self.assertEqual(document.error_message, "解析失败")
        self.assertEqual(document.chunks.count(), 0)
