import logging
import shutil
from pathlib import Path

from django.conf import settings

from llama_index.core import StorageContext, VectorStoreIndex, load_index_from_storage
from llama_index.core.schema import TextNode

from knowledgebase.models import DocumentChunk
from rag.services.llamaindex_embedding_adapter import LiteLLMEmbeddingAdapter
from rag.services.vector_store_service import (
    _candidate_limit,
    _fallback_keyword_search,
    _matches_filters,
    _merge_ranked_results,
    _mysql_full_text_search,
    _normalize_queries,
    _serialize_chunk_result,
)

logger = logging.getLogger(__name__)


def should_sync_llamaindex_index():
    retrieval_backends = {
        str(getattr(settings, "RAG_RETRIEVAL_BACKEND", "") or "").strip().lower(),
        str(getattr(settings, "CHAT_RETRIEVAL_BACKEND", "") or "").strip().lower(),
    }
    return "llamaindex" in retrieval_backends


class LlamaIndexStoreService:
    def _storage_dir(self):
        storage_dir = Path(getattr(settings, "LLAMAINDEX_STORAGE_DIR"))
        storage_dir.mkdir(parents=True, exist_ok=True)
        return storage_dir

    def _has_persisted_index(self):
        storage_dir = self._storage_dir()
        return any(storage_dir.iterdir())

    def _build_embed_model(self):
        return LiteLLMEmbeddingAdapter()

    def _persist_index(self, index):
        index.storage_context.persist(persist_dir=str(self._storage_dir()))

    def _create_index(self):
        index = VectorStoreIndex(
            nodes=[],
            embed_model=self._build_embed_model(),
            show_progress=False,
        )
        index.set_index_id(settings.LLAMAINDEX_INDEX_ID)
        self._persist_index(index)
        return index

    def _load_index(self):
        if not self._has_persisted_index():
            return self._create_index()

        storage_context = StorageContext.from_defaults(
            persist_dir=str(self._storage_dir())
        )
        try:
            return load_index_from_storage(
                storage_context,
                index_id=settings.LLAMAINDEX_INDEX_ID,
                embed_model=self._build_embed_model(),
            )
        except Exception:
            logger.exception("failed to load llamaindex store; recreating empty index")
            return self._create_index()

    def _build_node_id(self, chunk_id):
        return f"chunk:{int(chunk_id)}"

    def _build_chunk_node(self, chunk):
        metadata = chunk.metadata or {}
        document = chunk.document
        return TextNode(
            id_=self._build_node_id(chunk.id),
            text=chunk.search_text or chunk.content,
            metadata={
                "document_id": document.id,
                "chunk_id": chunk.id,
                "document_title": metadata.get("document_title") or document.title,
                "doc_type": metadata.get("doc_type") or document.doc_type,
                "source_date": metadata.get("source_date")
                or (document.source_date.isoformat() if document.source_date else None),
                "page_label": metadata.get(
                    "page_label", f"chunk-{chunk.chunk_index + 1}"
                ),
                "chunk_index": chunk.chunk_index,
            },
        )

    def _delete_existing_nodes(self, index, node_ids):
        if not node_ids:
            return

        nodes_dict = getattr(getattr(index, "index_struct", None), "nodes_dict", None) or {}
        existing_node_ids = [node_id for node_id in node_ids if node_id in nodes_dict]
        if existing_node_ids:
            index.delete_nodes(existing_node_ids, delete_from_docstore=True)

    def sync_document(self, document):
        index = self._load_index()
        chunks = list(
            DocumentChunk.objects.select_related("document")
            .filter(document=document)
            .order_by("chunk_index")
        )
        node_ids = [self._build_node_id(chunk.id) for chunk in chunks]
        self._delete_existing_nodes(index, node_ids)
        if chunks:
            index.insert_nodes([self._build_chunk_node(chunk) for chunk in chunks])
        self._persist_index(index)

    def delete_document(self, *, document_id, chunk_ids=None):
        if not self._has_persisted_index():
            return

        resolved_chunk_ids = [int(chunk_id) for chunk_id in (chunk_ids or [])]
        if not resolved_chunk_ids:
            resolved_chunk_ids = list(
                DocumentChunk.objects.filter(document_id=document_id).values_list(
                    "id", flat=True
                )
            )
        if not resolved_chunk_ids:
            return

        index = self._load_index()
        self._delete_existing_nodes(
            index,
            [self._build_node_id(chunk_id) for chunk_id in resolved_chunk_ids],
        )
        self._persist_index(index)

    def clear(self):
        storage_dir = self._storage_dir()
        if storage_dir.exists():
            shutil.rmtree(storage_dir)

    def search(self, *, query, filters=None, top_k=5):
        if not self._has_persisted_index():
            return []

        index = self._load_index()
        retriever = index.as_retriever(similarity_top_k=max(int(top_k), 1))
        retrieved_nodes = retriever.retrieve(query)

        score_by_chunk_id = {}
        for result in retrieved_nodes:
            metadata = result.node.metadata or {}
            if not _matches_filters(metadata, filters or {}):
                continue
            chunk_id = metadata.get("chunk_id")
            if chunk_id in (None, ""):
                continue
            score_by_chunk_id[int(chunk_id)] = max(
                score_by_chunk_id.get(int(chunk_id), 0.0),
                float(result.score or 0.0),
            )

        if not score_by_chunk_id:
            return []

        chunks_by_id = {
            chunk.id: chunk
            for chunk in DocumentChunk.objects.select_related("document").filter(
                id__in=score_by_chunk_id.keys()
            )
        }
        results = []
        for chunk_id, score in score_by_chunk_id.items():
            chunk = chunks_by_id.get(chunk_id)
            if chunk is None:
                continue
            row = _serialize_chunk_result(chunk, score)
            row["score"] = score
            row["vector_score"] = score
            results.append(row)
        results.sort(
            key=lambda item: (
                item.get("score", 0.0),
                item.get("chunk_id") or 0,
            ),
            reverse=True,
        )
        return results[: int(top_k)]


def sync_document_index(document):
    return LlamaIndexStoreService().sync_document(document)


def delete_document_index(*, document_id, chunk_ids=None):
    return LlamaIndexStoreService().delete_document(
        document_id=document_id,
        chunk_ids=chunk_ids,
    )


def clear_llamaindex_store():
    return LlamaIndexStoreService().clear()


def query_llamaindex_store(
    query,
    filters=None,
    top_k=5,
    query_variants=None,
    allow_keyword_fallback=True,
):
    candidate_limit = _candidate_limit(top_k)
    queries = _normalize_queries(query, query_variants)
    ranked_lists = []

    for query_text in queries:
        vector_results = LlamaIndexStoreService().search(
            query=query_text,
            filters=filters,
            top_k=candidate_limit,
        )
        if vector_results:
            ranked_lists.append(("llamaindex_vector", query_text, vector_results))

        mysql_fulltext_results = _mysql_full_text_search(
            query_text,
            filters=filters,
            limit=candidate_limit,
        )
        if mysql_fulltext_results:
            ranked_lists.append(("mysql_fulltext", query_text, mysql_fulltext_results))

        should_run_keyword_fallback = allow_keyword_fallback and not (
            vector_results or mysql_fulltext_results
        )
        if should_run_keyword_fallback:
            fallback_keyword_results = _fallback_keyword_search(
                query_text,
                filters=filters,
                limit=candidate_limit,
            )
            if fallback_keyword_results:
                ranked_lists.append(("token_keyword", query_text, fallback_keyword_results))

    return _merge_ranked_results(ranked_lists)[: int(top_k)]
