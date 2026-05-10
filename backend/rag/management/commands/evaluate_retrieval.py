import json

from django.core.management.base import BaseCommand, CommandError

from common.exceptions import ServiceConfigurationError, UpstreamServiceError
from rag.services.retrieval_evaluation_service import (
    evaluate_retrieval_fixture,
    evaluate_generation_fixture,
    load_retrieval_cases,
)


class Command(BaseCommand):
    help = "Run retrieval/generation benchmark cases and print evaluation summary."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fixture",
            default="",
            help="Optional path to a retrieval evaluation JSON fixture.",
        )
        parser.add_argument(
            "--mode",
            choices=["retrieval", "generation", "all"],
            default="retrieval",
            help=(
                "Evaluation mode: retrieval metrics only, "
                "generation quality only, or both."
            ),
        )

    def handle(self, *args, **options):
        mode = options["mode"]
        fixture_path = options.get("fixture") or None

        try:
            if mode in ("retrieval", "all"):
                retrieval_result = evaluate_retrieval_fixture(fixture_path)
                self.stdout.write("=== RETRIEVAL EVALUATION ===")
                self.stdout.write(
                    json.dumps(retrieval_result, ensure_ascii=False, indent=2)
                )

            if mode in ("generation", "all"):
                cases = load_retrieval_cases(fixture_path)
                generation_result = evaluate_generation_fixture(fixture_path)
                if mode == "all":
                    self.stdout.write("")
                self.stdout.write("=== GENERATION EVALUATION ===")
                self.stdout.write(
                    json.dumps(generation_result, ensure_ascii=False, indent=2)
                )
        except ServiceConfigurationError as exc:
            raise CommandError(f"evaluation unavailable: {exc.message}") from exc
        except UpstreamServiceError as exc:
            raise CommandError(
                f"evaluation failed during upstream model call: {exc.message}"
            ) from exc
