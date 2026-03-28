import shutil
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from authentication.models import User
from authentication.services.jwt_service import generate_access_token
from knowledgebase.models import Document
from knowledgebase.services.document_service import create_document_from_upload, ingest_document
from rag.services.vector_store_service import clear_store
from rbac.services.rbac_service import ROLE_ADMIN, seed_roles_and_permissions


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class KnowledgebaseApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_roles_and_permissions()
        clear_store()
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
        self.override.disable()
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

        document_id = upload_payload["document"]["id"]
        detail_response = self.client.get(
            f"/api/knowledgebase/documents/{document_id}",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(set(detail_response.json().keys()), {"document"})
        self.assertEqual(detail_response.json()["document"]["title"], "2025 Q4 report")

        ingest_response = self.client.post(
            f"/api/knowledgebase/documents/{document_id}/ingest",
            HTTP_AUTHORIZATION=f"Bearer {self.access_token}",
        )
        self.assertEqual(ingest_response.status_code, 200)
        ingest_payload = ingest_response.json()
        self.assertEqual(set(ingest_payload.keys()), {"document", "message"})
        self.assertEqual(ingest_payload["message"], "摄取完成。")
        self.assertEqual(ingest_payload["document"]["status"], "indexed")
        self.assertGreaterEqual(ingest_payload["document"]["chunk_count"], 1)

        document = Document.objects.get(id=document_id)
        self.assertEqual(document.status, Document.STATUS_INDEXED)
        self.assertEqual(document.chunks.count(), ingest_payload["document"]["chunk_count"])

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


@override_settings(
    JWT_SECRET_KEY="test-jwt-secret",
    JWT_ACCESS_TOKEN_LIFETIME_SECONDS=3600,
)
class KnowledgebaseDocumentServiceTests(TestCase):
    def setUp(self):
        clear_store()
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
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
        )
        observed_statuses = []

        def capture_index_call(doc):
            doc.refresh_from_db()
            observed_statuses.append(doc.status)

        self.assertEqual(document.status, Document.STATUS_UPLOADED)

        with patch(
            "knowledgebase.services.document_service.index_document",
            side_effect=capture_index_call,
        ):
            ingest_document(document)

        document.refresh_from_db()
        self.assertEqual(document.status, Document.STATUS_INDEXED)
        self.assertEqual(document.error_message, "")
        self.assertEqual(observed_statuses, [Document.STATUS_CHUNKED])

        reparsed = Document.objects.get(id=document.id)
        self.assertEqual(reparsed.parsed_text, "revenue improved and margin recovered")
        self.assertEqual(reparsed.chunks.count(), 1)
