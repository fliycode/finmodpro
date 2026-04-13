import json
import os
import shutil
import tempfile
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import ProgrammingError, transaction
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from authentication.models import User
from authentication.services.jwt_service import generate_access_token
from knowledgebase.models import Document, IngestionTask
from knowledgebase.services.chunk_service import build_document_chunks
from knowledgebase.services.document_service import (
    batch_enqueue_document_ingestion,
    batch_delete_documents,
    create_document_from_upload,
    delete_document_with_vectors,
    enqueue_document_ingestion,
    get_document_for_user,
    ingest_document,
    vectorize_document,
)
from knowledgebase.services.vector_service import VectorService
from rag.services.vector_store_service import index_document
from knowledgebase.services.parser_service import ParserService
from knowledgebase.tasks import ingest_document_task
from rag.services.vector_store_service import _VECTOR_STORE, clear_store
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

    def test_document_list_returns_uploader_and_latest_ingestion_task(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "status.txt",
                b"funding profile stayed stable",
                content_type="text/plain",
            ),
            title="Status doc",
            source_date="2025-04-01",
            uploaded_by=self.user,
        )
        enqueue_document_ingestion(document)

        response = self.client.get(
            "/api/knowledgebase/documents",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        item = response.json()["documents"][0]
        self.assertEqual(item["uploader"]["username"], "kb-admin")
        self.assertEqual(item["owner"]["username"], "kb-admin")
        self.assertIn("latest_ingestion_task", item)
        self.assertGreaterEqual(item["chunk_count"], 1)
        self.assertGreaterEqual(item["vector_count"], 1)
        self.assertEqual(item["latest_ingestion_task"]["status"], "succeeded")
        self.assertEqual(item["latest_ingestion_task"]["current_step"], "completed")

    def test_document_list_without_pagination_params_returns_all_visible_documents(self):
        for index in range(12):
            create_document_from_upload(
                uploaded_file=SimpleUploadedFile(
                    f"doc-{index}.txt",
                    f"document {index}".encode("utf-8"),
                    content_type="text/plain",
                ),
                title=f"Doc {index}",
                source_date="2025-04-01",
                uploaded_by=self.user,
            )

        response = self.client.get(
            "/api/knowledgebase/documents",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 12)
        self.assertEqual(len(payload["documents"]), 12)
        self.assertNotIn("page", payload)
        self.assertNotIn("page_size", payload)
        self.assertNotIn("total_pages", payload)

    def test_batch_ingest_returns_accepted_and_skipped_counts(self):
        first = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "first.txt",
                b"first document content",
                content_type="text/plain",
            ),
            title="First",
            source_date="2026-04-10",
            uploaded_by=self.user,
        )
        second = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "second.txt",
                b"second document content",
                content_type="text/plain",
            ),
            title="Second",
            source_date="2026-04-10",
            uploaded_by=self.user,
        )
        running_task = IngestionTask.objects.create(
            document=second,
            status=IngestionTask.STATUS_RUNNING,
            current_step=IngestionTask.STEP_INDEXING,
        )

        response = self.client.post(
            "/api/knowledgebase/documents/batch/ingest",
            data=json.dumps({"document_ids": [first.id, second.id]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["accepted_count"], 1)
        self.assertEqual(payload["skipped_count"], 1)
        self.assertEqual(payload["failed_count"], 0)
        self.assertEqual(len(payload["results"]), 2)
        self.assertEqual(payload["results"][0]["document_id"], first.id)
        self.assertEqual(payload["results"][0]["status"], "accepted")
        self.assertEqual(payload["results"][1]["document_id"], second.id)
        self.assertEqual(payload["results"][1]["status"], "skipped")
        self.assertEqual(payload["results"][1]["reason"], "已有进行中的摄取任务。")
        self.assertEqual(payload["results"][1]["task_id"], running_task.id)

    def test_batch_ingest_reports_partial_failure_without_aborting_batch(self):
        first = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "first-partial.txt",
                b"first document content",
                content_type="text/plain",
            ),
            title="First partial",
            source_date="2026-04-10",
            uploaded_by=self.user,
        )
        second = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "second-partial.txt",
                b"second document content",
                content_type="text/plain",
            ),
            title="Second partial",
            source_date="2026-04-10",
            uploaded_by=self.user,
        )

        accepted_task = SimpleNamespace(id="task-accepted", status=IngestionTask.STATUS_QUEUED)
        with patch(
            "knowledgebase.services.document_service.enqueue_document_ingestion",
            side_effect=[(accepted_task, True), RuntimeError("queue unavailable")],
        ):
            response = self.client.post(
                "/api/knowledgebase/documents/batch/ingest",
                data=json.dumps({"document_ids": [first.id, second.id]}),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["accepted_count"], 1)
        self.assertEqual(payload["skipped_count"], 0)
        self.assertEqual(payload["failed_count"], 1)
        self.assertEqual(
            payload["results"],
            [
                {
                    "document_id": first.id,
                    "status": "accepted",
                    "task_id": accepted_task.id,
                },
                {
                    "document_id": second.id,
                    "status": "failed",
                    "reason": "queue unavailable",
                },
            ],
        )

    def test_batch_delete_removes_file_chunks_and_vectors(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "delete.txt",
                b"delete me",
                content_type="text/plain",
            ),
            title="Delete me",
            source_date="2026-04-10",
            uploaded_by=self.user,
        )
        enqueue_document_ingestion(document)
        document.refresh_from_db()
        original_path = document.file.path
        chunk_ids = list(document.chunks.values_list("id", flat=True))

        with patch.object(
            VectorService,
            "delete_document",
            return_value=None,
        ) as delete_vector_mock:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    "/api/knowledgebase/documents/batch/delete",
                    data=json.dumps({"document_ids": [document.id]}),
                    content_type="application/json",
                    HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["deleted_count"], 1)
        self.assertEqual(payload["failed_count"], 0)
        self.assertEqual(payload["results"], [{"document_id": document.id, "status": "deleted"}])
        self.assertFalse(Document.objects.filter(id=document.id).exists())
        self.assertFalse(IngestionTask.objects.filter(document_id=document.id).exists())
        self.assertFalse(document.chunks.model.objects.filter(id__in=chunk_ids).exists())
        self.assertFalse(os.path.exists(original_path))
        delete_vector_mock.assert_called_once_with(document.id)

    def test_batch_ingest_rejects_non_integer_document_ids(self):
        response = self.client.post(
            "/api/knowledgebase/documents/batch/ingest",
            data=json.dumps({"document_ids": [True, 1.5, "2"]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"message": "document_ids 必须是整数数组。"})

    def test_batch_delete_rejects_non_integer_document_ids(self):
        response = self.client.post(
            "/api/knowledgebase/documents/batch/delete",
            data=json.dumps({"document_ids": [True, 1.5, "2"]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"message": "document_ids 必须是整数数组。"})

    def test_batch_ingest_rejects_non_object_json_body(self):
        response = self.client.post(
            "/api/knowledgebase/documents/batch/ingest",
            data=json.dumps(["not-an-object"]),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"message": "请求体必须是 JSON 对象。"})

    def test_batch_delete_rejects_non_object_json_body(self):
        response = self.client.post(
            "/api/knowledgebase/documents/batch/delete",
            data=json.dumps(["not-an-object"]),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"message": "请求体必须是 JSON 对象。"})

    def test_batch_ingest_rejects_false_and_zero_document_ids_payload(self):
        for invalid_value in (False, 0):
            response = self.client.post(
                "/api/knowledgebase/documents/batch/ingest",
                data=json.dumps({"document_ids": invalid_value}),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
            )

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json(), {"message": "document_ids 必须是整数数组。"})

    def test_batch_delete_rejects_false_and_zero_document_ids_payload(self):
        for invalid_value in (False, 0):
            response = self.client.post(
                "/api/knowledgebase/documents/batch/delete",
                data=json.dumps({"document_ids": invalid_value}),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
            )

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json(), {"message": "document_ids 必须是整数数组。"})

    def test_batch_ingest_rejects_null_and_empty_string_document_ids_payload(self):
        for invalid_value in (None, ""):
            response = self.client.post(
                "/api/knowledgebase/documents/batch/ingest",
                data=json.dumps({"document_ids": invalid_value}),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
            )

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json(), {"message": "document_ids 必须是整数数组。"})

    def test_batch_delete_rejects_null_and_empty_string_document_ids_payload(self):
        for invalid_value in (None, ""):
            response = self.client.post(
                "/api/knowledgebase/documents/batch/delete",
                data=json.dumps({"document_ids": invalid_value}),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
            )

            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json(), {"message": "document_ids 必须是整数数组。"})

    def test_batch_ingest_rejects_malformed_utf8_body(self):
        response = self.client.generic(
            "POST",
            "/api/knowledgebase/documents/batch/ingest",
            b"\xff",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"message": "请求体必须是合法 JSON。"})

    def test_batch_delete_rejects_malformed_utf8_body(self):
        response = self.client.generic(
            "POST",
            "/api/knowledgebase/documents/batch/delete",
            b"\xff",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"message": "请求体必须是合法 JSON。"})

    def test_document_list_filters_and_paginates_results(self):
        now = timezone.now()

        recent_indexed_a = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "liquidity-a.txt",
                b"liquidity remained strong",
                content_type="text/plain",
            ),
            title="Liquidity A",
            source_date="2025-04-01",
            uploaded_by=self.user,
        )
        recent_indexed_b = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "liquidity-b.txt",
                b"liquidity remained strong with ample buffers",
                content_type="text/plain",
            ),
            title="Liquidity B",
            source_date="2025-04-01",
            uploaded_by=self.user,
        )
        recent_processing = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "processing.txt",
                b"pipeline still running",
                content_type="text/plain",
            ),
            title="Processing doc",
            source_date="2025-04-01",
            uploaded_by=self.user,
        )
        old_indexed = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "liquidity-old.txt",
                b"liquidity remained strong in the past",
                content_type="text/plain",
            ),
            title="Liquidity Old",
            source_date="2025-04-01",
            uploaded_by=self.user,
        )
        failed_match = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "liquidity-failed.txt",
                b"liquidity failed during ingestion",
                content_type="text/plain",
            ),
            title="Liquidity Failed",
            source_date="2025-04-01",
            uploaded_by=self.user,
        )

        Document.objects.filter(id=recent_indexed_a.id).update(
            status=Document.STATUS_INDEXED,
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(days=1),
        )
        Document.objects.filter(id=recent_indexed_b.id).update(
            status=Document.STATUS_INDEXED,
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(days=2),
        )
        Document.objects.filter(id=recent_processing.id).update(
            status=Document.STATUS_UPLOADED,
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(days=1),
        )
        IngestionTask.objects.create(
            document=recent_processing,
            status=IngestionTask.STATUS_RUNNING,
            current_step=IngestionTask.STEP_INDEXING,
        )
        Document.objects.filter(id=old_indexed.id).update(
            status=Document.STATUS_INDEXED,
            created_at=now - timedelta(days=20),
            updated_at=now - timedelta(days=20),
        )
        Document.objects.filter(id=failed_match.id).update(
            status=Document.STATUS_FAILED,
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(days=1),
        )

        response = self.client.get(
            "/api/knowledgebase/documents?q=liquidity&status=indexed&time_range=7d&page=2&page_size=1",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(set(payload.keys()), {"documents", "total", "page", "page_size", "total_pages"})
        self.assertEqual(payload["total"], 2)
        self.assertEqual(payload["page"], 2)
        self.assertEqual(payload["page_size"], 1)
        self.assertEqual(payload["total_pages"], 2)
        self.assertEqual(len(payload["documents"]), 1)
        self.assertEqual(payload["documents"][0]["id"], recent_indexed_b.id)
        self.assertNotIn("chunks", payload["documents"][0])

        processing_response = self.client.get(
            "/api/knowledgebase/documents?status=processing",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(processing_response.status_code, 200)
        processing_payload = processing_response.json()
        self.assertEqual(processing_payload["total"], 1)
        self.assertEqual(processing_payload["documents"][0]["id"], recent_processing.id)

    def test_document_chunks_endpoint_returns_chunk_rows(self):
        owner = User.objects.create_user(
            username="chunk-owner",
            password="secret123",
            email="chunk-owner@example.com",
        )
        owner.groups.add(Group.objects.get(name="member"))
        stranger = User.objects.create_user(
            username="chunk-stranger",
            password="secret123",
            email="chunk-stranger@example.com",
        )
        stranger.groups.add(Group.objects.get(name="member"))
        stranger_token = generate_access_token(stranger)

        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "chunks.txt",
                b"chunk one chunk two chunk three",
                content_type="text/plain",
            ),
            title="Chunk doc",
            source_date="2025-04-01",
            uploaded_by=owner,
            visibility=Document.VISIBILITY_PRIVATE,
        )
        document.chunks.create(
            chunk_index=0,
            content="chunk one",
            metadata={"page_label": "chunk-1"},
        )
        document.chunks.create(
            chunk_index=1,
            content="chunk two",
            metadata={"page_label": "chunk-2"},
        )

        response = self.client.get(
            f"/api/knowledgebase/documents/{document.id}/chunks",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["document_id"], document.id)
        self.assertEqual(len(payload["chunks"]), 2)
        self.assertEqual(payload["chunks"][0]["chunk_index"], 0)
        self.assertEqual(payload["chunks"][0]["content"], "chunk one")
        self.assertEqual(payload["chunks"][0]["page_label"], "chunk-1")
        self.assertEqual(payload["chunks"][0]["metadata"], {"page_label": "chunk-1"})
        self.assertNotIn("document", payload)

        hidden_response = self.client.get(
            f"/api/knowledgebase/documents/{document.id}/chunks",
            HTTP_AUTHORIZATION=f"Bearer {stranger_token}",
        )
        self.assertEqual(hidden_response.status_code, 404)

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

    def test_document_detail_returns_503_when_schema_is_outdated(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "schema.txt",
                b"schema drift content",
                content_type="text/plain",
            ),
            title="Schema doc",
            source_date="2025-03-01",
            uploaded_by=self.user,
        )
        self.client.raise_request_exception = False

        with patch(
            "knowledgebase.controllers.document_controller.build_document_response",
            side_effect=ProgrammingError("no such column: knowledgebase_document.visibility"),
        ):
            response = self.client.get(
                f"/api/knowledgebase/documents/{document.id}",
                HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["message"],
            "知识库数据表尚未初始化，请先执行后端迁移与 RBAC 初始化。",
        )

    def test_document_ingest_returns_503_when_schema_is_outdated(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "schema-ingest.txt",
                b"schema drift content",
                content_type="text/plain",
            ),
            title="Schema ingest doc",
            source_date="2025-03-01",
            uploaded_by=self.user,
        )
        self.client.raise_request_exception = False

        with patch(
            "knowledgebase.controllers.ingest_controller.enqueue_document_ingestion",
            return_value=(SimpleNamespace(id="task-1"), True),
        ), patch(
            "knowledgebase.controllers.ingest_controller.build_document_response",
            side_effect=ProgrammingError("no such column: knowledgebase_ingestiontask.current_step"),
        ):
            response = self.client.post(
                f"/api/knowledgebase/documents/{document.id}/ingest",
                HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["message"],
            "知识库数据表尚未初始化，请先执行后端迁移与 RBAC 初始化。",
        )

    def test_document_batch_delete_returns_503_when_schema_is_outdated(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "schema-delete.txt",
                b"schema drift content",
                content_type="text/plain",
            ),
            title="Schema delete doc",
            source_date="2025-03-01",
            uploaded_by=self.user,
        )
        self.client.raise_request_exception = False

        with patch(
            "knowledgebase.services.document_service.delete_document_with_vectors",
            side_effect=ProgrammingError("no such table: knowledgebase_document"),
        ):
            response = self.client.post(
                "/api/knowledgebase/documents/batch/delete",
                data=json.dumps({"document_ids": [document.id]}),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["message"],
            "知识库数据表尚未初始化，请先执行后端迁移与 RBAC 初始化。",
        )


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

    def test_batch_enqueue_document_ingestion_treats_disappeared_row_as_missing_result(self):
        user = User.objects.create_user(
            username="gone-admin",
            password="secret123",
            email="gone@example.com",
        )
        user.groups.add(Group.objects.get(name=ROLE_ADMIN))
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "gone.txt",
                b"gone document",
                content_type="text/plain",
            ),
            title="Gone doc",
            source_date="2025-03-01",
            uploaded_by=user,
        )

        with patch(
            "knowledgebase.services.document_service.enqueue_document_ingestion",
            side_effect=Document.DoesNotExist,
        ):
            result = batch_enqueue_document_ingestion(user, [document.id])

        self.assertEqual(
            result,
            {
                "accepted_count": 0,
                "skipped_count": 1,
                "failed_count": 0,
                "results": [
                    {
                        "document_id": document.id,
                        "status": "missing",
                        "reason": "文档不存在。",
                    }
                ],
            },
        )


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class KnowledgebaseVectorCleanupTests(TestCase):
    def setUp(self):
        seed_roles_and_permissions()
        clear_store()
        self.embedding_provider_patcher = patch(
            "knowledgebase.services.embedding_service.get_embedding_provider",
            return_value=FakeEmbeddingProvider(),
        )
        self.embedding_provider_patcher.start()
        self.media_root = tempfile.mkdtemp()
        self.milvus_uri = f"{self.media_root}/test-milvus.db"
        self.override = override_settings(
            MEDIA_ROOT=self.media_root,
            MILVUS_URI=self.milvus_uri,
            MILVUS_COLLECTION_NAME="test_document_chunks",
        )
        self.override.enable()
        self.user = User.objects.create_user(
            username="cleanup-admin",
            password="secret123",
            email="cleanup@example.com",
            is_staff=True,
        )
        self.user.groups.add(Group.objects.get(name=ROLE_ADMIN))

    def tearDown(self):
        self.embedding_provider_patcher.stop()
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)
        clear_store()

    def test_batch_delete_documents_removes_document_vectors_from_all_stores(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "cleanup.txt",
                b"treasury liquidity remained resilient through quarter end",
                content_type="text/plain",
            ),
            title="Cleanup doc",
            source_date="2026-04-10",
            uploaded_by=self.user,
        )
        ingest_document(document)
        document.refresh_from_db()
        original_path = document.file.path

        self.assertIn(document.id, _VECTOR_STORE)
        self.assertTrue(_VECTOR_STORE[document.id])
        self.assertTrue(
            VectorService().search(
                query="treasury liquidity resilient",
                filters={"document_id": document.id},
                top_k=5,
            )
        )

        with self.captureOnCommitCallbacks(execute=True):
            result = batch_delete_documents(self.user, [document.id])

        self.assertEqual(
            result,
            {
                "deleted_count": 1,
                "failed_count": 0,
                "results": [{"document_id": document.id, "status": "deleted"}],
            },
        )
        self.assertFalse(Document.objects.filter(id=document.id).exists())
        self.assertFalse(IngestionTask.objects.filter(document_id=document.id).exists())
        self.assertFalse(os.path.exists(original_path))
        self.assertNotIn(document.id, _VECTOR_STORE)
        self.assertEqual(
            VectorService().search(
                query="treasury liquidity resilient",
                filters={"document_id": document.id},
                top_k=5,
            ),
            [],
        )

    def test_batch_delete_hides_stale_vector_hits_when_vector_cleanup_fails(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "cleanup-stale-vectors.txt",
                b"stale vectors should not stay searchable",
                content_type="text/plain",
            ),
            title="Cleanup stale vector doc",
            source_date="2026-04-10",
            uploaded_by=self.user,
        )
        ingest_document(document)
        document.refresh_from_db()

        self.assertTrue(
            VectorService().search(
                query="stale vectors searchable",
                filters={"document_id": document.id},
                top_k=5,
            )
        )

        with patch.object(
            VectorService,
            "delete_document",
            side_effect=OSError("milvus unavailable"),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                result = batch_delete_documents(self.user, [document.id])

        self.assertEqual(
            result,
            {
                "deleted_count": 1,
                "failed_count": 0,
                "results": [{"document_id": document.id, "status": "deleted"}],
            },
        )
        self.assertFalse(Document.objects.filter(id=document.id).exists())
        self.assertNotIn(document.id, _VECTOR_STORE)
        self.assertEqual(
            VectorService().search(
                query="stale vectors searchable",
                filters={"document_id": document.id},
                top_k=5,
            ),
            [],
        )

    def test_delete_document_with_vectors_defers_vector_cleanup_until_commit(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "cleanup-deferred.txt",
                b"cleanup waits for commit",
                content_type="text/plain",
            ),
            title="Cleanup deferred doc",
            source_date="2026-04-10",
            uploaded_by=self.user,
        )
        ingest_document(document)
        document.refresh_from_db()

        self.assertIn(document.id, _VECTOR_STORE)
        self.assertTrue(
            VectorService().search(
                query="cleanup waits commit",
                filters={"document_id": document.id},
                top_k=5,
            )
        )

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            with transaction.atomic():
                locked_document = Document.objects.select_for_update().get(id=document.id)
                delete_document_with_vectors(locked_document)

                self.assertFalse(Document.objects.filter(id=document.id).exists())
                self.assertIn(document.id, _VECTOR_STORE)
                self.assertEqual(
                    VectorService().search(
                        query="cleanup waits commit",
                        filters={"document_id": document.id},
                        top_k=5,
                    ),
                    [],
                )

        self.assertEqual(len(callbacks), 1)
        self.assertIn(document.id, _VECTOR_STORE)
        callbacks[0]()
        self.assertEqual(
            VectorService().search(
                query="cleanup waits commit",
                filters={"document_id": document.id},
                top_k=5,
            ),
            [],
        )

    def test_batch_delete_reports_success_when_file_cleanup_fails_after_destructive_steps(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "cleanup-fail.txt",
                b"cleanup should survive storage failure",
                content_type="text/plain",
            ),
            title="Cleanup file failure doc",
            source_date="2026-04-10",
            uploaded_by=self.user,
        )
        ingest_document(document)
        document.refresh_from_db()
        file_name = document.file.name
        original_path = document.file.path

        with patch.object(
            document.file.storage,
            "delete",
            side_effect=OSError("disk busy"),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                result = batch_delete_documents(self.user, [document.id])

        self.assertEqual(
            result,
            {
                "deleted_count": 1,
                "failed_count": 0,
                "results": [{"document_id": document.id, "status": "deleted"}],
            },
        )
        self.assertFalse(Document.objects.filter(id=document.id).exists())
        self.assertFalse(IngestionTask.objects.filter(document_id=document.id).exists())
        self.assertNotIn(document.id, _VECTOR_STORE)
        self.assertEqual(
            VectorService().search(
                query="cleanup storage failure",
                filters={"document_id": document.id},
                top_k=5,
            ),
            [],
        )
        self.assertTrue(os.path.exists(original_path))
        self.assertTrue(document.file.storage.exists(file_name))

    def test_batch_delete_reports_success_when_file_exists_check_fails(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "cleanup-exists-fail.txt",
                b"cleanup should survive exists failure",
                content_type="text/plain",
            ),
            title="Cleanup exists failure doc",
            source_date="2026-04-10",
            uploaded_by=self.user,
        )
        ingest_document(document)
        document.refresh_from_db()
        original_path = document.file.path

        with patch.object(
            document.file.storage,
            "exists",
            side_effect=OSError("stat failed"),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                result = batch_delete_documents(self.user, [document.id])

        self.assertEqual(
            result,
            {
                "deleted_count": 1,
                "failed_count": 0,
                "results": [{"document_id": document.id, "status": "deleted"}],
            },
        )
        self.assertFalse(Document.objects.filter(id=document.id).exists())
        self.assertFalse(IngestionTask.objects.filter(document_id=document.id).exists())
        self.assertNotIn(document.id, _VECTOR_STORE)
        self.assertEqual(
            VectorService().search(
                query="cleanup exists failure",
                filters={"document_id": document.id},
                top_k=5,
            ),
            [],
        )
        self.assertTrue(os.path.exists(original_path))


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
    CELERY_TASK_ALWAYS_EAGER=False,
    CELERY_TASK_EAGER_PROPAGATES=True,
    CELERY_BROKER_URL="redis://127.0.0.1:6379/0",
)
class KnowledgebaseAsyncQueueTests(TestCase):
    def setUp(self):
        seed_roles_and_permissions()
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.user = User.objects.create_user(
            username="async-admin",
            password="secret123",
            email="async@example.com",
        )
        self.user.groups.add(Group.objects.get(name=ROLE_ADMIN))

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_enqueue_document_ingestion_resets_failed_document_to_uploaded_before_requeue(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "retry.txt",
                b"retry me",
                content_type="text/plain",
            ),
            title="Retry doc",
            source_date="2025-03-01",
        )
        document.status = Document.STATUS_FAILED
        document.error_message = "上一次解析失败"
        document.save(update_fields=["status", "error_message", "updated_at"])
        IngestionTask.objects.create(
            document=document,
            status=IngestionTask.STATUS_FAILED,
            current_step=IngestionTask.STEP_FAILED,
            error_message="上一次解析失败",
        )

        with patch(
            "knowledgebase.tasks.ingest_document_task.delay",
            return_value=SimpleNamespace(id="celery-task-123"),
        ) as delay_mock:
            ingestion_task, created = enqueue_document_ingestion(document)

        self.assertTrue(created)
        delay_mock.assert_called_once_with(document.id, ingestion_task.id)

        document.refresh_from_db()
        ingestion_task.refresh_from_db()
        self.assertEqual(document.status, Document.STATUS_UPLOADED)
        self.assertEqual(document.error_message, "")
        self.assertEqual(ingestion_task.status, IngestionTask.STATUS_QUEUED)
        self.assertEqual(ingestion_task.current_step, IngestionTask.STEP_QUEUED)
        self.assertEqual(ingestion_task.celery_task_id, "celery-task-123")

    def test_enqueue_document_ingestion_reuses_existing_running_task(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "running.txt",
                b"still working",
                content_type="text/plain",
            ),
            title="Running doc",
            source_date="2025-03-01",
        )
        running_task = IngestionTask.objects.create(
            document=document,
            status=IngestionTask.STATUS_RUNNING,
            current_step=IngestionTask.STEP_INDEXING,
        )

        with patch("knowledgebase.tasks.ingest_document_task.delay") as delay_mock:
            ingestion_task, created = enqueue_document_ingestion(document)

        self.assertFalse(created)
        self.assertEqual(ingestion_task.id, running_task.id)
        delay_mock.assert_not_called()

    def test_enqueue_document_ingestion_locks_document_before_creating_task(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "lock.txt",
                b"lock me",
                content_type="text/plain",
            ),
            title="Lock doc",
            source_date="2025-03-01",
        )

        with patch.object(
            Document.objects,
            "select_for_update",
            wraps=Document.objects.select_for_update,
        ) as select_for_update_mock, patch(
            "knowledgebase.tasks.ingest_document_task.delay",
            return_value=SimpleNamespace(id="celery-task-lock"),
        ):
            ingestion_task, created = enqueue_document_ingestion(document)

        self.assertTrue(created)
        self.assertEqual(ingestion_task.status, IngestionTask.STATUS_QUEUED)
        select_for_update_mock.assert_called_once()

    def test_enqueue_document_ingestion_cleans_up_queued_task_when_dispatch_fails(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "dispatch-fail.txt",
                b"dispatch failure",
                content_type="text/plain",
            ),
            title="Dispatch fail doc",
            source_date="2025-03-01",
        )
        document.status = Document.STATUS_FAILED
        document.error_message = "上一次解析失败"
        document.save(update_fields=["status", "error_message", "updated_at"])

        with patch(
            "knowledgebase.tasks.ingest_document_task.delay",
            side_effect=RuntimeError("queue unavailable"),
        ):
            with self.assertRaisesMessage(RuntimeError, "queue unavailable"):
                enqueue_document_ingestion(document)

        document.refresh_from_db()
        self.assertEqual(document.status, Document.STATUS_FAILED)
        self.assertEqual(document.error_message, "上一次解析失败")
        self.assertFalse(document.ingestion_tasks.filter(status=IngestionTask.STATUS_QUEUED).exists())

        with patch(
            "knowledgebase.tasks.ingest_document_task.delay",
            return_value=SimpleNamespace(id="celery-task-after-failure"),
        ) as delay_mock:
            ingestion_task, created = enqueue_document_ingestion(document)

        self.assertTrue(created)
        delay_mock.assert_called_once_with(document.id, ingestion_task.id)

    def test_batch_delete_skips_document_with_active_ingestion_task(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "queued-delete.txt",
                b"queued for ingestion",
                content_type="text/plain",
            ),
            title="Queued delete doc",
            source_date="2025-03-01",
            uploaded_by=self.user,
        )

        with patch(
            "knowledgebase.tasks.ingest_document_task.delay",
            return_value=SimpleNamespace(id="celery-task-456"),
        ):
            ingestion_task, created = enqueue_document_ingestion(document)

        self.assertTrue(created)
        result = batch_delete_documents(self.user, [document.id])

        self.assertEqual(
            result,
            {
                "deleted_count": 0,
                "failed_count": 1,
                "results": [
                    {
                        "document_id": document.id,
                        "status": "busy",
                        "message": "文档存在进行中的摄取任务，无法删除。",
                    }
                ],
            },
        )
        self.assertTrue(Document.objects.filter(id=document.id).exists())
        ingestion_task.refresh_from_db()
        self.assertEqual(ingestion_task.status, IngestionTask.STATUS_QUEUED)

    def test_batch_delete_locks_document_before_busy_check_and_delete(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "delete-lock.txt",
                b"delete lock me",
                content_type="text/plain",
            ),
            title="Delete lock doc",
            source_date="2025-03-01",
            uploaded_by=self.user,
        )

        with patch.object(
            Document.objects,
            "select_for_update",
            wraps=Document.objects.select_for_update,
        ) as select_for_update_mock, patch(
            "knowledgebase.services.document_service.delete_document_with_vectors",
            return_value=None,
        ) as delete_document_mock:
            result = batch_delete_documents(self.user, [document.id])

        self.assertEqual(
            result,
            {
                "deleted_count": 1,
                "failed_count": 0,
                "results": [{"document_id": document.id, "status": "deleted"}],
            },
        )
        select_for_update_mock.assert_called_once()
        delete_document_mock.assert_called_once()

    def test_ingest_document_task_returns_without_error_when_rows_were_deleted(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "stale-task.txt",
                b"stale task payload",
                content_type="text/plain",
            ),
            title="Stale task doc",
            source_date="2025-03-01",
            uploaded_by=self.user,
        )
        ingestion_task = IngestionTask.objects.create(
            document=document,
            status=IngestionTask.STATUS_QUEUED,
            current_step=IngestionTask.STEP_QUEUED,
        )
        document.delete()

        self.assertIsNone(ingest_document_task(document.id, ingestion_task.id))


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
    CELERY_TASK_ALWAYS_EAGER=False,
    CELERY_TASK_EAGER_PROPAGATES=True,
    CELERY_BROKER_URL="memory://",
)
class KnowledgebaseLocalMemoryBrokerTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        clear_store()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)
        clear_store()

    def test_enqueue_document_ingestion_executes_inline_when_memory_broker_is_used(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "inline.txt",
                b"cash flow stayed resilient",
                content_type="text/plain",
            ),
            title="Inline doc",
            source_date="2025-03-01",
        )

        with patch(
            "knowledgebase.services.embedding_service.get_embedding_provider",
            return_value=FakeEmbeddingProvider(),
        ), patch(
            "knowledgebase.services.document_service.index_document_chunks",
            side_effect=fake_index_document_chunks,
        ):
            ingestion_task, created = enqueue_document_ingestion(document)

        self.assertTrue(created)
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
        self.assertTrue(ingestion_task.celery_task_id)


class VectorServiceDimensionTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_index_creates_collection_with_actual_embedding_dimension(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "vector.txt",
                b"vector dimension sample",
                content_type="text/plain",
            ),
            title="Vector doc",
            source_date="2025-03-01",
        )
        document.parsed_text = "vector dimension sample"
        document.save(update_fields=["parsed_text", "updated_at"])
        chunk = document.chunks.create(
            chunk_index=0,
            content="vector dimension sample",
            metadata={"page_label": "chunk-1"},
        )

        mocked_client = Mock()
        mocked_client.has_collection.return_value = False

        with patch.object(VectorService, "_get_client", return_value=mocked_client), patch(
            "knowledgebase.services.vector_service.build_dense_embedding",
            return_value=[0.1, 0.2, 0.3, 0.4],
        ), patch("rag.services.vector_store_service.index_document"):
            VectorService().index(document)

        mocked_client.create_collection.assert_called_once()
        self.assertEqual(mocked_client.create_collection.call_args.kwargs["dimension"], 4)
        chunk.refresh_from_db()
        self.assertEqual(chunk.vector_id, str(chunk.id))

    def test_ensure_collection_recreates_existing_collection_when_dimension_mismatches(self):
        mocked_client = Mock()
        mocked_client.has_collection.return_value = True
        mocked_client.describe_collection.return_value = {
            "fields": [
                {"name": "id"},
                {"name": "vector", "params": {"dim": 64}},
            ]
        }

        with patch.object(VectorService, "_get_client", return_value=mocked_client):
            VectorService().ensure_collection(dimension=1024)

        mocked_client.drop_collection.assert_called_once()
        mocked_client.create_collection.assert_called_once()
        self.assertEqual(mocked_client.create_collection.call_args.kwargs["dimension"], 1024)

    def test_search_uses_query_embedding_dimension_instead_of_default_setting(self):
        mocked_client = Mock()
        mocked_client.has_collection.return_value = True
        mocked_client.describe_collection.return_value = {
            "fields": [
                {"name": "id"},
                {"name": "vector", "params": {"dim": 4}},
            ]
        }
        mocked_client.search.return_value = [[]]

        with override_settings(KB_EMBEDDING_DIMENSION=64), patch.object(
            VectorService, "_get_client", return_value=mocked_client
        ), patch(
            "knowledgebase.services.vector_service.build_dense_embedding",
            return_value=[0.1, 0.2, 0.3, 0.4],
        ):
            VectorService().search(query="开题报告", top_k=5)

        mocked_client.drop_collection.assert_not_called()
        mocked_client.create_collection.assert_not_called()
        mocked_client.search.assert_called_once()
