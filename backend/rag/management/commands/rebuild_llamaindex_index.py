from django.core.management.base import BaseCommand

from knowledgebase.models import Document
from rag.services.llamaindex_store_service import (
    clear_llamaindex_store,
    sync_document_index,
)


class Command(BaseCommand):
    help = "Rebuild the persisted LlamaIndex retrieval store from indexed knowledgebase documents."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear-only",
            action="store_true",
            help="Only clear the persisted LlamaIndex store without rebuilding it.",
        )

    def handle(self, *args, **options):
        clear_llamaindex_store()
        if options["clear_only"]:
            self.stdout.write(self.style.SUCCESS("Cleared LlamaIndex store."))
            return

        documents = Document.objects.filter(status=Document.STATUS_INDEXED).order_by("id")
        indexed_count = 0
        for document in documents:
            sync_document_index(document)
            indexed_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Rebuilt LlamaIndex store for {indexed_count} indexed document(s)."
            )
        )
