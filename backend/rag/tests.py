import json
import shutil
import tempfile
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch


from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, TestCase, override_settings

from authentication.models import User
from authentication.services.jwt_service import generate_access_token
from common.exceptions import UpstreamRateLimitError
from knowledgebase.models import Document, DocumentChunk
from knowledgebase.services.document_service import create_document_from_upload, ingest_document
from rag.models import RetrievalLog
from rag.services.llamaindex_store_service import query_llamaindex_store
from rag.services.retrieval_backend_service import (
    retrieve_chat_context,
    retrieve_rag_context,
)
from rag.services.retrieval_evaluation_service import evaluate_retrieval_cases
from rag.services.llamaindex_store_service import clear_store, sync_document
from rag.services.retrieval_service import retrieve
from rbac.services.rbac_service import ROLE_ADMIN, seed_roles_and_permissions

import re as _re
_TOKEN_PATTERN = _re.compile(r"[\w一-鿿]+", _re.UNICODE)

def tokenize(text):
    return _TOKEN_PATTERN.findall((text or "").lower())


class FakeEmbeddingProvider:
    def embed(self, *, texts, options=None):
        return SimpleNamespace(vectors=[[float(index + 1) for index in range(1024)] for _ in texts])


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


class RetrievalBackendSelectionTests(SimpleTestCase):
    @patch("rag.services.retrieval_backend_service.query_llamaindex_store")
    def test_retrieve_rag_context_uses_llamaindex_backend(self, mocked_query):
        mocked_query.return_value = [{"document_id": 1, "chunk_id": 1, "score": 1.0}]

        results = retrieve_rag_context(query="cash flow", filters={"doc_type": "txt"}, top_k=3)

        self.assertEqual(results, mocked_query.return_value)
        mocked_query.assert_called_once_with(
            query="cash flow",
            filters={"doc_type": "txt"},
            top_k=3,
            query_variants=None,
            allow_keyword_fallback=True,
        )

    @patch("rag.services.retrieval_backend_service.query_llamaindex_store")
    def test_retrieve_chat_context_uses_llamaindex_backend(self, mocked_query):
        mocked_query.return_value = [{"document_id": 2, "chunk_id": 4, "score": 0.8}]

        results = retrieve_chat_context(
            query="margin risk",
            filters={"document_id": 2},
            top_k=4,
            query_variants=["risk margin"],
        )

        self.assertEqual(results, mocked_query.return_value)
        mocked_query.assert_called_once_with(
            query="margin risk",
            filters={"document_id": 2},
            top_k=4,
            query_variants=["risk margin"],
            allow_keyword_fallback=False,
        )


class LlamaIndexQueryStrategyTests(SimpleTestCase):
    @patch("rag.services.llamaindex_store_service._fallback_keyword_search")
    @patch("rag.services.llamaindex_store_service._mysql_full_text_search")
    @patch("rag.services.llamaindex_store_service._bm25_search")
    @patch("rag.services.llamaindex_store_service.search")
    def test_query_llamaindex_store_skips_keyword_fallback_when_other_hits_exist(
        self,
        mocked_search,
        mocked_bm25,
        mocked_fulltext,
        mocked_fallback,
    ):
        mocked_search.return_value = [{"document_id": 1, "chunk_id": 10, "score": 0.8}]
        mocked_bm25.return_value = []
        mocked_fulltext.return_value = []
        mocked_fallback.return_value = [{"document_id": 1, "chunk_id": 11, "score": 0.7}]

        results = query_llamaindex_store(
            query="cash flow",
            top_k=3,
            allow_keyword_fallback=True,
        )

        self.assertEqual(len(results), 1)
        mocked_fallback.assert_not_called()

    @patch("rag.services.llamaindex_store_service._fallback_keyword_search")
    @patch("rag.services.llamaindex_store_service._mysql_full_text_search")
    @patch("rag.services.llamaindex_store_service._bm25_search")
    @patch("rag.services.llamaindex_store_service.search")
    def test_query_llamaindex_store_runs_keyword_fallback_only_when_enabled_and_needed(
        self,
        mocked_search,
        mocked_bm25,
        mocked_fulltext,
        mocked_fallback,
    ):
        mocked_search.return_value = []
        mocked_bm25.return_value = []
        mocked_fulltext.return_value = []
        mocked_fallback.return_value = [{"document_id": 1, "chunk_id": 11, "score": 0.7}]

        disabled_results = query_llamaindex_store(
            query="treasury hedging note",
            top_k=2,
            allow_keyword_fallback=False,
        )
        enabled_results = query_llamaindex_store(
            query="treasury hedging note",
            top_k=2,
            allow_keyword_fallback=True,
        )

        self.assertEqual(disabled_results, [])
        self.assertEqual(len(enabled_results), 1)
        mocked_fallback.assert_called_once()


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
            "rag.services.llamaindex_store_service.search",
            side_effect=fake_vector_search,
        )
        self.vector_search_patcher.start()
        self.vector_index_patcher = patch(
            "knowledgebase.services.document_service.index_document_chunks",
            side_effect=sync_document,
        )
        self.vector_index_patcher.start()
        self.bm25_search_patcher = patch(
            "rag.services.llamaindex_store_service._bm25_search",
            return_value=[],
        )
        self.bm25_search_patcher.start()
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
        self.bm25_search_patcher.stop()
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

    @patch("rag.services.llamaindex_store_service.search")
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


