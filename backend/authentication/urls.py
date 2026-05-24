"""
认证模块 URL 路由配置

将 URL 路径映射到对应的视图函数（Controller）。
path() 的第一个参数是路径，第二个参数是处理函数，name 是路由名称（用于反向解析）。

SpringBoot 类比:
  - path(a, b, name="c") ≈ @RequestMapping(a) + 方法名 = b
  - name 参数 ≈ @RequestMapping 的 name 属性，用于 URL 反向生成
"""

from django.urls import path

from authentication.controllers.auth_controller import (
    csrf_view,
    forgot_password_view,
    login_view,
    logout_view,
    refresh_view,
    register_view,
    reset_password_view,
)


urlpatterns = [
    path("csrf", csrf_view, name="csrf"),
    path("register", register_view, name="register"),
    path("login", login_view, name="login"),
    path("refresh", refresh_view, name="refresh"),        # Token 刷新
    path("logout", logout_view, name="logout"),
    path("forgot-password", forgot_password_view, name="forgot-password"),
    path("reset-password", reset_password_view, name="reset-password"),
]
