"""
DRF 认证后端 — JWT Bearer Token 认证

每个 HTTP 请求到达 DRF 视图前，此认证类会从 Authorization header 中提取 Bearer token，
解码验证后，将用户对象挂载到 request.user 上。

SpringBoot 类比: OncePerRequestFilter 或 AuthenticationProvider，
从 Header 中提取 Bearer token → 验证 → 设置 SecurityContext。
"""

from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication, get_authorization_header

from authentication.models import User
from authentication.services.jwt_service import decode_access_token


class JWTAuthentication(BaseAuthentication):
    """JWT Bearer Token 认证类。

    解析流程:
      1. 从请求头获取 Authorization: Bearer <token>
      2. 解码 token 签名和有效期
      3. 根据 token 中的 user_id 查找用户
      4. 返回 (user, token) 或 None（未提供 token 的情况）

    配置: 在 settings.py 的 REST_FRAMEWORK.DEFAULT_AUTHENTICATION_CLASSES 中注册。
    """

    keyword = "Bearer"  # Header 前缀: Authorization: Bearer <token>

    def authenticate(self, request):
        """从请求中提取并验证 JWT token。

        参数:
            request: DRF 的 HttpRequest 对象
        返回:
            (user, token_str) — 认证成功
            None — 没有提供 token（交给其他认证类或匿名访问）
        抛出:
            AuthenticationFailed — token 无效或过期
        """
        # 从 Authorization header 中按空格分割: ["Bearer", "<token>"]
        auth = get_authorization_header(request).split()
        if not auth:
            return None  # 没有提供认证 header，允许匿名访问

        # 检查前缀必须是 "Bearer"
        if auth[0].decode("utf-8") != self.keyword:
            return None

        # 格式不对（不是 "Bearer <token>"）
        if len(auth) != 2:
            raise exceptions.AuthenticationFailed("Authorization header 格式错误。")

        try:
            # 解码并验证 JWT
            claims = decode_access_token(auth[1].decode("utf-8"))
            # 根据 token 中的 user_id 查找用户
            user = User.objects.get(id=claims["user_id"])
        except (KeyError, User.DoesNotExist, ValueError) as exc:
            raise exceptions.AuthenticationFailed("无效的访问令牌。") from exc

        return (user, auth[1].decode("utf-8"))
