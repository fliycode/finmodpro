import json
from pathlib import Path

from django.conf import settings


def _build_placeholder_samples(*, fine_tune_run):
    dataset_label = fine_tune_run.dataset_name or "未命名训练集"
    prompt = (
        f"你是 FinModPro 的训练样本导出占位数据。"
        f" 数据集：{dataset_label}。"
        f" 基础模型：{fine_tune_run.base_model.model_name}。"
    )
    response = fine_tune_run.notes or "当前阶段尚未接入真实监督数据导出，这是一条占位样本。"
    return [{"messages": [{"role": "user", "content": prompt}, {"role": "assistant", "content": response}]}]


def _write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def create_export_bundle(*, fine_tune_run):
    export_root = Path(settings.FINE_TUNE_EXPORT_ROOT)
    export_dir = export_root / fine_tune_run.run_key
    export_dir.mkdir(parents=True, exist_ok=True)

    train_samples = _build_placeholder_samples(fine_tune_run=fine_tune_run)
    manifest = {
        "fine_tune_run_id": fine_tune_run.id,
        "run_key": fine_tune_run.run_key,
        "base_model_id": fine_tune_run.base_model_id,
        "base_model_name": fine_tune_run.base_model.name,
        "base_model_provider": fine_tune_run.base_model.provider,
        "dataset_name": fine_tune_run.dataset_name,
        "dataset_version": fine_tune_run.dataset_version,
        "task_type": "chat",
        "sample_count": len(train_samples),
        "format": "llamafactory-conversations",
        "created_by": "finmodpro",
        "export_status": "ready",
        "placeholder": True,
        "source_snapshot": {
            "strategy": fine_tune_run.strategy,
            "notes": fine_tune_run.notes,
        },
    }
    dataset_info = {
        "finmodpro_train": {
            "file_name": "train.jsonl",
            "formatting": "sharegpt",
            "columns": {"messages": "messages"},
            "tags": {"role_tag": "role", "content_tag": "content", "user_tag": "user", "assistant_tag": "assistant"},
        }
    }

    _write_json(export_dir / "manifest.json", manifest)
    _write_json(export_dir / "dataset_info.json", dataset_info)
    (export_dir / "train.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in train_samples) + "\n",
        encoding="utf-8",
    )
    (export_dir / "README.md").write_text(
        "# FinModPro fine-tune export\n\n"
        "This phase-one export is intentionally placeholder-backed until a real supervised dataset "
        "builder is wired into the control plane.\n",
        encoding="utf-8",
    )

    return {
        "export_path": str(export_dir),
        "dataset_manifest": manifest,
    }


def get_export_bundle_detail(*, fine_tune_run):
    export_dir = Path(fine_tune_run.export_path or "")
    if not export_dir.exists():
        return {
            "fine_tune_run_id": fine_tune_run.id,
            "run_key": fine_tune_run.run_key,
            "export_path": fine_tune_run.export_path,
            "manifest": {},
            "files": [],
        }

    manifest_path = export_dir / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    files = []
    for path in sorted(export_dir.iterdir()):
        files.append(
            {
                "name": path.name,
                "path": str(path),
                "size_bytes": path.stat().st_size if path.is_file() else 0,
            }
        )

    return {
        "fine_tune_run_id": fine_tune_run.id,
        "run_key": fine_tune_run.run_key,
        "export_path": str(export_dir),
        "manifest": manifest,
        "files": files,
    }
