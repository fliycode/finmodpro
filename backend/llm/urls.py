from django.urls import path

from llm.controllers.model_config_controller import ModelConfigActivationView, ModelConfigListView


urlpatterns = [
    path(
        "model-configs/<int:model_config_id>/activation",
        ModelConfigActivationView.as_view(),
        name="model-config-activation-legacy",
    ),
    path(
        "model-configs/<int:model_config_id>/activation/",
        ModelConfigActivationView.as_view(),
        name="model-config-activation",
    ),
    path("model-configs", ModelConfigListView.as_view(), name="model-config-list-legacy"),
    path("model-configs/", ModelConfigListView.as_view(), name="model-config-list"),
]
