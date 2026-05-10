from django.urls import path

from rbac.controllers import (
    admin_user_collection_view,
    admin_user_detail_view,
    admin_group_list_view,
    admin_user_groups_update_view,
    change_password_view,
    current_user_profile_view,
    upload_avatar_view,
)


urlpatterns = [
    path("auth/me", current_user_profile_view, name="auth-me"),
    path("auth/me/", current_user_profile_view, name="auth-me-slash"),
    path("auth/me/password", change_password_view, name="auth-me-password-legacy"),
    path("auth/me/password/", change_password_view, name="auth-me-password"),
    path("auth/me/avatar", upload_avatar_view, name="auth-avatar-legacy"),
    path("auth/me/avatar/", upload_avatar_view, name="auth-avatar"),
    path("admin/users", admin_user_collection_view, name="admin-user-list-legacy"),
    path("admin/users/", admin_user_collection_view, name="admin-user-list"),
    path("admin/groups", admin_group_list_view, name="admin-group-list-legacy"),
    path("admin/groups/", admin_group_list_view, name="admin-group-list"),
    path("admin/users/<int:user_id>", admin_user_detail_view, name="admin-user-detail-legacy"),
    path("admin/users/<int:user_id>/", admin_user_detail_view, name="admin-user-detail"),
    path(
        "admin/users/<int:user_id>/groups",
        admin_user_groups_update_view,
        name="admin-user-groups-update-legacy",
    ),
    path(
        "admin/users/<int:user_id>/groups/",
        admin_user_groups_update_view,
        name="admin-user-groups-update",
    ),
]
