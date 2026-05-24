"""
llm 应用的 Django AppConfig 配置类（类比 SpringBoot 的 @Configuration + @ComponentScan）。
该文件定义了 LlmConfig 类，告诉 Django 此 app 的名称和默认主键字段类型。
Django 启动时会读取此配置，完成模型注册、信号绑定等初始化工作。
"""
from django.apps import AppConfig


class LlmConfig(AppConfig):
    """llm 应用的配置类。

    类比 SpringBoot 中一个 @Configuration 标注的配置类，但更轻量。
    - default_auto_field: 指定自动生成主键的字段类型（BigAutoField = 大整数自增）
    - name: 应用名称，Django 用此标识符来引用本应用（对应 INSTALLED_APPS 中的 'llm'）
    """
    default_auto_field = "django.db.models.BigAutoField"
    name = "llm"

