from django.conf import settings

# Element types from Unstructured that start a new chunk group.
_BOUNDARY_TYPES = {"Title", "Section-header", "Header"}
# Element types that should be isolated in their own chunk.
_ISOLATED_TYPES = {"Table"}


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

    def build_chunks_from_elements(self, elements, metadata_builder, max_chunk_size=None, overlap=None):
        """Build chunks respecting Unstructured element boundaries.

        * Title / Section-header / Header starts a new chunk.
        * Table gets its own chunk (isolated from surrounding text).
        * Paragraph / NarrativeText / ListItem merge into the current chunk.
        * A chunk that exceeds *max_chunk_size* is split at the most recent
          element boundary first; only if a single element overflows do we
          fall back to character-offset splitting (with overlap).

        Parameters
        ----------
        elements : list[dict]
            Unstructured elements with ``type``, ``text``, ``metadata`` keys.
        metadata_builder : callable
            ``(index) -> dict`` — per-chunk metadata factory.
        max_chunk_size : int, optional
            Max characters per chunk.  Defaults to ``settings.KB_CHUNK_SIZE``.
        overlap : int, optional
            Character overlap for overflow splitting.  Defaults to
            ``settings.KB_CHUNK_OVERLAP``.
        """
        max_chunk_size = max_chunk_size or settings.KB_CHUNK_SIZE
        overlap = settings.KB_CHUNK_OVERLAP if overlap is None else overlap
        if max_chunk_size <= 0:
            raise ValueError("max_chunk_size 必须大于 0。")
        if overlap < 0 or overlap >= max_chunk_size:
            raise ValueError("overlap 必须大于等于 0 且小于 max_chunk_size。")
        if not elements:
            raise ValueError("elements 列表为空，无法分块。")

        # ── Step 1: group elements, respecting boundaries ──────────────────
        groups = []
        group = []
        group_len = 0

        def _flush():
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
                # Table — flush preceding group, then stand alone
                _flush()
                groups.append([(text, elem_type)])
                continue

            if elem_type in _BOUNDARY_TYPES:
                # Flush previous group so the Title starts fresh
                _flush()

            # Estimate length with separator if merging
            sep = 2 if group else 0
            if group and group_len + sep + elem_len > max_chunk_size:
                _flush()

            group.append((text, elem_type))
            group_len += sep + elem_len

        _flush()

        # ── Step 2: build chunk dicts, splitting overflow groups ──────────
        chunks = []
        for g in groups:
            texts = [t for t, _ in g]
            content = "\n\n".join(texts)
            if len(content) <= max_chunk_size:
                chunks.append({"content": content})
                continue

            # Single over-sized element — split by char offset
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

        # ── Step 3: assign index and run metadata_builder ─────────────────
        return [
            {
                "chunk_index": i,
                "content": c["content"],
                "metadata": metadata_builder(i),
            }
            for i, c in enumerate(chunks)
        ]


def estimate_flat_chunk_count(text, chunk_size=None, overlap=None):
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
    if parsed_text_length >= settings.KB_HIERARCHICAL_TEXT_THRESHOLD:
        return "hierarchical"
    if estimated_flat_chunk_count >= settings.KB_HIERARCHICAL_CHUNK_THRESHOLD:
        return "hierarchical"
    return "flat"


def build_document_chunks(text, metadata_builder, chunk_size=None, overlap=None):
    return ChunkService().build_chunks(
        text,
        metadata_builder,
        chunk_size=chunk_size,
        overlap=overlap,
    )


def build_document_chunks_from_elements(elements, metadata_builder, max_chunk_size=None, overlap=None):
    return ChunkService().build_chunks_from_elements(
        elements,
        metadata_builder,
        max_chunk_size=max_chunk_size,
        overlap=overlap,
    )
