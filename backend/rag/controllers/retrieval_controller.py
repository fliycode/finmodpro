import json
import time

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from common.exceptions import UpstreamServiceError
from rag.services.retrieval_service import build_retrieval_response, retrieve
from rag.services.retrieval_log_service import create_retrieval_log
from rbac.services.authz_service import permission_required


def _parse_json_body(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None


@csrf_exempt
@require_POST
@permission_required("auth.ask_financial_qa")
def retrieval_query_view(request):
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse({"message": "请求体必须是合法 JSON。"}, status=400)

    query = ((payload.get("query") or payload.get("question") or "")).strip()
    filters = payload.get("filters") or {}
    top_k = payload.get("top_k", 5)
    if not query:
        return JsonResponse({"message": "query 或 question 为必填项。"}, status=400)
    if not isinstance(filters, dict):
        return JsonResponse({"message": "filters 必须是对象。"}, status=400)

    started_at = time.monotonic()
    try:
        results = retrieve(query=query, filters=filters, top_k=top_k)
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

    create_retrieval_log(
        query=query,
        top_k=top_k,
        filters=filters,
        results=results,
        source="retrieval_api",
        duration_ms=int((time.monotonic() - started_at) * 1000),
    )
    return JsonResponse(build_retrieval_response(query=query, results=results))
