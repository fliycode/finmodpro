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
