"""
文档解析服务 —— 对应 SpringBoot 中的 @Service 组件，负责将上传文件解析为结构化文本和元素。

支持三种文档格式的解析：
- TXT：直接读取 UTF-8 文本
- PDF：优先使用 pymupdf4llm（生成 Markdown 元素结构），失败时回退到 pypdf（纯文本提取）
- DOCX：使用 python-docx 解析段落和表格，支持样式到元素类型的映射

解析结果包含：
- parsed_text: 清洗后的纯文本
- elements: 文档元素列表（用于智能分块）
- document_metadata: 解析来源和策略信息
- chunk_metadata_defaults: 分块元数据的默认值

SpringBoot 类比：
- Django ParserService 类            →  SpringBoot @Service 解析器组件
- Django 多格式解析 dispatch          →  SpringBoot 策略模式（TxtParser/PdfParser/DocxParser）
- Django DOCX 样式 → 元素类型映射     →  SpringBoot @ConfigurationProperties 配置映射
"""

import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO
from pathlib import Path

from django.conf import settings


# DOCX 关系文件的 XML 命名空间
RELATIONSHIPS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

# DOCX 段落样式名 → 文档元素类型映射表
# 将 Word 样式名映射为 Unstructured 兼容的元素类型
_DOCX_STYLE_TO_ELEMENT_MAPPING = {
    "Heading 1": "Title",
    "Heading 2": "Title",
    "Heading 3": "Title",
    "Heading 4": "Title",
    "Heading 5": "Title",
    "Heading 6": "Title",
    "Heading 7": "Title",
    "Heading 8": "Title",
    "Heading 9": "Title",
    "List": "ListItem",
    "List 2": "ListItem",
    "List 3": "ListItem",
    "List Bullet": "ListItem",
    "List Bullet 2": "ListItem",
    "List Bullet 3": "ListItem",
    "List Continue": "ListItem",
    "List Continue 2": "ListItem",
    "List Continue 3": "ListItem",
    "List Number": "ListItem",
    "List Number 2": "ListItem",
    "List Number 3": "ListItem",
    "List Paragraph": "ListItem",
    "Subtitle": "Title",
    "TOCHeading": "Title",
    "Title": "Title",
}

# Markdown 标题正则：匹配 "# 标题" 到 "###### 标题"
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
# Markdown 表格行正则：匹配 "| 单元格 |" 格式
_TABLE_ROW_RE = re.compile(r"^\|(.+)\|$")


