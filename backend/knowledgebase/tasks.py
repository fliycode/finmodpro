"""
知识库异步任务 —— 定义 Celery 异步任务，用于触发文档摄取管道。

类比 SpringBoot: 相当于 @Async 注解的异步方法 + @Scheduled 的定时任务，
由 Celery Worker 执行文档从解析到索引的完整管道。

任务:
- ingest_document_task: 对单个文档执行完整的摄取管线 (解析 -> 清洗 -> 分块 -> 索引)
"""
from celery import shared_task

from knowledgebase.models import Document, IngestionTask
from knowledgebase.services.document_service import ingest_document, start_ingestion_task


@shared_task(name="knowledgebase.ingest_document_task")
def ingest_document_task(document_id, ingestion_task_id=None):
    """
    异步执行文档摄取任务。

    类比 SpringBoot: 相当于 @Async("celeryTaskExecutor") 的异步方法，
    由 Celery Worker 从队列中拾取并执行。

    摄取管线步骤: 解析 -> 清洗 -> 分块 -> 索引 -> (可选) 图谱同步

    参数:
        document_id (int): 要摄取的文档 ID。
        ingestion_task_id (int, 可选): 关联的摄取任务记录 ID，用于跟踪进度。

    返回:
        int | None: 成功时返回文档 ID，文档不存在或任务记录不存在时返回 None。
    """
    try:
        document = Document.objects.get(id=document_id)
    except Document.DoesNotExist:
        return None

    ingestion_task = None
    if ingestion_task_id is not None:
        try:
            ingestion_task = IngestionTask.objects.get(id=ingestion_task_id)
        except IngestionTask.DoesNotExist:
            return None
        start_ingestion_task(ingestion_task)

    ingest_document(document, ingestion_task=ingestion_task)
    return document.id
