"""
检索文本构建服务 —— 对应 SpringBoot 中的 @Service 组件，为向量检索构建上下文增强文本。

将文档元数据（标题、类型、日期、数据集、页码、段落路径等）拼接到分块内容的前面，
使向量嵌入携带更丰富的语义上下文，提升检索准确率。

SpringBoot 类比：
- Django 上下文文本构建               →  SpringBoot @Service 的文本预处理方法
- Django metadata dict 展开            →  SpringBoot Map/Properties 的字段提取
"""


def _normalize_text(value):
    """
    归一化文本：将任意值转为字符串并合并多余空白。

    参数：
        value (any): 任意输入值。

    返回：
        str: 去除首尾空白并合并连续空格后的归一化文本。若为空则返回空字符串。
    """
    return " ".join(str(value or "").strip().split())


def build_contextual_search_text(*, content, metadata=None):
    """
    构建上下文增强的检索文本。

    将文档元数据字段（文档标题、类型、来源日期、数据集名称、页码、段落标签、
    段落路径）以 "字段名: 值" 的格式前置到分块内容之前，形成上下文感知的检索文本。
    如果元数据中包含句子窗口信息（"window"字段）且与正文不同，会追加到末尾。

    这样做的目的是让向量嵌入（embedding）携带元数据语义，提升检索时的匹配精度。
    类似 SpringBoot 中在全文检索前对文档进行字段加权和上下文拼接的预处理。

    参数：
        content (str): 分块的正文内容。
        metadata (dict, optional): 分块的元数据字典，可选包含以下键：
            - document_title: 文档标题
            - doc_type: 文档类型
            - source_date: 来源日期
            - dataset_name: 数据集名称
            - page_label: 页码标签
            - section_label / section_page_label: 段落标签
            - section_path: 段落路径
            - window: 句子窗口上下文

    返回：
        str: 拼接后的上下文检索文本，每行一个 "字段: 值" 键值对或内容块。
    """
    metadata = metadata or {}
    fields = (
        ("title", metadata.get("document_title")),
        ("doc_type", metadata.get("doc_type")),
        ("source_date", metadata.get("source_date")),
        ("dataset", metadata.get("dataset_name")),
        ("page", metadata.get("page_label")),
        ("section", metadata.get("section_label") or metadata.get("section_page_label")),
        ("section_path", metadata.get("section_path")),
    )
    lines = [f"{label}: {_normalize_text(value)}" for label, value in fields if _normalize_text(value)]
    body = _normalize_text(content)
    if body:
        lines.append(body)
    window = _normalize_text(metadata.get("window"))
    if window and window != body:
        lines.append(window)
    return "\n".join(lines)
