from rag.services.retrieval_service import build_retrieval_response, retrieve


def _build_answer(question, citations):
    if not citations:
        return f"针对“{question}”，当前知识库中未检索到相关资料，无法生成基于引用的回答。"

    lead_citation = citations[0]
    return (
        f"针对“{question}”，当前可参考《{lead_citation['document_title']}》"
        f"（{lead_citation['page_label']}）：{lead_citation['snippet']}"
    )


def ask_question(*, question, filters=None, top_k=5):
    retrieval_results = retrieve(query=question, filters=filters, top_k=top_k)
    retrieval_payload = build_retrieval_response(query=question, results=retrieval_results)
    citations = retrieval_payload["citations"]
    return {
        "question": question,
        "query": question,
        "answer": _build_answer(question, citations),
        "citations": citations,
    }
