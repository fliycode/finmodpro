from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("systemcheck.urls")),
    path("api/auth/", include("authentication.urls")),
    path("api/", include("rbac.urls")),
    path("api/knowledgebase/", include("knowledgebase.urls")),
    path("api/rag/", include("rag.urls")),
    path("api/chat/", include("chat.urls")),
]
