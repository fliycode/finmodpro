import json
import subprocess
from pathlib import Path
from urllib import request


def _build_api_url(api_base_url, path):
    return f"{api_base_url.rstrip('/')}{path}"


def _send_json_request(*, url, method, token, payload=None, timeout=30):
    headers = {
        "Content-Type": "application/json",
        "X-Fine-Tune-Token": token,
    }
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    response = request.urlopen(
        request.Request(url, data=body, headers=headers, method=method),
        timeout=timeout,
    )
    response_payload = json.loads(response.read().decode("utf-8"))
    if response_payload.get("code") not in {0, 200, 201}:
        raise RuntimeError(response_payload.get("message") or "Runner API request failed.")
    return response_payload.get("data") or {}


def fetch_runner_spec(*, api_base_url, fine_tune_run_id, token):
    return _send_json_request(
        url=_build_api_url(api_base_url, f"/api/ops/fine-tunes/{fine_tune_run_id}/runner-spec/"),
        method="GET",
        token=token,
    )


def report_runner_status(*, api_base_url, fine_tune_run_id, token, payload):
    return _send_json_request(
        url=_build_api_url(api_base_url, f"/api/ops/fine-tunes/{fine_tune_run_id}/callback/"),
        method="POST",
        token=token,
        payload=payload,
    )


def materialize_export_bundle(*, spec, work_dir):
    export_bundle = spec.get("export_bundle") or {}
    export_path = Path(export_bundle.get("export_path") or "")
    if export_path.exists():
        return str(export_path)

    run_key = spec.get("run_key") or "fine-tune-run"
    target_dir = Path(work_dir) / run_key
    target_dir.mkdir(parents=True, exist_ok=True)

    files = export_bundle.get("files") or []
    if not files:
        raise FileNotFoundError("No export bundle files available for runner.")

    for file_item in files:
        file_name = file_item.get("name") or ""
        file_url = file_item.get("url") or ""
        if not file_name or not file_url:
            raise FileNotFoundError(f"Missing downloadable file contract for {file_name or 'unknown file'}.")
        response = request.urlopen(file_url, timeout=30)
        (target_dir / file_name).write_bytes(response.read())

    return str(target_dir)


def build_llamafactory_command(*, spec, export_dir, output_dir):
    training_job = spec.get("training_job") or {}
    training_config = training_job.get("training_config") or {}

    command = [
        "llamafactory-cli",
        "train",
        "--stage",
        "sft",
        "--do_train",
        "true",
        "--model_name_or_path",
        training_job.get("base_model_name") or "",
        "--dataset_dir",
        str(export_dir),
        "--dataset",
        "finmodpro_train",
        "--finetuning_type",
        training_job.get("strategy") or "lora",
        "--output_dir",
        str(output_dir),
        "--overwrite_output_dir",
        "true",
    ]

    option_mapping = {
        "epochs": "--num_train_epochs",
        "learning_rate": "--learning_rate",
        "batch_size": "--per_device_train_batch_size",
        "cutoff_len": "--cutoff_len",
    }
    for config_key, cli_flag in option_mapping.items():
        value = training_config.get(config_key)
        if value is None or value == "":
            continue
        command.extend([cli_flag, str(value)])

    return command


def run_remote_fine_tune(
    *,
    api_base_url,
    fine_tune_run_id,
    token,
    work_dir,
    dry_run=False,
    deployment_endpoint="",
    deployment_model_name="",
):
    spec = fetch_runner_spec(
        api_base_url=api_base_url,
        fine_tune_run_id=fine_tune_run_id,
        token=token,
    )
    export_dir = materialize_export_bundle(spec=spec, work_dir=work_dir)
    output_dir = Path(work_dir) / spec["run_key"] / "artifacts"
    output_dir.mkdir(parents=True, exist_ok=True)
    command = build_llamafactory_command(
        spec=spec,
        export_dir=export_dir,
        output_dir=str(output_dir),
    )

    if dry_run:
        return {
            "spec": spec,
            "export_dir": export_dir,
            "output_dir": str(output_dir),
            "command": command,
        }

    external_job_id = f"local-llamafactory-{spec['run_key']}"
    report_runner_status(
        api_base_url=api_base_url,
        fine_tune_run_id=fine_tune_run_id,
        token=token,
        payload={"status": "running", "external_job_id": external_job_id},
    )

    try:
        subprocess.run(command, check=True, cwd=export_dir)
    except subprocess.CalledProcessError as exc:
        report_runner_status(
            api_base_url=api_base_url,
            fine_tune_run_id=fine_tune_run_id,
            token=token,
            payload={"status": "failed", "external_job_id": external_job_id, "failure_reason": str(exc)},
        )
        raise

    callback_payload = {
        "status": "succeeded",
        "external_job_id": external_job_id,
        "artifact_manifest": {"adapter_path": str(output_dir)},
    }
    if deployment_endpoint:
        callback_payload["deployment_endpoint"] = deployment_endpoint
    if deployment_model_name:
        callback_payload["deployment_model_name"] = deployment_model_name
    report_runner_status(
        api_base_url=api_base_url,
        fine_tune_run_id=fine_tune_run_id,
        token=token,
        payload=callback_payload,
    )
    return {
        "spec": spec,
        "export_dir": export_dir,
        "output_dir": str(output_dir),
        "command": command,
        "callback_payload": callback_payload,
    }
