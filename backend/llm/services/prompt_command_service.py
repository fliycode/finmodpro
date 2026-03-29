from llm.services.prompt_query_service import build_prompt_config, resolve_prompt_path
from llm.services.prompt_service import clear_prompt_template_cache


def update_prompt_config(*, key, template):
    prompt_path = resolve_prompt_path(key)
    if not prompt_path.exists() or not prompt_path.is_file():
        raise FileNotFoundError("Prompt 模板不存在。")

    prompt_path.write_text(template, encoding="utf-8")
    clear_prompt_template_cache()
    return build_prompt_config(prompt_path)
