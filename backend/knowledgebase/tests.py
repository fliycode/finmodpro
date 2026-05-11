import importlib
import json
import os
import shutil
import tempfile
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.apps import apps
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import ProgrammingError, transaction
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from authentication.models import User
from authentication.services.jwt_service import generate_access_token
from common.exceptions import UpstreamServiceError
from knowledgebase.models import (
    CleaningRule,
    Document,
    DocumentChunk,
    DocumentCleaningResult,
    DocumentSectionChunk,
    IngestionTask,
)
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
from rag.services.llamaindex_store_service import clear_store, sync_document, query_llamaindex_store
from knowledgebase.services.parser_service import ParserService, parse_document_file
from knowledgebase.tasks import ingest_document_task
from rbac.services.rbac_service import ROLE_ADMIN, seed_roles_and_permissions
from systemcheck.models import AuditRecord


class AuditRecordAssertionMixin:
    def assert_latest_audit(self, *, action, status, target_type=None, target_id=None):
        audit = AuditRecord.objects.order_by("-id").first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.action, action)
        self.assertEqual(audit.status, status)
        if target_type is not None:
            self.assertEqual(audit.target_type, target_type)
        if target_id is not None:
            self.assertEqual(audit.target_id, str(target_id))
        return audit


class FakeEmbeddingProvider:
    def embed(self, *, texts, options=None):
        return SimpleNamespace(vectors=[[float(index + 1) for index in range(64)] for _ in texts])


class RecordingEmbeddingProvider:
    def __init__(self):
        self.calls = []

    def embed(self, *, texts, options=None):
        self.calls.append(list(texts))
        return SimpleNamespace(vectors=[[float(index + 1) for index in range(64)] for _ in texts])


def fake_index_document_chunks(document):
    for chunk in document.chunks.all():
        chunk.vector_id = str(chunk.id)
        chunk.save(update_fields=["vector_id"])



