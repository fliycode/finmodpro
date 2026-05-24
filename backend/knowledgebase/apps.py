"""
知识库应用配置模块。

类比 SpringBoot: 相当于 SpringBoot 的 @SpringBootApplication 注解类或
@Configuration 配置类，负责注册应用的基本元信息（名称、默认主键类型等）。
Django 在启动时读取此配置，将 knowledgebase 应用纳入项目体系。
"""
from django.apps import AppConfig


class KnowledgebaseConfig(AppConfig):
    """
    知识库应用配置类。

    类比 SpringBoot: 相当于 @Configuration + @ComponentScan 的组合，
    声明应用的名称和默认主键字段类型。

    属性:
        default_auto_field: 默认主键字段类型，BigAutoField 对应数据库 BIGINT AUTO_INCREMENT。
        name: 应用名称，用于在 Django 项目 settings.INSTALLED_APPS 中注册。
    """
    default_auto_field = "django.db.models.BigAutoField"
    name = "knowledgebase"
