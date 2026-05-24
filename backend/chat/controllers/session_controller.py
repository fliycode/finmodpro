"""
Chat 会话管理控制器（Session Controller）。

类比 SpringBoot：
  - ChatSessionCreateView 相当于 @RestController 类：
      GET   -> @GetMapping("/sessions")  列出会话列表
      POST  -> @PostMapping("/sessions") 创建新会话
  - ChatSessionDetailView 相当于：
      GET    -> @GetMapping("/sessions/{sessionId}")    获取会话详情
      DELETE -> @DeleteMapping("/sessions/{sessionId}")  删除会话
  - ChatSessionExportView 相当于：
      GET -> @GetMapping("/sessions/{sessionId}/export")  导出会话数据

本模块处理聊天会话的 CRUD 操作，支持按 dataset_id / keyword 过滤列表，以及会话数据的完整导出。
"""

from django.http import JsonResponse
from rest_framework.views import APIView

from chat.models import ChatSession
from chat.serializers import (
    ChatSessionDetailSerializer,
    ChatSessionListSerializer,
    ChatSessionSerializer,
    CreateChatSessionSerializer,
)
from chat.services.session_service import (
    build_chat_session_export,
    create_chat_session,
    delete_chat_session_for_user,
    get_chat_session_for_user,
    list_chat_sessions_for_user,
)
from common.api_response import error_response, success_response
from rbac.services.authz_service import get_authenticated_user, user_has_permission


class ChatSessionCreateView(APIView):
    """
    会话管理与创建视图。

    类比 SpringBoot：
      - 同时处理 GET（列表）和 POST（创建）请求。
      - GET 返回当前用户的会话列表，支持 dataset_id / keyword 过滤。
      - POST 创建一条新的聊天会话。
    """

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """
        获取当前用户的会话列表。

        查询参数：
          - dataset_id: 数据集 ID（可选，过滤关联特定数据集的会话）。
          - keyword: 关键词搜索（可选，匹配标题或消息内容）。

        返回：
          - 成功：{"sessions": [...]}
          - 失败：401（未认证）/ 403（无权限）
        """
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.ask_financial_qa"):
            return error_response(code=403, message="无权限。", status_code=403)

        sessions = list_chat_sessions_for_user(
            user=user,
            dataset_id=request.query_params.get("dataset_id"),
            keyword=request.query_params.get("keyword", ""),
        )
        return success_response(data={"sessions": ChatSessionListSerializer(sessions, many=True).data})

    def post(self, request):
        """
        创建一条新的聊天会话。

        请求体 JSON：
          - title: 会话标题（可选，不提供则使用默认值"新会话"）。
          - context_filters: 上下文过滤器（可选，如 {"dataset_id": 1}）。

        返回：
          - 成功（201）：{"session": {...}, "session_id": <id>}
          - 失败：400（校验失败）/ 401（未认证）/ 403（无权限）
        """
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
        session_payload = ChatSessionSerializer(session).data
        return success_response(
            data={
                "session": session_payload,
                "session_id": session.id,
            },
            status_code=201,
        )


class ChatSessionDetailView(APIView):
    """
    会话详情视图。

    类比 SpringBoot：
      - GET /sessions/{session_id}  获取会话详情（含消息列表）
      - DELETE /sessions/{session_id}  删除会话及其所有消息
    """

    authentication_classes = []
    permission_classes = []

    def get(self, request, session_id):
        """
        获取指定会话的详细信息（含关联的消息列表）。

        参数：
          - request: Django Request。
          - session_id: URL 路径参数，会话 ID。

        返回：
          - 成功：{"session": {...}}（含 messages 列表）
          - 失败：401（未认证）/ 403（无权限或无权访问）/ 404（会话不存在）
        """
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

    def delete(self, request, session_id):
        """
        删除指定会话（级联删除关联的所有消息）。

        参数：
          - request: Django Request。
          - session_id: URL 路径参数，会话 ID。

        返回：
          - 成功：{"session_id": <deleted_id>}
          - 失败：401（未认证）/ 403（无权限或无权访问）/ 404（会话不存在）
        """
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.ask_financial_qa"):
            return error_response(code=403, message="无权限。", status_code=403)

        try:
            deleted_id = delete_chat_session_for_user(user=user, session_id=session_id)
        except PermissionError as exc:
            return error_response(code=403, message=str(exc), status_code=403)
        except ChatSession.DoesNotExist:
            return error_response(code=404, message="会话不存在。", status_code=404)

        return success_response(data={"session_id": deleted_id})


class ChatSessionExportView(APIView):
    """
    会话导出视图。

    类比 SpringBoot：
      - @GetMapping("/sessions/{sessionId}/export")
      - 返回包含会话完整数据和所有消息的 JSON 对象，用于导出/备份。

    返回的 JSON 结构：
      {
        "session": { ... 会话字段 ... },
        "messages": [ ... 所有消息 ... ],
        "exported_at": "ISO-8601 时间戳"
      }
    """

    authentication_classes = []
    permission_classes = []

    def get(self, request, session_id):
        """
        导出指定会话的完整数据。

        参数：
          - request: Django Request。
          - session_id: URL 路径参数，会话 ID。

        返回：
          - 成功：JsonResponse 包含 session + messages 的完整导出数据。
          - 失败：401（未认证）/ 403（无权限或无权访问）/ 404（会话不存在）
        """
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

        return JsonResponse(build_chat_session_export(session=session))
