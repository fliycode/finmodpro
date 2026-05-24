"""
RBAC 核心业务服务 — 角色/权限管理的业务逻辑层。

作用：封装所有角色、权限、用户分组的增删改查核心操作，是平台权限体系的"单一事实来源"。
      提供权限种子（seed）、角色默认权限定义、用户-角色绑定、序列化等能力。

类比 Spring Boot：
  - 本模块相当于一个 `@Service`（RbacService），其中每个函数是一个公开或私有的业务方法。
  - ROLE_PERMISSION_MAP 常量相当于 Spring Security 配置类中的角色-权限映射表，
    即 `antMatchers("/admin/**").hasRole("ADMIN")` 的数据化版本。
  - `ensure_custom_permissions` 相当于应用启动时自动执行的 `PermissionInitializer`。
"""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from authentication.models import User, UserProfile


# =============================================================================
# 系统角色常量定义 — 类似于 Spring Security 的角色枚举/配置
# =============================================================================

ROLE_SUPER_ADMIN = "super_admin"        # 超级管理员 — 类似于 ROLE_SUPER_ADMIN
ROLE_ADMIN = "admin"                    # 管理员 — 类似于 ROLE_ADMIN
ROLE_MEMBER = "member"                  # 普通成员 — 类似于 ROLE_USER
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

# 系统角色必须保留的最低权限集合 — 即使管理员修改系统角色的权限，这些权限也不能被移除
# 类似于 Spring Security 中角色继承体系中的"不可剥离权限"
SYSTEM_ROLE_REQUIRED_PERMISSION_CODENAMES = {
    ROLE_SUPER_ADMIN: {"view_role", "assign_role"},
}

# =============================================================================
# 自定义权限定义 — 类似于 Spring Security 的 GrantedAuthority 注册表
# =============================================================================

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

# =============================================================================
# 角色-权限映射表 — 类似于 Spring Security 的 securityFilterChain 权限矩阵
# =============================================================================
# 每个系统角色所拥有的权限集合（格式："app_label.codename"）。
# ROLE_SUPER_ADMIN: 拥有平台全部权限。
# ROLE_ADMIN:       大部分管理功能，但缺少 user 删除和 assign_role。
# ROLE_MEMBER:      仅基础功能：仪表板、文档查看、金融问答。

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


# =============================================================================
# 权限初始化（idempotent）— 类似于 Spring Boot 启动时执行的数据初始化
# =============================================================================


def ensure_custom_permissions():
    """
    确保所有自定义权限（CUSTOM_PERMISSION_DEFINITIONS）已在 Django 权限表中存在。

    使用 `get_or_create` 实现幂等操作：多次调用不会重复创建权限。

    返回:
        dict[str, Permission]: 以 "auth.<codename>" 为键的权限对象字典。

    类比 Spring Boot:
        `ApplicationRunner` 或 `@PostConstruct` 中执行的权限初始化，
        确保数据库中存储的权限与代码定义一致。
    """
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
    """
    判断给定的角色名称是否属于三大系统角色之一。

    参数:
        role_name: str，角色名称。

    返回:
        bool: 是系统角色则返回 True。

    类比 Spring Boot: 检查某个 Role 是否为内置角色（如 ROLE_ADMIN），
    内置角色与自定义角色有不同的约束规则。
    """
    return role_name in SYSTEM_ROLE_NAMES


def ensure_role_groups():
    """
    确保三个系统角色的 Django Group 存在（idempotent 操作）。

    实现 Redis 缓存策略：首次调用或缓存失效时写数据库并设缓存；否则直接返回缓存。
    缓存键为 "rbac:role_groups"，TTL 3600 秒。

    返回:
        dict[str, Group]: 以角色名为键的 Group 对象字典。

    类比 Spring Boot:
        `@Cacheable` 注解方法，使用 Redis 作为缓存后端，
        确保启动时三个核心 Role 实体已就绪。
    """
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


# =============================================================================
# 内部辅助函数
# =============================================================================


def _get_permissions_by_name(permission_names):
    """
    根据权限全名列表（如 "auth.view_user"）批量获取 Permission 实例。

    参数:
        permission_names: iterable[str]，权限的全限定名称（app_label.codename）。

    返回:
        list[Permission]: 对应的 Permission 模型实例列表。

    类比 Spring Boot:
        `permissionRepository.findByNames(names)` — 在数据库/缓存中批量
        查找 GrantedAuthority 实体。
    """
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
    """
    从全限定权限名（如 "auth.view_dashboard"）中提取 codename 部分。

    参数:
        permission_name: str，形如 "app_label.codename" 的全限定名。

    返回:
        str: 仅 codename 部分（如 "view_dashboard"）；若不含 "." 则原样返回。

    类比 Spring Boot: 从 "ROLE_ADMIN" 中剥离 "ROLE_" 前缀，得到 "ADMIN"。
    """
    return permission_name.split(".", 1)[1] if "." in permission_name else permission_name


