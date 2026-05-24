"""
向量存储服务 —— 对应 SpringBoot 中的 @Service 组件，管理 Milvus 向量数据库的连接和操作。

核心职责（类似于 SpringBoot 中管理 Milvus 客户端的 @Service Bean）：
- 向量集合（Collection）的生命周期：创建、确保存在、清空
- 文档分块的向量索引：批量生成 embedding 并写入 Milvus
- 层级分块的段落索引：对 DocumentSectionChunk 进行增量向量化
- 过滤表达式构建：支持按 document_id、doc_type、source_date 等字段过滤
- 混合搜索支持：可选启用 BM25 稀疏向量 + 稠密向量混合索引

SpringBoot 类比：
- Django VectorService                  →  SpringBoot @Service 单例 Bean
- Django MilvusClient                   →  SpringBoot @Bean MilvusClient
- Django settings.MILVUS_URI            →  SpringBoot @Value("${milvus.uri}")
- Django settings.MILVUS_COLLECTION_NAME →  SpringBoot @Value("${milvus.collection}")
- Django ensure_collection()            →  SpringBoot @PostConstruct 初始化检查
- Django bulk_create + bulk_update      →  SpringBoot JPA saveAll() 批量操作
"""

import logging
import os

from django.conf import settings

from knowledgebase.models import DocumentChunk, DocumentSectionChunk, IngestionTask
from knowledgebase.services.embedding_service import build_dense_embeddings

# 嵌入模型每次请求的最大文本数（API 限流控制）
EMBEDDING_PROVIDER_BATCH_LIMIT = 10

logger = logging.getLogger(__name__)


