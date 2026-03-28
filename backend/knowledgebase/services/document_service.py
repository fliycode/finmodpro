from datetime import date
from pathlib import Path

from knowledgebase.models import Document, DocumentChunk
from knowledgebase.services.chunk_service import build_document_chunks
from knowledgebase.services.parser_service import parse_document_file
from rag.services.vector_store_service import index_document


def _detect_doc_type(filename):
    extension = Path(filename).suffix.lower().lstrip(".")
    return extension or "unknown"


def _parse_source_date(raw_value):
    if not raw_value:
        return None
    try:
        return date.fromisoformat(raw_value)
    except ValueError as exc:
        raise ValueError("source_date 必须是 YYYY-MM-DD 格式。") from exc


def serialize_document(document, include_content_preview=False):
    payload = {
        "id": document.id,
        "title": document.title,
        "filename": document.filename,
        "doc_type": document.doc_type,
        "status": document.status,
        "source_date": document.source_date.isoformat() if document.source_date else None,
        "file_path": document.file.name,
        "chunk_count": document.chunks.count(),
        "error_message": document.error_message or None,
        "created_at": document.created_at.isoformat(),
        "updated_at": document.updated_at.isoformat(),
    }
    if include_content_preview:
        payload["parsed_text_preview"] = document.parsed_text[:200]
    return payload


def build_document_response(document, *, include_content_preview=False, message=None):
    payload = {
        "document": serialize_document(
            document,
            include_content_preview=include_content_preview,
        )
    }
    if message is not None:
        payload["message"] = message
    return payload


def build_document_list_response():
    documents = list_documents()
    return {
        "documents": documents,
        "total": len(documents),
    }


def create_document_from_upload(*, uploaded_file, title, source_date):
    filename = uploaded_file.name
    doc_type = _detect_doc_type(filename)
    if doc_type not in {"txt", "pdf", "docx"}:
        raise ValueError("当前仅支持 txt/pdf/docx 文件上传。")

    document = Document.objects.create(
        title=title or Path(filename).stem,
        file=uploaded_file,
        filename=filename,
        doc_type=doc_type,
        source_date=_parse_source_date(source_date),
    )
    return document


def list_documents():
    return [serialize_document(document) for document in Document.objects.all()]


def _update_document_status(document, *, status, error_message=None):
    document.status = status
    update_fields = ["status", "updated_at"]
    if error_message is not None:
        document.error_message = error_message
        update_fields.append("error_message")
    document.save(update_fields=update_fields)


def ingest_document(document):
    try:
        parsed_text = parse_document_file(document)
        document.parsed_text = parsed_text
        document.error_message = ""
        document.save(
            update_fields=["parsed_text", "error_message", "updated_at"]
        )
        _update_document_status(document, status=Document.STATUS_PARSED)

        DocumentChunk.objects.filter(document=document).delete()
        chunks = build_document_chunks(
            parsed_text,
            metadata_builder=lambda index: {
                "document_id": document.id,
                "document_title": document.title,
                "doc_type": document.doc_type,
                "source_date": (
                    document.source_date.isoformat() if document.source_date else None
                ),
                "chunk_index": index,
                "page_label": f"chunk-{index + 1}",
            },
        )
        DocumentChunk.objects.bulk_create(
            [
                DocumentChunk(
                    document=document,
                    chunk_index=chunk["chunk_index"],
                    content=chunk["content"],
                    metadata=chunk["metadata"],
                )
                for chunk in chunks
            ]
        )
        _update_document_status(document, status=Document.STATUS_CHUNKED)

        index_document(document)
        _update_document_status(document, status=Document.STATUS_INDEXED)
        return document
    except ValueError as exc:
        DocumentChunk.objects.filter(document=document).delete()
        _update_document_status(
            document,
            status=Document.STATUS_FAILED,
            error_message=str(exc),
        )
        raise
