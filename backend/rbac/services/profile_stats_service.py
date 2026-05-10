from django.utils import timezone

from chat.models import ChatMessage
from knowledgebase.models import Document


def get_user_stats(user):
    today = timezone.now().date()

    question_count = ChatMessage.objects.filter(
        session__user=user,
        role=ChatMessage.ROLE_USER,
    ).count()

    question_count_today = ChatMessage.objects.filter(
        session__user=user,
        role=ChatMessage.ROLE_USER,
        created_at__date=today,
    ).count()

    document_count = Document.objects.filter(uploaded_by=user).count()

    usage_days = max((timezone.now() - user.date_joined).days, 1) if user.date_joined else 0

    return {
        "question_count": question_count,
        "question_count_today": question_count_today,
        "document_count": document_count,
        "usage_days": usage_days,
    }
