from celery import shared_task

from knowledgebase.models import Document
from knowledgebase.services.document_service import ingest_document


@shared_task(name="knowledgebase.ingest_document_task")
def ingest_document_task(document_id):
    document = Document.objects.get(id=document_id)
    ingest_document(document)
    return document.id
