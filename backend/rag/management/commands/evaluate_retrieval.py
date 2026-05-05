import json

from django.core.management.base import BaseCommand, CommandError

from common.exceptions import ServiceConfigurationError, UpstreamServiceError
from rag.services.retrieval_evaluation_service import evaluate_retrieval_fixture


class Command(BaseCommand):
    help = "Run retrieval benchmark cases and print Recall@K / MRR / nDCG / latency summary."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fixture",
            default="",
            help="Optional path to a retrieval evaluation JSON fixture.",
        )

    def handle(self, *args, **options):
        try:
            result = evaluate_retrieval_fixture(options.get("fixture") or None)
        except ServiceConfigurationError as exc:
            raise CommandError(f"retrieval evaluation unavailable: {exc.message}") from exc
        except UpstreamServiceError as exc:
            raise CommandError(
                f"retrieval evaluation failed during upstream model call: {exc.message}"
            ) from exc
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
