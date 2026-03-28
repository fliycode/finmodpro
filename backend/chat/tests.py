import json
import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import Client, TestCase, override_settings

from authentication.models import User
from authentication.services.jwt_service import generate_access_token
from chat.models import ChatMessage, ChatSession
from common.exceptions import UpstreamRateLimitError
from knowledgebase.services.document_service import create_document_from_upload, ingest_document
from rag.models import RetrievalLog
from rag.services.vector_store_service import clear_store
from rbac.services.rbac_service import ROLE_ADMIN, seed_roles_and_permissions


class FakeEmbeddingProvider:
    def embed(self, *, texts, options=None):
        return [[float(index + 1) for index in range(64)] for _ in texts]


class FakeChatProvider:
    def chat(self, *, messages, options=None):
        return messages[0]["content"]


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class ChatAskApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()
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
        self.chat_provider_patcher.start()
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
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
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)
        clear_store()

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

    def test_chat_ask_accepts_query_alias_and_returns_empty_citations_when_no_match(self):
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
        self.assertEqual(response.json()["question"], "foreign exchange exposure")
        self.assertEqual(response.json()["query"], "foreign exchange exposure")
        self.assertEqual(response.json()["citations"], [])
        self.assertIn("未检索到相关资料", response.json()["answer"])
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
            },
        )
        self.assertEqual(response["Retry-After"], "30")
        self.assertEqual(RetrievalLog.objects.count(), 0)


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class ChatSessionModelTests(TestCase):
    def test_chat_session_can_be_created_with_default_title_and_filters(self):
        user = User.objects.create_user(
            username="session-user",
            password="secret123",
            email="session@example.com",
        )

        session = ChatSession.objects.create(user=user)

        self.assertEqual(session.title, "新会话")
        self.assertEqual(session.context_filters, {})
        self.assertEqual(user.chat_sessions.count(), 1)

    def test_chat_session_allows_rag_scope_filters_without_strong_document_binding(self):
        user = User.objects.create_user(
            username="session-scope",
            password="secret123",
            email="scope@example.com",
        )

        session = ChatSession.objects.create(
            user=user,
            title="风险问答",
            context_filters={
                "document_id": 12,
                "doc_type": "pdf",
                "source_date_from": "2025-01-01",
            },
        )

        session.refresh_from_db()
        self.assertEqual(
            session.context_filters,
            {
                "document_id": 12,
                "doc_type": "pdf",
                "source_date_from": "2025-01-01",
            },
        )

    def test_deleting_user_cascades_chat_sessions(self):
        user = User.objects.create_user(
            username="session-delete",
            password="secret123",
            email="delete@example.com",
        )
        ChatSession.objects.create(user=user, title="待删除会话")

        user.delete()

        self.assertEqual(ChatSession.objects.count(), 0)


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
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
        self.assertEqual(payload["data"]["session"]["title"], "新会话")
        self.assertEqual(payload["data"]["session"]["context_filters"], {})
        self.assertEqual(payload["data"]["session"]["user_id"], self.user.id)
        self.assertEqual(ChatSession.objects.count(), 1)

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


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class ChatMessageModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="message-user",
            password="secret123",
            email="message@example.com",
        )
        self.session = ChatSession.objects.create(user=self.user, title="测试会话")

    def test_chat_message_can_be_created_with_default_type_and_incrementing_sequence(self):
        first_message = ChatMessage.objects.create(
            session=self.session,
            role=ChatMessage.ROLE_USER,
            content="第一条问题",
        )
        second_message = ChatMessage.objects.create(
            session=self.session,
            role=ChatMessage.ROLE_ASSISTANT,
            content="第一条回答",
        )

        self.assertEqual(first_message.sequence, 1)
        self.assertEqual(second_message.sequence, 2)
        self.assertEqual(first_message.message_type, ChatMessage.TYPE_TEXT)

    def test_chat_message_is_scoped_to_session_and_ordered_by_sequence(self):
        ChatMessage.objects.create(
            session=self.session,
            sequence=2,
            role=ChatMessage.ROLE_ASSISTANT,
            content="第二条",
        )
        ChatMessage.objects.create(
            session=self.session,
            sequence=1,
            role=ChatMessage.ROLE_USER,
            content="第一条",
        )

        self.assertEqual(
            list(self.session.messages.values_list("content", flat=True)),
            ["第一条", "第二条"],
        )

    def test_chat_message_sequence_must_be_unique_within_session(self):
        ChatMessage.objects.create(
            session=self.session,
            sequence=1,
            role=ChatMessage.ROLE_USER,
            content="重复检测 1",
        )

        with self.assertRaises(IntegrityError):
            ChatMessage.objects.create(
                session=self.session,
                sequence=1,
                role=ChatMessage.ROLE_ASSISTANT,
                content="重复检测 2",
            )

    def test_deleting_session_cascades_chat_messages(self):
        ChatMessage.objects.create(
            session=self.session,
            role=ChatMessage.ROLE_USER,
            content="待删除消息",
        )

        self.session.delete()

        self.assertEqual(ChatMessage.objects.count(), 0)
