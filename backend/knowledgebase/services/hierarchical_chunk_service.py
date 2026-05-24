"""
层级分块服务 —— 对应 SpringBoot 中的 @Service 组件，将文档组织为两级分块结构。

层级分块策略：
1. 第一层（section / 段）：较粗粒度的段落分块，保留文档的宏观结构
2. 第二层（child / 子块）：在段内进行细粒度分块，用于精确检索

适用于长文档场景，解决单层分块在长文档中丢失层级结构信息的问题。

SpringBoot 类比：
- Django 两层分块逻辑               →  SpringBoot @Service 的复合分块方法
- Django settings chunk size 配置   →  SpringBoot @Value 注入的分块参数
"""

from django.conf import settings

from knowledgebase.services.chunk_service import (
    build_document_chunks,
    build_document_chunks_from_elements,
)


def build_hierarchical_document_chunks(
    *,
    text,
    elements,
    section_metadata_builder,
    child_metadata_builder,
):
    """
    构建层级化文档分块：先产 Section 级大块，再在每段内产 Child 级小块。

    流程：
    1. 优先使用 elements 进行智能段分块（尊重文档结构边界），否则用固定长度分块。
    2. 第一层使用 KB_SECTION_CHUNK_SIZE / KB_SECTION_CHUNK_OVERLAP 参数。
    3. 在每个 section 内部再次执行固定长度分块，生成 child chunks。
    4. 每个 child chunk 携带其所属 section 的索引信息。

    返回的 sections 列表中每个元素包含 "chunk_index", "content", "metadata"。
    返回的 child_chunks 列表中每个元素额外包含 "section_index"（所属段索引）、
    "chunk_index_in_section"（段内全局索引）。

    参数：
        text (str): 文档的完整解析文本。
        elements (list[dict] | None): Unstructured 解析出的文档元素列表，可为空。
        section_metadata_builder (callable): Section 级元数据工厂函数，签名为 (index: int) -> dict。
            类似 SpringBoot 中的 Function<Integer, Map>。
        child_metadata_builder (callable): Child 级元数据工厂函数，签名为 (section: dict, index: int) -> dict。
            接收所属 section 对象和段内索引，返回元数据字典。

    返回：
        dict: {"sections": list[dict], "child_chunks": list[dict]}
            - sections: Section 级分块列表
            - child_chunks: 所有段下 child 级分块的展平列表
    """
    if elements:
        sections = build_document_chunks_from_elements(
            elements,
            metadata_builder=section_metadata_builder,
            max_chunk_size=settings.KB_SECTION_CHUNK_SIZE,
            overlap=settings.KB_SECTION_CHUNK_OVERLAP,
        )
    else:
        sections = build_document_chunks(
            text,
            metadata_builder=section_metadata_builder,
            chunk_size=settings.KB_SECTION_CHUNK_SIZE,
            overlap=settings.KB_SECTION_CHUNK_OVERLAP,
        )

    child_chunks = []
    child_chunk_index = 0
    for section in sections:
        section_children = build_document_chunks(
            section["content"],
            metadata_builder=lambda index, section=section: child_metadata_builder(section, index),
        )
        for child in section_children:
            child_chunks.append(
                {
                    **child,
                    "chunk_index": child_chunk_index,
                    "chunk_index_in_section": child["chunk_index"],
                    "section_index": section["chunk_index"],
                }
            )
            child_chunk_index += 1

    return {
        "sections": sections,
        "child_chunks": child_chunks,
    }
