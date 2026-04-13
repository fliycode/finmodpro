import json

from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from chat.models import ChatSession
from chat.services.ask_service import ask_question, stream_question
from chat.services.session_service import get_chat_session_for_user
from common.exceptions import (
    ModelNotConfiguredError,
    ProviderConfigurationError,
    ServiceConfigurationError,
    UpstreamServiceError,
)
from rbac.services.authz_service import permission_required


def _parse_json_body(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None


def _build_error_payload(*, message, code, error_type, provider=None, details=None):
    error_payload = {
        "type": error_type,
        "code": code,
        "message": message,
    }
    if provider:
        error_payload["provider"] = provider
    if details:
        error_payload["details"] = details

    payload = {
        "message": message,
        "code": code,
        "data": {"error": error_payload},
    }
    if provider:
        payload["provider"] = provider
    return payload


def _build_configuration_error_response(exc):
    if isinstance(exc, ModelNotConfiguredError):
        message = (
            "\u5f53\u524d\u672a\u914d\u7f6e\u53ef\u7528\u7684\u5bf9\u8bdd\u6a21\u578b\uff0c"
            "\u8bf7\u5148\u5728\u6a21\u578b\u914d\u7f6e\u4e2d\u542f\u7528 chat \u6a21\u578b\u3002"
        )
        code = "chat_model_not_configured"
    elif isinstance(exc, ProviderConfigurationError):
        message = (
            "\u5f53\u524d\u5bf9\u8bdd\u6a21\u578b provider \u4e0d\u53ef\u7528\uff0c"
            "\u8bf7\u68c0\u67e5\u6a21\u578b\u914d\u7f6e\u3002"
        )
        code = "chat_provider_unavailable"
    else:
        message = exc.message
        code = exc.code

    return JsonResponse(
        _build_error_payload(
            message=message,
            code=code,
            error_type="configuration_error",
            provider=exc.provider,
            details=exc.details,
        ),
        status=503,
    )


def _build_upstream_error_response(exc):
    if exc.code == "llm_provider_unavailable":
        message = (
            "\u5bf9\u8bdd\u6a21\u578b\u670d\u52a1\u5f53\u524d\u4e0d\u53ef\u7528\uff0c"
            "\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002"
        )
        error_type = "provider_unavailable"
    elif exc.code == "upstream_rate_limited":
        message = (
            "\u4e0a\u6e38\u6a21\u578b\u670d\u52a1\u89e6\u53d1\u9650\u6d41\uff0c"
            "\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002"
        )
        error_type = "rate_limited"
    elif exc.code == "llm_provider_auth_failed":
        message = "\u5f53\u524d\u5bf9\u8bdd\u6a21\u578b\u8ba4\u8bc1\u5931\u8d25\uff0c\u8bf7\u8054\u7cfb\u7ba1\u7406\u5458\u68c0\u67e5 API Key\u3002"
        error_type = "provider_auth_failed"
    elif exc.code == "llm_provider_invalid_model":
        message = "\u5f53\u524d\u5bf9\u8bdd\u6a21\u578b\u540d\u79f0\u65e0\u6548\uff0c\u8bf7\u8054\u7cfb\u7ba1\u7406\u5458\u68c0\u67e5\u6a21\u578b\u914d\u7f6e\u3002"
        error_type = "provider_invalid_model"
    else:
        message = (
            "\u5bf9\u8bdd\u6a21\u578b\u4e0a\u6e38\u670d\u52a1\u8c03\u7528\u5931\u8d25\uff0c"
            "\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002"
        )
        error_type = "upstream_error"

    details = {"upstream_message": exc.message}
    if exc.retry_after is not None:
        details["retry_after"] = exc.retry_after

    response = JsonResponse(
        _build_error_payload(
            message=message,
            code=exc.code,
            error_type=error_type,
            provider=exc.provider,
            details=details,
        ),
        status=exc.status_code,
    )
    if exc.retry_after is not None:
        response["Retry-After"] = str(exc.retry_after)
    return response


def _build_sse_event(event, data):
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _parse_request_payload(request):
    payload = _parse_json_body(request)
    if payload is None:
        return None, JsonResponse(
            {"message": "请求体必须是合法 JSON。"},
            status=400,
        )

    question = ((payload.get("question") or payload.get("query") or "")).strip()
    filters = payload.get("filters") or {}
    top_k = payload.get("top_k", 5)
    session_id = payload.get("session_id")

    if not question:
        return None, JsonResponse(
            {"message": "question 或 query 为必填项。"},
            status=400,
        )
    if not isinstance(filters, dict):
        return None, JsonResponse(
            {"message": "filters 必须是对象。"},
            status=400,
        )
    if session_id in ("", None):
        normalized_session_id = None
    else:
        try:
            normalized_session_id = int(session_id)
        except (TypeError, ValueError):
            return None, JsonResponse(
                {"message": "session_id 必须是整数。"},
                status=400,
            )

    return {
        "question": question,
        "filters": filters,
        "top_k": top_k,
        "session_id": normalized_session_id,
    }, None


@csrf_exempt
@require_POST
@permission_required("auth.ask_financial_qa")
def chat_ask_view(request):
    parsed_request, error_response = _parse_request_payload(request)
    if error_response is not None:
        return error_response

    session = None
    if parsed_request["session_id"] is not None:
        try:
            session = get_chat_session_for_user(user=request.user, session_id=parsed_request["session_id"])
        except PermissionError as exc:
            return JsonResponse({"message": str(exc)}, status=403)
        except ChatSession.DoesNotExist:
            return JsonResponse({"message": "会话不存在。"}, status=404)

    try:
        response_payload = ask_question(
            question=parsed_request["question"],
            filters=parsed_request["filters"],
            top_k=parsed_request["top_k"],
            session=session,
        )
    except ServiceConfigurationError as exc:
        return _build_configuration_error_response(exc)
    except UpstreamServiceError as exc:
        return _build_upstream_error_response(exc)
    except ValueError as exc:
        return JsonResponse({"message": str(exc)}, status=400)

    return JsonResponse(response_payload)


@csrf_exempt
@require_POST
@permission_required("auth.ask_financial_qa")
def chat_ask_stream_view(request):
    parsed_request, error_response = _parse_request_payload(request)
    if error_response is not None:
        return error_response

    session = None
    if parsed_request["session_id"] is not None:
        try:
            session = get_chat_session_for_user(user=request.user, session_id=parsed_request["session_id"])
        except PermissionError as exc:
            return JsonResponse({"message": str(exc)}, status=403)
        except ChatSession.DoesNotExist:
            return JsonResponse({"message": "会话不存在。"}, status=404)

    try:
        event_iterator = stream_question(
            question=parsed_request["question"],
            filters=parsed_request["filters"],
            top_k=parsed_request["top_k"],
            session=session,
        )
    except ServiceConfigurationError as exc:
        return _build_configuration_error_response(exc)
    except UpstreamServiceError as exc:
        return _build_upstream_error_response(exc)
    except ValueError as exc:
        return JsonResponse({"message": str(exc)}, status=400)

    def stream_response():
        try:
            for event in event_iterator:
                yield _build_sse_event(event["event"], event["data"])
        except ServiceConfigurationError as exc:
            yield _build_sse_event(
                "error",
                _build_error_payload(
                    message=exc.message,
                    code=exc.code,
                    error_type="configuration_error",
                    provider=exc.provider,
                    details=exc.details,
                )["data"]["error"],
            )
        except UpstreamServiceError as exc:
            yield _build_sse_event(
                "error",
                {
                    "type": "upstream_error",
                    "code": exc.code,
                    "message": exc.message,
                    "provider": exc.provider,
                },
            )

    response = StreamingHttpResponse(stream_response(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
