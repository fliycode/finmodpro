from django.core.management.base import BaseCommand

from systemcheck.services.demo_data_service import seed_demo_data


class Command(BaseCommand):
    help = "Seed repeatable demo data for the FinModPro demo flow."

    def handle(self, *args, **options):
        summary = seed_demo_data()
        self.stdout.write(
            self.style.SUCCESS(
                "Seeded demo data. "
                f"Users: {', '.join(summary['users'])}. "
                f"Documents: {len(summary['documents'])}. "
                f"Chat session: {summary['chat_session_id']}. "
                f"Risk events: {len(summary['risk_event_ids'])}. "
                f"Risk report: {summary['risk_report_id']}. "
                f"Default password: {summary['default_password']}"
            )
        )
