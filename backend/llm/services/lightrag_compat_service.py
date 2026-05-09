from collections import Counter

from django.db.models import Q

from knowledgebase.models import Document, DocumentChunk, IngestionTask
from knowledgebase.services.document_service import (
    batch_delete_documents,
    batch_enqueue_document_ingestion,
    build_document_list_response,
    build_stats_response,
    create_document_from_upload,
    enqueue_document_ingestion,
    get_visible_documents_queryset,
)
from rag.services.retrieval_backend_service import retrieve_rag_context


def _current_documents_queryset(user):
    return get_visible_documents_queryset(user).filter(
        Q(version_record__is_current=True) | Q(version_record__isnull=True)
    )


def _safe_int(value, default):
    try:
        return max(int(value), 1)
    except (TypeError, ValueError):
        return default


def _serialize_lightrag_document(item):
    latest_ingestion_task = item.get("latest_ingestion_task") or {}
    return {
        "id": str(item["id"]),
        "doc_id": str(item["id"]),
        "title": item.get("title") or item.get("filename") or f"Document {item['id']}",
        "file_name": item.get("filename") or "",
        "status": item.get("status") or "unknown",
        "track_id": str(latest_ingestion_task.get("id") or ""),
        "summary": item.get("process_result") or item.get("error_message") or "",
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
    }


def _status_counts(user):
    documents = _current_documents_queryset(user)
    counts = Counter(document.status for document in documents)
    counts["all"] = documents.count()
    return dict(counts)


def _label_catalog(user):
    label_counter = Counter()
    for document in _current_documents_queryset(user).select_related("dataset"):
        if document.title:
            label_counter[document.title] += 1
        if document.dataset and document.dataset.name:
            label_counter[document.dataset.name] += 1
        if document.filename:
            label_counter[document.filename] += 1
    return label_counter


