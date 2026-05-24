"""
WSGI 入口文件 — 同步 Web 服务器启动点

WSGI (Web Server Gateway Interface) 是 Python Web 应用与服务器之间的同步通信协议。
Gunicorn 等同步服务器用此文件启动应用。

SpringBoot 类比: 类似 SpringBoot 内嵌 Tomcat 的 main 方法入口，但不是直接启动服务器，
而是暴露一个 application 对象，由外部的 Gunicorn 加载运行。
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# application 对象被 Gunicorn 加载（如: gunicorn config.wsgi:application）
application = get_wsgi_application()
