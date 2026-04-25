"""Lightweight Unstructured parse API — ``strategy=fast`` only.

镜像体积 ~300-500 MB（对比官方 ~10 GB），因为不打包 Detectron2、PyTorch、
Tesseract OCR、LibreOffice 等重型 ML 依赖。只支持 ``fast`` 策略，适合
文本型 PDF/DOCX 的结构化提取。

Endpoint:  POST /general/v0/general  (兼容 Unstructured API 协议)
"""

from io import BytesIO

from fastapi import FastAPI, File, HTTPException, Query, UploadFile

app = FastAPI()


@app.post("/general/v0/general")
def parse_file(
    files: UploadFile = File(...),
    strategy: str = Query("fast"),
):
    if strategy not in ("fast", "auto"):
        raise HTTPException(
            status_code=400,
            detail=f"不支持 strategy={strategy}。轻量服务只支持 fast/auto。",
        )

    # Map auto to fast — we never run hi_res.
    actual_strategy = "fast"

    try:
        content = files.file.read()
        from unstructured.partition.auto import partition  # noqa: E402

        elements = partition(
            file=BytesIO(content),
            file_filename=files.filename or "unknown",
            content_type=files.content_type or "application/octet-stream",
            strategy=actual_strategy,
            languages=["eng", "chi_sim"],
        )
        return [el.to_dict() for el in elements]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/healthcheck")
def healthcheck():
    return {"status": "ok"}
