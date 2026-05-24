"""
文本分块服务 —— 对应 SpringBoot 中的 @Service 组件，负责将文档文本切分为语义段落。

提供多种分块策略：
- 固定长度分块（flat chunking）：按字符数滑动窗口切分，支持重叠
- 基于文档元素分块（element-aware chunking）：尊重标题/表格等语义边界
- 句子窗口分块（sentence-window chunking）：以句子为单位，携带上下文窗口

SpringBoot 类比：
- Django settings.KB_CHUNK_SIZE      →  SpringBoot @Value("${kb.chunk.size}")
- Django ChunkService 类             →  SpringBoot @Service 类
- Django 模块级辅助函数               →  SpringBoot @Component 工具方法
"""

from django.conf import settings

# Element types from Unstructured that start a new chunk group.
# 触发新分块组的文档元素类型：标题、节标题、子标题
_BOUNDARY_TYPES = {"Title", "Section-header", "Header"}
# Element types that should be isolated in their own chunk.
# 需要独立分块的元素类型：表格
_ISOLATED_TYPES = {"Table"}


class ChunkService:
    """
    文本分块服务类。

    负责将长文本按多种策略切分为适合 LLM 上下文的块（chunk），每条 chunk
    包含索引、内容和元数据。类似于 SpringBoot 中的 @Service 单例 Bean。
    """

    def build_chunks(self, text, metadata_builder, chunk_size=None, overlap=None):
        """
        固定长度分块：将文本按字符窗口切分，支持重叠（overlap）。

        参数：
            text (str): 待分块的原始文本。
            metadata_builder (callable): 元数据工厂函数，签名为 (chunk_index: int) -> dict，
                为每个分块生成元数据字典。类似 SpringBoot 中的 Function<Integer, Map>。
            chunk_size (int, optional): 每个分块的最大字符数，默认取 settings.KB_CHUNK_SIZE。
            overlap (int, optional): 相邻分块之间的重叠字符数，默认取 settings.KB_CHUNK_OVERLAP。

        返回：
            list[dict]: 分块列表，每个元素为 {"chunk_index": int, "content": str, "metadata": dict}。
        """
        chunk_size = chunk_size or settings.KB_CHUNK_SIZE
        overlap = settings.KB_CHUNK_OVERLAP if overlap is None else overlap
        if chunk_size <= 0:
            raise ValueError("chunk_size 必须大于 0。")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap 必须大于等于 0 且小于 chunk_size。")

        cleaned_text = (text or "").strip()
        if not cleaned_text:
            raise ValueError("文档内容为空，无法摄取。")

        chunks = []
        start = 0
        chunk_index = 0
        text_length = len(cleaned_text)

        while start < text_length:
            end = min(text_length, start + chunk_size)
            content = cleaned_text[start:end].strip()
            if content:
                chunks.append(
                    {
                        "chunk_index": chunk_index,
                        "content": content,
                        "metadata": metadata_builder(chunk_index),
                    }
                )
                chunk_index += 1
            if end >= text_length:
                break
            start = max(end - overlap, start + 1)

        return chunks

    def build_chunks_from_elements(self, elements, metadata_builder, max_chunk_size=None, overlap=None):
        """
        基于文档元素的分块策略：尊重 Unstructured 文档元素边界进行智能分块。

        分块规则：
        - Title / Section-header / Header 类型的元素触发新分块开始。
        - Table 类型的元素被隔离到独立分块中，不与周围文本合并。
        - Paragraph / NarrativeText / ListItem 合并到当前分块中。
        - 单个分块超过 max_chunk_size 时，先在最近元素边界处拆分；若单个元素
          仍溢出，则回退到字符偏移拆分（带 overlap）。

        参数：
            elements (list[dict]): Unstructured 解析出的元素列表，每个元素包含
                "type"（元素类型）, "text"（文本内容）, "metadata"（元数据）键。
            metadata_builder (callable): 元数据工厂函数，签名为 (index: int) -> dict。
            max_chunk_size (int, optional): 每个分块的最大字符数，默认取 settings.KB_CHUNK_SIZE。
            overlap (int, optional): 溢出拆分时的字符重叠数，默认取 settings.KB_CHUNK_OVERLAP。

        返回：
            list[dict]: 分块列表，每个元素为 {"chunk_index": int, "content": str, "metadata": dict}。
        """
        max_chunk_size = max_chunk_size or settings.KB_CHUNK_SIZE
        overlap = settings.KB_CHUNK_OVERLAP if overlap is None else overlap
        if max_chunk_size <= 0:
            raise ValueError("max_chunk_size 必须大于 0。")
        if overlap < 0 or overlap >= max_chunk_size:
            raise ValueError("overlap 必须大于等于 0 且小于 max_chunk_size。")
        if not elements:
            raise ValueError("elements 列表为空，无法分块。")

        # ── Step 1: group elements, respecting boundaries ──
        # 步骤1：按元素边界分组
        groups = []
        group = []
        group_len = 0

        def _flush():
            """将当前累积的元素组提交到 groups 列表，并重置 group 状态。"""
            nonlocal group, group_len
            if group:
                groups.append(group)
                group = []
                group_len = 0

        for elem in elements:
            elem_type = elem.get("type") or "Paragraph"
            text = (elem.get("text") or "").strip()
            if not text:
                continue

            elem_len = len(text)

            if elem_type in _ISOLATED_TYPES:
                # 表格元素 —— 先提交前一个组，再独立成组
                _flush()
                groups.append([(text, elem_type)])
                continue

            if elem_type in _BOUNDARY_TYPES:
                # 边界元素 —— 提交前一个组，新标题从新组开始
                _flush()

            # 估算合并后的长度（含分隔符）
            sep = 2 if group else 0
            if group and group_len + sep + elem_len > max_chunk_size:
                _flush()

            group.append((text, elem_type))
            group_len += sep + elem_len

        _flush()

        # ── Step 2: build chunk dicts, splitting overflow groups ──
        # 步骤2：构建分块字典，对溢出组进行拆分
        chunks = []
        for g in groups:
            texts = [t for t, _ in g]
            content = "\n\n".join(texts)
            if len(content) <= max_chunk_size:
                chunks.append({"content": content})
                continue

            # 单个超长元素 —— 按字符偏移拆分
            start = 0
            tlen = len(content)
            while start < tlen:
                end = min(tlen, start + max_chunk_size)
                piece = content[start:end].strip()
                if piece:
                    chunks.append({"content": piece})
                if end >= tlen:
                    break
                start = max(end - overlap, start + 1)

        # ── Step 3: assign index and run metadata_builder ──
        # 步骤3：为每个分块分配索引并运行元数据工厂
        return [
            {
                "chunk_index": i,
                "content": c["content"],
                "metadata": metadata_builder(i),
            }
            for i, c in enumerate(chunks)
        ]


