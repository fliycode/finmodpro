"""
向量嵌入服务 —— 对应 SpringBoot 中的 @Service 组件，封装文本向量化调用。

将文本转换为稠密向量（dense embedding），用于语义搜索和向量检索。
底层通过 LiteLLM 统一网关调用 DashScope 等嵌入模型。

SpringBoot 类比：
- Django get_embedding_provider()     →  SpringBoot @Autowired EmbeddingClient / @Bean
- Django build_dense_embedding()      →  SpringBoot @Service 的 embed() 方法
- Django LLM runtime_service         →  SpringBoot 的 AI/LLM 集成层
"""

from llm.services.runtime_service import get_embedding_provider


def build_dense_embedding(text):
    """
    将单条文本转换为稠密向量（dense embedding）。

    类似 SpringBoot 中调用向量化客户端 API 的 service 方法。

    参数：
        text (str): 待向量化的文本。

    返回：
        list[float]: 文本对应的稠密向量（浮点数列表）。
    """
    provider = get_embedding_provider()
    return provider.embed(texts=[text]).vectors[0]


def build_dense_embeddings(texts):
    """
    批量将多条文本转换为稠密向量，用于批量向量化场景（性能优于逐条调用）。

    类似 SpringBoot 中调用向量化 API 的 batch 接口。

    参数：
        texts (list[str]): 待向量化的文本列表。

    返回：
        list[list[float]]: 每条文本对应的稠密向量列表。若 texts 为空则返回空列表。
    """
    if not texts:
        return []
    provider = get_embedding_provider()
    return provider.embed(texts=texts).vectors
