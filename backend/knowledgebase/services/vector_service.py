from rag.services.vector_store_service import index_document


class VectorService:
    def index(self, document):
        index_document(document)


def index_document_chunks(document):
    return VectorService().index(document)
