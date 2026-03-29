from django.conf import settings
from django.contrib import admin
from django.conf.urls.static import static
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("systemcheck.urls")),
    path("api/auth/", include("authentication.urls")),
    path("api/", include("rbac.urls")),
    path("api/knowledgebase/", include("knowledgebase.urls")),
    path("api/ops/", include("llm.urls")),
    path("api/rag/", include("rag.urls")),
    path("api/chat/", include("chat.urls")),
    path("api/risk/", include("risk.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
