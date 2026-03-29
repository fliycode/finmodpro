from string import Formatter

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
        relative_path = prompt_path.relative_to(PROMPTS_DIR)
        template = prompt_path.read_text(encoding="utf-8")
        prompt_configs.append(
            {
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
        )

    return prompt_configs
