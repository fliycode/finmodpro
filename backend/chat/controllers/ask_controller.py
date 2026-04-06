import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from chat.services.ask_service import ask_question
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


@csrf_exempt
@require_POST
@permission_required("auth.ask_financial_qa")
def chat_ask_view(request):
    payload = _parse_json_body(request)
    if payload is None:
        return JsonResponse(
            {"message": "\u8bf7\u6c42\u4f53\u5fc5\u987b\u662f\u5408\u6cd5 JSON\u3002"},
            status=400,
        )

    question = ((payload.get("question") or payload.get("query") or "")).strip()
    filters = payload.get("filters") or {}
    top_k = payload.get("top_k", 5)

    if not question:
        return JsonResponse(
            {"message": "question \u6216 query \u4e3a\u5fc5\u586b\u9879\u3002"},
            status=400,
        )
    if not isinstance(filters, dict):
        return JsonResponse(
            {"message": "filters \u5fc5\u987b\u662f\u5bf9\u8c61\u3002"},
            status=400,
        )

    try:
        response_payload = ask_question(
            question=question,
            filters=filters,
            top_k=top_k,
        )
    except ServiceConfigurationError as exc:
        return _build_configuration_error_response(exc)
    except UpstreamServiceError as exc:
        return _build_upstream_error_response(exc)
    except ValueError as exc:
        return JsonResponse({"message": str(exc)}, status=400)

    return JsonResponse(response_payload)
