from django.core.management.base import BaseCommand

from rbac.services.rbac_service import ROLE_PERMISSION_MAP, seed_roles_and_permissions


class Command(BaseCommand):
    help = "Seed default RBAC groups and permissions."

    def handle(self, *args, **options):
        groups = seed_roles_and_permissions()
        permission_names = set()
        for values in ROLE_PERMISSION_MAP.values():
            permission_names.update(values)
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded RBAC roles: {', '.join(sorted(groups.keys()))}. "
                f"Permission map count: {len(permission_names)}."
            )
        )
