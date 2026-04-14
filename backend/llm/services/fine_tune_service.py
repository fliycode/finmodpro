from llm.models import FineTuneRun, ModelConfig


def list_fine_tune_runs(*, base_model_id=None):
    queryset = FineTuneRun.objects.select_related("base_model").order_by("-created_at", "-id")
    if base_model_id:
        queryset = queryset.filter(base_model_id=base_model_id)
    return queryset


def get_fine_tune_run(*, fine_tune_run_id):
    return FineTuneRun.objects.select_related("base_model").filter(id=fine_tune_run_id).first()


def create_fine_tune_run(*, payload):
    base_model_id = payload.pop("base_model_id")
    base_model = ModelConfig.objects.filter(id=base_model_id).first()
    if base_model is None:
        raise ValueError("模型配置不存在。")

    fine_tune_run = FineTuneRun.objects.create(base_model=base_model, **payload)
    fine_tune_run.refresh_from_db()
    return fine_tune_run


def update_fine_tune_run(*, fine_tune_run, payload):
    incoming_metrics = payload.pop("metrics", None)
    for key, value in payload.items():
        setattr(fine_tune_run, key, value)
    if incoming_metrics is not None:
        fine_tune_run.metrics = incoming_metrics
    fine_tune_run.save()
    fine_tune_run.refresh_from_db()
    return fine_tune_run
