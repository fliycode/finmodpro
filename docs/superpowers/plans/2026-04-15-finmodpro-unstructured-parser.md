# FinModPro Unstructured Parser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-phase Unstructured-backed parser lane for `pdf/docx` documents without changing FinModPro's existing ingest, chunking, retrieval, or API contracts.

**Architecture:** Keep `txt` parsing local in `knowledgebase.services.parser_service`, add a thin HTTP client for an external Unstructured service, and make `parse_document()` consume a structured parser result instead of a bare string. Persist parser provenance into `DocumentVersion`, merge parser metadata into `DocumentChunk.metadata`, and keep `pdf -> pypdf` as the only fallback path.

**Tech Stack:** Django, existing knowledgebase services, `urllib.request`, docker-compose, Django test runner, existing provenance/version models

---

## File Structure

- Modify: `backend/config/settings.py`
  Purpose: expose Unstructured environment-driven settings using existing config helpers
- Modify: `backend/knowledgebase/services/parser_service.py`
  Purpose: convert parser service from string-only parser to structured parser adapter with local txt parsing, Unstructured HTTP parsing, and pdf fallback
- Create: `backend/knowledgebase/services/unstructured_client.py`
  Purpose: isolate HTTP request/response handling for the external Unstructured service
- Modify: `backend/knowledgebase/services/document_service.py`
  Purpose: persist parser provenance to `DocumentVersion`, merge parser metadata into chunk metadata, and keep ingest flow compatible
- Modify: `backend/knowledgebase/tests.py`
  Purpose: add parser adapter, provenance, fallback, and chunk metadata regression coverage
- Modify: `backend/.env.example`
  Purpose: document new Unstructured configuration keys
- Modify: `backend/docs/dependency-services.md`
  Purpose: document the new parser-service dependency and fallback behavior
- Modify: `docker-compose.prod.yml`
  Purpose: add an internal `unstructured-api` service and wire backend/celery env vars

## Task 1: Add failing parser adapter tests

**Files:**
- Modify: `backend/knowledgebase/tests.py`

- [ ] **Step 1: Add failing tests for structured parser results**

```python
from knowledgebase.services.parser_service import ParserService


class KnowledgebaseDocumentServiceTests(TestCase):
    def test_parser_service_returns_structured_txt_result(self):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "memo.txt",
                b"Liquidity  risk\r\n\r\nremained stable.\n\n\nCapital-\nadequacy improved.",
                content_type="text/plain",
            ),
            title="Memo",
            source_date="2026-04-15",
            uploaded_by=self.user,
        )

        result = ParserService().parse(document)

        self.assertEqual(result["parsed_text"], "Liquidity risk\n\nremained stable.\n\nCapitaladequacy improved.")
        self.assertEqual(result["document_metadata"]["source_parser"], "txt")
        self.assertEqual(result["document_metadata"]["fallback_used"], False)
        self.assertEqual(result["chunk_metadata_defaults"]["source_strategy"], "local")

    @patch("knowledgebase.services.parser_service.parse_via_unstructured")
    def test_parser_service_routes_docx_to_unstructured(self, mocked_parse):
        mocked_parse.return_value = {
            "parsed_text": "board approved a revised policy",
            "document_metadata": {
                "source_parser": "unstructured",
                "source_strategy": "auto",
                "fallback_used": False,
                "element_count": 3,
            },
            "chunk_metadata_defaults": {
                "page_number": 1,
                "section_title": "Policy",
                "element_types": ["Title", "NarrativeText"],
                "source_parser": "unstructured",
                "source_strategy": "auto",
            },
        }
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "policy.docx",
                b"fake-docx-binary",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
            title="Policy",
            source_date="2026-04-15",
            uploaded_by=self.user,
        )

        result = ParserService().parse(document)

        self.assertEqual(result["parsed_text"], "board approved a revised policy")
        self.assertEqual(result["document_metadata"]["source_parser"], "unstructured")
        self.assertEqual(result["chunk_metadata_defaults"]["page_number"], 1)
```

- [ ] **Step 2: Run parser tests to verify they fail**

Run:

```bash
cd /root/finmodpro
backend/.venv/bin/python backend/manage.py test knowledgebase.tests.KnowledgebaseDocumentServiceTests.test_parser_service_returns_structured_txt_result knowledgebase.tests.KnowledgebaseDocumentServiceTests.test_parser_service_routes_docx_to_unstructured -v 2
```

