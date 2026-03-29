from string import Formatter
from pathlib import PurePosixPath

from django.utils import timezone

from llm.services.prompt_service import PROMPTS_DIR


def _extract_template_variables(template):
    variables = []
    seen = set()

    for _, field_name, _, _ in Formatter().parse(template):
        if field_name and field_name not in seen:
            seen.add(field_name)
            variables.append(field_name)

    return variables


def list_prompt_configs():
    prompt_configs = []

    for prompt_path in sorted(PROMPTS_DIR.rglob("*.txt")):
        prompt_configs.append(build_prompt_config(prompt_path))

    return prompt_configs


def validate_prompt_key(key):
    relative_path = PurePosixPath(key)
    if relative_path.is_absolute() or ".." in relative_path.parts or not relative_path.parts:
        raise ValueError("非法的 prompt key。")
    if relative_path.suffix != ".txt":
        raise ValueError("非法的 prompt key。")
    return relative_path


def resolve_prompt_path(key):
    relative_path = validate_prompt_key(key)
    return PROMPTS_DIR / relative_path


def build_prompt_config(prompt_path):
    relative_path = prompt_path.relative_to(PROMPTS_DIR)
    template = prompt_path.read_text(encoding="utf-8")
    return {
        "key": relative_path.as_posix(),
        "category": relative_path.parts[0] if len(relative_path.parts) > 1 else "",
        "name": relative_path.name,
        "template": template,
        "variables": _extract_template_variables(template),
        "updated_at": timezone.datetime.fromtimestamp(
            prompt_path.stat().st_mtime,
            tz=timezone.get_current_timezone(),
        ),
    }
