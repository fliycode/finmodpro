"""
Refresh Token 会话管理

Refresh Token 存储于 Redis 缓存中（开发环境用本地内存缓存），
通过 HTTP-only Cookie 传递给前端，用于在 Access Token 过期后获取新 Token。

核心设计（参考 OAuth 2.0 Refresh Token 最佳实践）:
  - Session ID + Token Secret 的双令牌设计
  - 每次轮换（rotate）生成新的 Token Secret，旧的标记为 previous_token_hash
  - 检测重放攻击: 如果请求携带的是 previous_token_hash 而非 current，
    说明同一 Refresh Token 被使用了两次，立即吊销整个 Session。

Cookie 中的值: "{session_id}.{token_secret}"
Redis Key:    "auth:refresh:{session_id}" → session_record JSON

SpringBoot 类比: Spring Security OAuth2 TokenStore (JdbcTokenStore / RedisTokenStore)。
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.core.cache import cache


class RefreshSessionError(ValueError):
    """Refresh Token 会话异常。"""
    pass


def _now():
    """返回当前 UTC 时间。"""
    return datetime.now(tz=timezone.utc)


def _refresh_session_ttl(remember_me):
    """根据是否"记住我"返回 Refresh Token 的 TTL 秒数。

    remember_me=True:  7天
    remember_me=False: 1天
    """
    return (
        settings.AUTH_REMEMBER_ME_REFRESH_TOKEN_LIFETIME_SECONDS
        if remember_me
        else settings.AUTH_REFRESH_TOKEN_LIFETIME_SECONDS
    )


def get_refresh_cookie_max_age(remember_me):
    """获取 Refresh Cookie 的 Max-Age 值。

    remember_me=True:  返回具体秒数（浏览器持久化存储）
    remember_me=False: 返回 None（会话 Cookie — 浏览器关闭即删除）
    """
    if remember_me:
        return settings.AUTH_REMEMBER_ME_REFRESH_TOKEN_LIFETIME_SECONDS
    return None


def _cache_key(session_id):
    """生成 Redis 缓存键: auth:refresh:{session_id}"""
    return f"auth:refresh:{session_id}"


def _hash_token_secret(token_secret):
    """对 Token Secret 进行 HMAC-SHA256 哈希。"""
    return hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        token_secret.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _build_cookie_value(session_id, token_secret):
    """组装 Cookie 值: {session_id}.{token_secret}"""
    return f"{session_id}.{token_secret}"


def _parse_cookie_value(cookie_value):
    """解析 Cookie 值为 (session_id, token_secret)。

    抛出:
        RefreshSessionError — 格式无效
    """
    if not cookie_value or "." not in cookie_value:
        raise RefreshSessionError("Invalid refresh token")

    session_id, token_secret = cookie_value.split(".", 1)
    if not session_id or not token_secret:
        raise RefreshSessionError("Invalid refresh token")

    return session_id, token_secret


def create_refresh_session(*, user_id, remember_me=False):
    """为用户创建新的 Refresh Session。

    1. 生成随机 session_id 和 token_secret
    2. 保存 session_record 到 Redis 缓存（TTL 与 Token 有效期一致）
    3. 返回 Cookie value 和 session_record

    参数:
        user_id: 用户 ID
        remember_me: 是否"记住我" — 决定 Token 有效期和 Cookie 持久化
    返回:
        (cookie_value, session_record)
    """
    session_id = secrets.token_urlsafe(18)
    token_secret = secrets.token_urlsafe(32)
    ttl_seconds = _refresh_session_ttl(remember_me)
    expires_at = _now() + timedelta(seconds=ttl_seconds)

    session_record = {
        "session_id": session_id,
        "user_id": user_id,
        "remember_me": bool(remember_me),
        "current_token_hash": _hash_token_secret(token_secret),
        "previous_token_hash": "",         # 新 session 没有上一次的 token
        "created_at": _now().isoformat(),
        "rotated_at": None,
        "expires_at": expires_at.isoformat(),
    }
    cache.set(_cache_key(session_id), session_record, timeout=ttl_seconds)
    return _build_cookie_value(session_id, token_secret), session_record


def rotate_refresh_session(cookie_value):
    """轮换 Refresh Token — 验证旧 Token 并生成新 Token。

    这是 Refresh Token 安全性中最关键的一环:
    - 每次使用后轮换为新 Token，旧 Token 移到 previous_token_hash
    - 如果检测到 previous_token_hash 被再次使用 → 重放攻击 → 立即吊销

    参数:
        cookie_value: Cookie 中获取的 "{session_id}.{token_secret}"
    返回:
        (new_cookie_value, rotated_session_record)
    抛出:
        RefreshSessionError — Token 无效 / 重放攻击检测 / Session 不存在
    """
    session_id, token_secret = _parse_cookie_value(cookie_value)

    # 从缓存中读取 session record
    session_record = cache.get(_cache_key(session_id))
    if not session_record:
        raise RefreshSessionError("Refresh session not found")

    token_hash = _hash_token_secret(token_secret)

    # 重放攻击检测: 请求使用的是上一次已轮换的 token
    if token_hash == session_record.get("previous_token_hash"):
        cache.delete(_cache_key(session_id))  # 立即吊销 session
        raise RefreshSessionError("Refresh token reuse detected")

    # Token 不匹配当前的
    if token_hash != session_record.get("current_token_hash"):
        raise RefreshSessionError("Invalid refresh token")

    # 生成新的 token_secret 并轮换
    rotated_secret = secrets.token_urlsafe(32)
    ttl_seconds = _refresh_session_ttl(session_record.get("remember_me"))
    rotated_record = {
        **session_record,
        "current_token_hash": _hash_token_secret(rotated_secret),
        "previous_token_hash": token_hash,  # 旧 token 移到 previous
        "rotated_at": _now().isoformat(),
        "expires_at": (_now() + timedelta(seconds=ttl_seconds)).isoformat(),
    }
    cache.set(_cache_key(session_id), rotated_record, timeout=ttl_seconds)
    return _build_cookie_value(session_id, rotated_secret), rotated_record


def revoke_refresh_session(cookie_value):
    """吊销 Refresh Session — 用户登出时调用。

    安全地从 Redis 缓存中删除 session，使后续刷新请求失败。
    如果 cookie_value 格式无效则静默忽略（可能是已过期/已删除的 Cookie）。
    """
    try:
        session_id, _ = _parse_cookie_value(cookie_value)
    except RefreshSessionError:
        return

    cache.delete(_cache_key(session_id))