Expected: FAIL because `ParserService.parse()` currently returns a string and there is no `parse_via_unstructured` helper.

- [ ] **Step 3: Add failing pdf fallback and failure-mode tests**

```python
    @patch("knowledgebase.services.parser_service.parse_via_unstructured", side_effect=ValueError("upstream timeout"))
    @patch("knowledgebase.services.parser_service.ParserService._parse_pdf", return_value="pdf fallback text")
    def test_parser_service_falls_back_to_pypdf_for_pdf(self, mocked_pdf, mocked_unstructured):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "report.pdf",
                b"%PDF-1.4 fake",
                content_type="application/pdf",
            ),
            title="Report",
            source_date="2026-04-15",
            uploaded_by=self.user,
        )

        result = ParserService().parse(document)

        self.assertEqual(result["parsed_text"], "pdf fallback text")
        self.assertEqual(result["document_metadata"]["source_parser"], "pypdf")
        self.assertEqual(result["document_metadata"]["fallback_used"], True)
        self.assertEqual(result["chunk_metadata_defaults"]["source_strategy"], "fallback")

    @patch("knowledgebase.services.parser_service.parse_via_unstructured", side_effect=ValueError("upstream timeout"))
    def test_parser_service_fails_fast_for_docx_when_unstructured_fails(self, mocked_parse):
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile(
                "report.docx",
                b"fake-docx-binary",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
            title="Report",
            source_date="2026-04-15",
            uploaded_by=self.user,
        )

        with self.assertRaisesMessage(ValueError, "upstream timeout"):
            ParserService().parse(document)
```

- [ ] **Step 4: Run fallback tests to verify they fail**

Run:

```bash
cd /root/finmodpro
backend/.venv/bin/python backend/manage.py test knowledgebase.tests.KnowledgebaseDocumentServiceTests.test_parser_service_falls_back_to_pypdf_for_pdf knowledgebase.tests.KnowledgebaseDocumentServiceTests.test_parser_service_fails_fast_for_docx_when_unstructured_fails -v 2
```

Expected: FAIL because parser fallback metadata does not exist yet.

- [ ] **Step 5: Commit**

```bash
cd /root/finmodpro
git add backend/knowledgebase/tests.py
git commit -m "Lock parser-adapter behavior before Unstructured integration" -m "These tests pin the first-phase parsing contract: structured parser results, docx routing through the external parser, and the asymmetric fallback policy where pdf may degrade to pypdf but docx fails fast." -m "Constraint: Existing parser tests only cover text cleaning and do not protect parser result shape\nRejected: Start implementation without contract tests | high risk of silent API drift in ingest path\nConfidence: high\nScope-risk: narrow\nReversibility: clean\nDirective: Keep parser result shape stable while phase one is landing; later parser backends should satisfy the same contract\nTested: Focused Django test commands for parser contract cases\nNot-tested: Real Unstructured service integration"
```

## Task 2: Implement the parser adapter and Unstructured client

**Files:**
- Create: `backend/knowledgebase/services/unstructured_client.py`
- Modify: `backend/knowledgebase/services/parser_service.py`
- Modify: `backend/config/settings.py`

- [ ] **Step 1: Add environment-backed settings**

```python
UNSTRUCTURED_API_URL = get_env("UNSTRUCTURED_API_URL", "http://unstructured-api:8000")
UNSTRUCTURED_API_KEY = get_env("UNSTRUCTURED_API_KEY", "")
UNSTRUCTURED_TIMEOUT_SECONDS = get_int_env("UNSTRUCTURED_TIMEOUT_SECONDS", 30)
UNSTRUCTURED_PDF_STRATEGY = get_env("UNSTRUCTURED_PDF_STRATEGY", "auto")
UNSTRUCTURED_DOCX_STRATEGY = get_env("UNSTRUCTURED_DOCX_STRATEGY", "auto")
UNSTRUCTURED_PDF_FALLBACK_ENABLED = get_bool_env("UNSTRUCTURED_PDF_FALLBACK_ENABLED", True)
```

- [ ] **Step 2: Add a thin HTTP client for the parser service**

