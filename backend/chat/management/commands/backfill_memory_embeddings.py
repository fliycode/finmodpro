from django.core.management.base import BaseCommand

from chat.models import MemoryItem
from knowledgebase.services.embedding_service import build_dense_embedding


class Command(BaseCommand):
    help = "Backfill embedding vectors for MemoryItem records that have none."

    def handle(self, *args, **options):
        qs = MemoryItem.objects.filter(
            status=MemoryItem.STATUS_ACTIVE,
            embedding=[],
        )
        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS("All active memories already have embeddings."))
            return

        self.stdout.write(f"Backfilling embeddings for {total} memories...")
        done = 0
        errors = 0
        for memory in qs.iterator():
            if not memory.content:
                continue
            try:
                memory.embedding = build_dense_embedding(memory.content)
                memory.save(update_fields=["embedding"])
                done += 1
            except Exception as exc:
                errors += 1
                self.stderr.write(f"  Error on memory #{memory.id}: {exc}")

        self.stdout.write(self.style.SUCCESS(
            f"Done. {done} embeddings written, {errors} errors."
        ))
