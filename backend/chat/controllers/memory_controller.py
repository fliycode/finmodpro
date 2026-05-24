"""
Chat 记忆管理控制器（Memory Controller）。

类比 SpringBoot：
  - ChatMemoryListView 相当于 @RestController 类，GET 映射到 @GetMapping("/memories")。
  - ChatMemoryEvidenceView 相当于 @GetMapping("/memories/{memoryId}/evidence")。
  - ChatMemoryPinView 相当于 @PostMapping("/memories/{memoryId}/pin")。
  - ChatMemoryDeleteView 相当于 @DeleteMapping("/memories/{memoryId}")。
  - APIView 类似于 Spring 的 RestController 基类，提供请求分发和序列化支持。

本模块处理用户长期记忆（Memory）的 CRUD 操作，包括列表查询、证据查看、置顶切换和软删除。
"""

from rest_framework.views import APIView

from chat.models import MemoryEvidence, MemoryItem
from chat.serializers import MemoryEvidenceSerializer, MemoryItemSerializer, MemoryPinSerializer
from chat.services.memory_service import (
    delete_memory_item,
    get_memory_item_for_user,
    list_memory_evidence_for_memory,
    list_memory_items_for_user,
    record_memory_view,
    set_memory_pin_state,
)
from common.api_response import error_response, success_response
from rbac.services.authz_service import get_authenticated_user, user_has_permission


def _build_validation_error_response(errors):
    """
    将 DRF 序列化器的校验错误转换为统一的错误响应。

    参数：
      - errors: DRF Serializer.errors 字典，如 {"field": ["错误信息"]}。

    返回：
      - HttpResponse: 包含 code=400 和第一条错误消息的响应。
    """
    message = "请求失败。"
    if isinstance(errors, dict):
        for value in errors.values():
            if isinstance(value, (list, tuple)) and value:
                message = str(value[0])
                break
            if value:
                message = str(value)
                break
    return error_response(code=400, message=message, data=errors, status_code=400)


class ChatMemoryListView(APIView):
    """
    记忆列表视图。

    类比 SpringBoot：
      - @GetMapping("/memories")
      - 查询当前用户的活跃记忆列表，支持按 scope_type / scope_key / q 过滤。

    请求参数 (query params):
      - scope_type: 作用域类型（可选过滤）
      - scope_key: 作用域键值（可选过滤）
      - q: 关键词搜索（可选）
    """

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """
        获取用户的记忆列表。

        参数：
          - request: Django Request（已认证用户通过 get_authenticated_user 获取）。

        返回：
          - 成功：{"memories": [MemoryItemSerializer(...), ...]}
          - 失败：401（未认证）/ 403（无权限）
        """
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.ask_financial_qa"):
            return error_response(code=403, message="无权限。", status_code=403)

        memories = list_memory_items_for_user(
            user=user,
            scope_type=request.query_params.get("scope_type"),
            scope_key=request.query_params.get("scope_key"),
            query=request.query_params.get("q"),
        )
        return success_response(data={"memories": MemoryItemSerializer(memories, many=True).data})


class ChatMemoryEvidenceView(APIView):
    """
    记忆证据查看视图。

    类比 SpringBoot：
      - @GetMapping("/memories/{memoryId}/evidence")
      - 查看指定记忆的关联证据（来源会话/消息摘要）。
    """

    authentication_classes = []
    permission_classes = []

    def get(self, request, memory_id):
        """
        获取指定记忆的证据列表和记忆详情。

        参数：
          - request: Django Request。
          - memory_id: URL 路径参数，记忆条目 ID。

        返回：
          - 成功：{"memory": {...}, "evidence": [...]}
          - 失败：401（未认证）/ 403（无权限）/ 404（记忆不存在）
          - 同时记录一次"查看"操作（record_memory_view）。
        """
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.ask_financial_qa"):
            return error_response(code=403, message="无权限。", status_code=403)

        try:
            memory = get_memory_item_for_user(user=user, memory_id=memory_id)
        except MemoryItem.DoesNotExist:
            return error_response(code=404, message="记忆不存在。", status_code=404)

        evidence_items = list_memory_evidence_for_memory(memory_item=memory)
        record_memory_view(memory_item=memory, actor_user=user)

        evidence_payload = MemoryEvidenceSerializer(evidence_items, many=True).data
        if not evidence_payload:
            evidence_payload = [
                {
                    "id": None,
                    "session_id": None,
                    "message_id": None,
                    "evidence_excerpt": memory.content,
                    "extractor_version": "",
                    "confirmation_status": MemoryEvidence.CONFIRMATION_PENDING,
                    "created_at": memory.updated_at.isoformat() if memory.updated_at else None,
                }
            ]

        return success_response(
            data={
                "memory": MemoryItemSerializer(memory).data,
                "evidence": evidence_payload,
            }
        )


class ChatMemoryPinView(APIView):
    """
    记忆置顶切换视图。

    类比 SpringBoot：
      - @PostMapping("/memories/{memoryId}/pin")
      - 切换记忆的置顶状态（pinned = true/false）。
    """

    authentication_classes = []
    permission_classes = []

    def post(self, request, memory_id):
        """
        切换指定记忆的置顶状态。

        参数：
          - request: Django Request（请求体中包含 {"pinned": true/false}）。
          - memory_id: URL 路径参数，记忆条目 ID。

        返回：
          - 成功：{"memory": {...}}（更新后的记忆对象）
          - 失败：400（校验失败）/ 401（未认证）/ 403（无权限）/ 404（记忆不存在）
        """
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.ask_financial_qa"):
            return error_response(code=403, message="无权限。", status_code=403)

        serializer = MemoryPinSerializer(data=request.data if isinstance(request.data, dict) else {})
        if not serializer.is_valid():
            return _build_validation_error_response(serializer.errors)

        try:
            memory = get_memory_item_for_user(user=user, memory_id=memory_id)
        except MemoryItem.DoesNotExist:
            return error_response(code=404, message="记忆不存在。", status_code=404)

        memory = set_memory_pin_state(
            memory_item=memory,
            actor_user=user,
            pinned=serializer.validated_data["pinned"],
        )
        return success_response(data={"memory": MemoryItemSerializer(memory).data})


class ChatMemoryDeleteView(APIView):
    """
    记忆删除视图。

    类比 SpringBoot：
      - @DeleteMapping("/memories/{memoryId}")
      - 软删除指定记忆（将 status 设为 deleted）。

    注意：这是软删除，不会真正从数据库中删除记录，只改变 status 字段为 "deleted"。
    """

    authentication_classes = []
    permission_classes = []

    def delete(self, request, memory_id):
        """
        软删除指定记忆条目。

        参数：
          - request: Django Request。
          - memory_id: URL 路径参数，记忆条目 ID。

        返回：
          - 成功：{"memory": {...}}（更新后的记忆对象，status 已变为 deleted）
          - 失败：401（未认证）/ 403（无权限）/ 404（记忆不存在）
        """
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.ask_financial_qa"):
            return error_response(code=403, message="无权限。", status_code=403)

        try:
            memory = get_memory_item_for_user(user=user, memory_id=memory_id)
        except MemoryItem.DoesNotExist:
            return error_response(code=404, message="记忆不存在。", status_code=404)

        memory = delete_memory_item(memory_item=memory, actor_user=user)
        return success_response(data={"memory": MemoryItemSerializer(memory).data})
