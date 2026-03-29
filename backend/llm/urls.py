from django.urls import path

from llm.controllers.model_config_controller import ModelConfigListView


urlpatterns = [
    path("model-configs", ModelConfigListView.as_view(), name="model-config-list-legacy"),
    path("model-configs/", ModelConfigListView.as_view(), name="model-config-list"),
]
