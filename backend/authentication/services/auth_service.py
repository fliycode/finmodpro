"""
用户认证服务 — 注册、登录、用户信息查询

Controller 不直接操作数据库，而是调用此模块的函数。
所有数据库查询和用户创建逻辑集中在此。

SpringBoot 类比: UserService / AuthService @Service 类。
"""

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
    """构建用户基本摘要信息。

    返回包含 id/username/email/avatar 的字典，不包含权限和组信息。
    用于 JWT token payload 和轻量级展示。
    """
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "avatar_url": get_avatar_url(user),
    }


def build_user_auth_profile(user, *, summary=None):
    """构建用户的完整认证资料（含权限和角色组）。

    参数:
        user: User 实例
        summary: 可选，预先构建的 user_summary，避免重复计算
    返回:
        合并了 groups 和 permissions 的完整用户资料字典
    """
    resolved_summary = summary or build_user_summary(user)
    return {
        **resolved_summary,
        "groups": collect_user_groups(user),
        "permissions": collect_user_permission_names(user),
    }


def register_user(*, username, password, email):
    """注册新用户。

    1. 通过 Django UserManager 创建 User（自动哈希密码）
    2. 分配默认 member 角色组

    参数:
        username: 用户名
        password: 明文密码（Django 会自动 bcrypt 哈希）
        email: 邮箱（可选）
    返回:
        新创建的 User 实例
    """
    user = User.objects.create_user(
        username=username,
        password=password,
        email=email,
    )
    assign_default_member_group(user)  # 给新用户分配默认角色
    return user


def username_exists(username):
    """检查用户名是否已被注册。"""
    return User.objects.filter(username=username).exists()


def authenticate_user(*, username, password):
    """验证用户名和密码。

    使用 Django 内置的 authenticate() 函数，自动比对密码哈希。

    参数:
        username: 用户名
        password: 明文密码
    返回:
        User 实例（认证成功）或 None（用户名不存在或密码不匹配）
    """
    user = authenticate(username=username, password=password)
    if user is None:
        return None

    ensure_user_role_bindings(user)  # 确保用户有角色绑定
    return user


def get_user_by_id(user_id):
    """根据用户 ID 获取用户。

    用于 Token 刷新等场景 — Refresh Token 验证通过后，通过 user_id 取用户。

    抛出:
        User.DoesNotExist — 用户不存在
    """
    user = User.objects.get(id=user_id)
    ensure_user_role_bindings(user)
    return user
