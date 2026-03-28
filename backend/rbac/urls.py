from django.urls import path

from rbac.controllers import (
    admin_group_list_view,
    admin_user_groups_update_view,
    admin_user_list_view,
    current_user_profile_view,
)


urlpatterns = [
    path("auth/me", current_user_profile_view, name="auth-me"),
    path("admin/users", admin_user_list_view, name="admin-user-list"),
    path("admin/groups", admin_group_list_view, name="admin-group-list"),
    path(
        "admin/users/<int:user_id>/groups",
        admin_user_groups_update_view,
        name="admin-user-groups-update",
    ),
]
