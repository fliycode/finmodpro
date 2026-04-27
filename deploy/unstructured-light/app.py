"""Lightweight document text extraction — strategy=fast only.

Covers ``pdf`` (via pdfminer.six), ``docx`` (via python-docx), and
``txt`` (raw read).  No ``unstructured``, Detectron2, PyTorch, Tesseract,
or LibreOffice — total image ~200 MB.
"""

from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import FastAPI, File, HTTPException, Query, UploadFile

app = FastAPI()

# ── helpers ──────────────────────────────────────────────────────────────


def _extract_pdf(file_bytes: bytes) -> list[dict]:
    from pdfminer.high_level import extract_text  # noqa: E402

    text = extract_text(BytesIO(file_bytes))
    elements = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            elements.append({"type": "Paragraph", "text": stripped, "metadata": {}})
    if not elements:
        # pdfminer returned nothing — basic fallback.
        decoded = text.strip()
        if decoded:
            elements.append({"type": "Paragraph", "text": decoded, "metadata": {}})
    return elements


def _extract_docx(file_bytes: bytes) -> list[dict]:
    from docx import Document  # noqa: E402

    doc = Document(BytesIO(file_bytes))
    elements = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            style = para.style.name if para.style else ""
            elem_type = "Title" if "heading" in style.lower() or "title" in style.lower() else "Paragraph"
            elements.append({"type": elem_type, "text": text, "metadata": {}})

    # Also extract tables.
    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                elements.append(
                    {"type": "Table", "text": " | ".join(cells), "metadata": {}}
                )
    return elements


# ── API ──────────────────────────────────────────────────────────────────


@app.post("/general/v0/general")
def parse_file(
    files: UploadFile = File(...),
    strategy: str = Query("fast"),
):
    if strategy not in ("fast", "auto"):
        raise HTTPException(
            status_code=400,
            detail=f"strategy={strategy} not supported (only fast/auto).",
        )

    content_type = files.content_type or ""
    filename = (files.filename or "").lower()

    raw = files.file.read()

    try:
        if "pdf" in content_type or filename.endswith(".pdf"):
            elements = _extract_pdf(raw)
        elif filename.endswith(".docx") or "wordprocessingml" in content_type:
            elements = _extract_docx(raw)
        elif filename.endswith(".txt") or "text/plain" in content_type:
            text = raw.decode("utf-8", errors="replace")
            elements = [
                {"type": "Paragraph", "text": line.strip(), "metadata": {}}
                for line in text.splitlines()
                if line.strip()
            ]
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported type: {content_type}")

        return elements
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/healthcheck")
def healthcheck():
    return {"status": "ok"}
