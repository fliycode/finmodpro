"""
后台任务工具 — 在独立线程中执行任务（不阻塞 HTTP 响应）

用于快速触发的非关键操作（如日志记录、通知），避免阻塞 API 响应。
对于耗时长的任务（如文档解析、风险提取），应使用 Celery 异步任务队列。

SpringBoot 类比: @Async 注解 + ThreadPoolTaskExecutor 的简单版，
但这里直接用 thread 而非线程池，适用轻量场景。
"""

import logging
import threading

from django.db import close_old_connections

logger = logging.getLogger(__name__)


def run_background_job(*, name, target, args=(), kwargs=None):
    """在独立的 daemon 线程中执行任务。

    任务执行前会关闭旧数据库连接（线程间不能共享 cursor），
    执行完毕后再次关闭连接防止泄漏。

    参数:
        name: 任务名称（用于线程名和日志）
        target: 要执行的函数
        args: 位置参数元组
        kwargs: 关键字参数字典
    返回:
        threading.Thread 实例
    """
    resolved_kwargs = kwargs or {}

    def _runner():
        close_old_connections()  # 线程前断开数据库连接
        try:
            target(*args, **resolved_kwargs)
        except Exception:
            logger.exception("Background job %s failed", name)
        finally:
            close_old_connections()  # 线程后断开数据库连接

    thread = threading.Thread(
        target=_runner,
        name=f"finmodpro-{name}",
        daemon=True,  # daemon 线程 — 主进程退出时自动终止
    )
    thread.start()
    return thread
