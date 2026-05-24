"""
Ops 应用配置类。
类比 SpringBoot: 相当于 @SpringBootApplication 中的组件扫描声明，
告诉 Django 此应用的名称、主键字段类型和展示名称。

Ops (Operations Monitoring) 负责系统运维监控：
- 系统指标采集（CPU、内存、磁盘、Celery、数据库健康等）
- 告警规则的 CRUD 与评估
- 告警事件的生命周期管理
"""

from django.apps import AppConfig


class OpsConfig(AppConfig):
    """运维监控应用的配置入口。

    类比 SpringBoot: 等同于 @Configuration + @ComponentScan 的组合，
    注册 ops 模块到 Django 应用容器中。
    """
    # 默认主键类型，使用 BigAutoField（64位自增整数）
    # 类比 SpringBoot: 对应 JPA 中 @Id 字段的默认生成策略
    default_auto_field = "django.db.models.BigAutoField"
    # 应用名称，用于在 INSTALLED_APPS 中注册
    # 类比 SpringBoot: 对应 spring.application.name 或模块名
    name = "ops"
    # 应用的可读展示名称，在 Django Admin 中显示
    verbose_name = "Operations Monitoring"
