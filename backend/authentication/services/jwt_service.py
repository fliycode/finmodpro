import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

from django.conf import settings


def _urlsafe_b64encode(raw_bytes):
    return base64.urlsafe_b64encode(raw_bytes).rstrip(b"=").decode("ascii")


def _urlsafe_b64decode(raw_text):
    padding = "=" * (-len(raw_text) % 4)
    return base64.urlsafe_b64decode(f"{raw_text}{padding}")


def _sign(message):
    return hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        message.encode("ascii"),
        hashlib.sha256,
    ).digest()


def generate_access_token(user):
    issued_at = datetime.now(tz=timezone.utc)
    expires_at = issued_at + timedelta(seconds=settings.JWT_ACCESS_TOKEN_LIFETIME_SECONDS)
    payload = {
        "sub": user.username,
        "user_id": user.id,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    header = {
        "alg": settings.JWT_ALGORITHM,
        "typ": "JWT",
    }
    encoded_header = _urlsafe_b64encode(
        json.dumps(header, separators=(",", ":")).encode("utf-8")
    )
    encoded_payload = _urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    signing_input = f"{encoded_header}.{encoded_payload}"
    signature = _urlsafe_b64encode(_sign(signing_input))
    return f"{signing_input}.{signature}"


def decode_access_token(token):
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
    except ValueError as exc:
        raise ValueError("Invalid token format") from exc

    signing_input = f"{encoded_header}.{encoded_payload}"
    expected_signature = _urlsafe_b64encode(_sign(signing_input))
    if not hmac.compare_digest(encoded_signature, expected_signature):
        raise ValueError("Invalid token signature")

    header = json.loads(_urlsafe_b64decode(encoded_header))
    if header.get("alg") != settings.JWT_ALGORITHM:
        raise ValueError("Unsupported token algorithm")

    payload = json.loads(_urlsafe_b64decode(encoded_payload))
    now_timestamp = int(datetime.now(tz=timezone.utc).timestamp())
    if payload.get("exp", 0) < now_timestamp:
        raise ValueError("Token has expired")

    return payload
