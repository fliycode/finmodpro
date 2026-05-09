import logging
import os

from django.conf import settings

from knowledgebase.models import DocumentChunk, DocumentSectionChunk, IngestionTask
from knowledgebase.services.embedding_service import build_dense_embeddings

EMBEDDING_PROVIDER_BATCH_LIMIT = 10

logger = logging.getLogger(__name__)


class VectorService:
    _client = None

    def _load_milvus_client_class(self):
        milvus_uri = str(settings.MILVUS_URI or "")
        if not milvus_uri.endswith(".db"):
            from pymilvus import MilvusClient

            return MilvusClient

        original_env_uri = os.environ.pop("MILVUS_URI", None)
        try:
            from pymilvus import MilvusClient
        finally:
            if original_env_uri is not None:
                os.environ["MILVUS_URI"] = original_env_uri

        return MilvusClient

    def _build_client_kwargs(self):
        kwargs = {"uri": settings.MILVUS_URI}
        if settings.MILVUS_TOKEN:
            kwargs["token"] = settings.MILVUS_TOKEN
        if settings.MILVUS_DB_NAME:
            kwargs["db_name"] = settings.MILVUS_DB_NAME
        return kwargs

    def _get_client(self):
        if self.__class__._client is None:
            milvus_client_class = self._load_milvus_client_class()
            self.__class__._client = milvus_client_class(**self._build_client_kwargs())
        return self.__class__._client

    def _extract_collection_dimension(self, collection_schema):
        if not isinstance(collection_schema, dict):
            return None

        fields = collection_schema.get("fields") or []
        for field in fields:
            if not isinstance(field, dict):
                continue
            if field.get("name") != "vector":
                continue
            params = field.get("params") or {}
            dimension = field.get("dimension") or params.get("dim") or params.get("dimension")
            if dimension is None:
                return None
            return int(dimension)
        return None

    def ensure_collection(self, *, dimension=None):
        client = self._get_client()

        target_dimension = int(dimension or settings.KB_EMBEDDING_DIMENSION)
        if client.has_collection(settings.MILVUS_COLLECTION_NAME):
            existing_schema = client.describe_collection(settings.MILVUS_COLLECTION_NAME)
            existing_dimension = self._extract_collection_dimension(existing_schema)
            if existing_dimension == target_dimension:
                return client
            client.drop_collection(settings.MILVUS_COLLECTION_NAME)

        client.create_collection(
            collection_name=settings.MILVUS_COLLECTION_NAME,
            dimension=target_dimension,
            primary_field_name="id",
            id_type="int",
            vector_field_name="vector",
            metric_type="COSINE",
            auto_id=False,
            enable_dynamic_field=True,
        )
        return client

    def _build_filter_expression(self, filters=None):
        filters = filters or {}
        clauses = []
        document_id = filters.get("document_id")
        if document_id not in (None, ""):
            clauses.append(f"document_id == {int(document_id)}")

        doc_type = filters.get("doc_type")
        if doc_type:
            clauses.append(f'doc_type == "{doc_type}"')

        source_date_from = filters.get("source_date_from")
        if source_date_from:
            clauses.append(f'source_date >= "{source_date_from}"')

        source_date_to = filters.get("source_date_to")
        if source_date_to:
            clauses.append(f'source_date <= "{source_date_to}"')
        return " and ".join(clauses)

    def _delete_existing_document_vectors(self, client, document):
        try:
            client.delete(
                settings.MILVUS_COLLECTION_NAME,
                filter=f"document_id == {document.id}",
            )
        except Exception:
            return

    def _build_chunk_rows(self, document):
        rows = []
        chunks_to_update = []
        chunks = list(DocumentChunk.objects.filter(document=document).order_by("chunk_index"))
        batch_size = max(int(getattr(settings, "KB_EMBEDDING_BATCH_SIZE", 1) or 1), 1)
        batch_size = min(batch_size, EMBEDDING_PROVIDER_BATCH_LIMIT)

        for start in range(0, len(chunks), batch_size):
            chunk_batch = chunks[start:start + batch_size]
            vectors = build_dense_embeddings(
                [chunk.search_text or chunk.content for chunk in chunk_batch]
            )
            for chunk, vector in zip(chunk_batch, vectors):
                vector_id = int(chunk.id)
                rows.append(
                    {
                        "id": vector_id,
                        "vector": vector,
                        "document_id": document.id,
                        "chunk_id": chunk.id,
                        "document_title": document.title,
                        "doc_type": document.doc_type,
                        "source_date": document.source_date.isoformat()
                        if document.source_date
                        else "",
                        "chunk_index": chunk.chunk_index,
                        "page_label": chunk.metadata.get("page_label", ""),
                        "content": chunk.content,
                    }
                )
                chunk.vector_id = str(vector_id)
                chunks_to_update.append(chunk)
        return rows, chunks_to_update

    def _build_section_rows(self, document):
        rows = []
        sections_to_update = []
        sections = list(
            DocumentSectionChunk.objects.filter(document=document, is_indexed=False).order_by("section_index")
        )
        batch_size = max(int(getattr(settings, "KB_EMBEDDING_BATCH_SIZE", 1) or 1), 1)
        batch_size = min(batch_size, EMBEDDING_PROVIDER_BATCH_LIMIT)

        for start in range(0, len(sections), batch_size):
            section_batch = sections[start:start + batch_size]
            vectors = build_dense_embeddings(
                [section.search_text or section.content for section in section_batch]
            )
            for section, vector in zip(section_batch, vectors):
                vector_id = -int(section.id)
                rows.append(
                    {
                        "id": vector_id,
                        "vector": vector,
                        "document_id": document.id,
                        "section_chunk_id": section.id,
                        "document_title": document.title,
                        "doc_type": document.doc_type,
                        "source_date": document.source_date.isoformat()
                        if document.source_date
                        else "",
                        "chunk_index": section.section_index,
                        "page_label": section.metadata.get("page_label", ""),
                        "content": section.content,
                    }
                )
                section.vector_id = str(vector_id)
                section.is_indexed = True
                sections_to_update.append(section)
        return rows, sections_to_update

    def _get_latest_ingestion_task(self, document):
        return IngestionTask.objects.filter(document=document).order_by("-id").first()

    def index(self, document):
        use_hierarchical_sections = DocumentSectionChunk.objects.filter(document=document).exists()
        if use_hierarchical_sections:
            rows, sections_to_update = self._build_section_rows(document)
        else:
            rows, chunks_to_update = self._build_chunk_rows(document)
        dimension = len(rows[0]["vector"]) if rows else settings.KB_EMBEDDING_DIMENSION
        client = self.ensure_collection(dimension=dimension)
        if not use_hierarchical_sections:
            self._delete_existing_document_vectors(client, document)
        if rows:
            client.insert(settings.MILVUS_COLLECTION_NAME, rows)
            if use_hierarchical_sections:
                DocumentSectionChunk.objects.bulk_update(sections_to_update, ["vector_id", "is_indexed"])
                ingestion_task = self._get_latest_ingestion_task(document)
                if ingestion_task and ingestion_task.strategy == IngestionTask.STRATEGY_HIERARCHICAL:
                    total_section_count = DocumentSectionChunk.objects.filter(document=document).count()
                    ingestion_task.total_section_count = max(
                        ingestion_task.total_section_count,
                        total_section_count,
                    )
                    ingestion_task.indexed_section_count = DocumentSectionChunk.objects.filter(
                        document=document,
                        is_indexed=True,
                    ).count()
                    ingestion_task.save(update_fields=["total_section_count", "indexed_section_count", "updated_at"])
            else:
                DocumentChunk.objects.bulk_update(chunks_to_update, ["vector_id"])

    def delete_document(self, document_id):
        client = self._get_client()
        if not client.has_collection(settings.MILVUS_COLLECTION_NAME):
            return
        client.delete(
            settings.MILVUS_COLLECTION_NAME,
            filter=f"document_id == {int(document_id)}",
        )

    def clear(self):
        client = self._get_client()
        if client.has_collection(settings.MILVUS_COLLECTION_NAME):
            client.drop_collection(settings.MILVUS_COLLECTION_NAME)
        self.__class__._client = None


def index_document_chunks(document):
    return VectorService().index(document)
