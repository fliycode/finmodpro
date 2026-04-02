import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from authentication.models import User
from authentication.services.jwt_service import generate_access_token
from knowledgebase.models import Document, IngestionTask
from knowledgebase.services.chunk_service import build_document_chunks
from knowledgebase.services.document_service import (
    create_document_from_upload,
    enqueue_document_ingestion,
    get_document_for_user,
    ingest_document,
    vectorize_document,
)
from rag.services.vector_store_service import index_document
from knowledgebase.services.parser_service import ParserService
from knowledgebase.tasks import ingest_document_task
from rag.services.vector_store_service import clear_store
from rbac.services.rbac_service import ROLE_ADMIN, seed_roles_and_permissions


class FakeEmbeddingProvider:
    def embed(self, *, texts, options=None):
        return [[float(index + 1) for index in range(64)] for _ in texts]


def fake_index_document_chunks(document):
    for chunk in document.chunks.all():
        chunk.vector_id = str(chunk.id)
        chunk.save(update_fields=["vector_id"])
    index_document(document)



@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class KnowledgebaseApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()
        clear_store()
        self.embedding_provider_patcher = patch(
            "knowledgebase.services.embedding_service.get_embedding_provider",
            return_value=FakeEmbeddingProvider(),
        )
        self.embedding_provider_patcher.start()
        self.vector_index_patcher = patch(
            "knowledgebase.services.document_service.index_document_chunks",
            side_effect=fake_index_document_chunks,
        )
        self.vector_index_patcher.start()
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()

        self.user = User.objects.create_user(
            username="kb-admin",
            password="secret123",
            email="kb@example.com",
        )
        self.user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.access_token = generate_access_token(self.user)

    def tearDown(self):
        self.embedding_provider_patcher.stop()
        self.override.disable()
        self.vector_index_patcher.stop()
        shutil.rmtree(self.media_root, ignore_errors=True)
        clear_store()

    def test_document_upload_list_detail_and_ingest_flow(self):
        upload_response = self.client.post(
            "/api/knowledgebase/documents",
            data={
                "title": "2025 Q4 report",
                "source_date": "2025-12-31",
                "file": SimpleUploadedFile(
                    "report.txt",
                    b"revenue increased materially in q4 and liquidity remained strong",
                    content_type="text/plain",
                ),
            },
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(upload_response.status_code, 201)
        upload_payload = upload_response.json()
        self.assertEqual(set(upload_payload.keys()), {"document"})
        self.assertEqual(upload_payload["document"]["status"], "uploaded")
        self.assertEqual(upload_payload["document"]["doc_type"], "txt")
        self.assertEqual(upload_payload["document"]["visibility"], "internal")
        self.assertEqual(upload_payload["document"]["uploader"]["username"], "kb-admin")
        self.assertEqual(upload_payload["document"]["owner"]["username"], "kb-admin")
        self.assertEqual(
            upload_payload["document"]["process_result"],
            "文档已上传，等待摄取任务执行。",
        )
        self.assertTrue(
            upload_payload["document"]["file_path"].startswith("knowledgebase/documents/")
        )

        list_response = self.client.get(
            "/api/knowledgebase/documents",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["total"], 1)
        self.assertEqual(len(list_response.json()["documents"]), 1)
        self.assertEqual(
            list_response.json()["documents"][0]["uploader"]["username"],
            "kb-admin",
        )

        document_id = upload_payload["document"]["id"]
        detail_response = self.client.get(
            f"/api/knowledgebase/documents/{document_id}",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(set(detail_response.json().keys()), {"document"})
        self.assertEqual(detail_response.json()["document"]["title"], "2025 Q4 report")
        self.assertEqual(
            detail_response.json()["document"]["parsed_text"],
            "",
        )
        self.assertEqual(
            detail_response.json()["document"]["preview_url"],
            detail_response.json()["document"]["original_url"],
        )

        ingest_response = self.client.post(
            f"/api/knowledgebase/documents/{document_id}/ingest",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        self.assertEqual(ingest_response.status_code, 200)
        ingest_payload = ingest_response.json()
        self.assertEqual(set(ingest_payload.keys()), {"document", "message"})
        self.assertEqual(ingest_payload["message"], "摄取任务已提交。")
        self.assertEqual(ingest_payload["document"]["status"], "indexed")
        self.assertGreaterEqual(ingest_payload["document"]["chunk_count"], 1)
        self.assertEqual(
            ingest_payload["document"]["process_result"],
            "文档已完成解析、切块与索引，可用于检索。",
        )

        document = Document.objects.get(id=document_id)
        ingestion_task = IngestionTask.objects.get(document=document)
        self.assertEqual(document.status, Document.STATUS_INDEXED)
        self.assertEqual(document.chunks.count(), ingest_payload["document"]["chunk_count"])
        self.assertEqual(ingestion_task.status, IngestionTask.STATUS_SUCCEEDED)
        self.assertEqual(ingestion_task.current_step, IngestionTask.STEP_COMPLETED)
        self.assertEqual(ingestion_task.retry_count, 0)
        self.assertEqual(ingestion_task.error_message, "")
        self.assertIsNotNone(ingestion_task.started_at)
        self.assertIsNotNone(ingestion_task.finished_at)
        self.assertTrue(ingestion_task.celery_task_id)

    def test_upload_requires_upload_permission_even_when_user_can_view_documents(self):
        member_user = User.objects.create_user(
            username="kb-member",
            password="secret123",
            email="member@example.com",
        )
        member_user.groups.add(Group.objects.get(name="member"))
        member_token = generate_access_token(member_user)

        response = self.client.post(
            "/api/knowledgebase/documents",
            data={
                "file": SimpleUploadedFile(
                    "report.txt",
                    b"content",
                    content_type="text/plain",
                ),
            },
            HTTP_AUTHORIZATION=f"Bearer {member_token}",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"message": "无权限。"})

    def test_list_and_detail_only_return_documents_visible_to_request_user(self):
        owner = User.objects.create_user(
            username="kb-owner",
            password="secret123",
            email="owner@example.com",
        )
        owner.groups.add(Group.objects.get(name="member"))
        owner_token = generate_access_token(owner)

        stranger = User.objects.create_user(
            username="kb-stranger",
            password="secret123",
            email="stranger@example.com",
        )
        stranger.groups.add(Group.objects.get(name="member"))
        stranger_token = generate_access_token(stranger)

        private_document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "private.txt",
                b"private content",
                content_type="text/plain",
            ),
            title="Private doc",
            source_date="2025-03-01",
            uploaded_by=owner,
            visibility=Document.VISIBILITY_PRIVATE,
        )
        shared_document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "shared.txt",
                b"shared content",
                content_type="text/plain",
            ),
            title="Shared doc",
            source_date="2025-03-01",
            uploaded_by=owner,
            visibility=Document.VISIBILITY_INTERNAL,
        )

        owner_list_response = self.client.get(
            "/api/knowledgebase/documents",
            HTTP_AUTHORIZATION=f"Bearer {owner_token}",
        )
        self.assertEqual(owner_list_response.status_code, 200)
        self.assertEqual(owner_list_response.json()["total"], 2)

        stranger_list_response = self.client.get(
            "/api/knowledgebase/documents",
            HTTP_AUTHORIZATION=f"Bearer {stranger_token}",
        )
        self.assertEqual(stranger_list_response.status_code, 200)
        self.assertEqual(stranger_list_response.json()["total"], 1)
        self.assertEqual(
            stranger_list_response.json()["documents"][0]["id"],
            shared_document.id,
        )

        hidden_detail_response = self.client.get(
            f"/api/knowledgebase/documents/{private_document.id}",
            HTTP_AUTHORIZATION=f"Bearer {stranger_token}",
        )
        self.assertEqual(hidden_detail_response.status_code, 404)


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class KnowledgebaseDocumentServiceTests(TestCase):
    def setUp(self):
        seed_roles_and_permissions()
        clear_store()
        self.embedding_provider_patcher = patch(
            "knowledgebase.services.embedding_service.get_embedding_provider",
            return_value=FakeEmbeddingProvider(),
        )
        self.embedding_provider_patcher.start()
        self.vector_index_patcher = patch(
            "knowledgebase.services.document_service.index_document_chunks",
            side_effect=fake_index_document_chunks,
        )
        self.vector_index_patcher.start()
        self.media_root = tempfile.mkdtemp()
        self.milvus_uri = f"{self.media_root}/test-milvus.db"
        self.override = override_settings(
            MEDIA_ROOT=self.media_root,
            MILVUS_URI=self.milvus_uri,
            MILVUS_COLLECTION_NAME="test_document_chunks",
        )
        self.override.enable()

    def tearDown(self):
        self.embedding_provider_patcher.stop()
        self.override.disable()
        self.vector_index_patcher.stop()
        shutil.rmtree(self.media_root, ignore_errors=True)
        clear_store()

    def test_ingest_document_transitions_uploaded_to_parsed_chunked_indexed(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "stages.txt",
                b"revenue improved and margin recovered",
                content_type="text/plain",
            ),
            title="Stages doc",
            source_date="2025-03-01",
            visibility=Document.VISIBILITY_PRIVATE,
        )
        observed_statuses = []

        def capture_index_call(doc):
            doc.refresh_from_db()
            observed_statuses.append(doc.status)

        self.assertEqual(document.status, Document.STATUS_UPLOADED)

        with patch(
            "knowledgebase.services.document_service.vectorize_document",
            side_effect=lambda doc: (
                capture_index_call(doc),
                vectorize_document(doc),
            )[1],
        ):
            ingest_document(document)

        document.refresh_from_db()
        self.assertEqual(document.status, Document.STATUS_INDEXED)
        self.assertEqual(document.error_message, "")
        self.assertTrue(all(chunk.vector_id for chunk in document.chunks.all()))
        self.assertEqual(observed_statuses, [Document.STATUS_CHUNKED])

        reparsed = Document.objects.get(id=document.id)
        self.assertEqual(reparsed.parsed_text, "revenue improved and margin recovered")
        self.assertEqual(reparsed.chunks.count(), 1)
        self.assertTrue(reparsed.chunks.exclude(vector_id="").exists())

    def test_ingest_document_task_indexes_uploaded_document(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "task.txt",
                b"capital adequacy remained stable across the reporting period",
                content_type="text/plain",
            ),
            title="Task doc",
            source_date="2025-03-01",
        )
        ingestion_task = IngestionTask.objects.create(document=document)

        ingest_document_task(document.id, ingestion_task.id)

        document.refresh_from_db()
        ingestion_task.refresh_from_db()
        self.assertEqual(document.status, Document.STATUS_INDEXED)
        self.assertEqual(document.error_message, "")
        self.assertEqual(document.chunks.count(), 1)
        self.assertTrue(document.chunks.exclude(vector_id="").exists())
        self.assertEqual(ingestion_task.status, IngestionTask.STATUS_SUCCEEDED)
        self.assertEqual(ingestion_task.current_step, IngestionTask.STEP_COMPLETED)
        self.assertIsNotNone(ingestion_task.started_at)
        self.assertIsNotNone(ingestion_task.finished_at)

    def test_enqueue_document_ingestion_creates_queued_then_succeeded_task_record(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "queued.txt",
                b"cash flow remained resilient",
                content_type="text/plain",
            ),
            title="Queued doc",
            source_date="2025-03-01",
        )

        ingestion_task, created = enqueue_document_ingestion(document)

        self.assertTrue(created)
        ingestion_task.refresh_from_db()
        self.assertEqual(ingestion_task.status, IngestionTask.STATUS_SUCCEEDED)
        self.assertEqual(ingestion_task.current_step, IngestionTask.STEP_COMPLETED)
        self.assertEqual(ingestion_task.retry_count, 0)
        self.assertTrue(ingestion_task.celery_task_id)
        self.assertIsNotNone(ingestion_task.started_at)
        self.assertIsNotNone(ingestion_task.finished_at)

    def test_ingest_document_marks_task_failed_when_parser_raises(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "failed.txt",
                b"should fail",
                content_type="text/plain",
            ),
            title="Failed doc",
            source_date="2025-03-01",
        )
        ingestion_task = IngestionTask.objects.create(document=document)

        with patch(
            "knowledgebase.services.document_service.parse_document",
            side_effect=ValueError("解析失败"),
        ):
            with self.assertRaisesMessage(ValueError, "解析失败"):
                ingest_document_task(document.id, ingestion_task.id)

        document.refresh_from_db()
        ingestion_task.refresh_from_db()
        self.assertEqual(document.status, Document.STATUS_FAILED)
        self.assertEqual(document.error_message, "解析失败")
        self.assertEqual(ingestion_task.status, IngestionTask.STATUS_FAILED)
        self.assertEqual(ingestion_task.current_step, IngestionTask.STEP_FAILED)
        self.assertEqual(ingestion_task.error_message, "解析失败")
        self.assertIsNotNone(ingestion_task.started_at)
        self.assertIsNotNone(ingestion_task.finished_at)

    def test_get_document_for_user_allows_owner_to_access_private_document(self):
        owner = User.objects.create_user(
            username="private-owner",
            password="secret123",
            email="private-owner@example.com",
        )
        owner.groups.add(Group.objects.get(name="member"))
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "owner.txt",
                b"owner scoped content",
                content_type="text/plain",
            ),
            title="Owner doc",
            source_date="2025-03-01",
            uploaded_by=owner,
            visibility=Document.VISIBILITY_PRIVATE,
        )

        visible_document = get_document_for_user(owner, document.id)

        self.assertEqual(visible_document.id, document.id)

    def test_parser_service_cleans_whitespace_and_blank_lines(self):
        cleaned = ParserService().clean_text(
            "Liquidity  risk \r\n\r\nwas stable.\n\n\nCapital-\nadequacy improved.\x00"
        )

        self.assertEqual(
            cleaned,
            "Liquidity risk\n\nwas stable.\n\nCapitaladequacy improved.",
        )

    def test_chunk_service_uses_fixed_length_with_overlap(self):
        chunks = build_document_chunks(
            "abcdefghij1234567890",
            metadata_builder=lambda index: {"chunk_index": index},
            chunk_size=10,
            overlap=2,
        )

        self.assertEqual([chunk["content"] for chunk in chunks], ["abcdefghij", "ij12345678", "7890"])
