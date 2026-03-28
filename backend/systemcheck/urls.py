from django.urls import path

from systemcheck.controllers.health_controller import HealthView


urlpatterns = [
    path("health", HealthView.as_view(), name="health-legacy"),
    path("health/", HealthView.as_view(), name="health"),
]
