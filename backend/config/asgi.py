"""
ASGI 入口文件 — 异步 Web 服务器启动点

ASGI (Asynchronous Server Gateway Interface) 是 WSGI 的异步演进版。
Daphne / Uvicorn 等异步服务器用此文件启动应用，支持 WebSocket、HTTP/2 等长时间连接。

SpringBoot 类比: SpringBoot 3.x / WebFlux 的响应式启动入口，但 Django 默认仍是同步为主，
ASGI 仅用于需要异步的场景（如 WebSocket 连接）。
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_asgi_application()
