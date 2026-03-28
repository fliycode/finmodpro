from django.urls import path

from rag.controllers import retrieval_query_view


urlpatterns = [
    path("retrieval/query", retrieval_query_view, name="rag-retrieval-query"),
]
