#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from llm.services.fine_tune_runner_client import run_remote_fine_tune  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Minimal FinModPro LLaMA-Factory runner client.")
    parser.add_argument("--api-base-url", required=True, help="FinModPro API base URL, e.g. http://127.0.0.1:8000")
    parser.add_argument("--run-id", required=True, type=int, help="FineTuneRun id")
    parser.add_argument("--token", required=True, help="Fine-tune callback token")
    parser.add_argument("--work-dir", default=str(REPO_ROOT / ".runner-workdir"), help="Working directory for bundle/artifacts")
    parser.add_argument("--deployment-endpoint", default="", help="Inference endpoint to report back on success")
    parser.add_argument("--deployment-model-name", default="", help="LiteLLM alias or upstream model name to report back on success")
    parser.add_argument("--dry-run", action="store_true", help="Fetch spec and build command without executing or posting callbacks")
    return parser.parse_args()


def main():
    args = parse_args()
    result = run_remote_fine_tune(
        api_base_url=args.api_base_url,
        fine_tune_run_id=args.run_id,
        token=args.token,
        work_dir=args.work_dir,
        dry_run=args.dry_run,
        deployment_endpoint=args.deployment_endpoint,
        deployment_model_name=args.deployment_model_name,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
