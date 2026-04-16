from django.urls import path

from llm.controllers.fine_tune_controller import (
    FineTuneRunCallbackView,
    FineTuneRunDetailView,
    FineTuneRunListCreateView,
)
from llm.controllers.evaluation_controller import EvalRecordListCreateView
from llm.controllers.model_config_controller import (
    ModelConfigActivationView,
    ModelConfigConnectionTestView,
    ModelConfigDetailView,
    ModelConfigListView,
)
from llm.controllers.prompt_config_controller import PromptConfigListView, PromptConfigUpdateView


urlpatterns = [
    path("evaluations", EvalRecordListCreateView.as_view(), name="evaluation-list-create-legacy"),
    path("evaluations/", EvalRecordListCreateView.as_view(), name="evaluation-list-create"),
    path("fine-tunes", FineTuneRunListCreateView.as_view(), name="fine-tune-list-create-legacy"),
    path("fine-tunes/", FineTuneRunListCreateView.as_view(), name="fine-tune-list-create"),
    path(
        "fine-tunes/<int:fine_tune_run_id>",
        FineTuneRunDetailView.as_view(),
        name="fine-tune-detail-legacy",
    ),
    path(
        "fine-tunes/<int:fine_tune_run_id>/",
        FineTuneRunDetailView.as_view(),
        name="fine-tune-detail",
    ),
    path(
        "fine-tunes/<int:fine_tune_run_id>/callback",
        FineTuneRunCallbackView.as_view(),
        name="fine-tune-callback-legacy",
    ),
    path(
        "fine-tunes/<int:fine_tune_run_id>/callback/",
        FineTuneRunCallbackView.as_view(),
        name="fine-tune-callback",
    ),
    path(
        "model-configs/test-connection",
        ModelConfigConnectionTestView.as_view(),
        name="model-config-test-connection-legacy",
    ),
    path(
        "model-configs/test-connection/",
        ModelConfigConnectionTestView.as_view(),
        name="model-config-test-connection",
    ),
    path(
        "model-configs/<int:model_config_id>",
        ModelConfigDetailView.as_view(),
        name="model-config-detail-legacy",
    ),
    path(
        "model-configs/<int:model_config_id>/",
        ModelConfigDetailView.as_view(),
        name="model-config-detail",
    ),
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
    path(
        "prompt-configs/<path:key>",
        PromptConfigUpdateView.as_view(),
        name="prompt-config-update-legacy",
    ),
    path(
        "prompt-configs/<path:key>/",
        PromptConfigUpdateView.as_view(),
        name="prompt-config-update",
    ),
    path("prompt-configs", PromptConfigListView.as_view(), name="prompt-config-list-legacy"),
    path("prompt-configs/", PromptConfigListView.as_view(), name="prompt-config-list"),
    path("model-configs", ModelConfigListView.as_view(), name="model-config-list-legacy"),
    path("model-configs/", ModelConfigListView.as_view(), name="model-config-list"),
]
