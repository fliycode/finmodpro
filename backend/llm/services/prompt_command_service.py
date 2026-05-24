"""
Prompt 命令服务（类比 SpringBoot 中 @Service 的写操作层）。
负责 Prompt 模板文件的内容更新。
在更新文件后会清除模板缓存，确保下次渲染使用最新内容。
"""
from llm.services.prompt_query_service import build_prompt_config, resolve_prompt_path
from llm.services.prompt_service import clear_prompt_template_cache


def update_prompt_config(*, key, template):
    """更新指定 Prompt 模板文件的内容。

    参数:
        key: str，模板文件的相对路径（如 'chat/answer.txt'）。
        template: str，新的模板内容（完整替换原有内容）。
    返回:
        dict，更新后的模板配置（包含 key、category、variables 等）。
    异常:
        FileNotFoundError: 当 key 对应的模板文件不存在时抛出。
    """
    prompt_path = resolve_prompt_path(key)
    if not prompt_path.exists() or not prompt_path.is_file():
        raise FileNotFoundError("Prompt 模板不存在。")

    prompt_path.write_text(template, encoding="utf-8")
    clear_prompt_template_cache()
    return build_prompt_config(prompt_path)
