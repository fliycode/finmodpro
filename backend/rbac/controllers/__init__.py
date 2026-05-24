"""
RBAC 控制器包 — 视图聚合导出模块（Barrel File）。

作用：将 admin_controller 和 profile_controller 中所有对外暴露的视图函数统一
      在此 re-export，使得 URL 路由配置可以直接通过 `rbac.controllers` 引用，
      无需关心底层视图分布在哪个子模块。

类比 Spring Boot：相当于一个 `@Configuration` 类中集中注册所有 `@Bean`，
      或者说是将分散在各 Controller 类中的端点统一声明到同一个包级入口。
"""

from rbac.controllers.admin_controller import (
    admin_permission_list_view,
    admin_role_collection_view,
    admin_role_create_view,
    admin_role_detail_view,
    admin_role_restore_defaults_view,
    admin_user_collection_view,
    admin_user_detail_view,
    admin_group_list_view,
    admin_user_groups_update_view,
)
from rbac.controllers.profile_controller import (
    change_password_view,
    current_user_profile_view,
    upload_avatar_view,
)


__all__ = [
    "admin_user_collection_view",
    "admin_user_detail_view",
    "admin_group_list_view",
    "admin_user_groups_update_view",
    "admin_permission_list_view",
    "admin_role_collection_view",
    "admin_role_create_view",
    "admin_role_detail_view",
    "admin_role_restore_defaults_view",
    "change_password_view",
    "current_user_profile_view",
    "upload_avatar_view",
]