```python
import json
from urllib import request
from urllib.error import HTTPError, URLError

from django.conf import settings


def parse_via_unstructured(*, file_path, filename, content_type, strategy):
    url = f"{settings.UNSTRUCTURED_API_URL.rstrip('/')}/parse"
    payload = json.dumps(
        {
            "filename": filename,
            "content_type": content_type,
            "strategy": strategy,
            "file_path": str(file_path),
        }
    ).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if settings.UNSTRUCTURED_API_KEY:
        headers["Authorization"] = f"Bearer {settings.UNSTRUCTURED_API_KEY}"
    http_request = request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with request.urlopen(http_request, timeout=settings.UNSTRUCTURED_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise ValueError(f"Unstructured 解析失败: HTTP {exc.code}") from exc
    except URLError as exc:
        raise ValueError("Unstructured 解析服务不可达。") from exc
```

- [ ] **Step 3: Convert parser service to structured-result adapter**

```python
class ParserService:
    def _txt_result(self, text):
        return {
            "parsed_text": self.clean_text(text),
            "document_metadata": {
                "source_parser": "txt",
                "source_strategy": "local",
                "fallback_used": False,
                "element_count": 0,
            },
            "chunk_metadata_defaults": {
                "page_number": None,
                "section_title": "",
                "element_types": [],
                "source_parser": "txt",
                "source_strategy": "local",
            },
        }

    def _pdf_fallback_result(self, text):
        return {
            "parsed_text": self.clean_text(text),
            "document_metadata": {
                "source_parser": "pypdf",
                "source_strategy": "fallback",
                "fallback_used": True,
                "element_count": 0,
            },
            "chunk_metadata_defaults": {
                "page_number": None,
                "section_title": "",
                "element_types": [],
                "source_parser": "pypdf",
                "source_strategy": "fallback",
            },
        }
```

- [ ] **Step 4: Implement `parse()` routing**

```python
    def parse(self, document):
        file_path = Path(document.file.path)
        if document.doc_type == "txt":
            return self._txt_result(file_path.read_text(encoding="utf-8"))

        if document.doc_type == "pdf":
            try:
                result = parse_via_unstructured(
                    file_path=file_path,
                    filename=document.filename,
                    content_type="application/pdf",
                    strategy=settings.UNSTRUCTURED_PDF_STRATEGY,
                )
                result["parsed_text"] = self.clean_text(result.get("parsed_text", ""))
                if not result["parsed_text"]:
                    raise ValueError("Unstructured 返回空文本。")
                return result
            except ValueError:
                if not settings.UNSTRUCTURED_PDF_FALLBACK_ENABLED:
                    raise
                return self._pdf_fallback_result(self._parse_pdf(file_path))

        if document.doc_type == "docx":
            result = parse_via_unstructured(
                file_path=file_path,
                filename=document.filename,
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                strategy=settings.UNSTRUCTURED_DOCX_STRATEGY,
            )
            result["parsed_text"] = self.clean_text(result.get("parsed_text", ""))
            if not result["parsed_text"]:
                raise ValueError("Unstructured 返回空文本。")
            return result
```

- [ ] **Step 5: Run parser tests to verify they pass**

Run:

```bash
cd /root/finmodpro
backend/.venv/bin/python backend/manage.py test knowledgebase.tests.KnowledgebaseDocumentServiceTests.test_parser_service_returns_structured_txt_result knowledgebase.tests.KnowledgebaseDocumentServiceTests.test_parser_service_routes_docx_to_unstructured knowledgebase.tests.KnowledgebaseDocumentServiceTests.test_parser_service_falls_back_to_pypdf_for_pdf knowledgebase.tests.KnowledgebaseDocumentServiceTests.test_parser_service_fails_fast_for_docx_when_unstructured_fails -v 2
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd /root/finmodpro
git add backend/config/settings.py backend/knowledgebase/services/unstructured_client.py backend/knowledgebase/services/parser_service.py backend/knowledgebase/tests.py
git commit -m "Introduce a structured parser adapter for Unstructured" -m "The parser layer now returns a stable structured result, keeps txt local, routes docx through the external service, and preserves the one allowed fallback path for pdf." -m "Constraint: Phase one must not add parser-heavy dependencies to the Django runtime\nRejected: Return raw Unstructured elements directly from parser service | leaks parser backend details into ingest pipeline\nConfidence: high\nScope-risk: moderate\nReversibility: clean\nDirective: Keep `parse_via_unstructured()` thin and backend-agnostic so future parser services can reuse the same contract\nTested: Focused Django parser tests\nNot-tested: Live HTTP round-trip against a real Unstructured container"
```

## Task 3: Persist provenance and enrich chunk metadata

