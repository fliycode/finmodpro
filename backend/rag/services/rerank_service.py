def rerank_results(results):
    return sorted(results, key=lambda item: item["score"], reverse=True)
