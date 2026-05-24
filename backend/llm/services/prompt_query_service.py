"""
Prompt 查询服务（类比 SpringBoot 中 @Service 的只读查询层）。
负责枚举 Prompt 模板文件、提取模板变量、构建配置字典。
模板文件的 key 是其相对于 PROMPTS_DIR 的路径（如 'chat/answer.txt'）。
"""
from string import Formatter
from pathlib import PurePosixPath

from django.utils import timezone

from llm.services.prompt_service import PROMPTS_DIR


def _extract_template_variables(template):
    """从模板内容中提取所有 Python 格式化变量名。

    使用 string.Formatter().parse() 解析模板中的 {field_name} 占位符，
    去重后返回变量名列表。

    参数:
        template: str，模板原始文本。
    返回:
        list[str]，去重后的变量名列表。
    """
    variables = []
    seen = set()

    for _, field_name, _, _ in Formatter().parse(template):
        if field_name and field_name not in seen:
            seen.add(field_name)
            variables.append(field_name)

    return variables


def list_prompt_configs():
    """列出所有 Prompt 模板配置。

    遍历 PROMPTS_DIR 下所有 .txt 文件，逐个构建配置字典。

    返回:
        list[dict]，每个元素包含 key、category、name、template、variables、updated_at。
    """
    prompt_configs = []

    for prompt_path in sorted(PROMPTS_DIR.rglob("*.txt")):
        prompt_configs.append(build_prompt_config(prompt_path))

    return prompt_configs


def validate_prompt_key(key):
    """校验 Prompt 模板的 key 是否合法。

    校验规则：
    - key 不能是绝对路径
    - key 不能包含 ".."（防止目录遍历）
    - key 必须有路径部分（至少包含文件名）
    - key 必须以 .txt 结尾

    参数:
        key: str，从 URL 传递的 prompt key。
    返回:
        PurePosixPath，校验后的相对路径对象。
    异常:
        ValueError: 当 key 不合法时抛出。
    """
    relative_path = PurePosixPath(key)
    if relative_path.is_absolute() or ".." in relative_path.parts or not relative_path.parts:
        raise ValueError("非法的 prompt key。")
    if relative_path.suffix != ".txt":
        raise ValueError("非法的 prompt key。")
    return relative_path


def resolve_prompt_path(key):
    """将 key 解析为文件系统中的绝对路径。

    先校验 key 的合法性，再拼接为 PROMPTS_DIR 下的完整路径。

    参数:
        key: str，prompt 模板的相对路径（如 'chat/answer.txt'）。
    返回:
        Path，模板文件的绝对路径。
    """
    relative_path = validate_prompt_key(key)
    return PROMPTS_DIR / relative_path


def build_prompt_config(prompt_path):
    """为给定的模板文件构建配置字典。

    参数:
        prompt_path: Path 对象，模板文件的绝对路径。
    返回:
        dict，包含：
        - key: 相对路径（Posix 风格）
        - category: 第一级目录名作为分类
        - name: 文件名
        - template: 模板文本内容
        - variables: 模板变量名列表
        - updated_at: 文件的最后修改时间（携带当前时区）
    """
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