class ParserService:
    """
    文档解析服务类。

    负责解析上传的 TXT/PDF/DOCX 文档为结构化文本并提供 Unstructured 兼容的
    元素列表。类似于 SpringBoot 中注入多个解析策略的 @Service 单例 Bean。
    """

    # 多次空白压缩正则（保留换行符）
    _MULTISPACE_PATTERN = re.compile(r"[^\S\r\n]+")
    # 三次以上连续换行合并为正则
    _MULTIBLANK_PATTERN = re.compile(r"\n{3,}")

    def clean_text(self, text):
        """
        清洗原始文本：去除空字符、统一换行符、合并多余空白、去除行尾空白。

        参数：
            text (str): 原始文本。

        返回：
            str: 清洗后的干净文本。
        """
        cleaned = (text or "").replace("\x00", "")
        cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
        cleaned = re.sub(r"(?<=\w)-\n(?=\w)", "", cleaned)
        cleaned = self._MULTISPACE_PATTERN.sub(" ", cleaned)
        cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
        cleaned = self._MULTIBLANK_PATTERN.sub("\n\n", cleaned)
        return cleaned.strip()

    def _base_document_metadata(self, *, source_parser, source_strategy, fallback_used, element_count=0):
        """
        构建基础文档元数据字典（解析来源信息）。

        参数：
            source_parser (str): 解析器名称（如 "pymupdf4llm"、"python-docx"、"txt"）。
            source_strategy (str): 解析策略（如 "auto"、"native"、"fallback"）。
            fallback_used (bool): 是否使用了回退解析器。
            element_count (int): 解析出的文档元素数量。

        返回：
            dict: 包含 source_parser, source_strategy, fallback_used, element_count 的元数据。
        """
        return {
            "source_parser": source_parser,
            "source_strategy": source_strategy,
            "fallback_used": fallback_used,
            "element_count": element_count,
        }

    def _base_chunk_metadata_defaults(self, *, source_parser, source_strategy):
        """
        构建分块元数据的默认值字典。

        参数：
            source_parser (str): 解析器名称。
            source_strategy (str): 解析策略。

        返回：
            dict: 包含 page_number, section_title, element_types, source_parser, source_strategy 的默认值。
        """
        return {
            "page_number": None,
            "section_title": "",
            "element_types": [],
            "source_parser": source_parser,
            "source_strategy": source_strategy,
        }

    def _structured_result(
        self,
        *,
        parsed_text,
        source_parser,
        source_strategy,
        fallback_used,
        element_count=0,
        chunk_metadata_defaults=None,
        document_metadata=None,
    ):
        """
        构建标准化的解析结果字典，包含文本、元数据和分块预设。

        参数：
            parsed_text (str): 解析并清洗后的纯文本。
            source_parser (str): 解析器名称。
            source_strategy (str): 解析策略。
            fallback_used (bool): 是否使用了回退方案。
            element_count (int): 文档元素数量。
            chunk_metadata_defaults (dict, optional): 分块元数据默认值。
            document_metadata (dict, optional): 补充的文档元数据。

        返回：
            dict: 标准解析结果，包含 parsed_text, document_metadata, chunk_metadata_defaults。
        """
        result = {
            "parsed_text": self.clean_text(parsed_text),
            "document_metadata": self._base_document_metadata(
                source_parser=source_parser,
                source_strategy=source_strategy,
                fallback_used=fallback_used,
                element_count=element_count,
            ),
            "chunk_metadata_defaults": self._base_chunk_metadata_defaults(
                source_parser=source_parser,
                source_strategy=source_strategy,
            ),
        }
        if document_metadata:
            result["document_metadata"].update(document_metadata)
            result["document_metadata"]["source_parser"] = source_parser
            result["document_metadata"]["source_strategy"] = source_strategy
            result["document_metadata"]["fallback_used"] = fallback_used
            result["document_metadata"].setdefault("element_count", element_count)
        if chunk_metadata_defaults:
            result["chunk_metadata_defaults"].update(chunk_metadata_defaults)
            result["chunk_metadata_defaults"]["source_parser"] = source_parser
            result["chunk_metadata_defaults"]["source_strategy"] = source_strategy
        return result

    # ── pypdf fallback ────────────────────────────────────────────────────

    def _parse_pdf_via_pypdf(self, file_path):
        """
        使用 pypdf 库解析 PDF 文件（回退方案，仅提取纯文本）。

        参数：
            file_path (Path): PDF 文件的路径对象。

        返回：
            str: 提取的纯文本，各页之间用双换行分隔。

        异常：
            ValueError: 当前环境未安装 PDF 解析依赖。
        """
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError("当前环境未安装 PDF 解析依赖。") from exc

        reader = PdfReader(str(file_path))
        pages = []
        for page in reader.pages:
            extracted = page.extract_text() or ""
            if extracted.strip():
                pages.append(extracted.strip())
        return "\n\n".join(pages)

    # ── pymupdf4llm PDF parsing ──────────────────────────────────────────

    @staticmethod
    def _markdown_to_elements(md_text, page_number):
        """
        将 Markdown 格式文本转换为 Unstructured 兼容的元素列表。

        识别规则：
        - "# 标题" (1个#)  → Title 类型
        - "## 标题" (2个#) → Section-header 类型
        - "### ... ###### 标题" (3-6个#) → Header 类型
        - "| ... |" 格式行  → Table 类型
        - 其他文本          → Paragraph 类型

        参数：
            md_text (str): pymupdf4llm 生成的 Markdown 文本。
            page_number (int): 当前页码（从 1 开始）。

        返回：
            list[dict]: 文档元素列表，每个元素包含 type, text, metadata。
        """
        elements = []
        for line in md_text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue

            heading_match = _HEADING_RE.match(stripped)
            if heading_match:
                level = len(heading_match.group(1))
                text = heading_match.group(2).strip()
                if text:
                    if level == 1:
                        elem_type = "Title"
                    elif level == 2:
                        elem_type = "Section-header"
                    else:
                        elem_type = "Header"
                    elements.append({
                        "type": elem_type,
                        "text": text,
                        "metadata": {"page_number": page_number},
                    })
                continue

            if _TABLE_ROW_RE.match(stripped):
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                cells = [c for c in cells if c and not set(c) <= {"-", ":", " "}]
                if cells:
                    elements.append({
                        "type": "Table",
                        "text": " | ".join(cells),
                        "metadata": {"page_number": page_number},
                    })
                continue

            elements.append({
                "type": "Paragraph",
                "text": stripped,
                "metadata": {"page_number": page_number},
            })

        return elements

    def _parse_pdf_via_pymupdf4llm(self, file_path):
        """
        使用 pymupdf4llm 库解析 PDF 文件（主要方案），生成 Markdown 后转换为元素列表。

        参数：
            file_path (Path): PDF 文件的路径对象。

        返回：
            list[dict]: 文档元素列表。
        """
        import pymupdf4llm

        page_chunks = pymupdf4llm.to_markdown(str(file_path), page_chunks=True)
        elements = []
        for chunk in page_chunks:
            md_text = chunk.get("text", "")
            metadata = chunk.get("metadata", {})
            page_number = metadata.get("page", 0) + 1
            elements.extend(self._markdown_to_elements(md_text, page_number))
        return elements

    # ── python-docx DOCX parsing ─────────────────────────────────────────

    @staticmethod
    def _source_part_path(relationships_path):
        """
        从 OPC（Open Packaging Conventions）关系文件路径推导对应的文档部件路径。

        参数：
            relationships_path (str): .rels 文件在 ZIP 中的路径。

        返回：
            str: 对应的文档部件路径。
        """
        if relationships_path == "_rels/.rels":
            return ""
        container, _, relationship_name = relationships_path.partition("/_rels/")
        if not relationship_name.endswith(".rels"):
            return ""
        part_name = relationship_name[:-5]
        if not container:
            return part_name
        return f"{container}/{part_name}"

    @staticmethod
    def _normalize_internal_target(base_dir, target):
        """
        标准化 DOCX 关系文件中的内部目标路径。

        参数：
            base_dir (str): 关系文件所在的目录路径。
            target (str): 关系目标路径（可能为相对路径或绝对路径）。

        返回：
            str | None: 标准化后的路径，若无效则返回 None。
        """
        normalized_target = (target or "").strip()
        if not normalized_target or normalized_target.upper() == "NULL":
            return None
        if normalized_target.startswith("/"):
            candidate = normalized_target.lstrip("/")
        else:
            candidate = posixpath.normpath(posixpath.join(base_dir, normalized_target))
        candidate = candidate.lstrip("/")
        if not candidate or candidate == "." or candidate.startswith("../"):
            return None
        return candidate

    @classmethod
    def _repair_docx_relationships(cls, file_bytes):
        """
        修复 DOCX 文件中的残损关系引用：移除指向不存在目标的 Relationship 元素。

        某些 DOCX 文件包含指向已删除图像或其他资源的残损引用，这会导致 python-docx 解析失败。
        此方法扫描所有 .rels 文件并移除死链，返回修复后的文件内容。

        参数：
            file_bytes (bytes): DOCX 文件的原始字节内容。

        返回：
            bytes: 修复后的 DOCX 文件字节内容。若无残损引用则返回原始内容。
        """
        source_buffer = BytesIO(file_bytes)
        rewritten_payloads = {}

        with zipfile.ZipFile(source_buffer) as source_zip:
            archive_members = set(source_zip.namelist())
            for info in source_zip.infolist():
                if not info.filename.endswith(".rels"):
                    continue
                payload = source_zip.read(info.filename)
                try:
                    root = ET.fromstring(payload)
                except ET.ParseError:
                    continue
                if root.tag != f"{{{RELATIONSHIPS_NS}}}Relationships":
                    continue

                base_dir = posixpath.dirname(cls._source_part_path(info.filename))
                removed = False

                for relationship in list(root):
                    if relationship.tag != f"{{{RELATIONSHIPS_NS}}}Relationship":
                        continue
                    if relationship.attrib.get("TargetMode") == "External":
                        continue
                    normalized = cls._normalize_internal_target(
                        base_dir,
                        relationship.attrib.get("Target"),
                    )
                    if normalized and normalized in archive_members:
                        continue
                    root.remove(relationship)
                    removed = True

                if removed:
                    rewritten_payloads[info.filename] = ET.tostring(
                        root,
                        encoding="utf-8",
                        xml_declaration=True,
                    )

        if not rewritten_payloads:
            return file_bytes

        source_buffer.seek(0)
        output_buffer = BytesIO()
        with zipfile.ZipFile(source_buffer) as source_zip, zipfile.ZipFile(output_buffer, "w") as target_zip:
            for info in source_zip.infolist():
                payload = rewritten_payloads.get(info.filename, source_zip.read(info.filename))
                target_zip.writestr(info, payload)

        return output_buffer.getvalue()

    @staticmethod
    def _docx_paragraph_element_type(paragraph):
        """
        根据 DOCX 段落的样式名确定对应的文档元素类型。

        参数：
            paragraph (docx.text.paragraph.Paragraph): python-docx 的段落对象。

        返回：
            str: 文档元素类型（"Title", "ListItem", "Paragraph"）。
        """
        style_name = paragraph.style.name if paragraph.style else ""
        if style_name in _DOCX_STYLE_TO_ELEMENT_MAPPING:
            return _DOCX_STYLE_TO_ELEMENT_MAPPING[style_name]
        normalized_style = style_name.lower()
        if "heading" in normalized_style or "title" in normalized_style:
            return "Title"
        if normalized_style.startswith("list"):
            return "ListItem"
        return "Paragraph"

    def _parse_docx_via_python_docx(self, file_path):
        """
        使用 python-docx 库解析 DOCX 文件，提取段落和表格为元素列表。

        参数：
            file_path (Path): DOCX 文件的路径对象。

        返回：
            list[dict]: 文档元素列表，包含段落（type=Title/ListItem/Paragraph）和表格（type=Table）。
        """
        from docx import Document

        file_bytes = Path(file_path).read_bytes()
        repaired_bytes = self._repair_docx_relationships(file_bytes)
        doc = Document(BytesIO(repaired_bytes))
        elements = []

        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                elem_type = self._docx_paragraph_element_type(para)
                elements.append({"type": elem_type, "text": text, "metadata": {}})

        for table in doc.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    elements.append({
                        "type": "Table",
                        "text": " | ".join(cells),
                        "metadata": {},
                    })

        return elements

    # ── result builders ───────────────────────────────────────────────────

    def _txt_result(self, text):
        """
        构建 TXT 文件的解析结果。

        参数：
            text (str): TXT 文件的原始文本内容。

        返回：
            dict: 标准化解析结果，source_parser="txt"，无元素列表。
        """
        return self._structured_result(
            parsed_text=text,
            source_parser="txt",
            source_strategy="local",
            fallback_used=False,
            element_count=0,
        )

    def _pdf_fallback_result(self, text):
        """
        构建 PDF 回退解析（pypdf）的结果，标记 fallback_used=True。

        参数：
            text (str): pypdf 提取的纯文本。

        返回：
            dict: 标准化解析结果，source_parser="pypdf"，标记为回退模式。
        """
        return self._structured_result(
            parsed_text=text,
            source_parser="pypdf",
            source_strategy="fallback",
            fallback_used=True,
            element_count=0,
        )

    def _elements_to_result(self, elements, source_parser, strategy):
        """
        将文档元素列表构建为标准化解析结果，统计页码和元素类型分布。

        参数：
            elements (list[dict]): 文档元素列表。
            source_parser (str): 解析器名称。
            strategy (str): 解析策略。

        返回：
            dict: 标准化解析结果，包含 parsed_text, elements, document_metadata, chunk_metadata_defaults。

        异常：
            ValueError: 所有元素文本拼接后为空。
        """
        texts = []
        page_numbers = set()
        element_types = {}

        for elem in elements:
            text = (elem.get("text") or "").strip()
            if text:
                texts.append(text)
            meta = elem.get("metadata") or {}
            if meta.get("page_number") is not None:
                page_numbers.add(meta["page_number"])
            elem_type = elem.get("type")
            if elem_type:
                element_types[elem_type] = element_types.get(elem_type, 0) + 1

        parsed_text = "\n\n".join(texts)
        if not parsed_text:
            raise ValueError("解析返回空文本。")

        chunk_defaults = {}
        if page_numbers:
            chunk_defaults["page_number"] = min(page_numbers)
        if element_types:
            chunk_defaults["element_types"] = sorted(element_types.keys())

        result = self._structured_result(
            parsed_text=parsed_text,
            source_parser=source_parser,
            source_strategy=strategy,
            fallback_used=False,
            element_count=len(elements),
            chunk_metadata_defaults=chunk_defaults,
        )
        result["elements"] = elements
        return result

    # ── dispatch ──────────────────────────────────────────────────────────

    def parse(self, document):
        """
        根据文档类型分发到对应的解析器，返回标准解析结果。

        分发逻辑（类似 SpringBoot 策略模式的分发器）：
        - doc_type == "txt":  直接读取 UTF-8 文本
        - doc_type == "pdf":  优先 pymupdf4llm，失败时若 PDF_FALLBACK_ENABLED 则回退到 pypdf
        - doc_type == "docx": python-docx 解析段落和表格

        参数：
            document (Document): 文档模型实例（类似 JPA @Entity）。

        返回：
            dict: 标准化解析结果，包含 parsed_text, elements, document_metadata, chunk_metadata_defaults。

        异常：
            ValueError: 不支持的文档类型。
        """
        file_path = Path(document.file.path)
        if document.doc_type == "txt":
            return self._txt_result(file_path.read_text(encoding="utf-8"))

        if document.doc_type == "pdf":
            try:
                elements = self._parse_pdf_via_pymupdf4llm(file_path)
                return self._elements_to_result(elements, "pymupdf4llm", "auto")
            except Exception:
                if not settings.PDF_FALLBACK_ENABLED:
                    raise
                return self._pdf_fallback_result(self._parse_pdf_via_pypdf(file_path))

        if document.doc_type == "docx":
            elements = self._parse_docx_via_python_docx(file_path)
            return self._elements_to_result(elements, "python-docx", "native")

        raise ValueError("不支持的文档类型。")


def parse_document_file(document):
    """
    便捷函数：解析文档文件并返回标准结果。

    参数：
        document (Document): 文档模型实例。

    返回：
        dict: ParserService.parse() 的标准化解析结果。
    """
    return ParserService().parse(document)