@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class KnowledgebaseApiTests(AuditRecordAssertionMixin, TestCase):
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
        audit = self.assert_latest_audit(
            action="knowledgebase.document.upload",
            status=AuditRecord.STATUS_SUCCEEDED,
            target_type="document",
            target_id=upload_payload["document"]["id"],
        )
        self.assertEqual(audit.detail_payload["title"], "2025 Q4 report")
        self.assertEqual(audit.detail_payload["filename"], "report.txt")

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
        audit = self.assert_latest_audit(
            action="knowledgebase.dataset.create",
            status=AuditRecord.STATUS_SUCCEEDED,
            target_type="dataset",
            target_id=dataset_id,
        )
        self.assertEqual(audit.detail_payload["name"], "2025 年报数据集")

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
        audit = self.assert_latest_audit(
            action="knowledgebase.document_version.upload",
            status=AuditRecord.STATUS_SUCCEEDED,
            target_type="document",
            target_id=initial_document["id"],
        )
        self.assertEqual(audit.detail_payload["version_number"], 2)
        self.assertEqual(audit.detail_payload["source_type"], "upload")
        self.assertEqual(
            audit.detail_payload["source_metadata_keys"],
            ["channel", "checksum"],
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

    def test_document_list_serializes_hierarchical_ingestion_progress(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "hierarchical-status.txt",
                b"hierarchical status",
                content_type="text/plain",
            ),
            title="Hierarchical status",
            source_date="2025-04-01",
            uploaded_by=self.user,
        )
        IngestionTask.objects.create(
            document=document,
            status=IngestionTask.STATUS_RUNNING,
            current_step=IngestionTask.STEP_INDEXING,
            strategy=IngestionTask.STRATEGY_HIERARCHICAL,
            total_section_count=12,
            indexed_section_count=5,
            failed_section_count=0,
        )

        response = self.client.get(
            "/api/knowledgebase/documents",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        item = response.json()["documents"][0]
        self.assertEqual(item["latest_ingestion_task"]["strategy"], "hierarchical")
        self.assertEqual(item["latest_ingestion_task"]["total_section_count"], 12)
        self.assertEqual(item["latest_ingestion_task"]["indexed_section_count"], 5)
        self.assertEqual(item["latest_ingestion_task"]["failed_section_count"], 0)

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
        audit = self.assert_latest_audit(
            action="knowledgebase.document.batch_ingest",
            status=AuditRecord.STATUS_SUBMITTED,
            target_type="document",
        )
        self.assertEqual(audit.detail_payload["accepted_count"], 1)
        self.assertEqual(audit.detail_payload["skipped_count"], 1)

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
        audit = self.assert_latest_audit(
            action="knowledgebase.document.batch_delete",
            status=AuditRecord.STATUS_SUCCEEDED,
            target_type="document",
        )
        self.assertEqual(audit.detail_payload["deleted_count"], 1)
        self.assertEqual(audit.detail_payload["document_ids"], [document.id])

    def test_document_delete_writes_audit_record(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "single-delete.txt",
                b"single delete",
                content_type="text/plain",
            ),
            title="Single delete",
            source_date="2026-04-10",
            uploaded_by=self.user,
        )

        with patch.object(VectorService, "delete_document", return_value=None):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.delete(
                    f"/api/knowledgebase/documents/{document.id}",
                    HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
                )

        self.assertEqual(response.status_code, 200)
        audit = self.assert_latest_audit(
            action="knowledgebase.document.delete",
            status=AuditRecord.STATUS_SUCCEEDED,
            target_type="document",
            target_id=document.id,
        )
        self.assertEqual(audit.detail_payload["title"], "Single delete")
        self.assertEqual(audit.detail_payload["filename"], "single-delete.txt")

    def test_cleaning_rule_crud_and_document_cleaning_write_audit_records(self):
        create_rule_response = self.client.post(
            "/api/knowledgebase/cleaning/rules",
            data=json.dumps(
                {
                    "name": "Normalize quotes",
                    "rule_type": "normalize_quotes",
                    "config": {"locale": "zh-CN"},
                    "enabled": True,
                    "priority": 30,
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(create_rule_response.status_code, 201)
        rule_payload = create_rule_response.json()["rule"]
        audit = self.assert_latest_audit(
            action="knowledgebase.cleaning_rule.create",
            status=AuditRecord.STATUS_SUCCEEDED,
            target_type="cleaning_rule",
            target_id=rule_payload["id"],
        )
        self.assertEqual(audit.detail_payload["config_keys"], ["locale"])

        update_rule_response = self.client.patch(
            f"/api/knowledgebase/cleaning/rules/{rule_payload['id']}",
            data=json.dumps({"enabled": False, "priority": 10}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(update_rule_response.status_code, 200)
        audit = self.assert_latest_audit(
            action="knowledgebase.cleaning_rule.update",
            status=AuditRecord.STATUS_SUCCEEDED,
            target_type="cleaning_rule",
            target_id=rule_payload["id"],
        )
        self.assertEqual(audit.detail_payload["enabled"], False)
        self.assertEqual(audit.detail_payload["priority"], 10)

        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "cleaning.txt",
                b"Line one\nLine two",
                content_type="text/plain",
            ),
            title="Cleaning doc",
            source_date="2026-04-10",
            uploaded_by=self.user,
        )
        document.parsed_text = "Line one\nLine two"
        document.save(update_fields=["parsed_text", "updated_at"])

        cleaning_response = self.client.post(
            f"/api/knowledgebase/documents/{document.id}/cleaning",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(cleaning_response.status_code, 201)
        self.assertEqual(
            DocumentCleaningResult.objects.filter(document=document).count(),
            1,
        )
        audit = self.assert_latest_audit(
            action="knowledgebase.document.clean",
            status=AuditRecord.STATUS_SUCCEEDED,
            target_type="document",
            target_id=document.id,
        )
        self.assertEqual(audit.detail_payload["title"], "Cleaning doc")
        self.assertIn("quality_score", audit.detail_payload)

        delete_rule_response = self.client.delete(
            f"/api/knowledgebase/cleaning/rules/{rule_payload['id']}",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(delete_rule_response.status_code, 200)
        audit = self.assert_latest_audit(
            action="knowledgebase.cleaning_rule.delete",
            status=AuditRecord.STATUS_SUCCEEDED,
            target_type="cleaning_rule",
            target_id=rule_payload["id"],
        )
        self.assertEqual(audit.detail_payload["name"], "Normalize quotes")

    def test_cleaning_rule_bootstrap_is_idempotent_and_exposes_summary(self):
        bootstrap_response = self.client.post(
            "/api/knowledgebase/cleaning/rules/bootstrap",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(bootstrap_response.status_code, 201)
        bootstrap_payload = bootstrap_response.json()
        self.assertEqual(
            bootstrap_payload["created_count"],
            bootstrap_payload["summary"]["default_rule_total"],
        )
        self.assertTrue(bootstrap_payload["summary"]["default_rules_initialized"])
        self.assertEqual(
            CleaningRule.objects.count(),
            bootstrap_payload["summary"]["default_rule_total"],
        )
        audit = self.assert_latest_audit(
            action="knowledgebase.cleaning_rule.bootstrap",
            status=AuditRecord.STATUS_SUCCEEDED,
            target_type="cleaning_rule",
        )
        self.assertEqual(
            len(audit.detail_payload["rule_names"]),
            bootstrap_payload["summary"]["default_rule_total"],
        )

        second_response = self.client.post(
            "/api/knowledgebase/cleaning/rules/bootstrap",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        self.assertEqual(second_response.status_code, 200)
        second_payload = second_response.json()
        self.assertEqual(second_payload["created_count"], 0)
        self.assertEqual(
            second_payload["existing_count"],
            second_payload["summary"]["default_rule_total"],
        )
        audit = self.assert_latest_audit(
            action="knowledgebase.cleaning_rule.bootstrap",
            status=AuditRecord.STATUS_SKIPPED,
            target_type="cleaning_rule",
        )
        self.assertEqual(audit.detail_payload["created_count"], 0)

    def test_cleaning_summary_returns_gate_settings_and_recent_results(self):
        document_one = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "summary-one.txt",
                b"summary one",
                content_type="text/plain",
            ),
            title="Summary doc one",
            source_date="2026-04-10",
            uploaded_by=self.user,
        )
        document_two = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "summary-two.txt",
                b"summary two",
                content_type="text/plain",
            ),
            title="Summary doc two",
            source_date="2026-04-11",
            uploaded_by=self.user,
        )
        DocumentCleaningResult.objects.create(
            document=document_one,
            rules_applied=[],
            issues_found=[],
            quality_score=55.0,
            quality_signals={},
            original_length=100,
            cleaned_length=90,
            dedup_count=0,
        )
        DocumentCleaningResult.objects.create(
            document=document_two,
            rules_applied=[],
            issues_found=[],
            quality_score=88.0,
            quality_signals={},
            original_length=200,
            cleaned_length=180,
            dedup_count=1,
        )

        response = self.client.get(
            "/api/knowledgebase/cleaning/summary",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 200)
        summary = response.json()["summary"]
        self.assertEqual(summary["recent_result_count"], 2)
        self.assertEqual(summary["average_quality_score"], 71.5)
        self.assertEqual(summary["quality_gate"]["min_quality_score"], 60.0)
        self.assertFalse(summary["quality_gate"]["block_below_threshold"])
        self.assertEqual(summary["recent_results"][0]["document_title"], "Summary doc two")
        self.assertEqual(summary["recent_results"][0]["quality_gate"]["status"], "passed")
        self.assertEqual(summary["recent_results"][1]["quality_gate"]["status"], "warning")

    @override_settings(
        KB_CLEANING_MIN_QUALITY_SCORE=95,
        KB_CLEANING_WARN_QUALITY_SCORE=98,
        KB_CLEANING_BLOCK_BELOW_THRESHOLD=True,
    )
    def test_document_ingest_returns_422_when_cleaning_quality_is_blocked(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "quality-gate.txt",
                b"tiny",
                content_type="text/plain",
            ),
            title="Quality gate doc",
            source_date="2025-03-01",
            uploaded_by=self.user,
        )

        response = self.client.post(
            f"/api/knowledgebase/documents/{document.id}/ingest",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("质量不足", response.json()["message"])

        document.refresh_from_db()
        ingestion_task = IngestionTask.objects.filter(document=document).latest("id")
        self.assertEqual(document.status, Document.STATUS_FAILED)
        self.assertEqual(ingestion_task.status, IngestionTask.STATUS_FAILED)
        self.assertEqual(
            DocumentCleaningResult.objects.filter(document=document).count(),
            1,
        )
        audit = self.assert_latest_audit(
            action="knowledgebase.ingest",
            status=AuditRecord.STATUS_FAILED,
            target_type="document",
            target_id=document.id,
        )
        self.assertEqual(audit.detail_payload["quality_gate_status"], "blocked")

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
        result = ParserService()._elements_to_result(elements, source_parser="pymupdf4llm", strategy="auto")

        self.assertIn("Report", result["parsed_text"])
        self.assertIn("Body text.", result["parsed_text"])
        self.assertEqual(result["document_metadata"]["source_parser"], "pymupdf4llm")
        self.assertEqual(result["document_metadata"]["source_strategy"], "auto")
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
        result = ParserService()._elements_to_result(elements, source_parser="pymupdf4llm", strategy="auto")
        self.assertEqual(result["parsed_text"], "Real content")

    def test_elements_to_result_handles_multiple_pages(self):
        elements = [
            {"type": "Title", "text": "P1", "metadata": {"page_number": 1}},
            {"type": "Title", "text": "P2", "metadata": {"page_number": 2}},
            {"type": "Title", "text": "P3", "metadata": {"page_number": 3}},
        ]
        result = ParserService()._elements_to_result(elements, source_parser="pymupdf4llm", strategy="auto")
        self.assertEqual(result["chunk_metadata_defaults"]["page_number"], 1)

    def test_elements_to_result_raises_on_empty_elements(self):
        with self.assertRaises(ValueError):
            ParserService()._elements_to_result([], source_parser="pymupdf4llm", strategy="auto")

    def test_elements_to_result_raises_if_all_text_empty(self):
        elements = [
            {"type": "Figure", "text": "   ", "metadata": {}},
            {"type": "Table", "text": "", "metadata": {}},
        ]
        with self.assertRaises(ValueError):
            ParserService()._elements_to_result(elements, source_parser="pymupdf4llm", strategy="auto")

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

    @patch.object(ParserService, "_parse_pdf_via_pymupdf4llm")
    def test_pdf_calls_pymupdf4llm_and_returns_elements(self, mock_parse):
        mock_parse.return_value = [
            {"type": "Paragraph", "text": "PDF content", "metadata": {"page_number": 1}},
        ]
        doc = SimpleNamespace(
            doc_type="pdf",
            file=SimpleNamespace(path="/fake/test.pdf"),
            filename="test.pdf",
        )
        result = ParserService().parse(doc)
        self.assertEqual(result["document_metadata"]["source_parser"], "pymupdf4llm")
        self.assertIn("PDF content", result["parsed_text"])

    @patch.object(ParserService, "_parse_pdf_via_pymupdf4llm")
    def test_pdf_falls_back_to_pypdf_when_pymupdf4llm_fails(self, mock_parse):
        """When pymupdf4llm raises and PDF_FALLBACK_ENABLED, pypdf is used."""
        mock_parse.side_effect = ValueError("pymupdf4llm failed")

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
            with override_settings(PDF_FALLBACK_ENABLED=True):
                result = ParserService().parse(doc)

            self.assertEqual(result["document_metadata"]["source_parser"], "pypdf")
            self.assertEqual(result["document_metadata"]["source_strategy"], "fallback")
            self.assertTrue(result["document_metadata"]["fallback_used"])
        finally:
            os.unlink(pdf_path)

    @patch.object(ParserService, "_parse_pdf_via_pymupdf4llm")
    def test_pdf_no_fallback_when_disabled(self, mock_parse):
        mock_parse.side_effect = ValueError("pymupdf4llm failed")
        doc = SimpleNamespace(
            doc_type="pdf",
            file=SimpleNamespace(path="/fake/test.pdf"),
            filename="test.pdf",
        )
        with override_settings(PDF_FALLBACK_ENABLED=False):
            with self.assertRaises(ValueError):
                ParserService().parse(doc)

    @patch.object(ParserService, "_parse_pdf_via_pymupdf4llm")
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
            with override_settings(PDF_FALLBACK_ENABLED=True):
                result = ParserService().parse(doc)

            self.assertEqual(result["document_metadata"]["source_parser"], "pypdf")
            self.assertTrue(result["document_metadata"]["fallback_used"])
        finally:
            os.unlink(pdf_path)

    @patch.object(ParserService, "_parse_pdf_via_pymupdf4llm")
    def test_pdf_empty_elements_raises_when_fallback_disabled(self, mock_parse):
        mock_parse.return_value = []
        doc = SimpleNamespace(
            doc_type="pdf",
            file=SimpleNamespace(path="/fake/test.pdf"),
            filename="test.pdf",
        )
        with override_settings(PDF_FALLBACK_ENABLED=False):
            with self.assertRaises(ValueError):
                ParserService().parse(doc)

    # ── docx path ───────────────────────────────────────────────────────

    @patch.object(ParserService, "_parse_docx_via_python_docx")
    def test_docx_calls_python_docx_and_returns_elements(self, mock_parse):
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
        self.assertEqual(result["document_metadata"]["source_parser"], "python-docx")
        self.assertIn("DOCX Title", result["parsed_text"])

    @patch.object(ParserService, "_parse_docx_via_python_docx")
    def test_docx_raises_when_python_docx_fails(self, mock_parse):
        """docx has no fallback — failure propagates."""
        mock_parse.side_effect = ValueError("python-docx failed")
        doc = SimpleNamespace(
            doc_type="docx",
            file=SimpleNamespace(path="/fake/test.docx"),
            filename="test.docx",
        )
        with self.assertRaises(ValueError):
            ParserService().parse(doc)

    @patch.object(ParserService, "_parse_docx_via_python_docx")
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

    @patch.object(VectorService, "_delete_existing_document_vectors")
    @patch.object(VectorService, "ensure_collection")
    def test_index_batches_chunk_embeddings(self, mock_ensure_collection, _mock_delete_existing_vectors):
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
        self.assertEqual(
            DocumentChunk.objects.filter(document=document).exclude(vector_id="").count(),
            3,
        )

    @override_settings(KB_EMBEDDING_BATCH_SIZE=32)
    @patch.object(VectorService, "_delete_existing_document_vectors")
    @patch.object(VectorService, "ensure_collection")
    def test_index_caps_embedding_batch_size_at_provider_limit(self, mock_ensure_collection, _mock_delete_existing_vectors):
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
        self.assertEqual(
            DocumentChunk.objects.filter(document=document).exclude(vector_id="").count(),
            11,
        )

    @patch.object(VectorService, "_delete_existing_document_vectors")
    @patch.object(VectorService, "ensure_collection")
    def test_index_hierarchical_document_embeds_only_unindexed_sections(self, mock_ensure_collection, _mock_delete_existing_vectors):
        provider = RecordingEmbeddingProvider()
        fake_client = _FakeMilvusClient()
        mock_ensure_collection.return_value = fake_client
        document = Document.objects.create(
            title="Hierarchical batch me",
            file=SimpleUploadedFile("hierarchical.txt", b"hierarchical", content_type="text/plain"),
            filename="hierarchical.txt",
            doc_type="txt",
            status=Document.STATUS_CHUNKED,
            visibility=Document.VISIBILITY_INTERNAL,
            parsed_text="section one child one child two section two child three",
        )
        section_one = DocumentSectionChunk.objects.create(
            document=document,
            section_index=0,
            content="section one",
            metadata={"page_label": "section-1"},
            is_indexed=False,
        )
        DocumentSectionChunk.objects.create(
            document=document,
            section_index=1,
            content="section two",
            metadata={"page_label": "section-2"},
            is_indexed=True,
            vector_id="2",
        )
        DocumentChunk.objects.create(document=document, section_chunk=section_one, chunk_index=0, content="child one")
        DocumentChunk.objects.create(document=document, section_chunk=section_one, chunk_index=1, content="child two")
        IngestionTask.objects.create(
            document=document,
            strategy=IngestionTask.STRATEGY_HIERARCHICAL,
            total_section_count=2,
            indexed_section_count=1,
        )

        with patch(
            "knowledgebase.services.embedding_service.get_embedding_provider",
            return_value=provider,
        ):
            VectorService().index(document)

        self.assertEqual(provider.calls, [["section one"]])
        self.assertEqual(len(fake_client.insert_calls[0][1]), 1)
        self.assertEqual(
            DocumentSectionChunk.objects.filter(document=document, is_indexed=True).count(),
            2,
        )

    @patch.object(VectorService, "_delete_existing_document_vectors")
    @patch.object(VectorService, "ensure_collection")
    def test_index_hierarchical_document_updates_section_progress(self, mock_ensure_collection, _mock_delete_existing_vectors):
        provider = RecordingEmbeddingProvider()
        fake_client = _FakeMilvusClient()
        mock_ensure_collection.return_value = fake_client
        document = Document.objects.create(
            title="Hierarchical progress",
            file=SimpleUploadedFile("hierarchical-progress.txt", b"hierarchical", content_type="text/plain"),
            filename="hierarchical-progress.txt",
            doc_type="txt",
            status=Document.STATUS_CHUNKED,
            visibility=Document.VISIBILITY_INTERNAL,
            parsed_text="section one child one",
        )
        section = DocumentSectionChunk.objects.create(
            document=document,
            section_index=0,
            content="section one",
            metadata={"page_label": "section-1"},
            is_indexed=False,
        )
        DocumentChunk.objects.create(document=document, section_chunk=section, chunk_index=0, content="child one")
        task = IngestionTask.objects.create(
            document=document,
            strategy=IngestionTask.STRATEGY_HIERARCHICAL,
            total_section_count=1,
            indexed_section_count=0,
        )

        with patch(
            "knowledgebase.services.embedding_service.get_embedding_provider",
            return_value=provider,
        ):
            VectorService().index(document)

        section.refresh_from_db()
        task.refresh_from_db()
        self.assertTrue(section.is_indexed)
        self.assertTrue(section.vector_id)
        self.assertEqual(task.indexed_section_count, 1)



@override_settings(
    KB_SECTION_CHUNK_SIZE=2000,
    KB_SECTION_CHUNK_OVERLAP=200,
    KB_HIERARCHICAL_TEXT_THRESHOLD=500000,
    KB_HIERARCHICAL_CHUNK_THRESHOLD=3000,
)
class KnowledgebaseChunkServiceTests(TestCase):
    def test_build_hierarchical_chunks_from_plain_text_uses_large_sections(self):
        module = None
        try:
            module = importlib.import_module("knowledgebase.services.hierarchical_chunk_service")
        except ModuleNotFoundError:
            module = None

        builder = getattr(module, "build_hierarchical_document_chunks", None) if module else None
        self.assertIsNotNone(builder)

        result = builder(
            text="Section A\n\n" + ("A" * 3000) + "\n\nSection B\n\n" + ("B" * 3000),
            elements=None,
            section_metadata_builder=lambda index: {"section_index": index},
            child_metadata_builder=lambda section, index: {
                "section_index": section["chunk_index"],
                "chunk_index": index,
            },
        )

        self.assertGreaterEqual(len(result["sections"]), 2)
        self.assertGreater(len(result["child_chunks"]), len(result["sections"]))

    def test_large_document_trigger_switches_to_hierarchical_strategy(self):
        chooser = getattr(
            importlib.import_module("knowledgebase.services.chunk_service"),
            "choose_chunking_strategy",
            None,
        )
        self.assertIsNotNone(chooser)

        strategy = chooser(
            parsed_text_length=600_000,
            estimated_flat_chunk_count=3200,
        )

        self.assertEqual(strategy, "hierarchical")


class KnowledgebaseHierarchicalModelTests(TestCase):
    def test_large_document_can_store_section_and_child_chunks(self):
        section_model = None
        try:
            section_model = apps.get_model("knowledgebase", "DocumentSectionChunk")
        except LookupError:
            section_model = None

        self.assertIsNotNone(section_model)

    def test_child_chunks_can_reference_parent_section(self):
        section_chunk_field = next(
            (
                field
                for field in DocumentChunk._meta.get_fields()
                if getattr(field, "name", "") == "section_chunk"
            ),
            None,
        )

        self.assertIsNotNone(section_chunk_field)
        self.assertEqual(section_chunk_field.related_model.__name__, "DocumentSectionChunk")

    def test_ingestion_task_can_track_section_index_progress(self):
        field_names = {field.name for field in IngestionTask._meta.get_fields()}

        self.assertIn("strategy", field_names)
        self.assertIn("graph_sync_status", field_names)
        self.assertIn("graph_sync_error_message", field_names)
        self.assertIn("graph_document_id", field_names)
        self.assertIn("graph_track_id", field_names)
        self.assertIn("indexed_section_count", field_names)
        self.assertIn("total_section_count", field_names)
        self.assertIn("failed_section_count", field_names)


@override_settings(
    KB_HIERARCHICAL_TEXT_THRESHOLD=1000,
    KB_SECTION_CHUNK_SIZE=1200,
    KB_SECTION_CHUNK_OVERLAP=100,
)
class KnowledgebaseDocumentServiceTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.user = User.objects.create_user(
            username="kb-document-service",
            password="secret123",
            email="docsvc@example.com",
        )

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_chunk_document_persists_sections_and_children_for_large_document(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "large.txt",
                b"large document placeholder",
                content_type="text/plain",
            ),
            title="Large document",
            source_date="2026-04-28",
            uploaded_by=self.user,
        )

        chunks = chunk_document(
            document,
            {
                "parsed_text": "Section A\n\n" + ("A" * 1800) + "\n\nSection B\n\n" + ("B" * 1800),
                "elements": None,
                "chunk_metadata_defaults": {},
            },
        )

        self.assertGreater(DocumentSectionChunk.objects.filter(document=document).count(), 0)
        self.assertGreater(DocumentChunk.objects.filter(document=document).count(), 0)
        self.assertEqual(
            DocumentChunk.objects.filter(document=document, section_chunk__isnull=True).count(),
            0,
        )
        self.assertEqual(
            DocumentSectionChunk.objects.filter(document=document, search_text="").count(),
            0,
        )
        self.assertEqual(
            DocumentChunk.objects.filter(document=document, search_text="").count(),
            0,
        )
        self.assertEqual(document.status, Document.STATUS_CHUNKED)
        self.assertIn("sections", chunks)

    def test_chunk_document_populates_contextual_search_text_for_flat_chunks(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "flat.txt",
                b"flat document placeholder",
                content_type="text/plain",
            ),
            title="Liquidity memo",
            source_date="2026-04-28",
            uploaded_by=self.user,
        )

        chunk_document(
            document,
            {
                "parsed_text": "Liquidity remained strong and revenue improved.",
                "elements": None,
                "chunk_metadata_defaults": {},
            },
        )

        chunk = DocumentChunk.objects.get(document=document, chunk_index=0)
        self.assertIn("Liquidity memo", chunk.search_text)
        self.assertIn("txt", chunk.search_text)
        self.assertIn("2026-04-28", chunk.search_text)
        self.assertIn("Liquidity remained strong", chunk.search_text)


class RagHierarchicalRetrievalTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        clear_store()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)
        clear_store()

    @patch("rag.services.llamaindex_store_service.search")
    def test_query_store_returns_child_snippet_from_matched_section(self, mock_search):
        document = Document.objects.create(
            title="Annual report",
            file=SimpleUploadedFile("report.txt", b"report", content_type="text/plain"),
            filename="report.txt",
            doc_type="txt",
            status=Document.STATUS_INDEXED,
            visibility=Document.VISIBILITY_INTERNAL,
            parsed_text="revenue and liquidity",
        )
        section = DocumentSectionChunk.objects.create(
            document=document,
            section_index=0,
            content="Revenue overview and liquidity summary",
            metadata={"page_label": "section-1"},
            is_indexed=True,
            vector_id="-1",
        )
        DocumentChunk.objects.create(
            document=document,
            section_chunk=section,
            chunk_index=0,
            content="Liquidity remained strong throughout the year.",
            metadata={"page_label": "chunk-1"},
        )
        matching_child = DocumentChunk.objects.create(
            document=document,
            section_chunk=section,
            chunk_index=1,
            content="Revenue grew 10 percent year over year.",
            metadata={"page_label": "chunk-2"},
        )
        mock_search.return_value = [
            {
                "document_id": document.id,
                "chunk_id": matching_child.id,
                "section_chunk_id": section.id,
                "document_title": document.title,
                "doc_type": document.doc_type,
                "source_date": None,
                "page_label": "chunk-2",
                "snippet": matching_child.content,
                "metadata": {"page_label": "chunk-2"},
                "score": 0.9,
                "vector_score": 0.9,
                "keyword_score": 0.0,
                "section_context_summary": None,
                "matched_queries": [],
            }
        ]

        try:
            results = query_llamaindex_store("revenue growth", top_k=1)
        except Exception:
            results = []

        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["chunk_id"], matching_child.id)
        self.assertEqual(results[0]["section_chunk_id"], section.id)


