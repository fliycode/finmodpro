"""
密码重置服务 — 生成重置 Token 并更新密码

流程:
  1. 用户提交用户名 → create_reset_token() 生成一次性 Token
  2. Token 原文返回给前端（在开发环境中直接显示，生产环境应发送邮件）
  3. 用户用 Token + 新密码 → reset_password() 验证并更新密码

安全设计:
  - 数据库只存 Token 的 HMAC-SHA256 哈希而非原文
  - 每个新 Token 生成前，会将同一用户的旧未用 Token 标记为已用
  - Token 有过期时间，过期后无法使用

SpringBoot 类比: PasswordResetTokenService @Service。
"""

import hashlib
import hmac
import secrets
from datetime import timedelta, timezone
from datetime import datetime

from django.conf import settings
from django.contrib.auth import get_user_model

from authentication.models import PasswordResetToken

User = get_user_model()


def _now():
    """返回当前 UTC 时间。"""
    return datetime.now(tz=timezone.utc)


def _hash_token(raw_token):
    """对 Token 原文进行 HMAC-SHA256 哈希。

    数据库中只存哈希值，防止数据库泄露后 Token 被直接使用。
    """
    return hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        raw_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


class PasswordResetError(ValueError):
    """密码重置流程中的业务异常。"""
    pass


def create_reset_token(*, username):
    """为指定用户生成密码重置 Token。

    1. 查找用户是否存在
    2. 将该用户所有旧未用 Token 标记为已用（防止滥用）
    3. 生成安全的随机 Token，存哈希到数据库
    4. 返回原文 Token（由调用方传递给用户）

    参数:
        username: 用户名
    返回:
        (raw_token, token_lifetime) — Token 原文和有效期秒数
    抛出:
        PasswordResetError — 用户名不存在
    """
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        raise PasswordResetError("用户名不存在。")

    # 将旧未用 Token 标记为已用
    PasswordResetToken.objects.filter(user=user, used=False).update(used=True)

    # 生成安全的随机 Token
    raw_token = secrets.token_urlsafe(32)
    token_lifetime = settings.AUTH_PASSWORD_RESET_TOKEN_LIFETIME_SECONDS
    expires_at = _now() + timedelta(seconds=token_lifetime)

    PasswordResetToken.objects.create(
        user=user,
        token_hash=_hash_token(raw_token),  # 存哈希，不存原文
        expires_at=expires_at,
    )

    return raw_token, token_lifetime


def validate_reset_token(*, token):
    """验证密码重置 Token 是否有效。

    检查: Token 哈希匹配、未被使用、未过期。

    参数:
        token: Token 原文（用户从邮件/链接中获得）
    返回:
        PasswordResetToken 记录
    抛出:
        PasswordResetError — Token 无效或已过期
    """
    token_hash = _hash_token(token)

    try:
        record = PasswordResetToken.objects.get(
            token_hash=token_hash,
            used=False,
        )
    except PasswordResetToken.DoesNotExist:
        raise PasswordResetError("重置链接无效或已过期。")

    if record.expires_at < _now():
        raise PasswordResetError("重置链接无效或已过期。")

    return record


def reset_password(*, token, new_password):
    """使用重置 Token 更新用户密码。

    1. 验证 Token 有效性
    2. 调用 Django 的 set_password() 更新密码（自动哈希）
    3. 标记 Token 为已使用

    参数:
        token: Token 原文
        new_password: 新密码（明文）
    返回:
        更新后的 User 实例
    抛出:
        PasswordResetError — Token 无效
    """
    record = validate_reset_token(token=token)
    record.user.set_password(new_password)  # Django 自动 bcrypt 哈希
    record.user.save()
    record.used = True
    record.save(update_fields=["used"])
    return record.user
