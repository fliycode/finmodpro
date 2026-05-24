"""
检索日志服务 —— 记录每次检索请求的详细信息到数据库。
类比 SpringBoot: 相当于 @Service 中的审计日志记录器，
类似于 @Repository 的 save 操作，但专门用于记录检索操作的审计轨迹。
"""

from rag.models import RetrievalLog


def create_retrieval_log(
    *,
    query,
    top_k,
    filters,
    results,
    source,
    duration_ms=None,
    metadata=None,
):
    """
    创建一条检索日志记录。

    类比 SpringBoot: 相当于调用 JPA Repository 的 save() 方法，
    将检索请求的详情写入 retrieval_log 表，用于后续分析和监控。

    参数:
        query (str): 用户的查询文本。
        top_k (int): 请求的返回结果数量。
        filters (dict): 检索时使用的过滤条件。
        results (list): 检索返回的结果列表（用于计算 result_count）。
        source (str): 检索来源，可选值: "retrieval_api" 或 "chat_ask"。
        duration_ms (int, 可选): 检索耗时（毫秒），用于性能分析。
        metadata (dict, 可选): 额外的元数据信息。

    返回:
        RetrievalLog: 新创建的日志记录实例。
    """
    return RetrievalLog.objects.create(
        query=query,
        top_k=int(top_k),
        filters=filters or {},
        result_count=len(results),
        source=source,
        metadata=metadata or {},
        duration_ms=duration_ms,
    )
