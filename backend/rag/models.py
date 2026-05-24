"""
RAG 应用的数据模型定义。
类比 SpringBoot: 相当于 JPA 的 @Entity 实体类，定义数据库表结构和字段映射。
"""

from django.db import models


class RetrievalLog(models.Model):
    """检索日志模型，记录每次 RAG 检索请求的详情。

    类比 SpringBoot: 相当于一个 JPA @Entity 类，映射到 retrieval_log 表。
    每次检索调用（无论是 API 查询还是聊天提问）都会创建一条日志记录。
    """

    # 检索来源常量：通过检索 API 调用
    # 类比 SpringBoot: 对应枚举类型的常量定义
    SOURCE_RETRIEVAL_API = "retrieval_api"
    # 检索来源常量：通过聊天问答调用
    SOURCE_CHAT_ASK = "chat_ask"
    # 来源选项元组（数据库值, 展示名称）
    SOURCE_CHOICES = (
        (SOURCE_RETRIEVAL_API, "Retrieval API"),
        (SOURCE_CHAT_ASK, "Chat Ask"),
    )

    # 用户输入的查询文本
    # 类比 SpringBoot: 对应 @Column(columnDefinition = "TEXT")
    query = models.TextField()
    # 返回的最相似文档数，默认为 5
    # 类比 SpringBoot: 对应 @Column 的 Integer 字段，带默认值
    top_k = models.PositiveIntegerField(default=5)
    # 检索时使用的过滤条件，JSON 格式存储
    # 类比 SpringBoot: 对应 @Column(columnDefinition = "JSON") 或 JPA 的 @Convert 注解
    filters = models.JSONField(default=dict, blank=True)
    # 检索返回的结果数量
    result_count = models.PositiveIntegerField(default=0)
    # 检索来源标识，区分是 API 调用还是聊天调用
    source = models.CharField(
        max_length=32,
        choices=SOURCE_CHOICES,
        default=SOURCE_RETRIEVAL_API,
    )
    # 额外元数据，JSON 格式存储（例如 embedding 模型版本等）
    metadata = models.JSONField(default=dict, blank=True)
    # 检索耗时（毫秒），用于性能监控
    duration_ms = models.PositiveIntegerField(blank=True, null=True)
    # 记录创建时间，自动填充
    # 类比 SpringBoot: 对应 @CreatedDate 审计注解
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """模型元数据配置。

        类比 SpringBoot: 对应 JPA 的 @Table 注解中的索引和排序配置。
        """
        # 按创建时间倒序排列，最新的记录排在最前
        ordering = ["-created_at", "-id"]


# 创建别名，保持向后兼容
# RetrievalAuditLog 与 RetrievalLog 是同一模型，用于审计场景的语义区分
RetrievalAuditLog = RetrievalLog