**Files:**
- Modify: `backend/knowledgebase/services/document_service.py`
- Modify: `backend/knowledgebase/tests.py`

- [ ] **Step 1: Add failing ingestion tests for provenance and chunk metadata**

```python
    @patch("knowledgebase.services.document_service.parse_document_file")
    def test_parse_document_writes_parser_provenance_to_version_record(self, mocked_parse):
        mocked_parse.return_value = {
            "parsed_text": "capital buffer improved across the quarter",
            "document_metadata": {
                "source_parser": "unstructured",
                "source_strategy": "auto",
                "fallback_used": False,
                "element_count": 4,
            },
            "chunk_metadata_defaults": {
                "page_number": 2,
                "section_title": "Capital",
                "element_types": ["Title", "NarrativeText"],
                "source_parser": "unstructured",
                "source_strategy": "auto",
            },
        }
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile("capital.txt", b"capital buffer", content_type="text/plain"),
            title="Capital",
            source_date="2026-04-15",
            uploaded_by=self.user,
        )

        result = parse_document(document)
        document.refresh_from_db()

        self.assertEqual(result["parsed_text"], "capital buffer improved across the quarter")
        self.assertEqual(document.version_record.source_metadata["source_parser"], "unstructured")
        self.assertEqual(document.version_record.source_metadata["element_count"], 4)

    @patch("knowledgebase.services.document_service.parse_document_file")
    def test_chunk_document_merges_parser_metadata_defaults(self, mocked_parse):
        mocked_parse.return_value = {
            "parsed_text": "liquidity coverage ratio stayed above target",
            "document_metadata": {
                "source_parser": "pypdf",
                "source_strategy": "fallback",
                "fallback_used": True,
                "element_count": 0,
            },
            "chunk_metadata_defaults": {
                "page_number": 7,
                "section_title": "Liquidity",
                "element_types": ["NarrativeText"],
                "source_parser": "pypdf",
                "source_strategy": "fallback",
            },
        }
        document = create_document_from_upload(
            uploaded_file=SimpleUploadedFile("liquidity.txt", b"liquidity coverage ratio", content_type="text/plain"),
            title="Liquidity",
            source_date="2026-04-15",
            uploaded_by=self.user,
        )

        parser_result = parse_document(document)
        chunks = chunk_document(document, parser_result)

        self.assertEqual(chunks[0]["metadata"]["page_number"], 7)
        self.assertEqual(chunks[0]["metadata"]["section_title"], "Liquidity")
        self.assertEqual(chunks[0]["metadata"]["source_parser"], "pypdf")
```

- [ ] **Step 2: Run focused ingestion tests to verify they fail**

Run:

```bash
cd /root/finmodpro
backend/.venv/bin/python backend/manage.py test knowledgebase.tests.KnowledgebaseDocumentServiceTests.test_parse_document_writes_parser_provenance_to_version_record knowledgebase.tests.KnowledgebaseDocumentServiceTests.test_chunk_document_merges_parser_metadata_defaults -v 2
```

Expected: FAIL because `parse_document()` still expects a string and `_build_chunk_metadata()` does not accept parser defaults.

- [ ] **Step 3: Update parse and chunk flow**

```python
def _update_version_record_from_parser(document, parser_result):
    version_record = _get_version_record(document)
    if version_record is None:
        return
    document_metadata = parser_result.get("document_metadata") or {}
    version_record.source_metadata = {
        **(version_record.source_metadata or {}),
        **document_metadata,
    }
    if document_metadata.get("fallback_used"):
        version_record.processing_notes = "pdf parse fallback to pypdf"
    version_record.save(update_fields=["source_metadata", "processing_notes"])


def _build_chunk_metadata(document, index, parser_defaults=None):
    metadata = {
        "document_id": document.id,
        "document_title": document.title,
        "doc_type": document.doc_type,
        "source_date": document.source_date.isoformat() if document.source_date else None,
        "dataset_id": document.dataset_id,
        "dataset_name": document.dataset.name if getattr(document, "dataset", None) else None,
        "root_document_id": _get_root_document_id(document, _get_version_record(document)),
        "version_number": _get_current_version_number(document, _get_version_record(document)),
        "chunk_index": index,
        "page_label": f"chunk-{index + 1}",
    }
    return {**metadata, **(parser_defaults or {})}
```

- [ ] **Step 4: Make `parse_document()` and `chunk_document()` consume parser results**

