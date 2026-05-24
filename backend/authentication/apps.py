"""
Django App 配置类

每个 Django app 必须有一个 AppConfig 子类，在 INSTALLED_APPS 中注册后，
Django 通过此类识别和管理应用。

SpringBoot 类比: @SpringBootApplication 或 @Configuration 类，
但功能更轻量，主要用于标识应用名称和默认主键类型。
"""

from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"  # 默认使用 BIGINT 自增主键
    name = "authentication"  # 应用名称，需与 INSTALLED_APPS 中的路径一致
