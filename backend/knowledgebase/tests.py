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
from knowledgebase.models import Document, DocumentChunk, IngestionTask
from knowledgebase.services.chunk_service import build_document_chunks
from knowledgebase.services.document_service import (
    batch_enqueue_document_ingestion,
    batch_delete_documents,
    create_document_from_upload,
    delete_document_with_vectors,
    enqueue_document_ingestion,
    get_document_for_user,
    ingest_document,
    chunk_document,
    parse_document,
    vectorize_document,
)
from knowledgebase.services.vector_service import VectorService
from rag.services.vector_store_service import index_document
from knowledgebase.services.parser_service import ParserService, parse_document_file
from knowledgebase.tasks import ingest_document_task
from rag.services.vector_store_service import _VECTOR_STORE, clear_store
from rbac.services.rbac_service import ROLE_ADMIN, seed_roles_and_permissions


class FakeEmbeddingProvider:
    def embed(self, *, texts, options=None):
        return [[float(index + 1) for index in range(64)] for _ in texts]


class RecordingEmbeddingProvider:
    def __init__(self):
        self.calls = []

    def embed(self, *, texts, options=None):
        self.calls.append(list(texts))
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

    def test_document_ingest_retries_failed_document_and_increments_retry_count(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "retry.txt",
                b"requeue me after failure",
                content_type="text/plain",
            ),
            title="Retry doc",
            source_date="2025-03-01",
            uploaded_by=self.user,
        )
        document.status = Document.STATUS_FAILED
        document.error_message = "上一次解析失败"
        document.save(update_fields=["status", "error_message", "updated_at"])

        response = self.client.post(
            f"/api/knowledgebase/documents/{document.id}/ingest",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["message"], "摄取任务已提交。")
        self.assertEqual(payload["document"]["status"], "indexed")

        document.refresh_from_db()
        ingestion_task = IngestionTask.objects.filter(document=document).latest("id")
        self.assertEqual(ingestion_task.status, IngestionTask.STATUS_SUCCEEDED)
        self.assertEqual(ingestion_task.retry_count, 1)
        self.assertEqual(document.status, Document.STATUS_INDEXED)
        self.assertEqual(document.error_message, "")

    def test_dataset_create_list_detail_and_dataset_scoped_documents(self):
        create_response = self.client.post(
            "/api/knowledgebase/datasets",
            data=json.dumps(
                {
                    "name": "2025 年报数据集",
                    "description": "用于年报问答与风险提取",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(create_response.status_code, 201)
        dataset_payload = create_response.json()["dataset"]
        dataset_id = dataset_payload["id"]
        self.assertEqual(dataset_payload["name"], "2025 年报数据集")
        self.assertEqual(dataset_payload["document_count"], 0)

        list_response = self.client.get(
            "/api/knowledgebase/datasets",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["total"], 1)
        self.assertEqual(list_response.json()["datasets"][0]["id"], dataset_id)

        detail_response = self.client.get(
            f"/api/knowledgebase/datasets/{dataset_id}",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["dataset"]["id"], dataset_id)
        self.assertEqual(detail_response.json()["dataset"]["document_count"], 0)

        dataset_document_response = self.client.post(
            "/api/knowledgebase/documents",
            data={
                "title": "dataset scoped report",
                "dataset_id": str(dataset_id),
                "file": SimpleUploadedFile(
                    "dataset-report.txt",
                    b"dataset scoped content",
                    content_type="text/plain",
                ),
            },
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        self.assertEqual(dataset_document_response.status_code, 201)
        self.assertEqual(
            dataset_document_response.json()["document"]["dataset"],
            {
                "id": dataset_id,
                "name": "2025 年报数据集",
            },
        )

        other_document_response = self.client.post(
            "/api/knowledgebase/documents",
            data={
                "title": "ungrouped report",
                "file": SimpleUploadedFile(
                    "ungrouped.txt",
                    b"ungrouped content",
                    content_type="text/plain",
                ),
            },
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        self.assertEqual(other_document_response.status_code, 201)
        self.assertIsNone(other_document_response.json()["document"]["dataset"])

        filtered_response = self.client.get(
            f"/api/knowledgebase/documents?dataset_id={dataset_id}",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        self.assertEqual(filtered_response.status_code, 200)
        self.assertEqual(filtered_response.json()["total"], 1)
        self.assertEqual(
            filtered_response.json()["documents"][0]["title"],
            "dataset scoped report",
        )

    def test_document_version_upload_list_and_provenance_fields(self):
        upload_response = self.client.post(
            "/api/knowledgebase/documents",
            data={
                "title": "Q1 风险纪要",
                "file": SimpleUploadedFile(
                    "q1-report.txt",
                    b"original q1 risk memo",
                    content_type="text/plain",
                ),
            },
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(upload_response.status_code, 201)
        initial_document = upload_response.json()["document"]
        self.assertEqual(initial_document["version_number"], 1)
        self.assertEqual(initial_document["current_version"], 1)
        self.assertTrue(initial_document["is_current_version"])
        self.assertEqual(initial_document["provenance"]["source_type"], "upload")

        version_upload_response = self.client.post(
            f"/api/knowledgebase/documents/{initial_document['id']}/versions",
            data={
                "title": "Q1 风险纪要修订版",
                "source_type": "upload",
                "source_label": "Q1 风险纪要修订版",
                "source_metadata": json.dumps(
                    {
                        "channel": "email",
                        "checksum": "abc123",
                    }
                ),
                "processing_notes": "补充了董事会风险说明。",
                "file": SimpleUploadedFile(
                    "q1-report-v2.txt",
                    b"updated q1 risk memo",
                    content_type="text/plain",
                ),
            },
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(version_upload_response.status_code, 201)
        updated_document = version_upload_response.json()["document"]
        self.assertEqual(updated_document["root_document_id"], initial_document["id"])
        self.assertEqual(updated_document["version_number"], 2)
        self.assertEqual(updated_document["current_version"], 2)
        self.assertTrue(updated_document["is_current_version"])
        self.assertEqual(
            updated_document["provenance"]["source_label"],
            "Q1 风险纪要修订版",
        )
        self.assertEqual(
            updated_document["provenance"]["source_metadata"],
            {
                "channel": "email",
                "checksum": "abc123",
            },
        )
        self.assertEqual(
            updated_document["provenance"]["processing_notes"],
            "补充了董事会风险说明。",
        )

        versions_response = self.client.get(
            f"/api/knowledgebase/documents/{initial_document['id']}/versions",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        self.assertEqual(versions_response.status_code, 200)
        versions_payload = versions_response.json()
        self.assertEqual(versions_payload["document_id"], initial_document["id"])
        self.assertEqual(versions_payload["current_version"], 2)
        self.assertEqual(
            [item["version_number"] for item in versions_payload["versions"]],
            [2, 1],
        )
        self.assertTrue(versions_payload["versions"][0]["is_current"])
        self.assertFalse(versions_payload["versions"][1]["is_current"])
        self.assertEqual(
            versions_payload["versions"][0]["source_metadata"]["checksum"],
            "abc123",
        )

        list_response = self.client.get(
            "/api/knowledgebase/documents",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.json()["total"], 1)
        self.assertEqual(list_response.json()["documents"][0]["version_number"], 2)
        self.assertEqual(
            list_response.json()["documents"][0]["root_document_id"],
            initial_document["id"],
        )

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


class ParserServiceTests(TestCase):
    """ParserService unit tests — element conversion and dispatch paths."""

    # ── _elements_to_result conversion ──────────────────────────────────

    def test_elements_to_result_joins_texts_and_counts_elements(self):
        elements = [
            {"type": "Title", "text": "Report", "metadata": {"page_number": 1}},
            {"type": "Paragraph", "text": "Body text.", "metadata": {"page_number": 1}},
        ]
        result = ParserService()._elements_to_result(elements, strategy="fast")

        self.assertIn("Report", result["parsed_text"])
        self.assertIn("Body text.", result["parsed_text"])
        self.assertEqual(result["document_metadata"]["source_parser"], "unstructured")
        self.assertEqual(result["document_metadata"]["source_strategy"], "fast")
        self.assertEqual(result["document_metadata"]["element_count"], 2)
        self.assertFalse(result["document_metadata"]["fallback_used"])
        self.assertEqual(result["chunk_metadata_defaults"]["page_number"], 1)
        self.assertEqual(
            sorted(result["chunk_metadata_defaults"]["element_types"]),
            ["Paragraph", "Title"],
        )

    def test_elements_to_result_excludes_empty_text_entries(self):
        elements = [
            {"type": "Paragraph", "text": "Real content", "metadata": {}},
            {"type": "Figure", "text": "", "metadata": {}},
        ]
        result = ParserService()._elements_to_result(elements, strategy="auto")
        self.assertEqual(result["parsed_text"], "Real content")

    def test_elements_to_result_handles_multiple_pages(self):
        elements = [
            {"type": "Title", "text": "P1", "metadata": {"page_number": 1}},
            {"type": "Title", "text": "P2", "metadata": {"page_number": 2}},
            {"type": "Title", "text": "P3", "metadata": {"page_number": 3}},
        ]
        result = ParserService()._elements_to_result(elements, strategy="fast")
        self.assertEqual(result["chunk_metadata_defaults"]["page_number"], 1)

    def test_elements_to_result_raises_on_empty_elements(self):
        with self.assertRaises(ValueError):
            ParserService()._elements_to_result([], strategy="fast")

    def test_elements_to_result_raises_if_all_text_empty(self):
        elements = [
            {"type": "Figure", "text": "   ", "metadata": {}},
            {"type": "Table", "text": "", "metadata": {}},
        ]
        with self.assertRaises(ValueError):
            ParserService()._elements_to_result(elements, strategy="fast")

    def test_clean_text_normalizes_whitespace(self):
        service = ParserService()
        self.assertEqual(service.clean_text("hello   world"), "hello world")
        self.assertEqual(service.clean_text("line-\nbreak"), "linebreak")
        self.assertEqual(service.clean_text("a\r\nb\r\nc"), "a\nb\nc")

    # ── txt path ────────────────────────────────────────────────────────

    def test_txt_parses_locally(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
            f.write("plain text content")
            path = f.name
        try:
            doc = SimpleNamespace(doc_type="txt", file=SimpleNamespace(path=path))
            result = ParserService().parse(doc)
            self.assertEqual(result["document_metadata"]["source_parser"], "txt")
            self.assertEqual(result["parsed_text"], "plain text content")
        finally:
            os.unlink(path)

    # ── pdf path ────────────────────────────────────────────────────────

    @patch("knowledgebase.services.parser_service.parse_via_unstructured")
    def test_pdf_calls_unstructured_and_returns_elements(self, mock_parse):
        mock_parse.return_value = [
            {"type": "Paragraph", "text": "PDF content", "metadata": {"page_number": 1}},
        ]
        doc = SimpleNamespace(
            doc_type="pdf",
            file=SimpleNamespace(path="/fake/test.pdf"),
            filename="test.pdf",
        )
        result = ParserService().parse(doc)
        self.assertEqual(result["document_metadata"]["source_parser"], "unstructured")
        self.assertIn("PDF content", result["parsed_text"])

    @patch("knowledgebase.services.parser_service.parse_via_unstructured")
    def test_pdf_falls_back_to_pypdf_when_unstructured_fails(self, mock_parse):
        """When unstructured raises and PDF_FALLBACK_ENABLED, pypdf is used."""
        mock_parse.side_effect = ValueError("Service unreachable")

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            pdf_path = f.name
        try:
            from pypdf import PdfWriter

            writer = PdfWriter()
            writer.add_blank_page(612, 792)
            with open(pdf_path, "wb") as fw:
                writer.write(fw)

            doc = SimpleNamespace(
                doc_type="pdf",
                file=SimpleNamespace(path=pdf_path),
                filename="fallback.pdf",
            )
            with override_settings(UNSTRUCTURED_PDF_FALLBACK_ENABLED=True):
                result = ParserService().parse(doc)

            self.assertEqual(result["document_metadata"]["source_parser"], "pypdf")
            self.assertEqual(result["document_metadata"]["source_strategy"], "fallback")
            self.assertTrue(result["document_metadata"]["fallback_used"])
        finally:
            os.unlink(pdf_path)

    @patch("knowledgebase.services.parser_service.parse_via_unstructured")
    def test_pdf_no_fallback_when_disabled(self, mock_parse):
        mock_parse.side_effect = ValueError("Service unreachable")
        doc = SimpleNamespace(
            doc_type="pdf",
            file=SimpleNamespace(path="/fake/test.pdf"),
            filename="test.pdf",
        )
        with override_settings(UNSTRUCTURED_PDF_FALLBACK_ENABLED=False):
            with self.assertRaises(ValueError):
                ParserService().parse(doc)

    @patch("knowledgebase.services.parser_service.parse_via_unstructured")
    def test_pdf_empty_elements_falls_back_when_enabled(self, mock_parse):
        """Empty elements list triggers fallback to pypdf when fallback enabled."""
        mock_parse.return_value = []
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            pdf_path = f.name
        try:
            from pypdf import PdfWriter
            writer = PdfWriter()
            writer.add_blank_page(612, 792)
            with open(pdf_path, "wb") as fw:
                writer.write(fw)

            doc = SimpleNamespace(
                doc_type="pdf",
                file=SimpleNamespace(path=pdf_path),
                filename="empty.pdf",
            )
            with override_settings(UNSTRUCTURED_PDF_FALLBACK_ENABLED=True):
                result = ParserService().parse(doc)

            self.assertEqual(result["document_metadata"]["source_parser"], "pypdf")
            self.assertTrue(result["document_metadata"]["fallback_used"])
        finally:
            os.unlink(pdf_path)

    @patch("knowledgebase.services.parser_service.parse_via_unstructured")
    def test_pdf_empty_elements_raises_when_fallback_disabled(self, mock_parse):
        mock_parse.return_value = []
        doc = SimpleNamespace(
            doc_type="pdf",
            file=SimpleNamespace(path="/fake/test.pdf"),
            filename="test.pdf",
        )
        with override_settings(UNSTRUCTURED_PDF_FALLBACK_ENABLED=False):
            with self.assertRaises(ValueError):
                ParserService().parse(doc)

    # ── docx path ───────────────────────────────────────────────────────

    @patch("knowledgebase.services.parser_service.parse_via_unstructured")
    def test_docx_calls_unstructured_and_returns_elements(self, mock_parse):
        mock_parse.return_value = [
            {"type": "Title", "text": "DOCX Title", "metadata": {}},
            {"type": "Paragraph", "text": "Word content.", "metadata": {}},
        ]
        doc = SimpleNamespace(
            doc_type="docx",
            file=SimpleNamespace(path="/fake/test.docx"),
            filename="test.docx",
        )
        result = ParserService().parse(doc)
        self.assertEqual(result["document_metadata"]["source_parser"], "unstructured")
        self.assertIn("DOCX Title", result["parsed_text"])

    @patch("knowledgebase.services.parser_service.parse_via_unstructured")
    def test_docx_raises_when_unstructured_fails(self, mock_parse):
        """docx has no fallback — failure propagates."""
        mock_parse.side_effect = ValueError("Service unreachable")
        doc = SimpleNamespace(
            doc_type="docx",
            file=SimpleNamespace(path="/fake/test.docx"),
            filename="test.docx",
        )
        with self.assertRaises(ValueError):
            ParserService().parse(doc)

    @patch("knowledgebase.services.parser_service.parse_via_unstructured")
    def test_docx_empty_elements_raises(self, mock_parse):
        mock_parse.return_value = []
        doc = SimpleNamespace(
            doc_type="docx",
            file=SimpleNamespace(path="/fake/test.docx"),
            filename="test.docx",
        )
        with self.assertRaises(ValueError):
            ParserService().parse(doc)

    # ── unsupported type ────────────────────────────────────────────────

    def test_unsupported_doc_type_raises(self):
        doc = SimpleNamespace(
            doc_type="xls",
            file=SimpleNamespace(path="/fake/test.xls"),
        )
        with self.assertRaisesRegex(ValueError, "不支持的文档类型"):
            ParserService().parse(doc)


class _FakeMilvusClient:
    def __init__(self):
        self.insert_calls = []

    def insert(self, collection_name, rows):
        self.insert_calls.append((collection_name, rows))


@override_settings(KB_EMBEDDING_BATCH_SIZE=2)
class VectorServiceBatchingTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    @patch("rag.services.vector_store_service.index_document")
    @patch.object(VectorService, "_delete_existing_document_vectors")
    @patch.object(VectorService, "ensure_collection")
    def test_index_batches_chunk_embeddings(self, mock_ensure_collection, _mock_delete_existing_vectors, mock_index_document):
        provider = RecordingEmbeddingProvider()
        fake_client = _FakeMilvusClient()
        mock_ensure_collection.return_value = fake_client
        document = Document.objects.create(
            title="Batch me",
            file=SimpleUploadedFile("batch.txt", b"batch me", content_type="text/plain"),
            filename="batch.txt",
            doc_type="txt",
            status=Document.STATUS_CHUNKED,
            visibility=Document.VISIBILITY_INTERNAL,
            parsed_text="chunk one\nchunk two\nchunk three",
        )
        DocumentChunk.objects.create(document=document, chunk_index=0, content="chunk one")
        DocumentChunk.objects.create(document=document, chunk_index=1, content="chunk two")
        DocumentChunk.objects.create(document=document, chunk_index=2, content="chunk three")

        with patch(
            "knowledgebase.services.embedding_service.get_embedding_provider",
            return_value=provider,
        ):
            VectorService().index(document)

        self.assertEqual(
            provider.calls,
            [["chunk one", "chunk two"], ["chunk three"]],
        )
        self.assertEqual(len(fake_client.insert_calls), 1)
        inserted_rows = fake_client.insert_calls[0][1]
        self.assertEqual(len(inserted_rows), 3)
        mock_index_document.assert_called_once_with(document)

    @override_settings(KB_EMBEDDING_BATCH_SIZE=32)
    @patch("rag.services.vector_store_service.index_document")
    @patch.object(VectorService, "_delete_existing_document_vectors")
    @patch.object(VectorService, "ensure_collection")
    def test_index_caps_embedding_batch_size_at_provider_limit(self, mock_ensure_collection, _mock_delete_existing_vectors, mock_index_document):
        provider = RecordingEmbeddingProvider()
        fake_client = _FakeMilvusClient()
        mock_ensure_collection.return_value = fake_client
        document = Document.objects.create(
            title="Cap batch size",
            file=SimpleUploadedFile("cap.txt", b"cap", content_type="text/plain"),
            filename="cap.txt",
            doc_type="txt",
            status=Document.STATUS_CHUNKED,
            visibility=Document.VISIBILITY_INTERNAL,
            parsed_text=" ".join(f"chunk {index}" for index in range(11)),
        )
        for index in range(11):
            DocumentChunk.objects.create(
                document=document,
                chunk_index=index,
                content=f"chunk {index}",
            )

        with patch(
            "knowledgebase.services.embedding_service.get_embedding_provider",
            return_value=provider,
        ):
            VectorService().index(document)

        self.assertEqual([len(batch) for batch in provider.calls], [10, 1])
        self.assertEqual(len(fake_client.insert_calls[0][1]), 11)
        mock_index_document.assert_called_once_with(document)
