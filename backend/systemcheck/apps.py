"""
Systemcheck 应用配置 —— 注册系统巡检模块到 Django 应用容器。

类比 SpringBoot: 相当于 @SpringBootApplication 中的 @Configuration + @ComponentScan，
声明应用的名称和默认主键字段类型。
"""
from django.apps import AppConfig


class SystemcheckConfig(AppConfig):
    """
    系统巡检应用配置类。

    类比 SpringBoot: 相当于 @Configuration 注解的配置类，
    定义应用的元信息和数据库主键策略。

    属性:
        default_auto_field: 默认主键类型 (BigAutoField，对应 MySQL BIGINT AUTO_INCREMENT)
        name:               应用名称，在 INSTALLED_APPS 中注册时使用
    """
    default_auto_field = "django.db.models.BigAutoField"
    name = "systemcheck"
