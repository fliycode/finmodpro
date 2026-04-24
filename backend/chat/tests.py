import json
import shutil
import tempfile
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import Client, TestCase, override_settings

from authentication.models import User
from authentication.services.jwt_service import generate_access_token
from chat.models import ChatMessage, ChatSession
from chat.serializers import ChatMessageSerializer, ChatSessionSerializer
from chat.services.ask_service import stream_question
from chat.services.context_service import build_chat_messages
from chat.services.memory_service import delete_memory_item, extract_session_memories, set_memory_pin_state
from chat.services.session_service import dispatch_session_maintenance_tasks
from chat.services.session_service import (
    create_chat_session,
    create_session_message,
    finalize_session_message,
    persist_session_turn,
)
from chat.services.summary_service import update_session_summary
from chat.services.title_service import generate_session_title
from common.exceptions import (
    ModelNotConfiguredError,
    ProviderConfigurationError,
    UpstreamRateLimitError,
    UpstreamServiceError,
)
from knowledgebase.services.document_service import create_document_from_upload, ingest_document
from knowledgebase.models import DocumentChunk
from rag.models import RetrievalLog
from rag.services.embedding_service import tokenize
from rag.services.vector_store_service import clear_store, index_document
from rbac.services.rbac_service import ROLE_ADMIN, seed_roles_and_permissions


class FakeEmbeddingProvider:
    def embed(self, *, texts, options=None):
        return [[float(index + 1) for index in range(64)] for _ in texts]


