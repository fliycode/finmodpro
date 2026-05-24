"""
风险事件审核服务 —— 处理风险事件的审核状态变更。
类比 SpringBoot: 相当于 @Service 中的状态机方法，
将风险事件从 pending 状态变更为 approved 或 rejected。
"""

from risk.models import RiskEvent


def review_risk_event(*, risk_event, review_status):
    """
    审核指定的风险事件（通过或驳回）。

    类比 SpringBoot: 相当于 @Service 中的状态变更方法。

    参数:
        risk_event (RiskEvent): 要审核的风险事件实例。
        review_status (str): 目标审核状态，应为 "approved" 或 "rejected"。

    返回:
        RiskEvent: 更新后的风险事件实例。
    """
    risk_event.review_status = review_status
    risk_event.save(update_fields=["review_status", "updated_at"])
    return risk_event
