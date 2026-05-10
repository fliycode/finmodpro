from django.urls import path

from rag.controllers import retrieval_query_view
from rag.controllers.evaluation_controller import RagEvaluationView

urlpatterns = [
    path("retrieval/query", retrieval_query_view, name="rag-retrieval-query"),
    path("evaluations", RagEvaluationView.as_view(), name="rag-evaluation-legacy"),
    path("evaluations/", RagEvaluationView.as_view(), name="rag-evaluation"),
]