class FakeChatProvider:
    def chat(self, *, messages, options=None):
        return messages[-1]["content"]

    def stream(self, *, messages, options=None):
        content = self.chat(messages=messages, options=options)
        for chunk in [content[:12], content[12:]]:
            if chunk:
                yield chunk


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
class ChatAskApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()
        self.vector_clear_patcher = patch(
            "rag.services.vector_store_service.VectorService.clear",
            return_value=None,
        )
        self.vector_clear_patcher.start()
        clear_store()
        self.embedding_provider_patcher = patch(
            "knowledgebase.services.embedding_service.get_embedding_provider",
            return_value=FakeEmbeddingProvider(),
        )
        self.chat_provider_patcher = patch(
            "chat.services.ask_service.get_chat_provider",
            return_value=FakeChatProvider(),
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
        self.chat_provider_patcher.start()
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(
            MEDIA_ROOT=self.media_root,
            MILVUS_URI=f"{self.media_root}/test-milvus.db",
            MILVUS_COLLECTION_NAME="test_document_chunks",
        )
        self.override.enable()

        self.user = User.objects.create_user(
            username="chat-admin",
            password="secret123",
            email="chat@example.com",
        )
        self.user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.access_token = generate_access_token(self.user)

        self.document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "outlook.txt",
                (
                    b"revenue growth stayed resilient while operating margin improved "
                    b"with stronger cash generation"
                ),
                content_type="text/plain",
            ),
            title="Outlook memo",
            source_date="2025-02-18",
        )
        ingest_document(self.document)

    def tearDown(self):
        self.chat_provider_patcher.stop()
        self.embedding_provider_patcher.stop()
        self.vector_search_patcher.stop()
        self.override.disable()
        self.vector_index_patcher.stop()
        shutil.rmtree(self.media_root, ignore_errors=True)
        clear_store()
        self.vector_clear_patcher.stop()

    def test_chat_ask_returns_answer_and_citations_from_retrieval(self):
        response = self.client.post(
            "/api/chat/ask",
            data=json.dumps(
                {
                    "question": "revenue and margin outlook",
                    "top_k": 2,
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["question"], "revenue and margin outlook")
        self.assertEqual(payload["query"], "revenue and margin outlook")
        self.assertIn("Outlook memo", payload["answer"])
        self.assertIn("revenue growth stayed resilient", payload["answer"])
        self.assertIn("duration_ms", payload)
        self.assertIsInstance(payload["duration_ms"], int)
        self.assertGreaterEqual(payload["duration_ms"], 0)
        self.assertEqual(len(payload["citations"]), 1)
        self.assertEqual(
            payload["citations"][0],
            {
                "document_title": "Outlook memo",
                "doc_type": "txt",
                "source_date": "2025-02-18",
                "page_label": "chunk-1",
                "snippet": (
                    "revenue growth stayed resilient while operating margin improved "
                    "with stronger cash generation"
                ),
                "score": payload["citations"][0]["score"],
                "rerank_score": payload["citations"][0]["rerank_score"],
            },
        )
        self.assertEqual(RetrievalLog.objects.count(), 1)
        retrieval_log = RetrievalLog.objects.get()
        self.assertEqual(retrieval_log.query, "revenue and margin outlook")
        self.assertEqual(retrieval_log.top_k, 2)
        self.assertEqual(retrieval_log.filters, {})
        self.assertEqual(retrieval_log.result_count, 1)
        self.assertEqual(retrieval_log.source, RetrievalLog.SOURCE_CHAT_ASK)
        self.assertIsNotNone(retrieval_log.duration_ms)

    def test_chat_ask_accepts_query_alias_and_falls_back_to_model_answer_when_no_match(self):
        response = self.client.post(
            "/api/chat/ask",
            data=json.dumps(
                {
                    "query": "foreign exchange exposure",
                    "filters": {"doc_type": "pdf"},
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["question"], "foreign exchange exposure")
        self.assertEqual(payload["query"], "foreign exchange exposure")
        self.assertEqual(payload["citations"], [])
        self.assertEqual(payload["answer_mode"], "fallback")
        self.assertEqual(
            payload["answer_notice"],
            "当前回答未命中知识库引用，仅基于通用模型能力生成，请注意甄别。",
        )
        self.assertIn("foreign exchange exposure", payload["answer"])
        self.assertEqual(RetrievalLog.objects.count(), 1)
        retrieval_log = RetrievalLog.objects.get()
        self.assertEqual(retrieval_log.result_count, 0)
        self.assertEqual(retrieval_log.filters, {"doc_type": "pdf"})

    def test_chat_ask_uses_hybrid_retrieval_for_title_keyword_hits(self):
        response = self.client.post(
            "/api/chat/ask",
            data=json.dumps({"query": "Outlook memo"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["citations"]), 1)
        self.assertEqual(payload["citations"][0]["document_title"], "Outlook memo")
        self.assertIn("Outlook memo", payload["answer"])
        self.assertIn("duration_ms", payload)
        self.assertGreaterEqual(payload["duration_ms"], 0)

    def test_chat_ask_identity_question_skips_knowledgebase_retrieval(self):
        session = ChatSession.objects.create(
            user=self.user,
            title="旧会话",
            rolling_summary="参考上下文描述的是另一个系统。",
        )
        create_session_message(
            session=session,
            role=ChatMessage.ROLE_USER,
            content="另一个系统是谁？",
            status=ChatMessage.STATUS_COMPLETE,
        )

        with patch("chat.services.ask_service.retrieve", return_value=[]) as mocked_retrieve:
            response = self.client.post(
                "/api/chat/ask",
                data=json.dumps({"question": "你是谁？", "session_id": session.id}),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["answer_mode"], "direct")
        self.assertEqual(payload["citations"], [])
        self.assertNotIn("参考上下文", payload["answer"])
        self.assertNotIn("另一个系统", payload["answer"])
        mocked_retrieve.assert_not_called()

    def test_chat_ask_platform_question_skips_knowledgebase_retrieval(self):
        with patch("chat.services.ask_service.retrieve", return_value=[]) as mocked_retrieve:
            response = self.client.post(
                "/api/chat/ask",
                data=json.dumps({"question": "你好，这是什么平台？"}),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["answer_mode"], "direct")
        self.assertEqual(payload["citations"], [])
        self.assertNotIn("参考上下文", payload["answer"])
        mocked_retrieve.assert_not_called()

    def test_chat_ask_filters_weak_retrieval_matches(self):
        weak_match = {
            "document_title": "Unrelated memo",
            "doc_type": "txt",
            "source_date": "2025-02-18",
            "page_label": "chunk-9",
            "snippet": "only a very weak incidental overlap",
            "score": 0.05,
            "rerank_score": 0.05,
        }
        with patch("chat.services.ask_service.retrieve", return_value=[weak_match]):
            response = self.client.post(
                "/api/chat/ask",
                data=json.dumps({"question": "利润率趋势"}),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["answer_mode"], "fallback")
        self.assertEqual(payload["citations"], [])

    def test_chat_ask_limits_citations_to_focused_evidence(self):
        results = [
            {
                "document_title": f"Evidence {index}",
                "doc_type": "txt",
                "source_date": "2025-02-18",
                "page_label": f"chunk-{index}",
                "snippet": f"revenue and margin evidence {index}",
                "score": 0.9 - (index * 0.05),
                "rerank_score": 0.9 - (index * 0.05),
            }
            for index in range(5)
        ]
        with patch("chat.services.ask_service.retrieve", return_value=results):
            response = self.client.post(
                "/api/chat/ask",
                data=json.dumps({"question": "revenue and margin outlook", "top_k": 5}),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["citations"]), 3)
        self.assertEqual(
            [citation["document_title"] for citation in payload["citations"]],
            ["Evidence 0", "Evidence 1", "Evidence 2"],
        )

    def test_chat_ask_returns_only_citations_used_by_answer(self):
        class IndexedCitationProvider:
            def chat(self, *, messages, options=None):
                return "根据[2]，利润率改善更明显。"

        results = [
            {
                "document_title": f"Evidence {index}",
                "doc_type": "txt",
                "source_date": "2025-02-18",
                "page_label": f"chunk-{index}",
                "snippet": f"margin evidence {index}",
                "score": 0.8,
                "rerank_score": 0.8,
            }
            for index in range(3)
        ]
        with (
            patch("chat.services.ask_service.retrieve", return_value=results),
            patch("chat.services.ask_service.get_chat_provider", return_value=IndexedCitationProvider()),
        ):
            response = self.client.post(
                "/api/chat/ask",
                data=json.dumps({"question": "margin outlook", "top_k": 3}),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["answer"], "根据[2]，利润率改善更明显。")
        self.assertEqual(len(payload["citations"]), 1)
        self.assertEqual(payload["citations"][0]["document_title"], "Evidence 1")

    def test_chat_stream_returns_initial_metadata_event_and_chunks(self):
        response = self.client.post(
            "/api/chat/ask/stream",
            data=json.dumps({"question": "revenue and margin outlook", "top_k": 2}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/event-stream")
        self.assertEqual(response["Cache-Control"], "no-cache, no-transform")
        self.assertEqual(response["X-Accel-Buffering"], "no")
        body = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn('event: meta', body)
        self.assertIn('"answer_mode": "cited"', body)
        self.assertIn('event: chunk', body)
        self.assertIn('event: done', body)
        self.assertIn('"citations": []', body.split("event: chunk", 1)[0])

    def test_chat_stream_fallback_reports_notice_when_no_citations(self):
        response = self.client.post(
            "/api/chat/ask/stream",
            data=json.dumps({"query": "foreign exchange exposure", "filters": {"doc_type": "pdf"}}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        body = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn('"answer_mode": "fallback"', body)
        self.assertIn("answer_notice", body)

    def test_build_chat_messages_always_includes_platform_system_prompt(self):
        messages = build_chat_messages(question="你是谁？")

        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("FinModPro", messages[0]["content"])
        self.assertIn("平台助手", messages[0]["content"])
        self.assertEqual(messages[1], {"role": "user", "content": "你是谁？"})

    @patch("chat.services.ask_service.retrieve", return_value=[])
    def test_chat_ask_persists_session_messages_and_uses_session_filters(self, mocked_retrieve):
        session = ChatSession.objects.create(
            user=self.user,
            title="数据集问答",
            context_filters={"dataset_id": 7, "doc_type": "txt"},
        )

        response = self.client.post(
            "/api/chat/ask",
            data=json.dumps({"question": "revenue outlook", "session_id": session.id}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        mocked_retrieve.assert_called_once_with(
            query="revenue outlook",
            filters={"dataset_id": 7, "doc_type": "txt"},
            top_k=5,
        )
        session.refresh_from_db()
        self.assertEqual(
            list(session.messages.values_list("role", "content")),
            [
                (ChatMessage.ROLE_USER, "revenue outlook"),
                (ChatMessage.ROLE_ASSISTANT, "revenue outlook"),
            ],
        )

    @patch("chat.services.ask_service.retrieve", return_value=[])
    def test_chat_stream_persists_session_messages_and_uses_session_filters(self, mocked_retrieve):
        session = ChatSession.objects.create(
            user=self.user,
            title="流式数据集问答",
            context_filters={"dataset_id": 11},
        )

        response = self.client.post(
            "/api/chat/ask/stream",
            data=json.dumps({"question": "cash flow outlook", "session_id": session.id}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        body = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn("cash flow outlook", body)
        mocked_retrieve.assert_called_once_with(
            query="cash flow outlook",
            filters={"dataset_id": 11},
            top_k=5,
        )
        self.assertEqual(
            list(session.messages.values_list("role", "content")),
            [
                (ChatMessage.ROLE_USER, "cash flow outlook"),
                (ChatMessage.ROLE_ASSISTANT, "cash flow outlook"),
            ],
        )

    @patch("chat.services.ask_service.retrieve", return_value=[])
    def test_chat_ask_finalizes_assistant_message_and_updates_session_counters(
        self, mocked_retrieve
    ):
        session = ChatSession.objects.create(
            user=self.user,
            title="问答持久化",
            context_filters={"dataset_id": 7},
        )

        response = self.client.post(
            "/api/chat/ask",
            data=json.dumps({"question": "cash flow outlook", "session_id": session.id}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        response_payload = response.json()
        mocked_retrieve.assert_called_once_with(
            query="cash flow outlook",
            filters={"dataset_id": 7},
            top_k=5,
        )
        session.refresh_from_db()
        self.assertEqual(
            getattr(session, "message_count", None),
            2,
            "ChatSession must track message_count after persisted turns.",
        )
        self.assertIsNotNone(
            getattr(session, "last_message_at", None),
            "ChatSession must track last_message_at after persisted turns.",
        )
        assistant_message = session.messages.get(role=ChatMessage.ROLE_ASSISTANT)
        self.assertEqual(
            getattr(ChatMessage, "STATUS_COMPLETE", None),
            "complete",
            "ChatMessage must define STATUS_COMPLETE for finalized assistant turns.",
        )
        self.assertEqual(
            getattr(assistant_message, "status", None),
            "complete",
            "ChatMessage must persist assistant status for finalized turns.",
        )
        self.assertEqual(assistant_message.content, response_payload["answer"])
        self.assertTrue(assistant_message.content)

    @patch("chat.services.ask_service.retrieve", return_value=[])
    def test_chat_stream_finalizes_assistant_message_and_updates_session_counters(
        self, mocked_retrieve
    ):
        session = ChatSession.objects.create(
            user=self.user,
            title="流式问答持久化",
            context_filters={"dataset_id": 11},
        )

        response = self.client.post(
            "/api/chat/ask/stream",
            data=json.dumps({"question": "cash flow outlook", "session_id": session.id}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        body = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn("event: done", body)
        mocked_retrieve.assert_called_once_with(
            query="cash flow outlook",
            filters={"dataset_id": 11},
            top_k=5,
        )
        session.refresh_from_db()
        self.assertEqual(
            getattr(session, "message_count", None),
            2,
            "ChatSession must track message_count after streamed turns.",
        )
        self.assertIsNotNone(
            getattr(session, "last_message_at", None),
            "ChatSession must track last_message_at after streamed turns.",
        )
        assistant_message = session.messages.get(role=ChatMessage.ROLE_ASSISTANT)
        self.assertEqual(
            getattr(ChatMessage, "STATUS_COMPLETE", None),
            "complete",
            "ChatMessage must define STATUS_COMPLETE for streamed assistant turns.",
        )
        self.assertEqual(
            getattr(assistant_message, "status", None),
            "complete",
            "ChatMessage must persist assistant status for streamed turns.",
        )
        self.assertTrue(assistant_message.content)
        self.assertIn(assistant_message.content, body)

    @override_settings(
        CELERY_TASK_ALWAYS_EAGER=False,
        CELERY_BROKER_URL="redis://127.0.0.1:6379/0",
    )
    @patch("chat.tasks.extract_session_memories_task.delay")
    @patch("chat.tasks.update_session_summary_task.delay")
    @patch("chat.tasks.update_session_title_task.delay")
    @patch("chat.services.ask_service.retrieve", return_value=[])
    def test_chat_ask_dispatches_session_maintenance_tasks(
        self,
        mocked_retrieve,
        mocked_title_delay,
        mocked_summary_delay,
        mocked_memory_delay,
    ):
        session = ChatSession.objects.create(
            user=self.user,
            title="维护任务调度",
            context_filters={"dataset_id": 7},
        )

        response = self.client.post(
            "/api/chat/ask",
            data=json.dumps({"question": "liquidity outlook", "session_id": session.id}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        mocked_retrieve.assert_called_once_with(
            query="liquidity outlook",
            filters={"dataset_id": 7},
            top_k=5,
        )
        mocked_title_delay.assert_called_once_with(session.id)
        mocked_summary_delay.assert_called_once_with(session.id)
        mocked_memory_delay.assert_called_once_with(session.id)

    @patch(
        "chat.services.ask_service.dispatch_session_maintenance_tasks",
        side_effect=RuntimeError("maintenance queue unavailable"),
    )
    @patch("chat.services.ask_service.retrieve", return_value=[])
    def test_chat_ask_succeeds_when_session_maintenance_dispatch_fails(
        self,
        mocked_retrieve,
        mocked_dispatch,
    ):
        session = ChatSession.objects.create(
            user=self.user,
            title="维护失败不应影响问答",
            context_filters={"dataset_id": 7},
        )

        response = self.client.post(
            "/api/chat/ask",
            data=json.dumps({"question": "cash flow outlook", "session_id": session.id}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        mocked_retrieve.assert_called_once_with(
            query="cash flow outlook",
            filters={"dataset_id": 7},
            top_k=5,
        )
        mocked_dispatch.assert_called_once_with(session_id=session.id)
        session.refresh_from_db()
        assistant_message = session.messages.get(role=ChatMessage.ROLE_ASSISTANT)
        self.assertEqual(assistant_message.status, ChatMessage.STATUS_COMPLETE)
        self.assertEqual(assistant_message.content, response.json()["answer"])

    @patch(
        "chat.services.ask_service.dispatch_session_maintenance_tasks",
        side_effect=RuntimeError("maintenance queue unavailable"),
    )
    @patch("chat.services.ask_service.retrieve", return_value=[])
    def test_chat_stream_succeeds_when_session_maintenance_dispatch_fails(
        self,
        mocked_retrieve,
        mocked_dispatch,
    ):
        session = ChatSession.objects.create(
            user=self.user,
            title="流式维护失败不应影响问答",
            context_filters={"dataset_id": 11},
        )

        response = self.client.post(
            "/api/chat/ask/stream",
            data=json.dumps({"question": "cash flow outlook", "session_id": session.id}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        body = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn("event: done", body)
        mocked_retrieve.assert_called_once_with(
            query="cash flow outlook",
            filters={"dataset_id": 11},
            top_k=5,
        )
        mocked_dispatch.assert_called_once_with(session_id=session.id)
        session.refresh_from_db()
        assistant_message = session.messages.get(role=ChatMessage.ROLE_ASSISTANT)
        self.assertEqual(assistant_message.status, ChatMessage.STATUS_COMPLETE)
        self.assertTrue(assistant_message.content)
        self.assertIn(assistant_message.content, body)

    def test_chat_ask_requires_question_or_query(self):
        response = self.client.post(
            "/api/chat/ask",
            data=json.dumps({"question": "   "}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"message": "question 或 query 为必填项。"})
        self.assertEqual(RetrievalLog.objects.count(), 0)

    def test_chat_ask_rejects_user_without_ask_financial_qa_permission(self):
        unauthorized_user = User.objects.create_user(
            username="chat-member",
            password="secret123",
            email="chat-member@example.com",
        )
        token = generate_access_token(unauthorized_user)

        response = self.client.post(
            "/api/chat/ask",
            data=json.dumps({"question": "revenue"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"message": "无权限。"})
        self.assertEqual(RetrievalLog.objects.count(), 0)

    def test_chat_ask_maps_upstream_rate_limit_to_429(self):
        with patch(
            "chat.controllers.ask_controller.ask_question",
            side_effect=UpstreamRateLimitError(provider="openai", retry_after=30),
        ):
            response = self.client.post(
                "/api/chat/ask",
                data=json.dumps({"question": "revenue"}),
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
                "data": {
                    "error": {
                        "type": "rate_limited",
                        "code": "upstream_rate_limited",
                        "message": "上游模型服务触发限流，请稍后重试。",
                        "provider": "openai",
                        "details": {
                            "upstream_message": "上游模型服务触发限流，请稍后重试。",
                            "retry_after": 30,
                        },
                    }
                },
            },
        )
        self.assertEqual(response["Retry-After"], "30")
        self.assertEqual(RetrievalLog.objects.count(), 0)

    def test_chat_ask_returns_structured_error_when_chat_model_not_configured(self):
        with patch(
            "chat.controllers.ask_controller.ask_question",
            side_effect=ModelNotConfiguredError("chat"),
        ):
            response = self.client.post(
                "/api/chat/ask",
                data=json.dumps({"question": "revenue"}),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {
                "message": "当前未配置可用的对话模型，请先在模型配置中启用 chat 模型。",
                "code": "chat_model_not_configured",
                "data": {
                    "error": {
                        "type": "configuration_error",
                        "code": "chat_model_not_configured",
                        "message": "当前未配置可用的对话模型，请先在模型配置中启用 chat 模型。",
                        "details": {"capability": "chat"},
                    }
                },
            },
        )

    def test_chat_ask_returns_structured_error_when_provider_configuration_is_invalid(self):
        with patch(
            "chat.controllers.ask_controller.ask_question",
            side_effect=ProviderConfigurationError(
                "Unsupported provider: openai",
                provider="openai",
                details={"capability": "chat", "supported_providers": ["ollama"]},
            ),
        ):
            response = self.client.post(
                "/api/chat/ask",
                data=json.dumps({"question": "revenue"}),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {
                "message": "当前对话模型 provider 不可用，请检查模型配置。",
                "code": "chat_provider_unavailable",
                "provider": "openai",
                "data": {
                    "error": {
                        "type": "configuration_error",
                        "code": "chat_provider_unavailable",
                        "message": "当前对话模型 provider 不可用，请检查模型配置。",
                        "provider": "openai",
                        "details": {
                            "capability": "chat",
                            "supported_providers": ["ollama"],
                        },
                    }
                },
            },
        )

    def test_chat_ask_returns_structured_error_when_upstream_is_unavailable(self):
        with patch(
            "chat.controllers.ask_controller.ask_question",
            side_effect=UpstreamServiceError(
                "模型服务暂不可用。",
                status_code=503,
                code="llm_provider_unavailable",
                provider="ollama",
            ),
        ):
            response = self.client.post(
                "/api/chat/ask",
                data=json.dumps({"question": "revenue"}),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {
                "message": "对话模型服务当前不可用，请稍后重试。",
                "code": "llm_provider_unavailable",
                "provider": "ollama",
                "data": {
                    "error": {
                        "type": "provider_unavailable",
                        "code": "llm_provider_unavailable",
                        "message": "对话模型服务当前不可用，请稍后重试。",
                        "provider": "ollama",
                        "details": {"upstream_message": "模型服务暂不可用。"},
                    }
                },
            },
        )


class ChatSessionCreateApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()
        self.user = User.objects.create_user(
            username="session-admin",
            password="secret123",
            email="session-admin@example.com",
        )
        self.user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.access_token = generate_access_token(self.user)

    def test_create_session_returns_unified_response_with_defaults(self):
        response = self.client.post(
            "/api/chat/sessions",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["message"], "ok")
        self.assertIn("session_id", payload["data"])
        self.assertEqual(payload["data"]["session_id"], payload["data"]["session"]["id"])
        self.assertEqual(payload["data"]["session"]["session_id"], payload["data"]["session"]["id"])
        self.assertEqual(payload["data"]["session"]["title"], "新会话")
        self.assertEqual(payload["data"]["session"]["context_filters"], {})
        self.assertEqual(payload["data"]["session"]["user_id"], self.user.id)
        self.assertEqual(ChatSession.objects.count(), 1)

    def test_create_session_returns_session_truth_defaults(self):
        response = self.client.post(
            "/api/chat/sessions",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 201)
        session_payload = response.json()["data"]["session"]
        self.assertIn("title_status", session_payload)
        self.assertEqual(session_payload["title_status"], "pending")
        self.assertIn("rolling_summary", session_payload)
        self.assertEqual(session_payload["rolling_summary"], "")
        self.assertIn("message_count", session_payload)
        self.assertEqual(session_payload["message_count"], 0)
        self.assertIn("last_message_at", session_payload)
        self.assertIsNone(session_payload["last_message_at"])

    def test_create_session_accepts_title_and_context_filters(self):
        response = self.client.post(
            "/api/chat/sessions",
            data=json.dumps(
                {
                    "title": "流动性分析",
                    "context_filters": {"doc_type": "pdf", "document_id": 9},
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 201)
        session = ChatSession.objects.get()
        self.assertEqual(session.title, "流动性分析")
        self.assertEqual(session.context_filters, {"doc_type": "pdf", "document_id": 9})

    def test_generate_session_title_uses_model_summary_instead_of_raw_question(self):
        class TitleProvider:
            def chat(self, *, messages, options=None):
                return "平台身份咨询"

        session = create_chat_session(user=self.user)
        create_session_message(
            session=session,
            role=ChatMessage.ROLE_USER,
            content="你好，这是什么平台",
        )
        create_session_message(
            session=session,
            role=ChatMessage.ROLE_ASSISTANT,
            content="我是 FinModPro 平台助手。",
        )

        with patch("chat.services.title_service.get_chat_provider", return_value=TitleProvider()):
            title = generate_session_title(session_id=session.id)

        session.refresh_from_db()
        self.assertEqual(title, "平台身份咨询")
        self.assertEqual(session.title, "平台身份咨询")
        self.assertEqual(session.title_status, ChatSession.TITLE_STATUS_READY)
        self.assertEqual(session.title_source, ChatSession.TITLE_SOURCE_AI)

    def test_generate_session_title_does_not_regenerate_after_first_turn(self):
        class TitleProvider:
            def __init__(self):
                self.calls = 0

            def chat(self, *, messages, options=None):
                self.calls += 1
                return "首轮标题"

        provider = TitleProvider()
        session = create_chat_session(user=self.user)
        create_session_message(
            session=session,
            role=ChatMessage.ROLE_USER,
            content="第一问",
        )
        create_session_message(
            session=session,
            role=ChatMessage.ROLE_ASSISTANT,
            content="第一答",
        )

        with patch("chat.services.title_service.get_chat_provider", return_value=provider):
            first_title = generate_session_title(session_id=session.id)

        create_session_message(
            session=session,
            role=ChatMessage.ROLE_USER,
            content="第二问",
        )
        create_session_message(
            session=session,
            role=ChatMessage.ROLE_ASSISTANT,
            content="第二答",
        )

        with patch("chat.services.title_service.get_chat_provider", return_value=provider):
            second_title = generate_session_title(session_id=session.id)

        self.assertEqual(first_title, "首轮标题")
        self.assertEqual(second_title, "首轮标题")
        self.assertEqual(provider.calls, 1)

    def test_create_session_requires_authentication(self):
        response = self.client.post(
            "/api/chat/sessions",
            data=json.dumps({}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {"code": 401, "message": "未认证。", "data": {}},
        )
        self.assertEqual(ChatSession.objects.count(), 0)

    def test_create_session_rejects_user_without_permission(self):
        unauthorized_user = User.objects.create_user(
            username="session-member",
            password="secret123",
            email="session-member@example.com",
        )
        token = generate_access_token(unauthorized_user)

        response = self.client.post(
            "/api/chat/sessions",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {"code": 403, "message": "无权限。", "data": {}},
        )
        self.assertEqual(ChatSession.objects.count(), 0)

    def test_create_session_rejects_invalid_context_filters(self):
        response = self.client.post(
            "/api/chat/sessions",
            data=json.dumps({"context_filters": ["not-an-object"]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], 400)
        self.assertEqual(ChatSession.objects.count(), 0)


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class ChatSessionListApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()
        self.user = User.objects.create_user(
            username="history-admin",
            password="secret123",
            email="history-admin@example.com",
        )
        self.user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.access_token = generate_access_token(self.user)

        self.other_user = User.objects.create_user(
            username="history-other",
            password="secret123",
            email="history-other@example.com",
        )
        self.other_user.groups.add(Group.objects.get(name=ROLE_ADMIN))

    def test_list_sessions_requires_authentication(self):
        response = self.client.get("/api/chat/sessions")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {"code": 401, "message": "未认证。", "data": {}},
        )

    def test_list_sessions_rejects_user_without_permission(self):
        unauthorized_user = User.objects.create_user(
            username="history-member",
            password="secret123",
            email="history-member@example.com",
        )
        token = generate_access_token(unauthorized_user)

        response = self.client.get(
            "/api/chat/sessions",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {"code": 403, "message": "无权限。", "data": {}},
        )

    def test_list_sessions_returns_only_current_user_sessions(self):
        own_session = ChatSession.objects.create(user=self.user, title="我的会话")
        ChatMessage.objects.create(
            session=own_session,
            role=ChatMessage.ROLE_USER,
            content="我的最后一条消息",
        )
        other_session = ChatSession.objects.create(user=self.other_user, title="别人的会话")
        ChatMessage.objects.create(
            session=other_session,
            role=ChatMessage.ROLE_USER,
            content="不应返回",
        )

        response = self.client.get(
            "/api/chat/sessions",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(len(payload["data"]["sessions"]), 1)
        self.assertEqual(payload["data"]["sessions"][0]["id"], own_session.id)
        self.assertEqual(payload["data"]["sessions"][0]["title"], "我的会话")
        self.assertEqual(payload["data"]["sessions"][0]["last_message_preview"], "我的最后一条消息")

    def test_list_sessions_includes_session_truth_fields(self):
        session = ChatSession.objects.create(
            user=self.user,
            title="会话真相字段",
            context_filters={"dataset_id": 7},
        )

        response = self.client.get(
            "/api/chat/sessions",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        session_payload = next(
            item for item in response.json()["data"]["sessions"] if item["id"] == session.id
        )
        self.assertIn("title_status", session_payload)
        self.assertEqual(session_payload["title_status"], "pending")
        self.assertIn("rolling_summary", session_payload)
        self.assertEqual(session_payload["rolling_summary"], "")
        self.assertIn("message_count", session_payload)
        self.assertEqual(session_payload["message_count"], 0)
        self.assertIn("last_message_at", session_payload)
        self.assertIsNone(session_payload["last_message_at"])

    def test_list_sessions_orders_by_recently_updated_desc(self):
        older_session = ChatSession.objects.create(user=self.user, title="较早更新")
        newer_session = ChatSession.objects.create(user=self.user, title="最近更新")

        ChatSession.objects.filter(id=older_session.id).update(updated_at="2026-03-27T08:00:00Z")
        ChatSession.objects.filter(id=newer_session.id).update(updated_at="2026-03-28T08:00:00Z")

        response = self.client.get(
            "/api/chat/sessions",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [session["id"] for session in response.json()["data"]["sessions"]],
            [newer_session.id, older_session.id],
        )

    def test_list_sessions_uses_latest_message_as_preview(self):
        session = ChatSession.objects.create(user=self.user, title="带摘要会话")
        ChatMessage.objects.create(
            session=session,
            sequence=1,
            role=ChatMessage.ROLE_USER,
            content="第一条消息",
        )
        ChatMessage.objects.create(
            session=session,
            sequence=3,
            role=ChatMessage.ROLE_ASSISTANT,
            content="第三条消息摘要",
        )
        ChatMessage.objects.create(
            session=session,
            sequence=2,
            role=ChatMessage.ROLE_USER,
            content="第二条消息",
        )

        response = self.client.get(
            "/api/chat/sessions",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        session_payload = response.json()["data"]["sessions"][0]
        self.assertEqual(session_payload["id"], session.id)
        self.assertEqual(session_payload["last_message_preview"], "第三条消息摘要")
        self.assertIn("created_at", session_payload)
        self.assertIn("updated_at", session_payload)

    def test_list_sessions_filters_by_dataset_and_keyword(self):
        first_session = ChatSession.objects.create(
            user=self.user,
            title="流动性风险讨论",
            context_filters={"dataset_id": 7},
        )
        ChatMessage.objects.create(
            session=first_session,
            role=ChatMessage.ROLE_USER,
            content="现金流承压",
        )
        second_session = ChatSession.objects.create(
            user=self.user,
            title="信用风险回顾",
            context_filters={"dataset_id": 7},
        )
        ChatMessage.objects.create(
            session=second_session,
            role=ChatMessage.ROLE_ASSISTANT,
            content="资本充足率下降",
        )
        third_session = ChatSession.objects.create(
            user=self.user,
            title="汇率敞口分析",
            context_filters={"dataset_id": 8},
        )
        ChatMessage.objects.create(
            session=third_session,
            role=ChatMessage.ROLE_USER,
            content="美元波动扩大",
        )

        response = self.client.get(
            "/api/chat/sessions?dataset_id=7&keyword=资本",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        sessions = response.json()["data"]["sessions"]
        self.assertEqual([session["id"] for session in sessions], [second_session.id])
        self.assertEqual(sessions[0]["title"], "信用风险回顾")


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class ChatSessionDetailApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()
        self.user = User.objects.create_user(
            username="detail-admin",
            password="secret123",
            email="detail-admin@example.com",
        )
        self.user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.access_token = generate_access_token(self.user)

        self.other_user = User.objects.create_user(
            username="detail-other",
            password="secret123",
            email="detail-other@example.com",
        )
        self.other_user.groups.add(Group.objects.get(name=ROLE_ADMIN))

        self.session = ChatSession.objects.create(
            user=self.user,
            title="压力测试会话",
            context_filters={"doc_type": "pdf"},
        )
        ChatMessage.objects.create(
            session=self.session,
            sequence=2,
            role=ChatMessage.ROLE_ASSISTANT,
            content="第二条回答",
            citations_json=[
                {
                    "document_title": "压力测试报告",
                    "doc_type": "pdf",
                    "page_label": "p.3",
                    "snippet": "资本充足率压力测试结果。",
                }
            ],
        )
        ChatMessage.objects.create(
            session=self.session,
            sequence=1,
            role=ChatMessage.ROLE_USER,
            content="第一条问题",
        )

    def test_session_detail_returns_session_and_ordered_messages(self):
        response = self.client.get(
            f"/api/chat/sessions/{self.session.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["data"]["session"]["id"], self.session.id)
        self.assertEqual(payload["data"]["session"]["title"], "压力测试会话")
        self.assertEqual(payload["data"]["session"]["context_filters"], {"doc_type": "pdf"})
        self.assertEqual(
            [message["content"] for message in payload["data"]["session"]["messages"]],
            ["第一条问题", "第二条回答"],
        )
        self.assertEqual(
            [message["sequence"] for message in payload["data"]["session"]["messages"]],
            [1, 2],
        )
        assistant_message = payload["data"]["session"]["messages"][1]
        self.assertEqual(
            assistant_message["citations_json"],
            [
                {
                    "document_title": "压力测试报告",
                    "doc_type": "pdf",
                    "page_label": "p.3",
                    "snippet": "资本充足率压力测试结果。",
                }
            ],
        )

    def test_session_detail_requires_authentication(self):
        response = self.client.get(f"/api/chat/sessions/{self.session.id}")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {"code": 401, "message": "未认证。", "data": {}},
        )

    def test_session_detail_rejects_access_to_other_users_session(self):
        other_token = generate_access_token(self.other_user)

        response = self.client.get(
            f"/api/chat/sessions/{self.session.id}",
            HTTP_AUTHORIZATION=f"Bearer {other_token}",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {"code": 403, "message": "无权限访问该会话。", "data": {}},
        )

    def test_session_detail_returns_404_for_missing_session(self):
        response = self.client.get(
            "/api/chat/sessions/999999",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json(),
            {"code": 404, "message": "会话不存在。", "data": {}},
        )

    def test_session_delete_removes_owned_session(self):
        response = self.client.delete(
            f"/api/chat/sessions/{self.session.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["session_id"], self.session.id)
        self.assertFalse(ChatSession.objects.filter(id=self.session.id).exists())
        self.assertFalse(ChatMessage.objects.filter(session_id=self.session.id).exists())

    def test_session_delete_rejects_access_to_other_users_session(self):
        other_token = generate_access_token(self.other_user)

        response = self.client.delete(
            f"/api/chat/sessions/{self.session.id}",
            HTTP_AUTHORIZATION=f"Bearer {other_token}",
        )

        self.assertEqual(response.status_code, 403)
        self.assertTrue(ChatSession.objects.filter(id=self.session.id).exists())

    def test_session_export_returns_transcript_payload(self):
        response = self.client.get(
            f"/api/chat/sessions/{self.session.id}/export",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["session"]["id"], self.session.id)
        self.assertEqual(payload["session"]["title"], "压力测试会话")
        self.assertEqual(payload["session"]["context_filters"], {"doc_type": "pdf"})
        self.assertEqual(
            [message["content"] for message in payload["session"]["messages"]],
            ["第一条问题", "第二条回答"],
        )
        self.assertIn("exported_at", payload)


class ChatMemoryGovernanceApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()
        self.user = User.objects.create_user(
            username="memory-admin",
            password="secret123",
            email="memory-admin@example.com",
        )
        self.user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.access_token = generate_access_token(self.user)
        self.other_user = User.objects.create_user(
            username="memory-other",
            password="secret123",
            email="memory-other@example.com",
        )
        self.other_user.groups.add(Group.objects.get(name=ROLE_ADMIN))

    def _get_memory_item_model(self):
        try:
            return apps.get_model("chat", "MemoryItem")
        except LookupError:
            self.fail("chat.MemoryItem must exist before memory governance APIs can be exercised.")

    def _get_memory_item_constant(self, memory_item_model, constant_name):
        constant_value = getattr(memory_item_model, constant_name, None)
        self.assertIsNotNone(
            constant_value,
            f"MemoryItem must define {constant_name} before governance tests can create fixtures.",
        )
        return constant_value

    def _get_memory_evidence_model(self):
        try:
            return apps.get_model("chat", "MemoryEvidence")
        except LookupError:
            self.fail("chat.MemoryEvidence must exist before evidence APIs can be exercised.")

    def _get_memory_action_log_model(self):
        try:
            return apps.get_model("chat", "MemoryActionLog")
        except LookupError:
            self.fail("chat.MemoryActionLog must exist before governance actions can be audited.")

    def _create_memory_item(self, **overrides):
        memory_item_model = self._get_memory_item_model()
        payload = {
            "user": self.user,
            "scope_type": self._get_memory_item_constant(memory_item_model, "SCOPE_USER_GLOBAL"),
            "scope_key": "",
            "memory_type": self._get_memory_item_constant(
                memory_item_model, "TYPE_USER_PREFERENCE"
            ),
            "title": "偏好表格",
            "content": "先给表格再给解释。",
        }
        payload.update(overrides)
        return memory_item_model.objects.create(**payload)

    def _assert_memory_contract(self, memory_payload, **expected_values):
        required_keys = {
            "id",
            "memory_type",
            "scope_type",
            "scope_key",
            "title",
            "content",
            "confidence_score",
            "source_kind",
            "status",
            "pinned",
            "updated_at",
        }
        self.assertTrue(required_keys.issubset(memory_payload.keys()))
        for key, value in expected_values.items():
            self.assertEqual(memory_payload[key], value)

    def test_memory_list_filters_by_scope_and_query(self):
        matching_memory = self._create_memory_item(
            title="偏好表格",
            content="先给表格再给解释。",
        )
        self._create_memory_item(
            title="偏好口语化回答",
            content="先给摘要再给解释。",
        )
        self._create_memory_item(
            user=self.other_user,
            title="他人的偏好表格",
            content="不应返回给当前用户。",
        )
        memory_item_model = self._get_memory_item_model()
        self._create_memory_item(
            scope_type=self._get_memory_item_constant(memory_item_model, "SCOPE_DATASET"),
            scope_key="7",
            title="数据集 7 关注点",
            content="也不应出现在 user_global 列表里。",
        )

        response = self.client.get(
            "/api/chat/memories?scope_type=user_global&q=表格",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["message"], "ok")
        self.assertEqual(len(payload["data"]["memories"]), 1)
        self.assertEqual(payload["data"]["memories"][0]["id"], matching_memory.id)
        self.assertEqual(payload["data"]["memories"][0]["title"], "偏好表格")
        self.assertEqual(payload["data"]["memories"][0]["scope_type"], "user_global")
        self.assertEqual(payload["data"]["memories"][0]["scope_key"], "")
        self._assert_memory_contract(
            payload["data"]["memories"][0],
            id=matching_memory.id,
            title="偏好表格",
            scope_type="user_global",
            scope_key="",
        )

    def test_memory_list_filters_by_dataset_scope_key(self):
        memory_item_model = self._get_memory_item_model()
        matching_memory = self._create_memory_item(
            scope_type=self._get_memory_item_constant(memory_item_model, "SCOPE_DATASET"),
            scope_key="7",
            title="数据集 7 重点",
            content="只应返回给 scope_key=7 的请求。",
        )
        self._create_memory_item(
            scope_type=self._get_memory_item_constant(memory_item_model, "SCOPE_DATASET"),
            scope_key="8",
            title="数据集 8 重点",
            content="不应返回给 scope_key=7 的请求。",
        )

        response = self.client.get(
            "/api/chat/memories?scope_type=dataset&scope_key=7",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["data"]["memories"]), 1)
        self.assertEqual(payload["data"]["memories"][0]["id"], matching_memory.id)
        self.assertEqual(payload["data"]["memories"][0]["scope_key"], "7")

    def test_memory_evidence_returns_memory_and_evidence_entries(self):
        memory_item = self._create_memory_item(
            title="偏好结构化回答",
            content="先给表格再给解释。",
        )
        evidence_model = self._get_memory_evidence_model()
        action_log_model = self._get_memory_action_log_model()
        session = ChatSession.objects.create(user=self.user, title="记忆证据会话")
        evidence_model.objects.create(
            memory_item=memory_item,
            session=session,
            evidence_excerpt="来自会话的证据片段",
            extractor_version="task4_memory_v1",
        )

        response = self.client.get(
            f"/api/chat/memories/{memory_item.id}/evidence",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["message"], "ok")
        self.assertEqual(payload["data"]["memory"]["id"], memory_item.id)
        self.assertEqual(payload["data"]["memory"]["title"], "偏好结构化回答")
        self.assertIn("evidence", payload["data"])
        self.assertIsInstance(payload["data"]["evidence"], list)
        self.assertGreaterEqual(len(payload["data"]["evidence"]), 1)
        first_entry = payload["data"]["evidence"][0]
        self.assertEqual(first_entry["evidence_excerpt"], "来自会话的证据片段")
        self.assertIn("created_at", first_entry)
        self._assert_memory_contract(
            payload["data"]["memory"],
            id=memory_item.id,
            title="偏好结构化回答",
        )
        self.assertTrue(
            action_log_model.objects.filter(
                memory_item=memory_item,
                actor_user=self.user,
                action=action_log_model.ACTION_VIEW,
            ).exists()
        )

    def test_memory_pin_requires_explicit_boolean_payload(self):
        memory_item = self._create_memory_item(
            title="偏好结构化回答",
            content="先给结论后给依据。",
        )

        response = self.client.post(
            f"/api/chat/memories/{memory_item.id}/pin",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertEqual(payload["code"], 400)
        self.assertIn("pinned", payload["data"])

    def test_memory_pin_updates_memory_state(self):
        memory_item = self._create_memory_item(
            title="偏好结构化回答",
            content="先给结论后给依据。",
        )

        response = self.client.post(
            f"/api/chat/memories/{memory_item.id}/pin",
            data=json.dumps({"pinned": True}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["message"], "ok")
        self.assertTrue(payload["data"]["memory"]["pinned"])
        memory_item.refresh_from_db()
        self.assertTrue(memory_item.pinned)

    @patch("chat.services.memory_service.MemoryActionLog.objects.create")
    def test_memory_pin_state_rolls_back_when_audit_logging_fails(self, mocked_create):
        memory_item = self._create_memory_item(pinned=False)
        mocked_create.side_effect = RuntimeError("audit log failed")

        with self.assertRaises(RuntimeError):
            set_memory_pin_state(
                memory_item=memory_item,
                actor_user=self.user,
                pinned=True,
            )

        memory_item.refresh_from_db()
        self.assertFalse(memory_item.pinned)

    @patch("chat.services.memory_service.MemoryActionLog.objects.create")
    def test_memory_delete_rolls_back_when_audit_logging_fails(self, mocked_create):
        memory_item_model = self._get_memory_item_model()
        memory_item = self._create_memory_item(
            status=self._get_memory_item_constant(memory_item_model, "STATUS_ACTIVE")
        )
        mocked_create.side_effect = RuntimeError("audit log failed")

        with self.assertRaises(RuntimeError):
            delete_memory_item(
                memory_item=memory_item,
                actor_user=self.user,
            )

        memory_item.refresh_from_db()
        self.assertEqual(
            memory_item.status,
            self._get_memory_item_constant(memory_item_model, "STATUS_ACTIVE"),
        )

    def test_memory_delete_hides_memory_from_active_list(self):
        deleted_memory = self._create_memory_item(
            title="待删除记忆",
            content="删除后不应再出现在活跃列表中。",
        )
        survivor_memory = self._create_memory_item(
            title="保留记忆",
            content="删除其他项后仍应保留。",
        )

        response = self.client.delete(
            f"/api/chat/memories/{deleted_memory.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["message"], "ok")
        self.assertEqual(payload["data"]["memory"]["id"], deleted_memory.id)

        list_response = self.client.get(
            "/api/chat/memories?scope_type=user_global",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        self.assertEqual(list_response.status_code, 200)
        returned_ids = [item["id"] for item in list_response.json()["data"]["memories"]]
        self.assertNotIn(deleted_memory.id, returned_ids)
        self.assertIn(survivor_memory.id, returned_ids)
