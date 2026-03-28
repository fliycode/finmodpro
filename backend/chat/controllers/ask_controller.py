import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from chat.services.ask_service import ask_question
from common.exceptions import UpstreamServiceError
from rbac.services.authz_service import permission_required


def _parse_json_body(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None


@csrf_exempt
@require_POST
@permission_required("auth.ask_financial_qa")
def chat_ask_view(request):
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({"message": "请求体必须是合法 JSON。"}, status=400)

    question = ((payload.get("question") or payload.get("query") or "")).strip()
    filters = payload.get("filters") or {}
    top_k = payload.get("top_k", 5)

    if not question:
        return JsonResponse({"message": "question 或 query 为必填项。"}, status=400)
    if not isinstance(filters, dict):
        return JsonResponse({"message": "filters 必须是对象。"}, status=400)

    try:
        response_payload = ask_question(
            question=question,
            filters=filters,
            top_k=top_k,
        )
    except ValueError as exc:
        return JsonResponse({"message": str(exc)}, status=400)
    except UpstreamServiceError as exc:
        payload = {"message": exc.message, "code": exc.code}
        if exc.provider:
            payload["provider"] = exc.provider
        response = JsonResponse(payload, status=exc.status_code)
        if exc.retry_after is not None:
            response["Retry-After"] = str(exc.retry_after)
        return response

    return JsonResponse(response_payload)
