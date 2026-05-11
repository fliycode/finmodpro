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
    return datetime.now(tz=timezone.utc)


def _hash_token(raw_token):
    return hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        raw_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


class PasswordResetError(ValueError):
    pass


def create_reset_token(*, username):
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        raise PasswordResetError("用户名不存在。")

    PasswordResetToken.objects.filter(
        user=user,
        used=False,
    ).update(used=True)

    raw_token = secrets.token_urlsafe(32)
    token_lifetime = settings.AUTH_PASSWORD_RESET_TOKEN_LIFETIME_SECONDS
    expires_at = _now() + timedelta(seconds=token_lifetime)

    PasswordResetToken.objects.create(
        user=user,
        token_hash=_hash_token(raw_token),
        expires_at=expires_at,
    )

    return raw_token, token_lifetime


def validate_reset_token(*, token):
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
    record = validate_reset_token(token=token)
    record.user.set_password(new_password)
    record.user.save()
    record.used = True
    record.save(update_fields=["used"])
    return record.user