class RetrievalEvaluationServiceTests(TestCase):
    @patch("rag.services.retrieval_service.retrieve_rag_context")
    def test_retrieve_passes_query_variants_to_query_store(self, mocked_retrieve):
        mocked_retrieve.return_value = []

        retrieve(
            query="capital adequacy",
            query_variants=["capital adequacy", "car stress scenario"],
            top_k=5,
        )

        mocked_retrieve.assert_called_once_with(
            query="capital adequacy",
            filters=None,
            top_k=5,
            query_variants=["capital adequacy", "car stress scenario"],
        )

    def test_evaluate_retrieval_cases_computes_metrics_from_chunk_ids(self):
        result = evaluate_retrieval_cases(
            [
                {
                    "name": "chunk-id-hit",
                    "query": "capital adequacy",
                    "top_k": 3,
                    "relevant_chunk_ids": [11],
                }
            ],
            retrieve_fn=lambda **kwargs: [
                {
                    "chunk_id": 11,
                    "document_title": "Stress Test Report",
                    "page_label": "chunk-1",
                }
            ],
        )

        self.assertEqual(result["total_cases"], 1)
        self.assertEqual(result["summary"]["recall_at_k"], 1.0)
        self.assertEqual(result["summary"]["mrr"], 1.0)
        self.assertEqual(result["summary"]["ndcg_at_k"], 1.0)

    def test_evaluate_retrieval_command_prints_summary(self):
        import rag.management.commands.evaluate_retrieval as eval_cmd

        with patch.object(eval_cmd, "evaluate_retrieval_fixture") as mock_eval:
            mock_eval.return_value = {
                "total_cases": 1,
                "summary": {
                    "recall_at_k": 1.0,
                    "mrr": 1.0,
                    "ndcg_at_k": 1.0,
                    "average_latency_ms": 12.5,
                },
                "cases": [],
            }
            stdout = StringIO()
            call_command("evaluate_retrieval", stdout=stdout)
            output = stdout.getvalue()
            self.assertIn("RETRIEVAL EVALUATION", output)
            self.assertIn("recall_at_k", output)

    def test_evaluate_retrieval_command_all_mode_runs_both(self):
        import rag.management.commands.evaluate_retrieval as eval_cmd

        with patch.object(eval_cmd, "evaluate_retrieval_fixture") as mock_retrieval, \
             patch.object(eval_cmd, "evaluate_generation_fixture") as mock_generation:
            mock_retrieval.return_value = {
                "total_cases": 1,
                "summary": {"recall_at_k": 1.0, "mrr": 1.0, "ndcg_at_k": 1.0, "average_latency_ms": 10.0},
                "cases": [],
            }
            mock_generation.return_value = {
                "total_cases": 1,
                "summary": {"avg_faithfulness": 0.9, "avg_relevancy": 0.8},
                "cases": [],
            }
            stdout = StringIO()
            call_command("evaluate_retrieval", "--mode", "all", stdout=stdout)
            output = stdout.getvalue()
            self.assertIn("RETRIEVAL EVALUATION", output)
            self.assertIn("GENERATION EVALUATION", output)
            mock_retrieval.assert_called_once()
            mock_generation.assert_called_once()


class BM25RetrieverTests(TestCase):
    @override_settings(RAG_BM25_ENABLED=False)
    @patch("rag.services.llamaindex_store_service._get_or_build_bm25_retriever")
    def test_bm25_search_returns_empty_when_disabled(self, mock_retriever):
        from rag.services.llamaindex_store_service import _bm25_search

        results = _bm25_search("test query")
        self.assertEqual(results, [])
        mock_retriever.assert_not_called()

    @patch("rag.services.llamaindex_store_service._get_or_build_bm25_retriever")
    def test_bm25_search_returns_empty_when_no_retriever(self, mock_retriever):
        mock_retriever.return_value = None
        from rag.services.llamaindex_store_service import _bm25_search

        results = _bm25_search("test query")
        self.assertEqual(results, [])

    def test_bm25_cache_invalidation(self):
        from rag.services.llamaindex_store_service import (
            _bm25_cache,
            invalidate_bm25_cache,
        )

        _bm25_cache["retriever"] = object()
        _bm25_cache["built_at"] = 999999.0
        invalidate_bm25_cache()
        self.assertIsNone(_bm25_cache["retriever"])
        self.assertEqual(_bm25_cache["built_at"], 0.0)


