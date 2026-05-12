from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from authentication.models import User, UserProfile


ROLE_SUPER_ADMIN = "super_admin"
ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"
SYSTEM_ROLE_NAMES = (ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_MEMBER)
ROLE_LABELS = {
    ROLE_SUPER_ADMIN: "超级管理员",
    ROLE_ADMIN: "管理员",
    ROLE_MEMBER: "普通成员",
}
ROLE_DESCRIPTIONS = {
    ROLE_SUPER_ADMIN: "拥有平台级治理能力，可维护权限、用户、模型与治理配置。",
    ROLE_ADMIN: "负责日常管理、运维与内容治理，不具备平台最高控制权。",
    ROLE_MEMBER: "面向普通业务成员，保留基础问答与文档访问能力。",
}
SYSTEM_ROLE_REQUIRED_PERMISSION_CODENAMES = {
    ROLE_SUPER_ADMIN: {"view_role", "assign_role"},
}

CUSTOM_PERMISSION_DEFINITIONS = (
    ("view_dashboard", "Can view dashboard"),
    ("view_role", "Can view role"),
    ("assign_role", "Can assign role"),
    ("upload_document", "Can upload document"),
    ("view_document", "Can view document"),
    ("trigger_ingest", "Can trigger ingest"),
    ("delete_document", "Can delete document"),
    ("ask_financial_qa", "Can ask financial qa"),
    ("view_chat_session", "Can view chat session"),
    ("review_risk_event", "Can review risk event"),
    ("manage_model_config", "Can manage model config"),
    ("view_evaluation", "Can view evaluation"),
    ("run_evaluation", "Can run evaluation"),
    ("view_audit_log", "Can view audit log"),
    ("view_monitoring", "Can view system monitoring"),
    ("manage_alert_rules", "Can manage alert rules"),
    ("acknowledge_alerts", "Can acknowledge alerts"),
    ("manage_cleaning_rules", "Can manage cleaning rules"),
    ("trigger_cleaning", "Can trigger document cleaning"),
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
        "auth.delete_document",
        "auth.ask_financial_qa",
        "auth.view_chat_session",
        "auth.review_risk_event",
        "auth.manage_model_config",
        "auth.view_evaluation",
        "auth.run_evaluation",
        "auth.view_audit_log",
        "auth.view_monitoring",
        "auth.manage_alert_rules",
        "auth.acknowledge_alerts",
        "auth.manage_cleaning_rules",
        "auth.trigger_cleaning",
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
        "auth.delete_document",
        "auth.ask_financial_qa",
        "auth.view_chat_session",
        "auth.review_risk_event",
        "auth.manage_model_config",
        "auth.view_evaluation",
        "auth.view_audit_log",
        "auth.view_monitoring",
        "auth.manage_alert_rules",
        "auth.acknowledge_alerts",
        "auth.manage_cleaning_rules",
        "auth.trigger_cleaning",
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


def is_system_role_name(role_name):
    return role_name in SYSTEM_ROLE_NAMES


def ensure_role_groups():
    from django.core.cache import cache

    cache_key = "rbac:role_groups"
    cached = cache.get(cache_key)
    if isinstance(cached, (list, tuple, set)):
        cached_names = [str(name) for name in cached]
        cached_groups = {
            group.name: group
            for group in Group.objects.filter(name__in=cached_names)
        }
        if all(role_name in cached_groups for role_name in ROLE_PERMISSION_MAP):
            return cached_groups

    groups = {}
    for role_name in ROLE_PERMISSION_MAP:
        groups[role_name], _ = Group.objects.get_or_create(name=role_name)
    cache.set(cache_key, list(groups.keys()), 3600)
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


def _strip_permission_name(permission_name):
    return permission_name.split(".", 1)[1] if "." in permission_name else permission_name


def get_role_default_permission_codenames(role_name):
    return sorted(_strip_permission_name(name) for name in ROLE_PERMISSION_MAP.get(role_name, set()))


def list_rbac_permissions():
    ensure_custom_permissions()
    content_type = ContentType.objects.get_for_model(User)
    permissions = Permission.objects.filter(content_type=content_type).order_by("codename")

    serialized = []
    for permission in permissions:
        serialized.append(
            {
                "id": permission.id,
                "codename": permission.codename,
                "name": permission.name,
                "app_label": permission.content_type.app_label,
                "assigned_by_default_to": sorted(
                    role_name
                    for role_name, permission_names in ROLE_PERMISSION_MAP.items()
                    if f"auth.{permission.codename}" in permission_names
                ),
            }
        )

    return serialized


def _list_group_users(group):
    return list(group.user_set.order_by("id"))


def serialize_admin_role_row(group):
    users = _list_group_users(group)
    permission_codenames = sorted(group.permissions.values_list("codename", flat=True))
    default_permission_codenames = get_role_default_permission_codenames(group.name)
    is_system = is_system_role_name(group.name)

    return {
        "id": group.id,
        "name": group.name,
        "label": ROLE_LABELS.get(group.name, group.name),
        "description": ROLE_DESCRIPTIONS.get(group.name),
        "role_type": "system" if is_system else "custom",
        "is_system": is_system,
        "can_rename": not is_system,
        "can_delete": not is_system and not users,
        "member_count": len(users),
        "permissions": permission_codenames,
        "default_permissions": default_permission_codenames,
        "has_customized_permissions": is_system and permission_codenames != default_permission_codenames,
    }


def serialize_admin_role_detail(group):
    role = serialize_admin_role_row(group)
    role["assigned_users"] = [
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
        }
        for user in _list_group_users(group)
    ]
    return role


