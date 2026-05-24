"""
聊天模块的 Celery 异步任务

定义了3个 Celery 共享任务，用于异步执行耗时操作:
  - 会话标题自动生成（LLM 调用）
  - 会话摘要更新（滚动摘要算法）
  - 记忆提取（LLM 从对话中提取结构化记忆）

SpringBoot 类比: @Async 标记的方法，通过消息队列异步执行。
使用 @shared_task 而非 @app.task，使得任务可在未显式导入 app 实例的情况下被 worker 发现。
"""

from celery import shared_task

from chat.services.memory_service import extract_memories_with_llm
from chat.services.summary_service import update_session_summary
from chat.services.title_service import generate_session_title


@shared_task(name="chat.update_session_title_task")
def update_session_title_task(session_id):
    """异步生成会话标题。

    由聊天消息保存后自动触发，调用 LLM 生成标题。
    参数:
        session_id: ChatSession 的主键 ID
    返回:
        生成的标题字符串
    """
    return generate_session_title(session_id=session_id)


@shared_task(name="chat.update_session_summary_task")
def update_session_summary_task(session_id):
    """异步更新会话摘要。

    当累计足够消息后触发，执行滚动摘要的增量更新。
    参数:
        session_id: ChatSession 的主键 ID
    返回:
        更新后的摘要文本
    """
    return update_session_summary(session_id=session_id)


@shared_task(name="chat.extract_session_memories_task")
def extract_session_memories_task(session_id):
    """异步从对话中提取结构化记忆。

    调用 LLM 分析对话内容，提取关键信息存入 MemoryItem。
    参数:
        session_id: ChatSession 的主键 ID
    返回:
        提取的记忆条目列表
    """
    return extract_memories_with_llm(session_id=session_id)
