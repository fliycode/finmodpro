import secrets

from django.utils import timezone

from llm.models import FineTuneRun, ModelConfig
from llm.services.fine_tune_callback_service import hash_callback_token
from llm.services.fine_tune_export_service import create_export_bundle


def list_fine_tune_runs(*, base_model_id=None):
    queryset = FineTuneRun.objects.select_related("base_model", "registered_model_config").order_by("-created_at", "-id")
    if base_model_id:
        queryset = queryset.filter(base_model_id=base_model_id)
    return queryset


def get_fine_tune_run(*, fine_tune_run_id):
    return FineTuneRun.objects.select_related("base_model", "registered_model_config").filter(id=fine_tune_run_id).first()


def create_fine_tune_run(*, payload):
    base_model_id = payload.pop("base_model_id")
    base_model = ModelConfig.objects.filter(id=base_model_id).first()
    if base_model is None:
        raise ValueError("模型配置不存在。")

    now = timezone.now()
    run_key = f"ft-{now.strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(3)}"
    callback_token = f"ftcb_{secrets.token_urlsafe(24)}"
    fine_tune_run = FineTuneRun.objects.create(
        base_model=base_model,
        run_key=run_key,
        queued_at=now,
        callback_token_hash=hash_callback_token(callback_token),
        dataset_manifest={"dataset_name": payload.get("dataset_name", ""), "export_status": "pending"},
        training_config=payload.pop("training_config", {}),
        runner_name=payload.pop("runner_name", ""),
        **payload,
    )
    export_result = create_export_bundle(fine_tune_run=fine_tune_run)
    fine_tune_run.export_path = export_result["export_path"]
    fine_tune_run.dataset_manifest = export_result["dataset_manifest"]
    fine_tune_run.save(update_fields=["export_path", "dataset_manifest", "updated_at"])
    fine_tune_run.refresh_from_db()
    fine_tune_run.callback_token = callback_token
    return fine_tune_run


def update_fine_tune_run(*, fine_tune_run, payload):
    incoming_metrics = payload.pop("metrics", None)
    incoming_artifact_manifest = payload.pop("artifact_manifest", None)
    for key, value in payload.items():
        setattr(fine_tune_run, key, value)
    if incoming_metrics is not None:
        fine_tune_run.metrics = incoming_metrics
    if incoming_artifact_manifest is not None:
        fine_tune_run.artifact_manifest = incoming_artifact_manifest
    fine_tune_run.save()
    fine_tune_run.refresh_from_db()
    return fine_tune_run
