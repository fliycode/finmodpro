"""
RAG 应用配置类。
类比 SpringBoot: 相当于 @SpringBootApplication 中的组件扫描声明，告诉 Django 此应用的名称和主键字段类型。
"""

from django.apps import AppConfig


class RagConfig(AppConfig):
    """RAG（检索增强生成）应用的配置入口。

    类比 SpringBoot: 等同于 @Configuration + @ComponentScan 的组合，
    注册 rag 模块到 Django 应用容器中。
    """
    # 默认主键类型，使用 BigAutoField（64位自增整数）
    # 类比 SpringBoot: 对应 JPA 中 @Id 字段的默认生成策略
    default_auto_field = "django.db.models.BigAutoField"
    # 应用名称，用于在 INSTALLED_APPS 中注册
    # 类比 SpringBoot: 对应 spring.application.name 或模块名
    name = "rag"
