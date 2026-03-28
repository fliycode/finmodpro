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
from knowledgebase.services.document_service import create_document_from_upload, ingest_document
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

    def test_chat_ask_requires_question_or_query(self):
        response = self.client.post(
            "/api/chat/ask",
            data=json.dumps({"question": "   "}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"message": "question 或 query 为必填项。"})

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