def get_role_default_permission_codenames(role_name):
    """
    获取指定系统角色的默认权限 codename 列表（去前缀）。

    参数:
        role_name: str，角色名称。

    返回:
        list[str]: 该角色默认拥有的权限 codename 列表（已排序，不含 app_label 前缀）。

    类比 Spring Boot: 查询 ROLE_xxx 对应的静态权限配置，返回裸权限名列表。
    """
    return sorted(_strip_permission_name(name) for name in ROLE_PERMISSION_MAP.get(role_name, set()))


# =============================================================================
# 权限/角色/用户 查询函数 — 类似于 Spring Data JPA Repository 的 find/list 方法
# =============================================================================


def list_rbac_permissions():
    """
    列出平台上所有可用的 RBAC 权限。

    每种权限的信息包括：id、codename、name、app_label、
    以及默认被分配给哪些系统角色（assigned_by_default_to 字段）。

    返回:
        list[dict]: 序列化的权限对象列表。

    类比 Spring Boot:
        `permissionRepository.findAll()` 后转换为 `List<PermissionDTO>`，
        每个 DTO 附带所属角色的关联信息。
    """
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
    """
    获取某个角色组下的所有用户列表（按 ID 排序）。

    参数:
        group: Django Group 实例。

    返回:
        list[User]: 该组的成员用户列表。

    类比 Spring Boot: `group.getUsers()` — JPA ManyToMany 关联的惰性集合查询。
    """
    return list(group.user_set.order_by("id"))


def serialize_admin_role_row(group):
    """
    将一个 Django Group 序列化为管理员视角的角色摘要行。

    包含角色基本信息、权限集合、是否为系统角色、成员数量等。
    has_customized_permissions 字段标记系统角色是否被自定义修改过权限。

    参数:
        group: Django Group 实例。

    返回:
        dict: 角色摘要字典。

    类比 Spring Boot: Entity → RoleSummaryDTO 转换器（MapStruct / ModelMapper）。
    """
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
    """
    将一个 Django Group 序列化为管理员视角的角色详情（含成员列表）。

    在 serialize_admin_role_row 的基础上增加 assigned_users 字段。

    参数:
        group: Django Group 实例。

    返回:
        dict: 角色详情字典，含 assigned_users 列表。

    类比 Spring Boot: Entity → RoleDetailDTO 转换器。
    """
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
    """
    按名称排序返回所有角色的摘要列表。

    返回:
        list[dict]: 角色摘要对象列表。

    类比 Spring Boot: `roleRepository.findAll()` → `List<RoleSummaryDTO>`。
    """
    groups = Group.objects.order_by("name").prefetch_related("permissions", "user_set")
    return [serialize_admin_role_row(group) for group in groups]


def get_admin_role_detail(role_id):
    """
    根据角色 ID 获取角色详情（含成员列表）。

    参数:
        role_id: int，角色（Group）ID。

    返回:
        dict: 角色详情字典。

    异常:
        Group.DoesNotExist: 指定 ID 的角色不存在。

    类比 Spring Boot: `roleRepository.findById(roleId)` → `RoleDetailDTO`，
    不存在时抛出 `EntityNotFoundException`（此处由 Django 的 DoesNotExist 承载）。
    """
    group = Group.objects.prefetch_related("permissions", "user_set").get(id=role_id)
    return serialize_admin_role_detail(group)


# =============================================================================
# 角色 CRUD — 类似于 Spring Boot @Service 中的事务方法
# =============================================================================


def _normalize_role_name(role_name):
    """
    规范化角色名称：去首尾空格，校验非空和最大长度。

    参数:
        role_name: str，原始角色名称。

    返回:
        str: 规范化后的角色名称。

    异常:
        ValueError: 名称为空或超过字段最大长度限制。

    类比 Spring Boot: `@Valid` + Bean Validation 中的 `@NotBlank` / `@Size` 校验。
    """
    normalized_role_name = (role_name or "").strip()
    max_length = Group._meta.get_field("name").max_length

    if not normalized_role_name:
        raise ValueError("角色名称不能为空。")
    if len(normalized_role_name) > max_length:
        raise ValueError(f"角色名称不能超过 {max_length} 个字符。")
    return normalized_role_name


