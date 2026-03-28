from django.conf import settings

from knowledgebase.models import DocumentChunk
from knowledgebase.services.embedding_service import build_dense_embedding
from rag.services.vector_store_service import index_document


class VectorService:
    _client = None

    def _get_client(self):
        if self.__class__._client is None:
            from pymilvus import MilvusClient

            self.__class__._client = MilvusClient(uri=settings.MILVUS_URI)
        return self.__class__._client

    def ensure_collection(self):
        client = self._get_client()
        if client.has_collection(settings.MILVUS_COLLECTION_NAME):
            return client

        client.create_collection(
            collection_name=settings.MILVUS_COLLECTION_NAME,
            dimension=settings.KB_EMBEDDING_DIMENSION,
            primary_field_name="id",
            id_type="int",
            vector_field_name="vector",
            metric_type="COSINE",
            auto_id=False,
            enable_dynamic_field=True,
        )
        return client

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
            rows.append(
                {
                    "id": vector_id,
                    "vector": build_dense_embedding(chunk.content),
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
        if chunks_to_update:
            DocumentChunk.objects.bulk_update(chunks_to_update, ["vector_id"])
        return rows

    def index(self, document):
        client = self.ensure_collection()
        self._delete_existing_document_vectors(client, document)
        rows = self._build_rows(document)
        if rows:
            client.insert(settings.MILVUS_COLLECTION_NAME, rows)
        index_document(document)

    def clear(self):
        client = self._get_client()
        if client.has_collection(settings.MILVUS_COLLECTION_NAME):
            client.drop_collection(settings.MILVUS_COLLECTION_NAME)
        self.__class__._client = None


def index_document_chunks(document):
    return VectorService().index(document)