@override_settings(KB_SENTENCE_WINDOW_SIZE=2)
class SentenceWindowChunkServiceTests(TestCase):
    def test_splits_chinese_sentences_with_window(self):
        from knowledgebase.services.chunk_service import build_sentence_window_chunks

        text = "第一句。第二句。第三句。第四句。第五句。第六句。第七句。第八句。第九句。第十句。"
        chunks = build_sentence_window_chunks(
            text,
            metadata_builder=lambda index: {"index": index},
        )

        # Each chunk content should be a single sentence
        for chunk in chunks:
            self.assertTrue(chunk["content"].endswith("。"))
            self.assertNotIn("\n", chunk["content"])

        # Window should contain surrounding sentences
        first_chunk = chunks[0]
        self.assertIn("第一句", first_chunk["metadata"]["window"])
        self.assertIn("第二句", first_chunk["metadata"]["window"])
        self.assertIn("第三句", first_chunk["metadata"]["window"])

    def test_window_metadata_contains_surrounding_sentences(self):
        from knowledgebase.services.chunk_service import build_sentence_window_chunks

        text = "A句。B句。C句。D句。E句。F句。G句。H句。I句。J句。"
        chunks = build_sentence_window_chunks(
            text,
            metadata_builder=lambda index: {},
            window_size=1,
        )

        # Middle chunk (D句) should have window of C句D句E句
        d_chunk = next(c for c in chunks if c["content"] == "D句。")
        self.assertIn("C句", d_chunk["metadata"]["window"])
        self.assertIn("E句", d_chunk["metadata"]["window"])

    def test_sentence_index_is_sequential(self):
        from knowledgebase.services.chunk_service import build_sentence_window_chunks

        text = "一。二。三。四。五。六。七。八。九。十。"
        chunks = build_sentence_window_chunks(
            text,
            metadata_builder=lambda index: {},
        )

        for i, chunk in enumerate(chunks):
            self.assertEqual(chunk["metadata"]["sentence_index"], i)
            self.assertEqual(chunk["chunk_index"], i)

    def test_short_document_falls_back_to_flat_chunking(self):
        from knowledgebase.services.chunk_service import build_sentence_window_chunks

        # With window_size=2, threshold is 2*2+1=5 sentences.
        # 5 sentences should fall back to flat chunking.
        text = "一。二。三。四。五。"
        chunks = build_sentence_window_chunks(
            text,
            metadata_builder=lambda index: {},
            window_size=2,
        )

        # Flat chunking produces fewer, larger chunks
        self.assertLessEqual(len(chunks), 2)
        # No window metadata in flat fallback
        for chunk in chunks:
            self.assertNotIn("window", chunk["metadata"])

    def test_english_sentences(self):
        from knowledgebase.services.chunk_service import build_sentence_window_chunks

        text = "First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence. Sixth sentence. Seventh sentence. Eighth sentence. Ninth sentence. Tenth sentence."
        chunks = build_sentence_window_chunks(
            text,
            metadata_builder=lambda index: {},
            window_size=1,
        )

        self.assertGreater(len(chunks), 5)
        for chunk in chunks:
            self.assertIn("window", chunk["metadata"])
            self.assertIn("sentence_index", chunk["metadata"])
