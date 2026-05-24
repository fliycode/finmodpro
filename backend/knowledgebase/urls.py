"""
知识库 API 路由配置模块。

类比 SpringBoot: 相当于 @RestController 类上的 @RequestMapping 注解集合。
Django 的 urlpatterns 列表定义了 URL 路径 -> 视图函数的映射关系，
与 Spring 的 @GetMapping / @PostMapping / @DeleteMapping 注解功能一致。

本模块导入各 controller 中的视图函数，将其挂载到对应的 URL 端点（endpoint）上。
这些 URL 最终由 backend/config/urls.py 的 /api/ 前缀统一汇聚。
"""
from django.urls import path

from knowledgebase.controllers import (
    cleaning_rule_bootstrap_view,
    cleaning_rule_detail_view,
    cleaning_rule_list_create_view,
    cleaning_summary_view,
    dataset_detail_view,
    dataset_list_create_view,
    document_batch_delete_view,
    document_batch_ingest_view,
    document_chunks_view,
    document_cleaning_view,
    document_detail_view,
    document_ingest_view,
    document_list_create_view,
    document_stats_view,
    document_versions_view,
)


urlpatterns = [
    # ==================== 数据集 (Dataset) 路由 ====================
    # GET 列表 / POST 创建 -> 类似 @GetMapping + @PostMapping 同路径
    path("datasets", dataset_list_create_view, name="knowledgebase-dataset-list-create"),
    # GET 详情 -> 类似 @GetMapping("/{id}")
    path(
        "datasets/<int:dataset_id>",
        dataset_detail_view,
        name="knowledgebase-dataset-detail",
    ),

    # ==================== 文档 (Document) 路由 ====================
    # GET 列表 / POST 上传
    path("documents", document_list_create_view, name="knowledgebase-document-list-create"),
    # GET 统计信息
    path(
        "documents/stats",
        document_stats_view,
        name="knowledgebase-document-stats",
    ),
    # POST 批量摄取
    path(
        "documents/batch/ingest",
        document_batch_ingest_view,
        name="knowledgebase-document-batch-ingest",
    ),
    # POST 批量删除
    path(
        "documents/batch/delete",
        document_batch_delete_view,
        name="knowledgebase-document-batch-delete",
    ),
    # GET 详情 / DELETE 删除
    path(
        "documents/<int:document_id>",
        document_detail_view,
        name="knowledgebase-document-detail",
    ),
    # GET 文档分块列表
    path(
        "documents/<int:document_id>/chunks",
        document_chunks_view,
        name="knowledgebase-document-chunks",
    ),
    # GET/POST 文档版本
    path(
        "documents/<int:document_id>/versions",
        document_versions_view,
        name="knowledgebase-document-versions",
    ),
    # POST 单文档摄取
    path(
        "documents/<int:document_id>/ingest",
        document_ingest_view,
        name="knowledgebase-document-ingest",
    ),
    # GET/POST 文档清洗
    path(
        "documents/<int:document_id>/cleaning",
        document_cleaning_view,
        name="knowledgebase-document-cleaning",
    ),

    # ==================== 清洗规则 (CleaningRule) 路由 ====================
    # GET 列表 / POST 创建
    path(
        "cleaning/rules",
        cleaning_rule_list_create_view,
        name="knowledgebase-cleaning-rule-list-create",
    ),
    # GET 详情 / PATCH 更新 / DELETE 删除
    path(
        "cleaning/rules/<int:rule_id>",
        cleaning_rule_detail_view,
        name="knowledgebase-cleaning-rule-detail",
    ),
    # POST 一键初始化默认规则（无末尾斜杠）
    path(
        "cleaning/rules/bootstrap",
        cleaning_rule_bootstrap_view,
        name="knowledgebase-cleaning-rule-bootstrap",
    ),
    # POST 一键初始化默认规则（带末尾斜杠兼容）
    path(
        "cleaning/rules/bootstrap/",
        cleaning_rule_bootstrap_view,
        name="knowledgebase-cleaning-rule-bootstrap-slash",
    ),
    # GET 清洗汇总信息（无末尾斜杠）
    path(
        "cleaning/summary",
        cleaning_summary_view,
        name="knowledgebase-cleaning-summary",
    ),
    # GET 清洗汇总信息（带末尾斜杠兼容）
    path(
        "cleaning/summary/",
        cleaning_summary_view,
        name="knowledgebase-cleaning-summary-slash",
    ),
]
