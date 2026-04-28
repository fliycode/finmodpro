import os
import socket
import sys
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException

BACKEND_ROOT = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from llm.services.fine_tune_runner_client import run_remote_fine_tune  # noqa: E402

app = FastAPI(title="FinModPro LLaMA-Factory Runner Agent")
JOB_STORE: dict[str, dict] = {}
DEFAULT_WORK_DIR = "/tmp/finmodpro-fine-tunes"


def get_runner_name():
    return os.environ.get("FINE_TUNE_AGENT_RUNNER_NAME") or socket.gethostname()


def _require_agent_token(authorization: str):
    expected_token = os.environ.get("FINE_TUNE_AGENT_TOKEN", "").strip()
    if not expected_token:
        raise HTTPException(status_code=503, detail="Runner agent token is not configured.")
    incoming = (authorization or "").strip()
    if not incoming.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid runner agent token.")
    token = incoming[7:].strip()
    if token != expected_token:
        raise HTTPException(status_code=401, detail="Invalid runner agent token.")


def _normalize_job_payload(payload: dict):
    fine_tune_run_id = payload.get("fine_tune_run_id")
    api_base_url = (payload.get("platform") or {}).get("api_base_url", "").strip().rstrip("/")
    callback_token = (payload.get("callback") or {}).get("token", "").strip()
    work_dir = (
        (payload.get("runner_target") or {}).get("default_work_dir", "").strip()
        or os.environ.get("FINE_TUNE_AGENT_WORK_DIR", "").strip()
        or DEFAULT_WORK_DIR
    )
    if not fine_tune_run_id:
        raise ValueError("fine_tune_run_id is required.")
    if not api_base_url:
        raise ValueError("platform.api_base_url is required.")
    if not callback_token:
        raise ValueError("callback.token is required.")
    return {
        "fine_tune_run_id": int(fine_tune_run_id),
        "api_base_url": api_base_url,
        "token": callback_token,
        "work_dir": work_dir,
        "deployment_endpoint": (payload.get("deployment") or {}).get("endpoint", "").strip(),
        "deployment_model_name": (payload.get("deployment") or {}).get("model_name", "").strip(),
    }


def _run_job(job_id: str, payload: dict):
    JOB_STORE[job_id].update({"status": "running", "failure_reason": ""})
    try:
        job_args = _normalize_job_payload(payload)
        run_remote_fine_tune(
            api_base_url=job_args["api_base_url"],
            fine_tune_run_id=job_args["fine_tune_run_id"],
            token=job_args["token"],
            work_dir=job_args["work_dir"],
            dry_run=False,
            deployment_endpoint=job_args["deployment_endpoint"],
            deployment_model_name=job_args["deployment_model_name"],
        )
    except Exception as exc:  # noqa: BLE001
        JOB_STORE[job_id].update({"status": "failed", "failure_reason": str(exc)})
        return
    JOB_STORE[job_id].update({"status": "succeeded", "failure_reason": ""})


def _start_job_thread(job_id: str, payload: dict):
    thread = threading.Thread(target=_run_job, args=(job_id, payload), daemon=True)
    thread.start()
    return thread


@app.get("/health")
def health():
    return {"status": "ok", "runner_name": get_runner_name()}


@app.post("/api/v1/fine-tune-jobs")
def submit_fine_tune_job(payload: dict, authorization: str = Header(default="")):
    _require_agent_token(authorization)
    try:
        normalized = _normalize_job_payload(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job_id = f"gpu-job-{uuid.uuid4().hex[:12]}"
    JOB_STORE[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "runner_name": get_runner_name(),
        "fine_tune_run_id": normalized["fine_tune_run_id"],
        "failure_reason": "",
    }
    _start_job_thread(job_id, payload)
    return {
        "job_id": job_id,
        "status": "queued",
        "runner_name": get_runner_name(),
    }


@app.get("/api/v1/fine-tune-jobs/{job_id}")
def get_fine_tune_job(job_id: str, authorization: str = Header(default="")):
    _require_agent_token(authorization)
    job = JOB_STORE.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job
