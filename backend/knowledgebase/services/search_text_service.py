def _normalize_text(value):
    return " ".join(str(value or "").strip().split())


def build_contextual_search_text(*, content, metadata=None):
    metadata = metadata or {}
    fields = (
        ("title", metadata.get("document_title")),
        ("doc_type", metadata.get("doc_type")),
        ("source_date", metadata.get("source_date")),
        ("dataset", metadata.get("dataset_name")),
        ("page", metadata.get("page_label")),
        ("section", metadata.get("section_label") or metadata.get("section_page_label")),
        ("section_path", metadata.get("section_path")),
    )
    lines = [f"{label}: {_normalize_text(value)}" for label, value in fields if _normalize_text(value)]
    body = _normalize_text(content)
    if body:
        lines.append(body)
    return "\n".join(lines)
