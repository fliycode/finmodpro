"""
Prompt 基础服务（类比 SpringBoot 中 @Service 的模板渲染层）。
负责 Prompt 模板文件的加载、缓存和渲染。
模板文件存储在文件系统的 prompts/ 目录下，使用 Python 的 str.format() 进行变量替换。

类比：此服务类似于 SpringBoot 中配置了 Caffeine Cache 的模板工具类。
"""
from functools import lru_cache
from pathlib import Path

from config.settings import BASE_DIR


PROMPTS_DIR = BASE_DIR / "prompts"


@lru_cache(maxsize=32)
def load_prompt_template(template_name):
    """加载 Prompt 模板文件内容（带 LRU 缓存）。

    参数:
        template_name: str，相对于 PROMPTS_DIR 的模板文件路径（如 'chat/answer.txt'）。
    返回:
        str，模板文件的原始文本内容。
    """
    template_path = PROMPTS_DIR / template_name
    return template_path.read_text(encoding="utf-8")


def clear_prompt_template_cache():
    """清除 Prompt 模板的内存缓存。

    在模板文件被外部修改（写入更新）后调用，确保下次加载时读取最新内容。
    """
    load_prompt_template.cache_clear()


def render_prompt(template_name, **context):
    """加载并渲染 Prompt 模板。

    使用 Python 标准库的 str.format() 将上下文变量替换到模板中。
    模板使用 {variable_name} 语法定义占位符。

    参数:
        template_name: str，模板文件路径（相对于 PROMPTS_DIR）。
        **context: 关键字参数，模板变量的键值对（如 question="净利润情况如何？"）。
    返回:
        str，渲染后的最终 Prompt 文本。
    """
    return load_prompt_template(template_name).format(**context)
