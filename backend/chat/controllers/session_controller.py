from rest_framework.views import APIView

from chat.models import ChatSession
from chat.serializers import (
    ChatSessionDetailSerializer,
    ChatSessionListSerializer,
    ChatSessionSerializer,
    CreateChatSessionSerializer,
)
from chat.services.session_service import (
    create_chat_session,
    get_chat_session_for_user,
    list_chat_sessions_for_user,
)
from common.api_response import error_response, success_response
from rbac.services.authz_service import get_authenticated_user, user_has_permission


class ChatSessionCreateView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.ask_financial_qa"):
            return error_response(code=403, message="无权限。", status_code=403)

        sessions = list_chat_sessions_for_user(user=user)
        return success_response(data={"sessions": ChatSessionListSerializer(sessions, many=True).data})

    def post(self, request):
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.ask_financial_qa"):
            return error_response(code=403, message="无权限。", status_code=403)

        serializer = CreateChatSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = create_chat_session(
            user=user,
            title=serializer.validated_data.get("title", ""),
            context_filters=serializer.validated_data.get("context_filters", {}),
        )
        return success_response(
            data={"session": ChatSessionSerializer(session).data},
            status_code=201,
        )


class ChatSessionDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, session_id):
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.ask_financial_qa"):
            return error_response(code=403, message="无权限。", status_code=403)

        try:
            session = get_chat_session_for_user(user=user, session_id=session_id)
        except PermissionError as exc:
            return error_response(code=403, message=str(exc), status_code=403)
        except ChatSession.DoesNotExist:
            return error_response(code=404, message="会话不存在。", status_code=404)

        return success_response(data={"session": ChatSessionDetailSerializer(session).data})