def _get_group_by_id(role_id):
    """
    根据 ID 获取 Group 实例。

    参数:
        role_id: int，角色（Group）ID。

    返回:
        Group: 对应的 Group 实例。

    异常:
        Group.DoesNotExist: 指定 ID 的角色不存在。

    类比 Spring Boot: `groupRepository.getReferenceById(roleId)`。
    """
    return Group.objects.get(id=role_id)


def _resolve_permissions_by_codenames(permission_codenames):
    """
    将权限 codename 列表解析为 Permission 实例列表。

    同时完成以下校验：
    - 去重、去前后空格。
    - 所有 codename 必须能在数据库中查找到。

    参数:
        permission_codenames: list[str] | None，权限 codename 列表。

    返回:
        list[Permission] | None: 对应的 Permission 实例列表；若传入 None 则返回 None。

    异常:
        ValueError: codename 列表为空、或包含数据库中不存在的权限名。

    类比 Spring Boot: `permissionRepository.findByCodenameIn(codenames)`，
    找不到时抛异常提示非法权限。
    """
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
    """
    校验系统角色的权限集合是否保留了其必须拥有的最低权限。

    如果系统角色缺少 SYSTEM_ROLE_REQUIRED_PERMISSION_CODENAMES 中定义的必须权限，
    则抛出异常阻止保存。

    参数:
        group:                Django Group 实例。
        permission_codenames: list[str]，待设置的权限 codename 列表。

    异常:
        ValueError: 系统角色缺少必须保留的权限。

    类比 Spring Boot: 业务规则校验，类似于"超级管理员必须拥有 view_role 权限"的硬约束。
    """
    if not is_system_role_name(group.name):
        return

    required_permission_codenames = SYSTEM_ROLE_REQUIRED_PERMISSION_CODENAMES.get(group.name, set())
    missing_codenames = sorted(required_permission_codenames - set(permission_codenames))
    if missing_codenames:
        raise ValueError(
            f"系统角色 {group.name} 必须保留权限: {', '.join(missing_codenames)}"
        )


def create_admin_role(*, name, permission_codenames=None):
    """
    创建新的自定义角色。

    参数:
        name (str):                    角色名称（必填，须唯一）。
        permission_codenames (list[str] | None): 初始权限 codename 列表（可选）。

    返回:
        dict: 新创建角色的详情（含成员列表）。

    异常:
        ValueError: 名称已存在、权限非法。

    类比 Spring Boot:
        `roleService.createRole(RoleCreateDTO)` —
        使用 `@Transactional` 保证原子性，
        Group.objects.create(...) + group.permissions.set(...)。
    """
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
    """
    更新角色：可修改名称和/或权限集合（至少提供一项）。

    系统角色不允许重命名；名称冲突、权限非法等场景将抛出异常。

    参数:
        role_id (int):                   角色 ID。
        name (str | None):               新角色名称（可选）。
        permission_codenames (list[str] | None): 新权限 codename 列表（可选）。

    返回:
        dict: 更新后的角色详情。

    异常:
        ValueError:     参数校验失败（名称冲突、系统角色重命名等）。
        Group.DoesNotExist: 角色不存在。

    类比 Spring Boot:
        `roleService.updateRole(roleId, RoleUpdateDTO)` —
        条件更新字段，save() 后 refresh 以获取最新状态。
    """
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
    """
    将指定系统角色的权限集合恢复为 ROLE_PERMISSION_MAP 中的默认值。

    仅系统角色支持此操作，自定义角色会抛出异常。

    参数:
        role_id: int，角色（Group）ID。

    返回:
        dict: 恢复默认权限后的角色详情。

    异常:
        ValueError: 非系统角色（不支持恢复默认）。

    类比 Spring Boot:
        类似于"重置为出厂设置"的管理操作，仅对内置角色有效。
    """
    group = _get_group_by_id(role_id)
    if not is_system_role_name(group.name):
        raise ValueError("仅系统角色支持恢复默认权限。")

    default_permissions = _get_permissions_by_name(ROLE_PERMISSION_MAP[group.name])
    group.permissions.set(default_permissions)
    group.refresh_from_db()
    return serialize_admin_role_detail(group)


def delete_admin_role(role_id):
    """
    删除角色：系统角色和仍有用户关联的角色不可删除。

    参数:
        role_id: int，要删除的角色 ID。

    异常:
        ValueError:      系统角色不允许删除、或角色仍有关联用户。
        Group.DoesNotExist: 角色不存在。

    类比 Spring Boot: `roleRepository.deleteById(roleId)` —
    在此之前有业务规则校验（内置角色不可删、有成员不可删）。
    """
    group = _get_group_by_id(role_id)
    if is_system_role_name(group.name):
        raise ValueError("系统角色不允许删除。")
    if group.user_set.exists():
        raise ValueError("角色仍有关联用户，无法删除。")
    group.delete()


