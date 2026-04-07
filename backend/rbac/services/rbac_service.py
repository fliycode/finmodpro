from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from authentication.models import User


ROLE_SUPER_ADMIN = "super_admin"
ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"

CUSTOM_PERMISSION_DEFINITIONS = (
    ("view_dashboard", "Can view dashboard"),
    ("view_role", "Can view role"),
    ("assign_role", "Can assign role"),
    ("upload_document", "Can upload document"),
    ("view_document", "Can view document"),
    ("trigger_ingest", "Can trigger ingest"),
    ("ask_financial_qa", "Can ask financial qa"),
    ("view_chat_session", "Can view chat session"),
    ("review_risk_event", "Can review risk event"),
    ("manage_model_config", "Can manage model config"),
    ("view_evaluation", "Can view evaluation"),
    ("run_evaluation", "Can run evaluation"),
    ("view_audit_log", "Can view audit log"),
)

ROLE_PERMISSION_MAP = {
    ROLE_SUPER_ADMIN: {
        "auth.view_dashboard",
        "auth.view_user",
        "auth.add_user",
        "auth.change_user",
        "auth.delete_user",
        "auth.view_role",
        "auth.assign_role",
        "auth.upload_document",
        "auth.view_document",
        "auth.trigger_ingest",
        "auth.ask_financial_qa",
        "auth.view_chat_session",
        "auth.review_risk_event",
        "auth.manage_model_config",
        "auth.view_evaluation",
        "auth.run_evaluation",
        "auth.view_audit_log",
    },
    ROLE_ADMIN: {
        "auth.view_dashboard",
        "auth.view_user",
        "auth.add_user",
        "auth.change_user",
        "auth.view_role",
        "auth.upload_document",
        "auth.view_document",
        "auth.trigger_ingest",
        "auth.ask_financial_qa",
        "auth.view_chat_session",
        "auth.review_risk_event",
        "auth.manage_model_config",
        "auth.view_evaluation",
        "auth.view_audit_log",
    },
    ROLE_MEMBER: {
        "auth.view_dashboard",
        "auth.view_document",
        "auth.ask_financial_qa",
    },
}


def ensure_custom_permissions():
    content_type = ContentType.objects.get_for_model(User)
    permissions = {}

    for codename, name in CUSTOM_PERMISSION_DEFINITIONS:
        permission, _ = Permission.objects.get_or_create(
            content_type=content_type,
            codename=codename,
            defaults={"name": name},
        )
        permissions[f"auth.{codename}"] = permission

    return permissions


def ensure_role_groups():
    groups = {}
    for role_name in ROLE_PERMISSION_MAP:
        groups[role_name], _ = Group.objects.get_or_create(name=role_name)
    return groups


def _get_permissions_by_name(permission_names):
    custom_permissions = ensure_custom_permissions()
    content_type = ContentType.objects.get_for_model(User)
    permissions = dict(custom_permissions)

    for codename in ("view_user", "add_user", "change_user", "delete_user"):
        permissions[f"auth.{codename}"] = Permission.objects.get(
            content_type=content_type,
            codename=codename,
        )

    return [permissions[permission_name] for permission_name in permission_names]


def seed_roles_and_permissions():
    groups = ensure_role_groups()
    seeded_groups = {}

    for role_name, permission_names in ROLE_PERMISSION_MAP.items():
        group = groups[role_name]
        group.permissions.set(_get_permissions_by_name(permission_names))
        seeded_groups[role_name] = group

    return seeded_groups


def ensure_rbac_bootstrapped():
    return seed_roles_and_permissions()


def ensure_user_role_bindings(user):
    groups = ensure_rbac_bootstrapped()

    expected_role = ROLE_MEMBER
    should_bind_expected_role = not user.groups.exists()
    if user.is_superuser:
        expected_role = ROLE_SUPER_ADMIN
        should_bind_expected_role = True
    elif user.is_staff:
        expected_role = ROLE_ADMIN
        should_bind_expected_role = True

    if should_bind_expected_role and not user.groups.filter(name=expected_role).exists():
        user.groups.add(groups[expected_role])

    return groups[expected_role]


def assign_default_member_group(user):
    member_group = ensure_user_role_bindings(user)
    return member_group


def collect_user_groups(user):
    return sorted(user.groups.values_list("name", flat=True))


def collect_user_permission_names(user):
    return sorted(permission_name.split(".", 1)[1] for permission_name in user.get_all_permissions())


def serialize_user_rbac_profile(user):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "groups": collect_user_groups(user),
        "permissions": collect_user_permission_names(user),
    }


def serialize_admin_user_row(user):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "groups": collect_user_groups(user),
        "permissions": collect_user_permission_names(user),
        "is_superuser": user.is_superuser,
        "is_staff": user.is_staff,
        "date_joined": user.date_joined.isoformat(),
    }


def list_admin_user_rows():
    return [
        serialize_admin_user_row(user)
        for user in User.objects.order_by("id")
    ]


def list_assignable_groups():
    return list(Group.objects.order_by("name").values("id", "name"))


def replace_user_groups(user, group_names):
    groups = list(Group.objects.filter(name__in=group_names).order_by("name"))
    found_group_names = {group.name for group in groups}
    missing_group_names = sorted(set(group_names) - found_group_names)
    if missing_group_names:
        raise ValueError(f"Unknown groups: {', '.join(missing_group_names)}")

    user.groups.set(groups)
    user.refresh_from_db()
    return serialize_admin_user_row(user)
