import json

from django.core.management.base import BaseCommand

from llm.services.model_config_command_service import migrate_active_configs_to_litellm


class Command(BaseCommand):
    help = "Rebuild LiteLLM route snippets from active model configs and refresh the rendered gateway config."

    def handle(self, *args, **options):
        result = migrate_active_configs_to_litellm(triggered_by=None)
        self.stdout.write(self.style.SUCCESS(json.dumps(result, ensure_ascii=False)))
