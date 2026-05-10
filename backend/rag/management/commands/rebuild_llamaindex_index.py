from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand

from knowledgebase.models import Document
from rag.services.llamaindex_store_service import clear_store, sync_document


class Command(BaseCommand):
    help = "Rebuild the LlamaIndex Milvus vector store from indexed knowledgebase documents."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear-only",
            action="store_true",
            help="Only clear the vector store without rebuilding it.",
        )

    def handle(self, *args, **options):
        self.stdout.write(f"Embedding dimension: {settings.KB_EMBEDDING_DIMENSION}")
        cache.clear()
        clear_store()
        if options["clear_only"]:
            self.stdout.write(self.style.SUCCESS("Cleared vector store and embedding cache."))
            return

        documents = Document.objects.filter(status=Document.STATUS_INDEXED).order_by("id")
        indexed_count = 0
        for document in documents:
            sync_document(document)
            indexed_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Rebuilt vector store for {indexed_count} indexed document(s)."
            )
        )
