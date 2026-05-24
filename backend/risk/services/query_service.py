"""
风险事件查询服务 —— 提供灵活的风险事件过滤查询。
类比 SpringBoot: 相当于 @Repository / @Service 中的动态查询构建器，
类似于 Spring Data JPA 的 Specification 或 QueryDSL。
"""

from risk.models import RiskEvent


def build_risk_event_queryset(*, filters):
    """
    根据过滤条件构建 RiskEvent 的 QuerySet。

    类比 SpringBoot: 相当于 JPA Criteria API 或 Specification 的 where 条件构建。

    参数:
        filters (dict): 过滤条件字典，支持:
                        - company_name  (str): 公司名称（模糊匹配）
                        - risk_type     (str): 风险类型（模糊匹配）
                        - review_status (str): 审核状态（精确匹配）
                        - risk_level    (str): 风险级别（精确匹配）
                        - document_id   (int): 文档 ID（精确匹配）
                        - period_start  (date): 事件时间 >= 此日期
                        - period_end    (date): 事件时间 <= 此日期

    返回:
        QuerySet: 已应用所有过滤条件的查询集（含 select_related 预加载）。
    """
    queryset = RiskEvent.objects.select_related("document", "chunk").all()

    company_name = filters.get("company_name")
    if company_name:
        queryset = queryset.filter(company_name__icontains=company_name)

    risk_type = filters.get("risk_type")
    if risk_type:
        queryset = queryset.filter(risk_type__icontains=risk_type)

    review_status = filters.get("review_status")
    if review_status:
        queryset = queryset.filter(review_status=review_status)

    risk_level = filters.get("risk_level")
    if risk_level:
        queryset = queryset.filter(risk_level=risk_level)

    document_id = filters.get("document_id")
    if document_id:
        queryset = queryset.filter(document_id=document_id)

    period_start = filters.get("period_start")
    if period_start:
        queryset = queryset.filter(event_time__gte=period_start)

    period_end = filters.get("period_end")
    if period_end:
        queryset = queryset.filter(event_time__lte=period_end)

    return queryset


def list_risk_events(*, filters):
    """
    获取过滤后的风险事件列表（按创建时间倒序）。

    参数:
        filters (dict): 同 build_risk_event_queryset 的过滤条件。

    返回:
        QuerySet: 按创建时间倒序排列的风险事件查询集。
    """
    return build_risk_event_queryset(filters=filters).order_by("-created_at", "-id")
