from llm.services.runtime_service import get_embedding_provider


def build_dense_embedding(text):
    provider = get_embedding_provider()
    return provider.embed(texts=[text])[0]


def build_dense_embeddings(texts):
    if not texts:
        return []
    provider = get_embedding_provider()
    return provider.embed(texts=texts)
