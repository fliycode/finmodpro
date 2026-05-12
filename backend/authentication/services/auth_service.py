from django.contrib.auth import authenticate

from authentication.models import User
from rbac.services.rbac_service import (
    assign_default_member_group,
    collect_user_groups,
    collect_user_permission_names,
    ensure_user_role_bindings,
    get_avatar_url,
)


def build_user_summary(user):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "avatar_url": get_avatar_url(user),
    }


def build_user_auth_profile(user, *, summary=None):
    resolved_summary = summary or build_user_summary(user)
    return {
        **resolved_summary,
        "groups": collect_user_groups(user),
        "permissions": collect_user_permission_names(user),
    }


def register_user(*, username, password, email):
    user = User.objects.create_user(
        username=username,
        password=password,
        email=email,
    )
    assign_default_member_group(user)
    return user


def username_exists(username):
    return User.objects.filter(username=username).exists()


def authenticate_user(*, username, password):
    user = authenticate(username=username, password=password)
    if user is None:
        return None

    ensure_user_role_bindings(user)
    return user


def get_user_by_id(user_id):
    user = User.objects.get(id=user_id)
    ensure_user_role_bindings(user)
    return user