```python
def parse_document(document):
    parser_result = parse_document_file(document)
    document.parsed_text = parser_result["parsed_text"]
    document.error_message = ""
    document.save(update_fields=["parsed_text", "error_message", "updated_at"])
    _update_version_record_from_parser(document, parser_result)
    _update_document_status(document, status=Document.STATUS_PARSED)
    return parser_result


def chunk_document(document, parser_result):
    parsed_text = parser_result["parsed_text"]
    parser_defaults = parser_result.get("chunk_metadata_defaults") or {}
    DocumentChunk.objects.filter(document=document).delete()
    chunks = build_document_chunks(
        parsed_text,
        metadata_builder=lambda index: _build_chunk_metadata(document, index, parser_defaults),
    )
```

- [ ] **Step 5: Run ingestion and API compatibility tests**

Run:

```bash
cd /root/finmodpro
backend/.venv/bin/python backend/manage.py test knowledgebase.tests.KnowledgebaseDocumentServiceTests.test_parse_document_writes_parser_provenance_to_version_record knowledgebase.tests.KnowledgebaseDocumentServiceTests.test_chunk_document_merges_parser_metadata_defaults knowledgebase.tests.KnowledgebaseDocumentServiceTests.test_ingest_document_marks_task_failed_when_parser_raises knowledgebase.tests.KnowledgebaseApiTests.test_document_upload_list_detail_and_ingest_flow -v 2
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd /root/finmodpro
git add backend/knowledgebase/services/document_service.py backend/knowledgebase/tests.py
git commit -m "Persist parser provenance through ingest and chunking" -m "The ingest flow now records parser-source metadata on document versions and carries parser defaults into chunk metadata so citation and debugging surfaces can distinguish structured parses from fallback output." -m "Constraint: Existing document and retrieval APIs must stay stable while parser internals change\nRejected: Add a new parser-results database table in phase one | unnecessary schema scope for a first ingestion upgrade\nConfidence: high\nScope-risk: moderate\nReversibility: clean\nDirective: Preserve `parsed_text` as the document-detail source of truth until element-level storage is explicitly introduced\nTested: Focused Django ingest and API compatibility tests\nNot-tested: End-to-end citation quality against real parser output"
```

## Task 4: Wire deployment configuration and documentation

**Files:**
- Modify: `backend/.env.example`
- Modify: `backend/docs/dependency-services.md`
- Modify: `docker-compose.prod.yml`

- [ ] **Step 1: Add environment examples**

```dotenv
# ------------------------------------------------------------------------------
# Unstructured parser service
# ------------------------------------------------------------------------------
UNSTRUCTURED_API_URL=http://unstructured-api:8000
UNSTRUCTURED_API_KEY=
UNSTRUCTURED_TIMEOUT_SECONDS=30
UNSTRUCTURED_PDF_STRATEGY=auto
UNSTRUCTURED_DOCX_STRATEGY=auto
UNSTRUCTURED_PDF_FALLBACK_ENABLED=true
```

- [ ] **Step 2: Add compose service and wire backend/celery**

```yaml
  backend:
    environment:
      UNSTRUCTURED_API_URL: ${UNSTRUCTURED_API_URL:-http://unstructured-api:8000}
      UNSTRUCTURED_API_KEY: ${UNSTRUCTURED_API_KEY:-}
      UNSTRUCTURED_TIMEOUT_SECONDS: ${UNSTRUCTURED_TIMEOUT_SECONDS:-30}
      UNSTRUCTURED_PDF_STRATEGY: ${UNSTRUCTURED_PDF_STRATEGY:-auto}
      UNSTRUCTURED_DOCX_STRATEGY: ${UNSTRUCTURED_DOCX_STRATEGY:-auto}
      UNSTRUCTURED_PDF_FALLBACK_ENABLED: ${UNSTRUCTURED_PDF_FALLBACK_ENABLED:-true}
    depends_on:
      unstructured-api:
        condition: service_started

  unstructured-api:
    image: downloads.unstructured.io/unstructured-io/unstructured-api:latest
    restart: unless-stopped
```

- [ ] **Step 3: Update dependency documentation**

```markdown
## 七、Unstructured Parser Service

- 角色：为 `pdf/docx` 提供第一阶段结构化解析能力
- 访问方式：backend / celery 通过 `UNSTRUCTURED_API_URL` 访问内部 HTTP 服务
- 回退策略：`pdf` 允许回退到 `pypdf`，`docx` 不做本地回退
- 范围限制：当前只替换解析层，不改变 chunk / embedding / retrieval 主链路
```

