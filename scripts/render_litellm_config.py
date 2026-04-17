#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from llm.services.litellm_config_render_service import build_rendered_litellm_config  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(description="Render LiteLLM base config with generated fine-tune aliases.")
    parser.add_argument("--base-config", default=str(REPO_ROOT / "deploy" / "litellm" / "config.yaml"))
    parser.add_argument("--generated-root", default=str(REPO_ROOT / "deploy" / "litellm" / "generated"))
    parser.add_argument("--output", default=str(REPO_ROOT / "deploy" / "litellm" / "rendered.config.yaml"))
    return parser.parse_args()


def main():
    args = parse_args()
    result = build_rendered_litellm_config(
        base_config_path=args.base_config,
        generated_root=args.generated_root,
        output_path=args.output,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