# =============================================================================
# 权限种子与引导 — 类似于 Spring Boot 应用启动初始化
# =============================================================================


def seed_roles_and_permissions(*, reset_system_role_permissions=False):
    """
    初始化（种子填充）系统角色及其权限。

    如果角色组尚未拥有任何权限，或指定了 reset_system_role_permissions=True，
    则根据 ROLE_PERMISSION_MAP 重新设置权限。

    参数:
        reset_system_role_permissions (bool): 是否强制重置所有系统角色的权限为默认值。

    返回:
        dict[str, Group]: 以角色名为键的 Group 对象字典。

    类比 Spring Boot:
        ApplicationRunner / CommandLineRunner 中的初始化方法，
        类似 `DataInitializer` 在应用启动时执行 `INSERT ... ON DUPLICATE KEY UPDATE`。
    """
    groups = ensure_role_groups()
    seeded_groups = {}

    for role_name, permission_names in ROLE_PERMISSION_MAP.items():
        group = groups[role_name]
        if reset_system_role_permissions or not group.permissions.exists():
            group.permissions.set(_get_permissions_by_name(permission_names))
        seeded_groups[role_name] = group

    return seeded_groups


def ensure_rbac_bootstrapped():
    """
    确保 RBAC 基础数据已初始化（供其他模块在启动时调用）。

    返回:
        dict[str, Group]: 以角色名为键的 Group 对象字典。

    类比 Spring Boot:
        被 @PostConstruct / ApplicationListener<ContextRefreshedEvent> 调用的
        初始化方法，确保 RBAC 基础设施就绪。
    """
    return seed_roles_and_permissions()


# =============================================================================
# 用户-角色绑定 — 类似于 Spring Security 的 UserDetailsService 授予角色
# =============================================================================


def ensure_user_role_bindings(user):
    """
    确保用户至少绑定到一个默认角色（member）。

    绑定规则:
        - 如果用户尚无任何分组：根据 is_superuser / is_staff 属性分配对应角色。
          * superuser → super_admin
          * staff    → admin
          * 其他      → member
        - 如果已有分组但缺少其"应有"角色：补充绑定。

    参数:
        user: Django User 实例。

    返回:
        Group: 分配给用户的默认角色 Group。

    类比 Spring Boot: 确保 UserDetails 的 GrantedAuthority 列表不为空，
    类似 `UserDetailsService.loadUserByUsername()` 中默认授予 ROLE_USER。
    """
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
    """
    为新用户分配默认 member 分组。

    参数:
        user: Django User 实例。

    返回:
        Group: 分配给用户的 member 角色 Group。

    类比 Spring Boot: 用户注册后自动授予 ROLE_USER 默认角色。
    """
    member_group = ensure_user_role_bindings(user)
    return member_group


# =============================================================================
# 用户权限收集 — 类似于 SecurityContext 中的 getAuthorities
# =============================================================================


def collect_user_groups(user):
    """
    收集用户所属的所有分组（角色）名称列表。

    参数:
        user: Django User 实例。

    返回:
        list[str]: 分组名称列表（已排序）。

    类比 Spring Boot: `user.getAuthorities()` 返回 `Collection<GrantedAuthority>`，
    此处返回角色名列表。
    """
    return sorted(user.groups.values_list("name", flat=True))


def collect_user_permission_names(user):
    """
    收集用户的所有权限 codename（去掉 app_label 前缀）。

    通过 Django 的 `get_all_permissions()` 获取用户的所有权限（含通过分组继承的权限），
    然后剥离 "auth." 前缀。

    参数:
        user: Django User 实例。

    返回:
        list[str]: 权限 codename 列表（已排序）。

    类比 Spring Boot:
        从 Authentication 对象中提取所有 GrantedAuthority 的 authority 字符串。
    """
    return sorted(permission_name.split(".", 1)[1] for permission_name in user.get_all_permissions())


def get_avatar_url(user):
    """
    获取用户的头像 URL。

    参数:
        user: Django User 实例。

    返回:
        str | None: 头像的静态文件 URL；若用户无头像则返回 None。

    类比 Spring Boot: 访问 UserProfile 实体上的 avatar 字段（OneToOne 关联）。
    """
    try:
        profile = user.profile
    except (UserProfile.DoesNotExist, AttributeError):
        return None
    if profile.avatar:
        return profile.avatar.url
    return None


# =============================================================================
# 用户序列化 — 类似于 DTO 转换器（ModelMapper / MapStruct）
# =============================================================================