class GenerationEvaluationTests(TestCase):
    def test_evaluate_generation_case_requires_query(self):
        from rag.services.retrieval_evaluation_service import evaluate_generation_case

        with self.assertRaises(ValueError):
            evaluate_generation_case({"query": ""})

    @patch("rag.services.retrieval_evaluation_service._build_eval_llm")
    def test_evaluate_generation_case_returns_faithfulness_and_relevancy(self, mock_build_llm):
        from types import SimpleNamespace

        from rag.services.retrieval_evaluation_service import evaluate_generation_case

        mock_llm = SimpleNamespace(
            complete=lambda prompt: SimpleNamespace(text="test answer"),
        )
        mock_build_llm.return_value = mock_llm

        mock_faithfulness = SimpleNamespace(score=0.9, passing=True)
        mock_relevancy = SimpleNamespace(score=0.85, passing=True)

        with patch(
            "llama_index.core.evaluation.FaithfulnessEvaluator"
        ) as MockFaith, patch(
            "llama_index.core.evaluation.RelevancyEvaluator"
        ) as MockRel:
            MockFaith.return_value.evaluate.return_value = mock_faithfulness
            MockRel.return_value.evaluate.return_value = mock_relevancy

            result = evaluate_generation_case(
                {"query": "test query", "top_k": 3},
                retrieve_fn=lambda **kwargs: [
                    {"document_title": "Doc", "page_label": "p1", "snippet": "text"}
                ],
                llm=mock_llm,
            )

        self.assertEqual(result["faithfulness_score"], 0.9)
        self.assertEqual(result["relevancy_score"], 0.85)
        self.assertTrue(result["faithfulness_passing"])
        self.assertTrue(result["relevancy_passing"])


class SentenceWindowRetrievalTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.user = User.objects.create_user(
            username="swtest", password="testpass123", is_active=True,
        )
        self.group = Group.objects.create(name="member")
        self.user.groups.add(self.group)
        seed_roles_and_permissions()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    @override_settings(KB_SENTENCE_WINDOW_ENABLED=True, KB_SENTENCE_WINDOW_SIZE=2)
    @patch("knowledgebase.services.embedding_service.get_embedding_provider", return_value=FakeEmbeddingProvider())
    @patch("rag.services.llamaindex_store_service._fallback_keyword_search", return_value=[])
    @patch("rag.services.llamaindex_store_service._mysql_full_text_search", return_value=[])
    @patch("rag.services.llamaindex_store_service._bm25_search", return_value=[])
    @patch("rag.services.llamaindex_store_service.search")
    def test_retrieved_results_contain_window_metadata(
        self,
        mock_search,
        _mock_bm25,
        _mock_fulltext,
        _mock_fallback,
        _mock_embedding,
    ):
        document = Document.objects.create(
            title="Window Test",
            file=SimpleUploadedFile("test.txt", b"test", content_type="text/plain"),
            filename="test.txt",
            doc_type="txt",
            status=Document.STATUS_PARSED,
            parsed_text="第一句。第二句。第三句。第四句。第五句。第六句。第七句。第八句。第九句。第十句。",
            visibility=Document.VISIBILITY_INTERNAL,
            owner=self.user,
        )
        chunk = DocumentChunk.objects.create(
            document=document,
            chunk_index=2,
            content="第三句。",
            search_text="title: Window Test\n第三句。",
            metadata={"document_title": "Window Test", "window": "第一句。第二句。第三句。第四句。第五句。"},
        )

        mock_search.return_value = [
            {
                "document_id": document.id,
                "chunk_id": chunk.id,
                "section_chunk_id": None,
                "document_title": document.title,
                "doc_type": document.doc_type,
                "source_date": None,
                "page_label": "chunk-3",
                "snippet": chunk.content,
                "window": "第一句。第二句。第三句。第四句。第五句。",
                "metadata": chunk.metadata,
                "section_context_summary": None,
                "score": 0.9,
                "vector_score": 0.9,
                "keyword_score": 0.0,
                "matched_queries": [],
            }
        ]

        results = query_llamaindex_store("测试查询", top_k=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["window"], "第一句。第二句。第三句。第四句。第五句。")

    @override_settings(KB_SENTENCE_WINDOW_ENABLED=True, KB_SENTENCE_WINDOW_SIZE=2)
    @patch("knowledgebase.services.embedding_service.get_embedding_provider", return_value=FakeEmbeddingProvider())
    @patch("rag.services.llamaindex_store_service._fallback_keyword_search", return_value=[])
    @patch("rag.services.llamaindex_store_service._mysql_full_text_search", return_value=[])
    @patch("rag.services.llamaindex_store_service._bm25_search", return_value=[])
    @patch("rag.services.llamaindex_store_service.search")
    def test_citation_includes_window(
        self,
        _mock_search,
        _mock_bm25,
        _mock_fulltext,
        _mock_fallback,
        _mock_embedding,
    ):
        from rag.services.retrieval_service import serialize_citation

        item = {
            "document_title": "Test Doc",
            "doc_type": "pdf",
            "source_date": None,
            "page_label": "chunk-1",
            "snippet": "短句。",
            "window": "前文。短句。后文。",
            "score": 0.8,
            "rerank_score": 0.85,
        }

        citation = serialize_citation(item)

        self.assertEqual(citation["snippet"], "短句。")
        self.assertEqual(citation["window"], "前文。短句。后文。")