class VectorService:
    """
    向量存储服务类。

    提供 Milvus 向量数据库的连接管理、集合创建、数据插入和删除功能。
    类级 _client 缓存实现类似 SpringBoot 单例 Bean 的连接复用。
    """

    # 类级别的 Milvus 客户端缓存（类似 SpringBoot 单例 Bean）
    _client = None

    def _load_milvus_client_class(self):
        """
        加载 pymilvus 的 MilvusClient 类。

        对于本地 .db 文件模式，临时清理环境变量以避免 pymilvus 误判为远程模式。

        返回：
            type: MilvusClient 类。
        """
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
        """
        构建 MilvusClient 的初始化参数。

        返回：
            dict: 包含 uri, token（可选）, db_name（可选）的参数字典。
        """
        kwargs = {"uri": settings.MILVUS_URI}
        if settings.MILVUS_TOKEN:
            kwargs["token"] = settings.MILVUS_TOKEN
        if settings.MILVUS_DB_NAME:
            kwargs["db_name"] = settings.MILVUS_DB_NAME
        return kwargs

    def _get_client(self):
        """
        获取或懒初始化 MilvusClient 实例（类似 SpringBoot 懒加载单例 Bean）。

        返回：
            MilvusClient: Milvus 客户端实例。
        """
        if self.__class__._client is None:
            milvus_client_class = self._load_milvus_client_class()
            self.__class__._client = milvus_client_class(**self._build_client_kwargs())
        return self.__class__._client

    def _extract_collection_dimension(self, collection_schema):
        """
        从集合描述信息中提取向量维度。

        参数：
            collection_schema (dict): Milvus 的集合描述 schema。

        返回：
            int | None: 向量维度，若无法提取则返回 None。
        """
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

    def _has_sparse_field(self, collection_schema):
        """
        检查集合 schema 是否包含稀疏向量字段（用于混合搜索）。

        参数：
            collection_schema (dict): Milvus 集合 schema。

        返回：
            bool: 是否包含 sparse_vector 字段。
        """
        if not isinstance(collection_schema, dict):
            return False
        fields = collection_schema.get("fields") or []
        return any(
            isinstance(f, dict) and f.get("name") == "sparse_vector"
            for f in fields
        )

    def ensure_collection(self, *, dimension=None):
        """
        确保 Milvus 向量集合存在且 schema 匹配。

        当集合不存在时创建新集合；当维度不匹配或缺少必要的稀疏向量字段时，
        重建集合（类似 SpringBoot 中检查并自动创建数据库表/索引的机制）。

        支持两种模式：
        - 混合搜索模式（RAG_HYBRID_SEARCH_ENABLED=True）：创建带 BM25 稀疏向量的集合
        - 纯稠密向量模式：创建简单向量集合

        参数：
            dimension (int, optional): 向量维度，默认从 settings.KB_EMBEDDING_DIMENSION 读取。

        返回：
            MilvusClient: 就绪的 Milvus 客户端实例。
        """
        client = self._get_client()
        use_hybrid = getattr(settings, "RAG_HYBRID_SEARCH_ENABLED", False)

        target_dimension = int(dimension or settings.KB_EMBEDDING_DIMENSION)
        if client.has_collection(settings.MILVUS_COLLECTION_NAME):
            existing_schema = client.describe_collection(settings.MILVUS_COLLECTION_NAME)
            existing_dimension = self._extract_collection_dimension(existing_schema)
            has_sparse = self._has_sparse_field(existing_schema)
            if existing_dimension == target_dimension and (has_sparse or not use_hybrid):
                return client
            client.drop_collection(settings.MILVUS_COLLECTION_NAME)

        if use_hybrid:
            from pymilvus import CollectionSchema, DataType, Function, FunctionType

            schema = CollectionSchema(enable_dynamic_field=True)
            schema.add_field("id", DataType.INT64, is_primary=True, auto_id=False)
            schema.add_field("vector", DataType.FLOAT_VECTOR, dim=target_dimension)
            schema.add_field("sparse_vector", DataType.SPARSE_FLOAT_VECTOR)
            schema.add_field("content_text", DataType.VARCHAR, max_length=65535, analyzer_params={"type": "chinese"})
            schema.add_field("document_id", DataType.INT64)
            schema.add_field("chunk_id", DataType.INT64)
            schema.add_field("document_title", DataType.VARCHAR, max_length=512)
            schema.add_field("doc_type", DataType.VARCHAR, max_length=64)
            schema.add_field("source_date", DataType.VARCHAR, max_length=32)
            schema.add_field("page_label", DataType.VARCHAR, max_length=256)
            schema.add_field("chunk_index", DataType.INT64)
            schema.add_field("content", DataType.VARCHAR, max_length=65535)

            bm25_function = Function(
                name="bm25",
                function_type=FunctionType.BM25,
                input_field_names=["content_text"],
                output_field_names=["sparse_vector"],
            )
            schema.add_function(bm25_function)

            index_params = client.prepare_index_params()
            index_params.add_index(field_name="vector", index_type="AUTOINDEX", metric_type="COSINE")
            index_params.add_index(field_name="sparse_vector", index_type="AUTOINDEX", metric_type="BM25")

            client.create_collection(
                collection_name=settings.MILVUS_COLLECTION_NAME,
                schema=schema,
                index_params=index_params,
            )
        else:
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
        """
        构建 Milvus 标量过滤表达式（类似 SQL WHERE 子句或 JPA Specification）。

        支持的过滤条件：
        - document_id: 精确匹配文档ID
        - doc_type: 精确匹配文档类型
        - source_date_from: 来源日期起始（>=）
        - source_date_to: 来源日期截止（<=）

        参数：
            filters (dict, optional): 过滤条件字典。

        返回：
            str: Milvus 过滤表达式字符串（各条件 and 连接），无过滤条件时返回空字符串。
        """
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
        """
        删除指定文档在 Milvus 中的所有已有向量数据。

        用于重新索引场景：先清除旧数据，再插入新数据（类似 truncate + insert）。

        参数：
            client (MilvusClient): Milvus 客户端实例。
            document (Document): 文档模型实例。
        """
        try:
            client.delete(
                settings.MILVUS_COLLECTION_NAME,
                filter=f"document_id == {document.id}",
            )
        except Exception:
            return

    def _build_chunk_rows(self, document):
        """
        构建文档的普通分块向量行数据，按批次生成 embedding 并组装 Milvus 插入数据。

        流程：
        1. 逐个查询文档的所有 DocumentChunk（按 chunk_index 升序）
        2. 按批次调用嵌入模型生成稠密向量
        3. 组装每行的 id, vector, metadata 等字段
        4. 记录每个 chunk 的 vector_id 用于后续更新

        参数：
            document (Document): 文档模型实例。

        返回：
            tuple[list[dict], list[DocumentChunk]]:
                (Milvus 插入行数据列表, 需要更新 vector_id 的 chunk 列表)
        """
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
                row = {
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
                if getattr(settings, "RAG_HYBRID_SEARCH_ENABLED", False):
                    row["content_text"] = chunk.search_text or chunk.content
                rows.append(row)
                chunk.vector_id = str(vector_id)
                chunks_to_update.append(chunk)
        return rows, chunks_to_update

    def _build_section_rows(self, document):
        """
        构建文档的层级分块 Section 向量行数据（用于两级分块策略）。

        与 _build_chunk_rows 类似，但操作的是 DocumentSectionChunk 实体，
        且使用负数 ID 来区分 section 和普通 chunk 的向量记录。

        参数：
            document (Document): 文档模型实例。

        返回：
            tuple[list[dict], list[DocumentSectionChunk]]:
                (Milvus 插入行数据列表, 需要更新 vector_id 和 is_indexed 的 section 列表)
        """
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
                row = {
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
                if getattr(settings, "RAG_HYBRID_SEARCH_ENABLED", False):
                    row["content_text"] = section.search_text or section.content
                rows.append(row)
                section.vector_id = str(vector_id)
                section.is_indexed = True
                sections_to_update.append(section)
        return rows, sections_to_update

    def _get_latest_ingestion_task(self, document):
        """
        获取文档最近的摄取任务记录。

        参数：
            document (Document): 文档模型实例。

        返回：
            IngestionTask | None: 最近的摄取任务，若无则返回 None。
        """
        return IngestionTask.objects.filter(document=document).order_by("-id").first()

    def index(self, document):
        """
        将文档的全部 chunk 向量化并索引到 Milvus。

        区分两种模式：
        - 层级分块模式：索引 DocumentSectionChunk（增量的，只索引 is_indexed=False 的）
        - 普通分块模式：索引 DocumentChunk（全量替换，先删后插）

        索引完成后更新对应实体的 vector_id 字段。

        参数：
            document (Document): 文档模型实例。
        """
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
        """
        从 Milvus 中删除指定文档的所有向量数据。

        参数：
            document_id (int): 文档主键ID。
        """
        client = self._get_client()
        if not client.has_collection(settings.MILVUS_COLLECTION_NAME):
            return
        client.delete(
            settings.MILVUS_COLLECTION_NAME,
            filter=f"document_id == {int(document_id)}",
        )

    def clear(self):
        """
        清空整个向量集合：删除 Milvus 中的集合并重置客户端缓存。

        类似 SpringBoot 中调用 repository.deleteAll() 并清空缓存。
        """
        client = self._get_client()
        if client.has_collection(settings.MILVUS_COLLECTION_NAME):
            client.drop_collection(settings.MILVUS_COLLECTION_NAME)
        self.__class__._client = None


def index_document_chunks(document):
    """
    便捷函数：将文档的所有 chunk 索引到向量数据库。

    参数：
        document (Document): 文档模型实例。

    返回：
        None: VectorService.index() 的返回值。
    """
    return VectorService().index(document)
