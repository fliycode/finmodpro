"""
Django 根 URL 路由配置（SpringBoot 类比: @RequestMapping 的汇总入口）

Django 使用 urlpatterns 列表将 URL 前缀映射到各 app 的路由配置。
每个 path() 调用将某 URL 前缀转发给对应 app 的 urls.py 文件（即 include() 导入）。

例如:
  path("api/auth/", include("authentication.urls"))
  将 /api/auth/* 开头的请求路由到 authentication/urls.py 中定义的视图函数。

SpringBoot 类比:
  - include("app.urls") ≈ @RequestMapping("/api/auth") 作用在 Controller 上
  - path() ≈ @RequestMapping 的路径参数
"""

from django.conf import settings
from django.contrib import admin
from django.conf.urls.static import static
from django.urls import include, path


urlpatterns = [
    # Django 内置管理后台: /admin/
    path("admin/", admin.site.urls),

    # systemcheck 同时挂载在 /api/ 和 /api/systemcheck/ 下（兼容性）
    path("api/", include("systemcheck.urls")),
    path("api/systemcheck/", include("systemcheck.urls")),

    # 各个业务应用的路由
    path("api/auth/", include("authentication.urls")),    # 认证: 登录/注册/刷新
    path("api/", include("rbac.urls")),                    # RBAC: 角色权限管理
    path("api/knowledgebase/", include("knowledgebase.urls")),  # 知识库
    path("api/ops/", include("llm.urls")),                 # LLM 模型管理（路径前缀是 /ops/）
    path("api/rag/", include("rag.urls")),                 # RAG 检索
    path("api/chat/", include("chat.urls")),               # 对话系统
    path("api/risk/", include("risk.urls")),               # 风险分析
    path("api/monitoring/", include("ops.urls")),          # 运维监控
]

# 开发环境下提供文件上传访问
# SpringBoot 类比: spring.web.resources.static-locations
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
