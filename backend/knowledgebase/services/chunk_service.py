from django.conf import settings


class ChunkService:
    def build_chunks(self, text, metadata_builder, chunk_size=None, overlap=None):
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


def build_document_chunks(text, metadata_builder, chunk_size=None, overlap=None):
    return ChunkService().build_chunks(
        text,
        metadata_builder,
        chunk_size=chunk_size,
        overlap=overlap,
    )