def list_admin_role_rows():
    groups = Group.objects.order_by("name").prefetch_related("permissions", "user_set")
    return [serialize_admin_role_row(group) for group in groups]


def get_admin_role_detail(role_id):
    group = Group.objects.prefetch_related("permissions", "user_set").get(id=role_id)
    return serialize_admin_role_detail(group)


def _normalize_role_name(role_name):
    normalized_role_name = (role_name or "").strip()
    max_length = Group._meta.get_field("name").max_length

    if not normalized_role_name:
        raise ValueError("角色名称不能为空。")
    if len(normalized_role_name) > max_length:
        raise ValueError(f"角色名称不能超过 {max_length} 个字符。")
    return normalized_role_name


def _get_group_by_id(role_id):
    return Group.objects.get(id=role_id)


def _resolve_permissions_by_codenames(permission_codenames):
    if permission_codenames is None:
        return None

    ensure_custom_permissions()
    content_type = ContentType.objects.get_for_model(User)
    normalized_codenames = sorted(
        {
            _strip_permission_name(permission_codename).strip()
            for permission_codename in permission_codenames
            if isinstance(permission_codename, str) and permission_codename.strip()
        }
    )
    if len(normalized_codenames) != len(permission_codenames):
        raise ValueError("permissions 必须是非空字符串数组。")

    permissions = list(
        Permission.objects.filter(
            content_type=content_type,
            codename__in=normalized_codenames,
        ).order_by("codename")
    )
    found_codenames = {permission.codename for permission in permissions}
    missing_codenames = sorted(set(normalized_codenames) - found_codenames)
    if missing_codenames:
        raise ValueError(f"Unknown permissions: {', '.join(missing_codenames)}")

    return permissions


def _validate_system_role_permissions(group, permission_codenames):
    if not is_system_role_name(group.name):
        return

    required_permission_codenames = SYSTEM_ROLE_REQUIRED_PERMISSION_CODENAMES.get(group.name, set())
    missing_codenames = sorted(required_permission_codenames - set(permission_codenames))
    if missing_codenames:
        raise ValueError(
            f"系统角色 {group.name} 必须保留权限: {', '.join(missing_codenames)}"
        )


