import re
from pathlib import Path


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

    def parse(self, document):
        file_path = Path(document.file.path)
        if document.doc_type == "txt":
            return self.clean_text(file_path.read_text(encoding="utf-8"))

        if document.doc_type == "pdf":
            return self.clean_text(self._parse_pdf(file_path))

        if document.doc_type == "docx":
            raise ValueError("DOCX 解析暂未实现。")

        raise ValueError("不支持的文档类型。")


def parse_document_file(document):
    return ParserService().parse(document)
