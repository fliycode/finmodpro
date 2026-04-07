class BaseChatProvider:
    def chat(self, *, messages, options=None):
        raise NotImplementedError

    def stream(self, *, messages, options=None):
        raise NotImplementedError


class BaseEmbeddingProvider:
    def embed(self, *, texts, options=None):
        raise NotImplementedError