def create_admin_role(*, name, permission_codenames=None):
    normalized_role_name = _normalize_role_name(name)
    if Group.objects.filter(name=normalized_role_name).exists():
        raise ValueError("角色名称已存在。")

    group = Group.objects.create(name=normalized_role_name)
    if permission_codenames is not None:
        permissions = _resolve_permissions_by_codenames(permission_codenames)
        permission_names = [permission.codename for permission in permissions]
        _validate_system_role_permissions(group, permission_names)
        group.permissions.set(permissions)

    return serialize_admin_role_detail(group)


def update_admin_role(role_id, *, name=None, permission_codenames=None):
    group = _get_group_by_id(role_id)

    if name is None and permission_codenames is None:
        raise ValueError("至少需要更新角色名称或权限集合。")

    if name is not None:
        normalized_role_name = _normalize_role_name(name)
        if is_system_role_name(group.name) and normalized_role_name != group.name:
            raise ValueError("系统角色不允许重命名。")
        duplicate_exists = Group.objects.filter(name=normalized_role_name).exclude(id=group.id).exists()
        if duplicate_exists:
            raise ValueError("角色名称已存在。")
        group.name = normalized_role_name
        group.save(update_fields=["name"])

    if permission_codenames is not None:
        permissions = _resolve_permissions_by_codenames(permission_codenames)
        resolved_codenames = [permission.codename for permission in permissions]
        _validate_system_role_permissions(group, resolved_codenames)
        group.permissions.set(permissions)

    group.refresh_from_db()
    return serialize_admin_role_detail(group)


def restore_admin_role_permissions(role_id):
    group = _get_group_by_id(role_id)
    if not is_system_role_name(group.name):
        raise ValueError("仅系统角色支持恢复默认权限。")

    default_permissions = _get_permissions_by_name(ROLE_PERMISSION_MAP[group.name])
    group.permissions.set(default_permissions)
    group.refresh_from_db()
    return serialize_admin_role_detail(group)


def delete_admin_role(role_id):
    group = _get_group_by_id(role_id)
    if is_system_role_name(group.name):
        raise ValueError("系统角色不允许删除。")
    if group.user_set.exists():
        raise ValueError("角色仍有关联用户，无法删除。")
    group.delete()


def seed_roles_and_permissions(*, reset_system_role_permissions=False):
    groups = ensure_role_groups()
    seeded_groups = {}

    for role_name, permission_names in ROLE_PERMISSION_MAP.items():
        group = groups[role_name]
        if reset_system_role_permissions or not group.permissions.exists():
            group.permissions.set(_get_permissions_by_name(permission_names))
        seeded_groups[role_name] = group

    return seeded_groups


def ensure_rbac_bootstrapped():
    return seed_roles_and_permissions()


def ensure_user_role_bindings(user):
    groups = ensure_role_groups()

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


def get_avatar_url(user):
    try:
        profile = user.profile
    except (UserProfile.DoesNotExist, AttributeError):
        return None
    if profile.avatar:
        return profile.avatar.url
    return None


def serialize_user_rbac_profile(user):
    from rbac.services.profile_stats_service import get_user_stats

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "avatar_url": get_avatar_url(user),
        "groups": collect_user_groups(user),
        "permissions": collect_user_permission_names(user),
        "date_joined": user.date_joined.isoformat() if user.date_joined else None,
        "stats": get_user_stats(user),
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


def create_admin_user(*, username, email, password, group_names=None):
    if User.objects.filter(username=username).exists():
        raise ValueError("用户名已存在。")

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
    )

    if group_names:
        return replace_user_groups(user, group_names)

    assign_default_member_group(user)
    user.refresh_from_db()
    return serialize_admin_user_row(user)


def update_admin_user(user, *, username, email, password="", group_names=None):
    duplicate_username_exists = (
        User.objects.filter(username=username)
        .exclude(id=user.id)
        .exists()
    )
    if duplicate_username_exists:
        raise ValueError("用户名已存在。")

    user.username = username
    user.email = email
    if password:
        user.set_password(password)
    user.save()

    if group_names is not None:
        return replace_user_groups(user, group_names)

    user.refresh_from_db()
    return serialize_admin_user_row(user)


def delete_admin_user(user):
    user.delete()
