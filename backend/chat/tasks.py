from celery import shared_task

from chat.services.memory_service import extract_memories_with_llm
from chat.services.summary_service import update_session_summary
from chat.services.title_service import generate_session_title


@shared_task(name="chat.update_session_title_task")
def update_session_title_task(session_id):
    return generate_session_title(session_id=session_id)


@shared_task(name="chat.update_session_summary_task")
def update_session_summary_task(session_id):
    return update_session_summary(session_id=session_id)


@shared_task(name="chat.extract_session_memories_task")
def extract_session_memories_task(session_id):
    return extract_memories_with_llm(session_id=session_id)
