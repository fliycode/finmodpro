import json
from pathlib import Path

from django.db import transaction

from knowledgebase.models import DocumentVersion
from knowledgebase.services.document_service import create_document_from_upload


def get_document_version_record(document):
    if document is None:
        return None

    try:
        return document.version_record
    except DocumentVersion.DoesNotExist:
        return None


def get_root_document(document):
    version_record = get_document_version_record(document)
    if version_record is None:
        return document
    return version_record.root_document


def ensure_initial_document_version(
    document,
    *,
    source_type="upload",
    source_label="",
    source_metadata=None,
    processing_notes="",
):
    version_record = get_document_version_record(document)
    if version_record is not None:
        return version_record

    return DocumentVersion.objects.create(
        root_document=document,
        document=document,
        version_number=1,
        is_current=True,
        source_type=(source_type or "upload").strip() or "upload",
        source_label=(source_label or document.title or document.filename).strip(),
        source_metadata=source_metadata or {},
        processing_notes=processing_notes or "",
    )


def serialize_document_version(version_record):
    return {
        "document_id": version_record.document_id,
        "version_number": version_record.version_number,
        "is_current": version_record.is_current,
        "source_type": version_record.source_type or "",
        "source_label": version_record.source_label or "",
        "source_metadata": version_record.source_metadata or {},
        "processing_notes": version_record.processing_notes or "",
        "created_at": version_record.created_at.isoformat(),
    }


def build_document_versions_response(document):
    root_document = get_root_document(document)
    version_records = list(
        DocumentVersion.objects.filter(root_document=root_document)
        .select_related("document")
        .order_by("-version_number", "-id")
    )
    current_version = next(
        (record.version_number for record in version_records if record.is_current),
        version_records[0].version_number if version_records else 1,
    )
    return {
        "document_id": root_document.id,
        "current_version": current_version,
        "versions": [serialize_document_version(record) for record in version_records],
    }


def parse_source_metadata(raw_value):
    if raw_value in (None, ""):
        return {}
    if isinstance(raw_value, dict):
        return raw_value

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError("source_metadata 必须是合法 JSON。") from exc

    if not isinstance(parsed, dict):
        raise ValueError("source_metadata 必须是 JSON 对象。")
    return parsed


@transaction.atomic
def create_new_document_version(
    *,
    document,
    uploaded_file,
    uploaded_by,
    title="",
    source_date="",
    source_type="upload",
    source_label="",
    source_metadata=None,
    processing_notes="",
):
    root_document = get_root_document(document)
    existing_versions = list(
        DocumentVersion.objects.select_for_update()
        .filter(root_document=root_document)
        .order_by("-version_number", "-id")
    )
    if not existing_versions:
        existing_versions = [ensure_initial_document_version(root_document)]

    next_version_number = existing_versions[0].version_number + 1
    DocumentVersion.objects.filter(root_document=root_document, is_current=True).update(
        is_current=False
    )

    new_document = create_document_from_upload(
        uploaded_file=uploaded_file,
        title=title or Path(uploaded_file.name).stem,
        source_date=source_date,
        uploaded_by=uploaded_by,
        owner=root_document.owner,
        visibility=root_document.visibility,
        dataset=root_document.dataset,
        skip_initial_version=True,
    )

    version_record = DocumentVersion.objects.create(
        root_document=root_document,
        document=new_document,
        version_number=next_version_number,
        is_current=True,
        source_type=(source_type or "upload").strip() or "upload",
        source_label=(source_label or new_document.title or new_document.filename).strip(),
        source_metadata=source_metadata or {},
        processing_notes=(processing_notes or "").strip(),
    )
    new_document.version_record = version_record
    return new_document
