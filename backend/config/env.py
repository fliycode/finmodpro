"""
环境变量读取工具模块

提供类型安全的 env 读取函数。所有 Django 配置都应通过此模块获取环境变量，
而不是直接调用 os.getenv()，以确保类型转换一致且有合理的默认值。

SpringBoot 类比: 类似 application.yml 中的属性绑定，但这里是手动读取。
SpringBoot 用 @Value / @ConfigurationProperties 自动映射，Django 需要自行封装。
"""

import os


def get_env(name, default=None):
    """从环境变量获取字符串值。

    SpringBoot 类比: @Value("${name:default}")
    """
    return os.getenv(name, default)


def get_bool_env(name, default=False):
    """从环境变量获取布尔值。

    支持常见的 true 表示形式: 1 / true / yes / on（不区分大小写）。
    未设置时返回 default 值。

    SpringBoot 类比: @Value("${name:false}") + Boolean.parseBoolean()
    """
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_int_env(name, default):
    """从环境变量获取整数值。

    SpringBoot 类比: @Value("${name:0}") + Integer.parseInt()
    """
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def get_list_env(name, default):
    """从环境变量获取列表值（逗号分隔的字符串）。

    示例: "a,b,c" → ["a", "b", "c"]

    SpringBoot 类比: @Value("${name}") + String.split(",")
    """
    value = os.getenv(name)
    if value is None:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]
