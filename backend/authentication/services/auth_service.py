from django.contrib.auth import authenticate

from authentication.models import User
from rbac.services.rbac_service import assign_default_member_group, ensure_user_role_bindings


def build_user_summary(user):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
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
