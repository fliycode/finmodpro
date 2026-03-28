from rag.models import RetrievalLog


def create_retrieval_log(
    *,
    query,
    top_k,
    filters,
    results,
    source,
    duration_ms=None,
    metadata=None,
):
    return RetrievalLog.objects.create(
        query=query,
        top_k=int(top_k),
        filters=filters or {},
        result_count=len(results),
        source=source,
        metadata=metadata or {},
        duration_ms=duration_ms,
    )
