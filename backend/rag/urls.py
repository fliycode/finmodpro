"""
RAG 应用的 URL 路由配置。
类比 SpringBoot: 相当于 @RestController 中的 @RequestMapping 路径映射，
将 HTTP 请求路径分发到对应的控制器视图函数。
"""

from django.urls import path

from rag.controllers import retrieval_query_view

# URL 路由表，将请求路径映射到视图函数
# 类比 SpringBoot: 相当于 @GetMapping / @PostMapping 注解中的路径配置
urlpatterns = [
    # POST /api/rag/retrieval/query - 检索查询接口
    # 接收用户查询文本，返回相关文档片段
    # 类比 SpringBoot: @PostMapping("/retrieval/query")
    path("retrieval/query", retrieval_query_view, name="rag-retrieval-query"),
]
