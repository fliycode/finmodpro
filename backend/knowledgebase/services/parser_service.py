import re
from pathlib import Path

from django.conf import settings

from knowledgebase.services.unstructured_client import parse_via_unstructured


class ParserService:
    _MULTISPACE_PATTERN = re.compile(r"[^\S\r\n]+")
    _MULTIBLANK_PATTERN = re.compile(r"\n{3,}")

    def clean_text(self, text):
        cleaned = (text or "").replace("\x00", "")
        cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
        cleaned = re.sub(r"(?<=\w)-\n(?=\w)", "", cleaned)
        cleaned = self._MULTISPACE_PATTERN.sub(" ", cleaned)
        cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
        cleaned = self._MULTIBLANK_PATTERN.sub("\n\n", cleaned)
        return cleaned.strip()

    def _base_document_metadata(self, *, source_parser, source_strategy, fallback_used, element_count=0):
        return {
            "source_parser": source_parser,
            "source_strategy": source_strategy,
            "fallback_used": fallback_used,
            "element_count": element_count,
        }

    def _base_chunk_metadata_defaults(self, *, source_parser, source_strategy):
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

    def _parse_pdf(self, file_path):
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

    def _txt_result(self, text):
        return self._structured_result(
            parsed_text=text,
            source_parser="txt",
            source_strategy="local",
            fallback_used=False,
            element_count=0,
        )

    def _pdf_fallback_result(self, text):
        return self._structured_result(
            parsed_text=text,
            source_parser="pypdf",
            source_strategy="fallback",
            fallback_used=True,
            element_count=0,
        )

    def _elements_to_result(self, elements, strategy):
        """Convert an Unstructured elements list into a structured result dict."""
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
            raise ValueError("Unstructured 返回空文本。")

        chunk_defaults = {}
        if page_numbers:
            chunk_defaults["page_number"] = min(page_numbers)
        if element_types:
            chunk_defaults["element_types"] = sorted(element_types.keys())

        return self._structured_result(
            parsed_text=parsed_text,
            source_parser="unstructured",
            source_strategy=strategy,
            fallback_used=False,
            element_count=len(elements),
            chunk_metadata_defaults=chunk_defaults,
        )

    def parse(self, document):
        file_path = Path(document.file.path)
        if document.doc_type == "txt":
            return self._txt_result(file_path.read_text(encoding="utf-8"))

        if document.doc_type == "pdf":
            try:
                elements = parse_via_unstructured(
                    file_path=file_path,
                    filename=document.filename,
                    content_type="application/pdf",
                    strategy=settings.UNSTRUCTURED_PDF_STRATEGY,
                )
                return self._elements_to_result(
                    elements=elements or [],
                    strategy=settings.UNSTRUCTURED_PDF_STRATEGY,
                )
            except ValueError:
                if not settings.UNSTRUCTURED_PDF_FALLBACK_ENABLED:
                    raise
                return self._pdf_fallback_result(self._parse_pdf(file_path))

        if document.doc_type == "docx":
            elements = parse_via_unstructured(
                file_path=file_path,
                filename=document.filename,
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                strategy=settings.UNSTRUCTURED_DOCX_STRATEGY,
            )
            return self._elements_to_result(
                elements=elements or [],
                strategy=settings.UNSTRUCTURED_DOCX_STRATEGY,
            )

        raise ValueError("不支持的文档类型。")


def parse_document_file(document):
    return ParserService().parse(document)