def _build_graph_payload(user, label, *, max_nodes=120):
    normalized_label = str(label or "").strip()
    if not normalized_label:
        return {"nodes": [], "edges": [], "is_truncated": False}

    retrieval_limit = max(3, min(max_nodes // 3, 24))
    retrieval_results = retrieve_rag_context(
        query=normalized_label,
        filters={},
        top_k=retrieval_limit,
    )

    if not retrieval_results:
        exact_match_documents = list(
            _current_documents_queryset(user)
            .filter(Q(title__icontains=normalized_label) | Q(filename__icontains=normalized_label))[:6]
        )
        if exact_match_documents:
            chunk_ids = list(
                DocumentChunk.objects.filter(document_id__in=[doc.id for doc in exact_match_documents])
                .order_by("id")
                .values_list("id", flat=True)[:retrieval_limit]
            )
            retrieval_results = [
                {
                    "document_id": chunk.document_id,
                    "chunk_id": chunk.id,
                    "document_title": chunk.document.title,
                    "page_label": (chunk.metadata or {}).get("page_label", f"chunk-{chunk.chunk_index + 1}"),
                    "snippet": chunk.content,
                    "metadata": chunk.metadata or {},
                }
                for chunk in DocumentChunk.objects.select_related("document").filter(id__in=chunk_ids)
            ]

    document_ids = [item.get("document_id") for item in retrieval_results if item.get("document_id")]
    chunk_ids = [item.get("chunk_id") for item in retrieval_results if item.get("chunk_id")]
    documents = {
        document.id: document
        for document in _current_documents_queryset(user)
        .select_related("dataset", "owner", "uploaded_by")
        .filter(id__in=document_ids)
    }
    chunks = {
        chunk.id: chunk
        for chunk in DocumentChunk.objects.select_related("document").filter(id__in=chunk_ids)
    }

    nodes = []
    edges = []
    seen_nodes = set()
    seen_edges = set()
    is_truncated = False

    def add_node(node_id, *, label, node_type, description="", properties=None):
        nonlocal is_truncated
        if node_id in seen_nodes:
            return
        if len(nodes) >= max_nodes:
            is_truncated = True
            return
        seen_nodes.add(node_id)
        nodes.append(
            {
                "id": node_id,
                "label": label,
                "entity_type": node_type,
                "description": description,
                "properties": properties or {},
            }
        )

    def add_edge(source, target, relation, *, description="", properties=None):
        key = (source, target, relation)
        if key in seen_edges:
            return
        seen_edges.add(key)
        edges.append(
            {
                "id": f"{source}->{target}:{relation}",
                "source": source,
                "target": target,
                "label": relation,
                "description": description,
                "properties": properties or {},
            }
        )

    label_node_id = f"label:{normalized_label}"
    add_node(
        label_node_id,
        label=normalized_label,
        node_type="topic",
        description="LlamaIndex compatibility graph topic",
    )

    for result in retrieval_results:
        document = documents.get(result.get("document_id"))
        if document is None:
            continue

        doc_node_id = f"document:{document.id}"
        add_node(
            doc_node_id,
            label=document.title or document.filename or f"Document {document.id}",
            node_type="document",
            description=(result.get("snippet") or "")[:240],
            properties={
                "file_path": document.filename,
                "doc_type": document.doc_type,
                "status": document.status,
                "source_id": document.id,
                "created_at": int(document.created_at.timestamp()) if document.created_at else None,
            },
        )
        add_edge(
            label_node_id,
            doc_node_id,
            "命中",
            description="Retrieved by compatibility graph query.",
        )

        if document.dataset and document.dataset.name:
            dataset_node_id = f"dataset:{document.dataset_id}"
            add_node(
                dataset_node_id,
                label=document.dataset.name,
                node_type="dataset",
                description="Knowledgebase dataset",
            )
            add_edge(doc_node_id, dataset_node_id, "属于数据集")

        owner = document.owner or document.uploaded_by
        if owner is not None:
            owner_node_id = f"user:{owner.id}"
            add_node(
                owner_node_id,
                label=owner.username or owner.email or f"user-{owner.id}",
                node_type="owner",
                description=owner.email or "",
            )
            add_edge(doc_node_id, owner_node_id, "责任人")

        chunk = chunks.get(result.get("chunk_id"))
        if chunk is None:
            continue

        chunk_label = result.get("page_label") or (chunk.metadata or {}).get(
            "page_label",
            f"chunk-{chunk.chunk_index + 1}",
        )
        chunk_node_id = f"chunk:{chunk.id}"
        add_node(
            chunk_node_id,
            label=chunk_label,
            node_type="chunk",
            description=chunk.content[:240],
            properties={
                "file_path": document.filename,
                "source_id": chunk.id,
                "keywords": (chunk.metadata or {}).get("keywords", ""),
                "created_at": int(chunk.created_at.timestamp()) if chunk.created_at else None,
            },
        )
        add_edge(
            doc_node_id,
            chunk_node_id,
            "包含片段",
            description="Chunk retrieved from the selected document.",
        )

    return {"nodes": nodes, "edges": edges, "is_truncated": is_truncated}


def build_lightrag_compat_overview(user):
    stats = build_stats_response(user)
    popular_labels = [label for label, _ in _label_catalog(user).most_common(8)]
    return {
        "health": {"status": "healthy", "backend": "llamaindex"},
        "auth_status": {"auth_mode": "delegated", "provider": "django"},
        "status_counts": {"status_counts": _status_counts(user)},
        "popular_labels": popular_labels,
        "configuration": {
            "sync_enabled": True,
            "graph_storage": "LlamaIndexCompat",
            "neo4j_configured": False,
            "indexed_documents": stats["indexed_count"],
            "total_documents": stats["total_documents"],
        },
    }


def _paginated_documents(user, payload):
    response = build_document_list_response(
        user,
        status=payload.get("status_filter") or "all",
        page=payload.get("page") or 1,
        page_size=payload.get("page_size") or 12,
    )
    documents = [_serialize_lightrag_document(item) for item in response["documents"]]
    sort_field = str(payload.get("sort_field") or "updated_at")
    sort_direction = str(payload.get("sort_direction") or "desc").lower()
    reverse = sort_direction != "asc"
    sort_key_map = {
        "title": lambda item: item.get("title") or "",
        "status": lambda item: item.get("status") or "",
        "updated_at": lambda item: item.get("updated_at") or "",
    }
    documents.sort(key=sort_key_map.get(sort_field, sort_key_map["updated_at"]), reverse=reverse)
    return {
        "documents": documents,
        "pagination": {
            "current_page": response["page"],
            "page_size": response["page_size"],
            "total_count": response["total"],
            "total_pages": response["total_pages"],
        },
        "status_counts": _status_counts(user),
    }


def _upload_document(user, request_files, request_data):
    uploaded_file = request_files.get("file")
    if uploaded_file is None:
        raise ValueError("file 为必填项。")

    document = create_document_from_upload(
        uploaded_file=uploaded_file,
        title=(request_data.get("title") or "").strip(),
        source_date=(request_data.get("source_date") or "").strip(),
        uploaded_by=user,
        owner_id=request_data.get("owner_id"),
        visibility=request_data.get("visibility"),
        dataset_id=request_data.get("dataset_id"),
    )
    ingestion_task, _ = enqueue_document_ingestion(document)
    return {
        "status": "success",
        "message": "Uploaded",
        "doc_id": str(document.id),
        "track_id": str(ingestion_task.id),
    }


def _track_status(track_id):
    task = (
        IngestionTask.objects.select_related("document")
        .filter(Q(id=track_id) | Q(graph_track_id=str(track_id)))
        .order_by("-id")
        .first()
    )
    if task is None:
        return {"status": "missing", "message": "Track not found."}
    return {
        "status": task.status,
        "track_id": str(task.id),
        "doc_id": str(task.document_id),
        "current_step": task.current_step,
        "error_message": task.error_message or task.graph_sync_error_message or "",
    }


def _query(payload):
    query = str(payload.get("query") or "").strip()
    if not query:
        raise ValueError("query 为必填项。")

    try:
        top_k = max(int(payload.get("chunk_top_k") or payload.get("top_k") or 5), 1)
    except (TypeError, ValueError):
        top_k = 5
    filters = payload.get("filters") or {}
    results = retrieve_rag_context(query=query, filters=filters, top_k=top_k)
    references = [
        {
            "doc_id": str(item.get("document_id") or ""),
            "title": item.get("document_title") or "",
            "content": item.get("snippet") or "",
            "chunk_content": item.get("snippet") or "",
        }
        for item in results
    ]
    response_text = "\n\n".join(ref["content"] for ref in references[:3]).strip()
    if not response_text:
        response_text = "No relevant context found for the query."

    return {
        "response": response_text,
        "references": references,
    }


def _delete_documents(user, payload):
    doc_ids = payload.get("doc_ids") or []
    result = batch_delete_documents(user, doc_ids)
    return {
        "status": "success",
        "deleted_count": result["deleted_count"],
        "failed_count": result["failed_count"],
        "results": result["results"],
    }


def _reprocess_failed(user):
    failed_ids = list(
        get_visible_documents_queryset(user)
        .filter(status=Document.STATUS_FAILED)
        .values_list("id", flat=True)
    )
    return batch_enqueue_document_ingestion(user, failed_ids)


def handle_lightrag_compat_request(
    *,
    user,
    method,
    upstream_path,
    query_params=None,
    json_payload=None,
    request_data=None,
    request_files=None,
):
    normalized_method = str(method or "").upper()
    normalized_path = str(upstream_path or "").strip().strip("/")
    query_params = query_params or {}

    if normalized_method == "GET" and normalized_path == "health":
        return {"status": "healthy", "backend": "llamaindex"}
    if normalized_method == "GET" and normalized_path == "auth-status":
        return {"auth_mode": "delegated", "provider": "django"}
    if normalized_method == "GET" and normalized_path == "documents/status_counts":
        return {"status_counts": _status_counts(user)}
    if normalized_method == "POST" and normalized_path == "documents/paginated":
        return _paginated_documents(user, json_payload or {})
    if normalized_method == "POST" and normalized_path == "documents/upload":
        return _upload_document(user, request_files or {}, request_data or {})
    if normalized_method == "GET" and normalized_path.startswith("documents/track_status/"):
        return _track_status(normalized_path.rsplit("/", 1)[-1])
    if normalized_method == "POST" and normalized_path == "documents/scan":
        return {"status": "success", "message": "Scan skipped in llamaindex compatibility mode."}
    if normalized_method == "POST" and normalized_path == "documents/reprocess_failed":
        return _reprocess_failed(user)
    if normalized_method == "POST" and normalized_path == "documents/cancel_pipeline":
        return {"status": "success", "message": "Cancel is not supported in llamaindex compatibility mode."}
    if normalized_method == "POST" and normalized_path == "documents/clear_cache":
        return {"status": "success", "message": "Cache cleared."}
    if normalized_method == "DELETE" and normalized_path == "documents/delete_document":
        return _delete_documents(user, json_payload or {})
    if normalized_method == "POST" and normalized_path == "query":
        return _query(json_payload or {})
    if normalized_method == "GET" and normalized_path == "graph/label/popular":
        limit = _safe_int(query_params.get("limit"), 8)
        return [label for label, _ in _label_catalog(user).most_common(limit)]
    if normalized_method == "GET" and normalized_path == "graph/label/list":
        return [label for label, _ in _label_catalog(user).most_common()]
    if normalized_method == "GET" and normalized_path == "graph/label/search":
        query = str(query_params.get("q") or "").strip().lower()
        limit = _safe_int(query_params.get("limit"), 10)
        labels = [label for label, _ in _label_catalog(user).most_common()]
        if not query:
            return labels[:limit]
        return [label for label in labels if query in label.lower()][:limit]
    if normalized_method == "GET" and normalized_path == "graphs":
        return _build_graph_payload(
            user,
            query_params.get("label"),
            max_nodes=_safe_int(query_params.get("max_nodes"), 120),
        )

    raise ValueError("不支持的 LlamaIndex 兼容路径。")
