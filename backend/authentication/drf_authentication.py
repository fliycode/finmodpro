from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication, get_authorization_header

from authentication.models import User
from authentication.services.jwt_service import decode_access_token


class JWTAuthentication(BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        auth = get_authorization_header(request).split()
        if not auth:
            return None

        if auth[0].decode("utf-8") != self.keyword:
            return None

        if len(auth) != 2:
            raise exceptions.AuthenticationFailed("Authorization header 格式错误。")

        try:
            claims = decode_access_token(auth[1].decode("utf-8"))
            user = User.objects.get(id=claims["user_id"])
        except (KeyError, User.DoesNotExist, ValueError) as exc:
            raise exceptions.AuthenticationFailed("无效的访问令牌。") from exc

        return (user, auth[1].decode("utf-8"))
