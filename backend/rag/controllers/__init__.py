"""
RAG controllers 包，汇集所有 RAG 相关的控制器视图函数。
类比 SpringBoot: 相当于 @RestController 类的包目录，
每个控制器函数对应一个 HTTP 端点处理方法。
"""

from rag.controllers.retrieval_controller import retrieval_query_view


__all__ = ["retrieval_query_view"]
