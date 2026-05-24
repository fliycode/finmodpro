"""
RAG 检索控制器 —— 处理 POST /api/rag/retrieval/query 请求。
类比 SpringBoot: 相当于 @RestController 中的 @PostMapping 方法，
负责接收 HTTP 请求、校验参数、调用 Service 层、构造 HTTP 响应。
"""

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
    """
    解析 HTTP 请求体中的 JSON 数据。

    参数:
        request: Django HttpRequest 对象。
                 类比 SpringBoot: 相当于 @RequestBody 绑定的对象。

    返回:
        dict | None: 解析成功返回字典，失败返回 None。
                    类比 SpringBoot: 相当于 @RequestBody 自动反序列化。
    """
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None


@csrf_exempt
@require_POST
@permission_required("auth.ask_financial_qa")
def retrieval_query_view(request):
    """
    检索查询视图 —— POST /api/rag/retrieval/query

    接收用户查询文本，经过向量检索、BM25 检索、重排序等流程，
    返回按相关性排序的文档片段引用列表。

    类比 SpringBoot: 相当于一个 @PostMapping 方法，同时集成了
    @PreAuthorize 权限校验和 @Valid 参数校验。

    参数:
        request: Django HttpRequest，其 body 中应包含 JSON:
            - query / question (str, 必填): 用户查询文本
            - filters (dict, 可选): 过滤条件（document_id, doc_type, source_date 等）
            - top_k (int, 可选, 默认 5): 返回的最大结果数

    返回:
        JsonResponse: 包含 query、citations/results 列表和 duration_ms 的 JSON 响应。
                      状态码 200 成功，400 参数错误，502 上游服务失败。

    类比 SpringBoot: 对应 @PostMapping 的 ResponseEntity<RetrievalResponse> 返回。
    """
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

    duration_ms = int((time.monotonic() - started_at) * 1000)
    create_retrieval_log(
        query=query,
        top_k=top_k,
        filters=filters,
        results=results,
        source="retrieval_api",
        duration_ms=duration_ms,
    )
    response_payload = build_retrieval_response(query=query, results=results)
    response_payload["duration_ms"] = duration_ms
    return JsonResponse(response_payload)