def estimate_flat_chunk_count(text, chunk_size=None, overlap=None):
    """
    估算固定长度分块策略将产生的分块数量，不实际执行分块。

    参数：
        text (str): 待分块的文本。
        chunk_size (int, optional): 每个分块的最大字符数，默认取 settings.KB_CHUNK_SIZE。
        overlap (int, optional): 相邻分块之间的重叠字符数，默认取 settings.KB_CHUNK_OVERLAP。

    返回：
        int: 预估的分块数量。
    """
    chunk_size = chunk_size or settings.KB_CHUNK_SIZE
    overlap = settings.KB_CHUNK_OVERLAP if overlap is None else overlap
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0。")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap 必须大于等于 0 且小于 chunk_size。")

    cleaned_text = (text or "").strip()
    if not cleaned_text:
        return 0

    step = chunk_size - overlap
    return max(1, ((len(cleaned_text) - chunk_size + step - 1) // step) + 1)


def choose_chunking_strategy(*, parsed_text_length, estimated_flat_chunk_count):
    """
    根据文本长度和预估分块数量，自动选择分块策略。

    决策逻辑：
    - 如果解析文本长度 >= KB_HIERARCHICAL_TEXT_THRESHOLD → 使用层级分块
    - 如果固定分块预估数量 >= KB_HIERARCHICAL_CHUNK_THRESHOLD → 使用层级分块
    - 否则 → 使用固定长度分块

    参数：
        parsed_text_length (int): 解析后的文本总长度（字符数）。
        estimated_flat_chunk_count (int): 固定长度分块的预估数量。

    返回：
        str: 分块策略名称，可选值 "hierarchical"（层级分块）或 "flat"（固定长度分块）。
    """
    if parsed_text_length >= settings.KB_HIERARCHICAL_TEXT_THRESHOLD:
        return "hierarchical"
    if estimated_flat_chunk_count >= settings.KB_HIERARCHICAL_CHUNK_THRESHOLD:
        return "hierarchical"
    return "flat"


def build_document_chunks(text, metadata_builder, chunk_size=None, overlap=None):
    """
    便捷函数：使用固定长度分块策略构建文档分块。

    参数：
        text (str): 待分块的文本。
        metadata_builder (callable): 元数据工厂函数，签名为 (chunk_index: int) -> dict。
        chunk_size (int, optional): 每个分块的最大字符数。
        overlap (int, optional): 相邻分块之间的重叠字符数。

    返回：
        list[dict]: 分块列表。
    """
    return ChunkService().build_chunks(
        text,
        metadata_builder,
        chunk_size=chunk_size,
        overlap=overlap,
    )


def build_document_chunks_from_elements(elements, metadata_builder, max_chunk_size=None, overlap=None):
    """
    便捷函数：使用基于元素的智能分块策略构建文档分块。

    参数：
        elements (list[dict]): Unstructured 文档元素列表。
        metadata_builder (callable): 元数据工厂函数，签名为 (index: int) -> dict。
        max_chunk_size (int, optional): 每个分块的最大字符数。
        overlap (int, optional): 溢出拆分时的字符重叠数。

    返回：
        list[dict]: 分块列表。
    """
    return ChunkService().build_chunks_from_elements(
        elements,
        metadata_builder,
        max_chunk_size=max_chunk_size,
        overlap=overlap,
    )


# ---------------------------------------------------------------------------
# Sentence-level window chunking
# 句子级窗口分块
# ---------------------------------------------------------------------------

import re as _re

# 句子分割正则：匹配中文句号/感叹号/问号/分号/换行符、英文标点后的位置
_SENTENCE_PATTERN = _re.compile(
    r"(?<=[。！？；\n.!?;])\s*",
)


def _split_sentences(text):
    """
    将文本按句子切分，支持中英文标点符号。

    参数：
        text (str): 输入文本。

    返回：
        list[str]: 句子列表，每个元素为去除首尾空白后的完整句子。
    """
    parts = _SENTENCE_PATTERN.split(text)
    return [p.strip() for p in parts if p.strip()]


def build_sentence_window_chunks(text, metadata_builder, window_size=None):
    """
    句子窗口分块：将文本拆分为独立句子，每条句子携带前后上下文窗口。

    每个返回的分块包含：
    - "content": 单个句子（用于向量嵌入）
    - "metadata.window": 目标句子前后各 window_size 句的拼接上下文（用于 LLM 合成）
    - "metadata.sentence_index": 该句子在文档中的位置索引

    对于极短文档（句子数 <= window_size * 2 + 1），回退到固定长度分块
    以避免产生过多碎片化的句子级分块。

    参数：
        text (str): 输入文本。
        metadata_builder (callable): 元数据工厂函数，签名为 (index: int) -> dict。
        window_size (int, optional): 上下文窗口大小（句子数），默认取 settings.KB_SENTENCE_WINDOW_SIZE。

    返回：
        list[dict]: 句子级窗口分块列表，每个元素包含 "chunk_index", "content", "metadata"。
    """
    window_size = window_size if window_size is not None else settings.KB_SENTENCE_WINDOW_SIZE
    cleaned_text = (text or "").strip()
    if not cleaned_text:
        raise ValueError("文档内容为空，无法摄取。")

    sentences = _split_sentences(cleaned_text)
    if not sentences:
        raise ValueError("文档内容为空，无法摄取。")

    # 对于极短文档，回退到固定长度分块以避免创建过多碎片化块
    if len(sentences) <= window_size * 2 + 1:
        return build_document_chunks(cleaned_text, metadata_builder)

    chunks = []
    total = len(sentences)
    for i, sentence in enumerate(sentences):
        window_start = max(0, i - window_size)
        window_end = min(total, i + window_size + 1)
        window_text = "".join(sentences[window_start:window_end])

        metadata = metadata_builder(i)
        metadata["window"] = window_text
        metadata["sentence_index"] = i
        chunks.append({
            "chunk_index": i,
            "content": sentence,
            "metadata": metadata,
        })

    return chunks