def serialize_user_rbac_profile(user):
    """
    将用户序列化为前端所需的完整 RBAC 资料对象。

    包含基本信息、头像、分组、权限、注册时间、统计信息（通过 profile_stats_service）。

    参数:
        user: Django User 实例。

    返回:
        dict: 用户 RBAC 资料字典。

    类比 Spring Boot: `userMapper.toProfileDTO(user)` —
    将 User 实体 + UserProfile 实体 + 权限信息合并为一个前端 DTO。
    """
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
    """
    将用户序列化为管理员列表中的一行摘要。

    相比 serialize_user_rbac_profile，增加了 is_superuser、is_staff 字段，
    但不包含 stats 和 avatar_url（管理员列表不需要）。

    参数:
        user: Django User 实例。

    返回:
        dict: 管理员用户摘要字典。

    类比 Spring Boot: `userMapper.toAdminDTO(user)` —
    面向管理后台的用户列表 DTO。
    """
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


# =============================================================================
# 管理员用户管理 — 类似于 Spring Boot 的 UserAdminService CRUD
# =============================================================================


def list_admin_user_rows():
    """
    按 ID 排序返回所有用户的摘要列表。

    返回:
        list[dict]: 管理员用户摘要对象列表。

    类比 Spring Boot: `userRepository.findAll()` → `List<UserAdminDTO>`。
    """
    return [
        serialize_admin_user_row(user)
        for user in User.objects.order_by("id")
    ]


def list_assignable_groups():
    """
    列出所有可分配的分组（Django Group），供管理员为用户分配角色时参照。

    返回:
        list[dict]: 包含 id 和 name 字段的分组字典列表。

    类比 Spring Boot: `roleRepository.findAll()` → `List<RoleOptionDTO>`，
    用于前端下拉菜单的数据源。
    """
    return list(Group.objects.order_by("name").values("id", "name"))


def replace_user_groups(user, group_names):
    """
    将用户的角色分组整体替换为指定的分组列表。

    所有指定的分组名称必须在数据库中存在；若有不存在的分组名称将抛出异常。

    参数:
        user:        Django User 实例。
        group_names: list[str]，目标分组名称列表。

    返回:
        dict: 更新后的管理员用户摘要对象。

    异常:
        ValueError: 指定的分组名称中存在未知分组。

    类比 Spring Boot:
        `user.setRoles(newRoleSet)` + `userRepository.save(user)` —
        替换 User-Role ManyToMany 关系的全部记录。
    """
    groups = list(Group.objects.filter(name__in=group_names).order_by("name"))
    found_group_names = {group.name for group in groups}
    missing_group_names = sorted(set(group_names) - found_group_names)
    if missing_group_names:
        raise ValueError(f"Unknown groups: {', '.join(missing_group_names)}")

    user.groups.set(groups)
    user.refresh_from_db()
    return serialize_admin_user_row(user)


def create_admin_user(*, username, email, password, group_names=None):
    """
    通过管理员接口创建新用户。

    可选地分配分组；若未指定 group_names，则自动分配默认 member 分组。

    参数:
        username (str):              用户名（必填，须唯一）。
        email (str):                 邮箱（必填）。
        password (str):              密码（必填，明文，由 Django 内部哈希）。
        group_names (list[str] | None): 初始分组列表（可选）。

    返回:
        dict: 新创建的管理员用户摘要对象。

    异常:
        ValueError: 用户名已存在。
        Django 数据库异常: 其他唯一性冲突。

    类比 Spring Boot:
        `userService.createUser(UserCreateDTO)` —
        `passwordEncoder.encode()` 后 `userRepository.save()`，
        再通过 ManyToMany 关联保存角色。
    """
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
    """
    通过管理员接口更新用户信息。

    可更新 username、email、password（非空时才更新）和 group_names（None 表示不修改分组）。

    参数:
        user (User):                       待更新的用户实例。
        username (str):                    新用户名。
        email (str):                       新邮箱。
        password (str):                    新密码（空字符串表示不修改密码）。
        group_names (list[str] | None):    新分组列表（None 表示保持不变）。

    返回:
        dict: 更新后的管理员用户摘要对象。

    异常:
        ValueError: 用户名与现有用户冲突。

    类比 Spring Boot:
        `userService.updateUser(userId, UserUpdateDTO)` —
        条件更新字段，save() 后返回更新后的 DTO。
    """
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
    """
    通过管理员接口删除用户。

    参数:
        user: Django User 实例（待删除的用户）。

    类比 Spring Boot: `userRepository.delete(user)` —
    物理删除用户记录。
    """
    user.delete()
