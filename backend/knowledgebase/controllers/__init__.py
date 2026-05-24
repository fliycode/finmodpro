"""
知识库控制器 (Controllers) 包的公共导出模块。

类比 SpringBoot: 相当于一个模块的公开 API 门面 (Facade)，通过 __all__ 列表
显式声明哪些视图函数可以被外部导入使用。所有 controller 视图函数在此汇聚，
由 urls.py 统一导入并挂载到 URL 路由上。

这是 Django 惯用的做法：将分散在各 controller 模块中的视图函数统一收集，
提供一个干净的导入入口。
"""
from knowledgebase.controllers.document_controller import (
    document_detail_view,
    document_list_create_view,
    document_stats_view,
)
from knowledgebase.controllers.batch_controller import (
    document_batch_delete_view,
    document_batch_ingest_view,
)
from knowledgebase.controllers.chunk_controller import document_chunks_view
from knowledgebase.controllers.dataset_controller import (
    dataset_detail_view,
    dataset_list_create_view,
)
from knowledgebase.controllers.ingest_controller import document_ingest_view
from knowledgebase.controllers.version_controller import document_versions_view
from knowledgebase.controllers.cleaning_rule_controller import (
    cleaning_rule_bootstrap_view,
    cleaning_rule_list_create_view,
    cleaning_summary_view,
    cleaning_rule_detail_view,
)
from knowledgebase.controllers.cleaning_controller import document_cleaning_view


__all__ = [
    "cleaning_rule_list_create_view",
    "cleaning_rule_detail_view",
    "cleaning_rule_bootstrap_view",
    "dataset_detail_view",
    "dataset_list_create_view",
    "cleaning_summary_view",
    "document_batch_delete_view",
    "document_batch_ingest_view",
    "document_cleaning_view",
    "document_detail_view",
    "document_chunks_view",
    "document_ingest_view",
    "document_list_create_view",
    "document_stats_view",
    "document_versions_view",
]
