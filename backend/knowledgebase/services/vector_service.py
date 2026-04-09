from django.conf import settings

from knowledgebase.models import DocumentChunk
from knowledgebase.services.embedding_service import build_dense_embedding


class VectorService:
    _client = None

    def _build_client_kwargs(self):
        kwargs = {"uri": settings.MILVUS_URI}
        if settings.MILVUS_TOKEN:
            kwargs["token"] = settings.MILVUS_TOKEN
        if settings.MILVUS_DB_NAME:
            kwargs["db_name"] = settings.MILVUS_DB_NAME
        return kwargs

    def _get_client(self):
        if self.__class__._client is None:
            from pymilvus import MilvusClient

            self.__class__._client = MilvusClient(**self._build_client_kwargs())
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

    def _build_rows(self, document):
        rows = []
        chunks_to_update = []
        queryset = DocumentChunk.objects.filter(document=document).order_by("chunk_index")
        for chunk in queryset:
            vector_id = int(chunk.id)
            vector = build_dense_embedding(chunk.content)
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

    def index(self, document):
        rows, chunks_to_update = self._build_rows(document)
        dimension = len(rows[0]["vector"]) if rows else settings.KB_EMBEDDING_DIMENSION
        client = self.ensure_collection(dimension=dimension)
        self._delete_existing_document_vectors(client, document)
        if rows:
            client.insert(settings.MILVUS_COLLECTION_NAME, rows)
            DocumentChunk.objects.bulk_update(chunks_to_update, ["vector_id"])
        from rag.services.vector_store_service import index_document

        index_document(document)

    def search(self, *, query, filters=None, top_k=5):
        client = self.ensure_collection()
        search_results = client.search(
            collection_name=settings.MILVUS_COLLECTION_NAME,
            data=[build_dense_embedding(query)],
            limit=int(top_k),
            filter=self._build_filter_expression(filters),
            output_fields=[
                "document_id",
                "chunk_id",
                "document_title",
                "doc_type",
                "source_date",
                "page_label",
                "content",
            ],
        )
        hits = search_results[0] if search_results else []
        return [
            {
                "document_id": hit.get("entity", {}).get("document_id"),
                "chunk_id": hit.get("entity", {}).get("chunk_id"),
                "document_title": hit.get("entity", {}).get("document_title"),
                "doc_type": hit.get("entity", {}).get("doc_type"),
                "source_date": hit.get("entity", {}).get("source_date"),
                "page_label": hit.get("entity", {}).get("page_label"),
                "snippet": hit.get("entity", {}).get("content", ""),
                "metadata": {
                    "document_id": hit.get("entity", {}).get("document_id"),
                    "document_title": hit.get("entity", {}).get("document_title"),
                    "doc_type": hit.get("entity", {}).get("doc_type"),
                    "source_date": hit.get("entity", {}).get("source_date"),
                    "page_label": hit.get("entity", {}).get("page_label"),
                },
                "score": hit.get("distance", 0.0),
                "vector_score": hit.get("distance", 0.0),
                "keyword_score": 0.0,
            }
            for hit in hits
        ]

    def clear(self):
        client = self._get_client()
        if client.has_collection(settings.MILVUS_COLLECTION_NAME):
            client.drop_collection(settings.MILVUS_COLLECTION_NAME)
        self.__class__._client = None


def index_document_chunks(document):
    return VectorService().index(document)
