import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.core.cache import cache


class RefreshSessionError(ValueError):
    pass


def _now():
    return datetime.now(tz=timezone.utc)


def _refresh_session_ttl(remember_me):
    return (
        settings.AUTH_REMEMBER_ME_REFRESH_TOKEN_LIFETIME_SECONDS
        if remember_me
        else settings.AUTH_REFRESH_TOKEN_LIFETIME_SECONDS
    )


def get_refresh_cookie_max_age(remember_me):
    if remember_me:
        return settings.AUTH_REMEMBER_ME_REFRESH_TOKEN_LIFETIME_SECONDS
    return None


def _cache_key(session_id):
    return f"auth:refresh:{session_id}"


def _hash_token_secret(token_secret):
    return hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        token_secret.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _build_cookie_value(session_id, token_secret):
    return f"{session_id}.{token_secret}"


def _parse_cookie_value(cookie_value):
    if not cookie_value or "." not in cookie_value:
        raise RefreshSessionError("Invalid refresh token")

    session_id, token_secret = cookie_value.split(".", 1)
    if not session_id or not token_secret:
        raise RefreshSessionError("Invalid refresh token")

    return session_id, token_secret


def create_refresh_session(*, user_id, remember_me=False):
    session_id = secrets.token_urlsafe(18)
    token_secret = secrets.token_urlsafe(32)
    ttl_seconds = _refresh_session_ttl(remember_me)
    expires_at = _now() + timedelta(seconds=ttl_seconds)
    session_record = {
        "session_id": session_id,
        "user_id": user_id,
        "remember_me": bool(remember_me),
        "current_token_hash": _hash_token_secret(token_secret),
        "previous_token_hash": "",
        "created_at": _now().isoformat(),
        "rotated_at": None,
        "expires_at": expires_at.isoformat(),
    }
    cache.set(_cache_key(session_id), session_record, timeout=ttl_seconds)
    return _build_cookie_value(session_id, token_secret), session_record


def rotate_refresh_session(cookie_value):
    session_id, token_secret = _parse_cookie_value(cookie_value)
    session_record = cache.get(_cache_key(session_id))
    if not session_record:
        raise RefreshSessionError("Refresh session not found")

    token_hash = _hash_token_secret(token_secret)
    if token_hash == session_record.get("previous_token_hash"):
        cache.delete(_cache_key(session_id))
        raise RefreshSessionError("Refresh token reuse detected")

    if token_hash != session_record.get("current_token_hash"):
        raise RefreshSessionError("Invalid refresh token")

    rotated_secret = secrets.token_urlsafe(32)
    ttl_seconds = _refresh_session_ttl(session_record.get("remember_me"))
    rotated_record = {
        **session_record,
        "current_token_hash": _hash_token_secret(rotated_secret),
        "previous_token_hash": token_hash,
        "rotated_at": _now().isoformat(),
        "expires_at": (_now() + timedelta(seconds=ttl_seconds)).isoformat(),
    }
    cache.set(_cache_key(session_id), rotated_record, timeout=ttl_seconds)
    return _build_cookie_value(session_id, rotated_secret), rotated_record


def revoke_refresh_session(cookie_value):
    try:
        session_id, _ = _parse_cookie_value(cookie_value)
    except RefreshSessionError:
        return

    cache.delete(_cache_key(session_id))
