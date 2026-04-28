from django.conf import settings

from knowledgebase.services.chunk_service import (
    build_document_chunks,
    build_document_chunks_from_elements,
)


def build_hierarchical_document_chunks(
    *,
    text,
    elements,
    section_metadata_builder,
    child_metadata_builder,
):
    if elements:
        sections = build_document_chunks_from_elements(
            elements,
            metadata_builder=section_metadata_builder,
            max_chunk_size=settings.KB_SECTION_CHUNK_SIZE,
            overlap=settings.KB_SECTION_CHUNK_OVERLAP,
        )
    else:
        sections = build_document_chunks(
            text,
            metadata_builder=section_metadata_builder,
            chunk_size=settings.KB_SECTION_CHUNK_SIZE,
            overlap=settings.KB_SECTION_CHUNK_OVERLAP,
        )

    child_chunks = []
    child_chunk_index = 0
    for section in sections:
        section_children = build_document_chunks(
            section["content"],
            metadata_builder=lambda index, section=section: child_metadata_builder(section, index),
        )
        for child in section_children:
            child_chunks.append(
                {
                    **child,
                    "chunk_index": child_chunk_index,
                    "chunk_index_in_section": child["chunk_index"],
                    "section_index": section["chunk_index"],
                }
            )
            child_chunk_index += 1

    return {
        "sections": sections,
        "child_chunks": child_chunks,
    }