- [ ] **Step 4: Run deployment config verification**

Run:

```bash
cd /root/finmodpro
docker compose -f docker-compose.prod.yml config
```

Expected: PASS with a rendered `unstructured-api` service and the new parser environment variables present under `backend` and `celery-worker`.

- [ ] **Step 5: Commit**

```bash
cd /root/finmodpro
git add backend/.env.example backend/docs/dependency-services.md docker-compose.prod.yml
git commit -m "Document and wire the external parser service boundary" -m "Deployment now exposes the parser service as an explicit internal dependency and documents the environment needed to keep pdf/docx parsing outside the Django runtime." -m "Constraint: Phase one must keep parser infra internal and non-public\nRejected: Hide parser configuration entirely inside hard-coded defaults | makes deployment and fallback behavior opaque\nConfidence: medium\nScope-risk: narrow\nReversibility: clean\nDirective: Do not expose the parser service as a public ingress without revisiting auth and abuse controls\nTested: docker compose config\nNot-tested: Live container startup against the selected image"
```

## Task 5: Run regression verification and finish the branch

**Files:**
- Modify: `backend/knowledgebase/tests.py`
- Modify: `backend/knowledgebase/services/parser_service.py`
- Modify: `backend/knowledgebase/services/document_service.py`
- Modify: `backend/config/settings.py`
- Modify: `backend/.env.example`
- Modify: `backend/docs/dependency-services.md`
- Modify: `docker-compose.prod.yml`
- Create: `backend/knowledgebase/services/unstructured_client.py`

- [ ] **Step 1: Run parser and ingest regression suite**

Run:

```bash
cd /root/finmodpro
backend/.venv/bin/python backend/manage.py test knowledgebase.tests.KnowledgebaseDocumentServiceTests -v 2
```

Expected: PASS.

- [ ] **Step 2: Run broader knowledgebase and downstream compatibility tests**

Run:

```bash
cd /root/finmodpro
MILVUS_URI=milvus-lite-verify.db backend/.venv/bin/python backend/manage.py test knowledgebase chat rag -v 1
```

Expected: PASS. If sandbox blocks Milvus Lite socket creation, rerun in an escalated environment rather than weakening the regression set.

- [ ] **Step 3: Re-run deployment verification**

Run:

```bash
cd /root/finmodpro
docker compose -f docker-compose.prod.yml config
```

Expected: PASS.

- [ ] **Step 4: Commit the finished implementation**

```bash
cd /root/finmodpro
git add backend/config/settings.py backend/knowledgebase/services/parser_service.py backend/knowledgebase/services/unstructured_client.py backend/knowledgebase/services/document_service.py backend/knowledgebase/tests.py backend/.env.example backend/docs/dependency-services.md docker-compose.prod.yml
git commit -m "Make pdf/docx ingestion parser-aware without touching retrieval" -m "This phase replaces the parser edge of the knowledgebase pipeline while preserving the rest of the ingest and retrieval flow. Parser provenance now survives into document versions and chunk metadata, which makes fallback behavior visible without introducing new storage models." -m "Constraint: Existing API contracts and retrieval behavior must remain stable during the parser upgrade\nRejected: Couple parser rollout with new chunking semantics | mixes quality uplift with behavior change and expands rollback risk\nConfidence: medium\nScope-risk: moderate\nReversibility: clean\nDirective: Do not change citation structure as part of parser integration; richer metadata should remain additive\nTested: Focused parser tests, knowledgebase/chat/rag regression suite, docker compose config\nNot-tested: Real-world document quality across heterogeneous pdf/docx samples"
```

## Self-Review

- Spec coverage:
  - Parser adapter and `pdf/docx` routing are covered by Task 1 and Task 2.
  - Provenance persistence and chunk metadata enrichment are covered by Task 3.
  - Deployment boundary and configuration are covered by Task 4.
  - Regression verification is covered by Task 5.
- Placeholder scan:
  - No `TBD`, `TODO`, `FIXME`, or content-free “write tests” steps remain.
- Type consistency:
  - `parse_document_file()` is planned to return a dict with `parsed_text`, `document_metadata`, and `chunk_metadata_defaults` everywhere.
  - `parse_document()` and `chunk_document()` both consume the same parser-result shape.
