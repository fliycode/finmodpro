from celery import shared_task

from knowledgebase.models import Document, IngestionTask
from knowledgebase.services.document_service import ingest_document, start_ingestion_task


@shared_task(name="knowledgebase.ingest_document_task")
def ingest_document_task(document_id, ingestion_task_id=None):
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
