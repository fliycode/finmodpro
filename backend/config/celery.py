"""
Celery 应用配置 — 异步任务队列入口

Celery 是 Python 的分布式任务队列，用于异步执行耗时操作（如文档解析、风险提取等）。
此文件创建 Celery 应用实例，并从 Django settings 中加载配置（所有以 CELERY_ 开头的配置项）。

SpringBoot 类比: 类似 @EnableAsync + @Async 注解的异步机制，但 Celery 是独立的工作进程，
不嵌入在 Web 服务器中。消息通过 Broker（Redis/内存）在 Web 进程和 Worker 进程之间传递。

启动命令: celery -A config.celery worker -l info
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# 创建 Celery 实例
app = Celery("finmodpro_backend")
# 从 Django settings 加载所有 CELERY_ 开头的配置项
app.config_from_object("django.conf:settings", namespace="CELERY")
# 自动发现所有 Django app 下的 tasks.py 文件
app.autodiscover_tasks()
