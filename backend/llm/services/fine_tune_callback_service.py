import hashlib
import hmac

from django.conf import settings
from django.utils import timezone

from llm.models import FineTuneRun, ModelConfig
from llm.services.litellm_alias_service import provision_litellm_alias


def hash_callback_token(token):
    secret = settings.FINE_TUNE_CALLBACK_SECRET.encode("utf-8")
    return hmac.new(secret, token.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_callback_token(*, fine_tune_run, token):
    if not token or not fine_tune_run.callback_token_hash:
        return False
    expected_hash = hash_callback_token(token)
    return hmac.compare_digest(expected_hash, fine_tune_run.callback_token_hash)


def register_candidate_model_config(*, fine_tune_run):
    if fine_tune_run.registered_model_config_id:
        return fine_tune_run.registered_model_config

    endpoint = fine_tune_run.deployment_endpoint.strip()
    model_name = fine_tune_run.deployment_model_name.strip()
    if not endpoint or not model_name:
        return None

    config_name = f"{fine_tune_run.base_model.name}-{fine_tune_run.run_key}"
    model_config = ModelConfig.objects.create(
        name=config_name[:255],
        capability=fine_tune_run.base_model.capability,
        provider=ModelConfig.PROVIDER_LITELLM,
        model_name=model_name,
        endpoint=endpoint,
        options={},
        is_active=False,
    )
    fine_tune_run.registered_model_config = model_config
    fine_tune_run.save(update_fields=["registered_model_config", "updated_at"])
    return model_config


def apply_runner_callback(*, fine_tune_run, payload):
    now = timezone.now()
    for key in ("external_job_id", "deployment_endpoint", "deployment_model_name", "failure_reason"):
        if key in payload:
            setattr(fine_tune_run, key, payload.get(key) or "")

    incoming_status = payload.get("status")
    if incoming_status:
        fine_tune_run.status = incoming_status
        if incoming_status == FineTuneRun.STATUS_RUNNING and fine_tune_run.started_at is None:
            fine_tune_run.started_at = now
        if incoming_status in {FineTuneRun.STATUS_SUCCEEDED, FineTuneRun.STATUS_FAILED}:
            fine_tune_run.finished_at = now

    if "metrics" in payload:
        fine_tune_run.metrics = payload.get("metrics") or {}
    if "artifact_manifest" in payload:
        fine_tune_run.artifact_manifest = payload.get("artifact_manifest") or {}
        adapter_path = fine_tune_run.artifact_manifest.get("adapter_path", "")
        if adapter_path and not fine_tune_run.artifact_path:
            fine_tune_run.artifact_path = adapter_path

    fine_tune_run.last_heartbeat_at = now
    fine_tune_run.save()

    if fine_tune_run.status == FineTuneRun.STATUS_SUCCEEDED:
        alias_artifact = provision_litellm_alias(fine_tune_run=fine_tune_run)
        if alias_artifact:
            updated_artifact_manifest = {
                **(fine_tune_run.artifact_manifest or {}),
                **alias_artifact,
            }
            fine_tune_run.artifact_manifest = updated_artifact_manifest
            fine_tune_run.save(update_fields=["artifact_manifest", "updated_at"])
        register_candidate_model_config(fine_tune_run=fine_tune_run)

    fine_tune_run.refresh_from_db()
    return fine_tune_run
