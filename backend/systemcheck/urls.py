from django.urls import path

from systemcheck.controllers.health_controller import health_view


urlpatterns = [
    path("health", health_view, name="health"),
]
