from pathlib import Path

def parse_document_file(document):
    file_path = Path(document.file.path)
    if document.doc_type == "txt":
        return file_path.read_text(encoding="utf-8")

    if document.doc_type == "pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError("当前环境未安装 PDF 解析依赖。") from exc

        reader = PdfReader(str(file_path))
        return "\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()

    if document.doc_type == "docx":
        raise ValueError("DOCX 解析暂未实现。")

    raise ValueError("不支持的文档类型。")
