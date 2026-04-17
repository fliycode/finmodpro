from django.db.models import Q
from rest_framework.views import APIView

from chat.models import MemoryActionLog, MemoryEvidence, MemoryItem
from common.api_response import error_response, success_response
from rbac.services.authz_service import get_authenticated_user, user_has_permission


def _serialize_memory(memory):
    return {
        "id": memory.id,
        "scope_type": memory.scope_type,
        "scope_key": memory.scope_key,
        "memory_type": memory.memory_type,
        "title": memory.title,
        "content": memory.content,
        "confidence_score": float(memory.confidence_score),
        "source_kind": memory.source_kind,
        "status": memory.status,
        "pinned": memory.pinned,
        "fingerprint": memory.fingerprint,
        "last_verified_at": memory.last_verified_at.isoformat() if memory.last_verified_at else None,
        "created_at": memory.created_at.isoformat() if memory.created_at else None,
        "updated_at": memory.updated_at.isoformat() if memory.updated_at else None,
    }


def _serialize_evidence(evidence):
    return {
        "id": evidence.id,
        "session_id": evidence.session_id,
        "message_id": evidence.message_id,
        "evidence_excerpt": evidence.evidence_excerpt,
        "extractor_version": evidence.extractor_version,
        "confirmation_status": evidence.confirmation_status,
        "created_at": evidence.created_at.isoformat() if evidence.created_at else None,
    }


def _get_memory_for_user(*, user, memory_id):
    return MemoryItem.objects.get(id=memory_id, user=user)


class ChatMemoryListView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.ask_financial_qa"):
            return error_response(code=403, message="无权限。", status_code=403)

        queryset = MemoryItem.objects.filter(user=user, status=MemoryItem.STATUS_ACTIVE)

        scope_type = (request.query_params.get("scope_type") or "").strip()
        if scope_type:
          queryset = queryset.filter(scope_type=scope_type)

        query = " ".join(str(request.query_params.get("q") or "").split()).strip()
        if query:
            for token in query.split():
                queryset = queryset.filter(
                    Q(title__icontains=token) | Q(content__icontains=token)
                )

        memories = [_serialize_memory(item) for item in queryset.order_by("-pinned", "-updated_at", "-id")]
        return success_response(data={"memories": memories})


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
            memory = _get_memory_for_user(user=user, memory_id=memory_id)
        except MemoryItem.DoesNotExist:
            return error_response(code=404, message="记忆不存在。", status_code=404)

        evidence_items = list(memory.evidence_items.order_by("-created_at", "-id"))
        evidence_payload = [_serialize_evidence(item) for item in evidence_items]
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
                "memory": _serialize_memory(memory),
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

        try:
            memory = _get_memory_for_user(user=user, memory_id=memory_id)
        except MemoryItem.DoesNotExist:
            return error_response(code=404, message="记忆不存在。", status_code=404)

        payload = request.data if isinstance(request.data, dict) else {}
        pinned = bool(payload.get("pinned"))
        memory.pinned = pinned
        memory.save(update_fields=["pinned", "updated_at"])
        MemoryActionLog.objects.create(
            memory_item=memory,
            actor_user=user,
            action=MemoryActionLog.ACTION_PIN if pinned else MemoryActionLog.ACTION_UNPIN,
            details_json={"pinned": pinned},
        )
        return success_response(data={"memory": _serialize_memory(memory)})


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
            memory = _get_memory_for_user(user=user, memory_id=memory_id)
        except MemoryItem.DoesNotExist:
            return error_response(code=404, message="记忆不存在。", status_code=404)

        memory.status = MemoryItem.STATUS_DELETED
        memory.save(update_fields=["status", "updated_at"])
        MemoryActionLog.objects.create(
            memory_item=memory,
            actor_user=user,
            action=MemoryActionLog.ACTION_DELETE,
            details_json={},
        )
        return success_response(data={"memory": _serialize_memory(memory)})
