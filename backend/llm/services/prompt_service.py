from functools import lru_cache
from pathlib import Path

from config.settings import BASE_DIR


PROMPTS_DIR = BASE_DIR / "prompts"


@lru_cache(maxsize=32)
def load_prompt_template(template_name):
    template_path = PROMPTS_DIR / template_name
    return template_path.read_text(encoding="utf-8")


def clear_prompt_template_cache():
    load_prompt_template.cache_clear()


def render_prompt(template_name, **context):
    return load_prompt_template(template_name).format(**context)
