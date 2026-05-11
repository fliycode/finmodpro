from django.db import DatabaseError, OperationalError, ProgrammingError

from knowledgebase.models import DocumentVersion
from knowledgebase.services.cleaning_quality_service import evaluate_quality_gate
from systemcheck.services.audit_service import record_audit_event

_MAX_AUDIT_DOCUMENT_IDS = 20
_MAX_AUDIT_KEY_COUNT = 20


def safe_record_audit_event(**kwargs):
    try:
        return record_audit_event(**kwargs)
    except (OperationalError, ProgrammingError, DatabaseError):
        return None


def build_dataset_audit_payload(*, dataset=None, name="", description="", owner=None):
    if dataset is not None:
        name = dataset.name
        description = dataset.description
        owner = getattr(dataset, "owner", None)

    payload = {
        "name": (name or "").strip(),
        "description_length": len((description or "").strip()),
    }
    if owner is not None:
        payload["owner_id"] = owner.id
    return payload


def build_document_audit_payload(
    *,
    document=None,
    title="",
    filename="",
    doc_type="",
    visibility="",
    dataset=None,
    source_date=None,
    file_size=None,
):
    if document is not None:
        dataset = getattr(document, "dataset", None)
        title = document.title
        filename = document.filename
        doc_type = document.doc_type
        visibility = document.visibility
        source_date = document.source_date
        file_size = document.file_size

    payload = {
        "title": (title or "").strip(),
        "filename": (filename or "").strip(),
        "doc_type": (doc_type or "").strip(),
        "visibility": (visibility or "").strip(),
    }
    if dataset is not None:
        payload["dataset_id"] = dataset.id
        payload["dataset_name"] = dataset.name
    if source_date:
        payload["source_date"] = (
            source_date.isoformat()
            if hasattr(source_date, "isoformat")
            else str(source_date)
        )
    if file_size not in (None, ""):
        payload["file_size"] = int(file_size)
    if document is not None:
        payload["status"] = document.status
        payload["owner_id"] = document.owner_id
        payload["uploader_id"] = document.uploaded_by_id
        version_record = _get_document_version_record(document)
        if version_record is not None:
            payload["root_document_id"] = version_record.root_document_id
            payload["version_number"] = version_record.version_number
    return payload


def build_document_version_audit_payload(
    *,
    root_document=None,
    new_document=None,
    title="",
    file_size=None,
    source_type="",
    source_label="",
    source_metadata=None,
    processing_notes="",
):
    payload = build_document_audit_payload(document=new_document or root_document, title=title, file_size=file_size)
    if root_document is not None:
        payload["root_document_id"] = root_document.id

    version_record = _get_document_version_record(new_document) if new_document is not None else None
    if version_record is not None:
        payload["version_number"] = version_record.version_number
        source_type = version_record.source_type
        source_label = version_record.source_label
        source_metadata = version_record.source_metadata
        processing_notes = version_record.processing_notes

    if source_type:
        payload["source_type"] = source_type
    if source_label:
        payload["source_label"] = source_label
    if isinstance(source_metadata, dict) and source_metadata:
        payload["source_metadata_keys"] = sorted(source_metadata.keys())[:_MAX_AUDIT_KEY_COUNT]
    if processing_notes:
        payload["processing_notes_present"] = True
    return payload


def build_cleaning_rule_audit_payload(
    *,
    rule=None,
    name="",
    rule_type="",
    enabled=True,
    priority=100,
    config=None,
):
    if rule is not None:
        name = rule.name
        rule_type = rule.rule_type
        enabled = rule.enabled
        priority = rule.priority
        config = rule.config

    payload = {
        "name": (name or "").strip(),
        "rule_type": (rule_type or "").strip(),
        "enabled": bool(enabled),
        "priority": int(priority),
    }
    if isinstance(config, dict) and config:
        payload["config_keys"] = sorted(str(key) for key in config.keys())[:_MAX_AUDIT_KEY_COUNT]
    return payload


def build_document_cleaning_audit_payload(*, document, result):
    quality_gate = evaluate_quality_gate(result.quality_score)
    payload = build_document_audit_payload(document=document)
    payload.update(
        {
            "rules_applied_count": len(result.rules_applied or []),
            "issues_found_count": len(result.issues_found or []),
            "quality_score": result.quality_score,
            "quality_gate_status": quality_gate["status"],
            "quality_gate_min_score": quality_gate["min_quality_score"],
            "quality_gate_warn_score": quality_gate["warn_quality_score"],
            "quality_gate_should_block": quality_gate["should_block"],
            "original_length": result.original_length,
            "cleaned_length": result.cleaned_length,
            "dedup_count": result.dedup_count,
        }
    )
    return payload


def build_document_batch_audit_payload(*, document_ids, result):
    payload = summarize_document_ids(document_ids)
    payload.update(
        {
            "accepted_count": int(result.get("accepted_count", 0)),
            "skipped_count": int(result.get("skipped_count", 0)),
            "failed_count": int(result.get("failed_count", 0)),
        }
    )
    return payload


def build_document_batch_delete_audit_payload(*, document_ids, result):
    payload = summarize_document_ids(document_ids)
    payload.update(
        {
            "deleted_count": int(result.get("deleted_count", 0)),
            "failed_count": int(result.get("failed_count", 0)),
        }
    )
    return payload


def summarize_document_ids(document_ids):
    normalized_ids = []
    for document_id in document_ids or []:
        if isinstance(document_id, bool):
            continue
        try:
            normalized_ids.append(int(document_id))
        except (TypeError, ValueError):
            continue

    payload = {
        "document_count": len(normalized_ids),
        "document_ids": normalized_ids[:_MAX_AUDIT_DOCUMENT_IDS],
    }
    overflow = len(normalized_ids) - len(payload["document_ids"])
    if overflow > 0:
        payload["document_id_overflow"] = overflow
    return payload


def _get_document_version_record(document):
    try:
        return document.version_record
    except DocumentVersion.DoesNotExist:
        return None
