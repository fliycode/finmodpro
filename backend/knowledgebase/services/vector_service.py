import os

from django.conf import settings

from knowledgebase.models import DocumentChunk
from knowledgebase.services.embedding_service import build_dense_embedding, build_dense_embeddings


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

    def _build_rows(self, document):
        rows = []
        chunks_to_update = []
        chunks = list(DocumentChunk.objects.filter(document=document).order_by("chunk_index"))
        batch_size = max(int(getattr(settings, "KB_EMBEDDING_BATCH_SIZE", 1) or 1), 1)

        for start in range(0, len(chunks), batch_size):
            chunk_batch = chunks[start:start + batch_size]
            vectors = build_dense_embeddings([chunk.content for chunk in chunk_batch])
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
        query_vector = build_dense_embedding(query)
        client = self.ensure_collection(
            dimension=len(query_vector) if query_vector else settings.KB_EMBEDDING_DIMENSION
        )
        search_results = client.search(
            collection_name=settings.MILVUS_COLLECTION_NAME,
            data=[query_vector],
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
        chunk_ids = [
            hit.get("entity", {}).get("chunk_id")
            for hit in hits
            if hit.get("entity", {}).get("chunk_id") is not None
        ]
        chunks_by_id = {
            chunk.id: chunk
            for chunk in DocumentChunk.objects.select_related("document").filter(id__in=chunk_ids)
        }
        results = []
        for hit in hits:
            entity = hit.get("entity", {})
            chunk_id = entity.get("chunk_id")
            chunk = chunks_by_id.get(chunk_id)
            if chunk is None:
                continue

            metadata = chunk.metadata or {}
            results.append(
                {
                    "document_id": chunk.document_id,
                    "chunk_id": chunk.id,
                    "document_title": metadata.get("document_title") or chunk.document.title,
                    "doc_type": metadata.get("doc_type") or chunk.document.doc_type,
                    "source_date": metadata.get("source_date")
                    or (chunk.document.source_date.isoformat() if chunk.document.source_date else None),
                    "page_label": metadata.get("page_label", f"chunk-{chunk.chunk_index + 1}"),
                    "snippet": chunk.content,
                    "metadata": metadata,
                    "score": hit.get("distance", 0.0),
                    "vector_score": hit.get("distance", 0.0),
                    "keyword_score": 0.0,
                }
            )
        return results

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
