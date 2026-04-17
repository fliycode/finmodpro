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
    authentication_classes = []
    permission_classes = []

    def get(self, request):
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
    authentication_classes = []
    permission_classes = []

    def get(self, request, memory_id):
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
    authentication_classes = []
    permission_classes = []

    def post(self, request, memory_id):
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
    authentication_classes = []
    permission_classes = []

    def delete(self, request, memory_id):
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