@override_settings(RAG_HYBRID_SEARCH_ENABLED=True)
class HybridSearchTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.user = User.objects.create_user(
            username="hybridtest", password="testpass123", is_active=True,
        )
        self.group = Group.objects.create(name="member")
        self.user.groups.add(self.group)
        seed_roles_and_permissions()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    @patch("rag.services.llamaindex_store_service._get_hybrid_milvus_client")
    @patch("rag.services.llamaindex_store_service._build_embed_model")
    def test_hybrid_search_returns_results(self, mock_embed, mock_client):
        document = Document.objects.create(
            title="Hybrid Test",
            file=SimpleUploadedFile("test.txt", b"test", content_type="text/plain"),
            filename="test.txt",
            doc_type="txt",
            status=Document.STATUS_CHUNKED,
            visibility=Document.VISIBILITY_INTERNAL,
            owner=self.user,
        )
        chunk = DocumentChunk.objects.create(
            document=document,
            chunk_index=0,
            content="Revenue grew 10 percent.",
            search_text="title: Hybrid Test\nRevenue grew 10 percent.",
            metadata={"document_title": "Hybrid Test"},
        )

        embed_obj = SimpleNamespace()
        embed_obj._get_query_embedding = lambda q: [0.1] * 1024
        mock_embed.return_value = embed_obj

        mock_milvus_client = SimpleNamespace()
        mock_milvus_client.hybrid_search = lambda **kwargs: [[
            {
                "entity": {
                    "chunk_id": chunk.id,
                    "document_id": document.id,
                    "document_title": "Hybrid Test",
                    "doc_type": "txt",
                    "source_date": "",
                    "page_label": "chunk-1",
                    "chunk_index": 0,
                    "content": "Revenue grew 10 percent.",
                },
                "distance": 0.85,
            },
        ]]
        mock_client.return_value = mock_milvus_client

        results = query_llamaindex_store("revenue growth", top_k=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["chunk_id"], chunk.id)
        self.assertAlmostEqual(results[0]["score"], 0.85)

    @patch("rag.services.llamaindex_store_service._hybrid_search")
    def test_hybrid_query_fuses_multiple_variants(self, mock_hybrid):
        mock_hybrid.return_value = [
            {"document_id": 1, "chunk_id": 10, "score": 0.9, "matched_queries": []},
            {"document_id": 1, "chunk_id": 11, "score": 0.7, "matched_queries": []},
        ]

        results = query_llamaindex_store(
            "cash flow",
            top_k=2,
            query_variants=["cash flow", "liquidity"],
        )

        # Should have called hybrid_search for each unique query variant
        self.assertEqual(mock_hybrid.call_count, 2)

    @override_settings(RAG_HYBRID_SEARCH_ENABLED=False)
    @patch("rag.services.llamaindex_store_service._hybrid_search")
    @patch("rag.services.llamaindex_store_service.search")
    def test_legacy_path_used_when_flag_disabled(self, mock_legacy_search, mock_hybrid):
        mock_legacy_search.return_value = [
            {"document_id": 1, "chunk_id": 10, "score": 0.8, "matched_queries": []}
        ]

        results = query_llamaindex_store("test", top_k=1)

        mock_hybrid.assert_not_called()
        mock_legacy_search.assert_called_once()
