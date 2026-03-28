def build_document_chunks(text, metadata_builder, chunk_size=400, overlap=50):
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
