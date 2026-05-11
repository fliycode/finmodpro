from celery import shared_task


@shared_task(name="rag.run_evaluation_task")
def run_evaluation_task(mode="all"):
    from rag.services.retrieval_evaluation_service import (
        evaluate_generation_fixture,
        evaluate_retrieval_fixture,
    )

    data = {}
    if mode in ("retrieval", "all"):
        data["retrieval"] = evaluate_retrieval_fixture()
    if mode in ("generation", "all"):
        data["generation"] = evaluate_generation_fixture()
    return data
