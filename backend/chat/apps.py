"""
Chat 应用配置类。

类比 SpringBoot：
  - AppConfig 相当于 @Configuration + @ComponentScan 的结合体。
  - 告诉 Django 框架此应用的名字和元信息，类似于 SpringBoot 自动装配时扫描到的配置类。
  - 当 Django 启动时，会在 INSTALLED_APPS 中找到此配置并初始化应用。

字段说明：
  - default_auto_field: 默认主键类型，相当于 JPA 中 @Id 的默认生成策略（BigAutoField 类似 AUTO_INCREMENT）。
  - name: 应用名称，对应 SpringBoot Module 的模块名。
"""

from django.apps import AppConfig


class ChatConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "chat"
