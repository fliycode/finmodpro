import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
MODULE_SPEC = importlib.util.spec_from_file_location("llamafactory_runner_agent_app", APP_PATH)
APP_MODULE = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(APP_MODULE)


class RunnerAgentAppTests(unittest.TestCase):
    def setUp(self):
        self.original_token = os.environ.get("FINE_TUNE_AGENT_TOKEN")
        os.environ["FINE_TUNE_AGENT_TOKEN"] = "agent-secret"
        APP_MODULE.JOB_STORE.clear()
        self.client = TestClient(APP_MODULE.app)

    def tearDown(self):
        APP_MODULE.JOB_STORE.clear()
        if self.original_token is None:
            os.environ.pop("FINE_TUNE_AGENT_TOKEN", None)
        else:
            os.environ["FINE_TUNE_AGENT_TOKEN"] = self.original_token

    def test_submit_job_requires_valid_bearer_token(self):
        response = self.client.post(
            "/api/v1/fine-tune-jobs",
            json={},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Invalid runner agent token.")

    @patch.object(APP_MODULE, "_start_job_thread")
    def test_submit_job_enqueues_background_run(self, mock_start_job_thread):
        response = self.client.post(
            "/api/v1/fine-tune-jobs",
            headers={"Authorization": "Bearer agent-secret"},
            json={
                "fine_tune_run_id": 8,
                "platform": {"api_base_url": "https://finmodpro.example"},
                "runner_target": {"default_work_dir": "/srv/llamafactory/jobs"},
                "callback": {"token": "ftcb_job_token"},
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "queued")
        self.assertEqual(payload["runner_name"], APP_MODULE.get_runner_name())
        mock_start_job_thread.assert_called_once()

    @patch.object(APP_MODULE, "run_remote_fine_tune")
    def test_run_job_uses_runner_client_contract(self, mock_run_remote_fine_tune):
        APP_MODULE.JOB_STORE["job-1"] = {"status": "queued"}

        APP_MODULE._run_job(
            "job-1",
            {
                "fine_tune_run_id": 8,
                "platform": {"api_base_url": "https://finmodpro.example"},
                "runner_target": {"default_work_dir": "/srv/llamafactory/jobs"},
                "callback": {"token": "ftcb_job_token"},
            },
        )

        mock_run_remote_fine_tune.assert_called_once_with(
            api_base_url="https://finmodpro.example",
            fine_tune_run_id=8,
            token="ftcb_job_token",
            work_dir="/srv/llamafactory/jobs",
            dry_run=False,
            deployment_endpoint="",
            deployment_model_name="",
        )
        self.assertEqual(APP_MODULE.JOB_STORE["job-1"]["status"], "succeeded")


if __name__ == "__main__":
    unittest.main()
