"""
用户统计服务 — 查询用户的使用数据

从聊天消息和文档表中汇总统计数据，用于用户资料页面展示。

SpringBoot 类比: 一个轻量的统计查询 @Service。
"""

from django.utils import timezone

from chat.models import ChatMessage
from knowledgebase.models import Document


def get_user_stats(user):
    """获取用户的使用统计数据。

    包含:
      - question_count: 累计提问数
      - question_count_today: 今日提问数
      - document_count: 累计上传文档数
      - usage_days: 使用天数（从注册日到今日）

    参数:
        user: User 实例
    返回:
        dict 包含上述统计字段
    """
    today = timezone.now().date()

    # 累计提问次数
    question_count = ChatMessage.objects.filter(
        session__user=user,
        role=ChatMessage.ROLE_USER,
    ).count()

    # 今日提问次数
    question_count_today = ChatMessage.objects.filter(
        session__user=user,
        role=ChatMessage.ROLE_USER,
        created_at__date=today,
    ).count()

    # 上传文档数
    document_count = Document.objects.filter(uploaded_by=user).count()

    # 使用天数
    usage_days = max((timezone.now() - user.date_joined).days, 1) if user.date_joined else 0

    return {
        "question_count": question_count,
        "question_count_today": question_count_today,
        "document_count": document_count,
        "usage_days": usage_days,
    }
