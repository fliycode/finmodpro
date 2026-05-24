"""
JWT 令牌服务 — Access Token 的生成与解码

此项目使用自实现 JWT（不依赖 django-rest-framework-simplejwt 或 PyJWT），
采用 HMAC-SHA256 签名，使用 Base64URL 编码的三段式格式: header.payload.signature

JWT 格式:
  - Header:  {"alg": "HS256", "typ": "JWT"}   → Base64URL 编码
  - Payload: {"sub": username, "user_id": ..., "iat": ..., "exp": ...}  → Base64URL 编码
  - Signature: HMAC-SHA256(header.payload, secret_key)  → Base64URL 编码

SpringBoot 类比: JwtEncoder / JwtDecoder + Nimbus Jose JWT 库。
"""

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

from django.conf import settings


def _urlsafe_b64encode(raw_bytes):
    """Base64URL 编码（去掉末尾 = 填充符，适合 URL 安全传输）。"""
    return base64.urlsafe_b64encode(raw_bytes).rstrip(b"=").decode("ascii")


def _urlsafe_b64decode(raw_text):
    """Base64URL 解码（先补回 = 填充符再解码）。"""
    padding = "=" * (-len(raw_text) % 4)
    return base64.urlsafe_b64decode(f"{raw_text}{padding}")


def _sign(message):
    """对消息进行 HMAC-SHA256 签名。

    参数:
        message: 签名输入字符串 (header.payload)
    返回:
        32 字节的签名结果
    """
    return hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        message.encode("ascii"),
        hashlib.sha256,
    ).digest()


def generate_access_token(user, lifetime_seconds=None):
    """为用户生成 JWT Access Token。

    参数:
        user: User 实例
        lifetime_seconds: Token 有效期秒数，默认使用全局配置 JWT_ACCESS_TOKEN_LIFETIME_SECONDS
    返回:
        三段式 JWT 字符串 (header.payload.signature)
    """
    issued_at = datetime.now(tz=timezone.utc)
    token_lifetime_seconds = (
        settings.JWT_ACCESS_TOKEN_LIFETIME_SECONDS
        if lifetime_seconds is None
        else lifetime_seconds
    )
    expires_at = issued_at + timedelta(seconds=token_lifetime_seconds)

    # Token Payload — JWT Claims
    payload = {
        "sub": user.username,            # subject — 用户名
        "user_id": user.id,              # 用户 ID（本项目自定义字段）
        "iat": int(issued_at.timestamp()),  # issued at — 签发时间
        "exp": int(expires_at.timestamp()),  # expiration — 过期时间
    }
    header = {"alg": settings.JWT_ALGORITHM, "typ": "JWT"}

    # 编码 Header 和 Payload
    encoded_header = _urlsafe_b64encode(
        json.dumps(header, separators=(",", ":")).encode("utf-8")
    )
    encoded_payload = _urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )

    # 签名
    signing_input = f"{encoded_header}.{encoded_payload}"
    signature = _urlsafe_b64encode(_sign(signing_input))

    return f"{signing_input}.{signature}"


def decode_access_token(token):
    """解码并验证 JWT Access Token。

    验证步骤:
      1. 解析三段式格式
      2. 验证签名（HMAC 比对）
      3. 验证算法是否匹配
      4. 验证是否过期

    参数:
        token: JWT 字符串
    返回:
        解码后的 payload 字典 {"sub": ..., "user_id": ..., "iat": ..., "exp": ...}
    抛出:
        ValueError — token 格式错误 / 签名无效 / 算法不匹配 / 已过期
    """
    # 1. 拆分为三部分
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
    except ValueError as exc:
        raise ValueError("Invalid token format") from exc

    # 2. 验证签名
    signing_input = f"{encoded_header}.{encoded_payload}"
    expected_signature = _urlsafe_b64encode(_sign(signing_input))
    if not hmac.compare_digest(encoded_signature, expected_signature):
        raise ValueError("Invalid token signature")

    # 3. 验证算法
    header = json.loads(_urlsafe_b64decode(encoded_header))
    if header.get("alg") != settings.JWT_ALGORITHM:
        raise ValueError("Unsupported token algorithm")

    # 4. 验证有效期
    payload = json.loads(_urlsafe_b64decode(encoded_payload))
    now_timestamp = int(datetime.now(tz=timezone.utc).timestamp())
    if payload.get("exp", 0) < now_timestamp:
        raise ValueError("Token has expired")

    return payload
