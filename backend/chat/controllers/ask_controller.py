"""
Chat 问答控制器（Ask Controller）。

类比 SpringBoot：
  - chat_ask_view 相当于 @PostMapping("/ask") 的 @RestController 方法，同步返回 JSON。
  - chat_ask_stream_view 相当于 @PostMapping("/ask/stream") 的流式端点，使用 SSE 协议（text/event-stream）。
  - csrf_exempt 装饰器类似于 Spring Security 中对特定端点禁用 CSRF 保护。
  - permission_required 装饰器相当于 @PreAuthorize("hasAuthority('auth.ask_financial_qa')")。

本模块处理用户提问的请求流程：解析 JSON 请求体 -> 参数校验 -> 权限检查 -> 调用服务层 -> 构建响应。
"""

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
    """
    解析 HTTP 请求体为 JSON 字典。

    参数：
      - request: Django HttpRequest 对象，包含请求体。

    返回：
      - dict: 解析后的字典；如果 JSON 格式无效则返回 None。
    """
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None


def _build_error_payload(*, message, code, error_type, provider=None, details=None):
    """
    构建标准化的错误响应数据结构。

    参数：
      - message: 面向用户的错误描述消息。
      - code: 错误码（如 chat_model_not_configured）。
      - error_type: 错误类型（如 configuration_error / upstream_error）。
      - provider: 可选的模型提供商名称。
      - details: 可选的错误详情字典。

    返回：
      - dict: 包含 message / code / data.error 的统一错误响应结构。
    """
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


def _get_config_user_message(exc):
    """
    获取配置类异常对应的用户友好错误消息。

    根据 ServiceConfigurationError 的子类型返回不同的中文提示。

    参数：
      - exc: ServiceConfigurationError 实例或其子类。

    返回：
      - str: 中文错误消息。
    """
    if isinstance(exc, ModelNotConfiguredError):
        return (
            "当前未配置可用的对话模型，"
            "请先在模型配置中启用 chat 模型。"
        )
    if isinstance(exc, ProviderConfigurationError):
        return (
            "当前对话模型 provider 不可用，"
            "请检查模型配置。"
        )
    return exc.message


def _get_config_user_code(exc):
    """
    获取配置类异常对应的错误码。

    参数：
      - exc: ServiceConfigurationError 实例或其子类。

    返回：
      - str: 错误码字符串（如 chat_model_not_configured）。
    """
    if isinstance(exc, ModelNotConfiguredError):
        return "chat_model_not_configured"
    if isinstance(exc, ProviderConfigurationError):
        return "chat_provider_unavailable"
    return exc.code


def _build_configuration_error_response(exc):
    """
    根据配置异常构建 503 Service Unavailable 响应。

    参数：
      - exc: ServiceConfigurationError 实例。

    返回：
      - JsonResponse: 503 状态码的 JSON 错误响应。
    """
    message = _get_config_user_message(exc)
    code = _get_config_user_code(exc)

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


def _get_upstream_user_message(exc):
    """
    获取上游服务异常对应的用户友好错误消息。

    根据 UpstreamServiceError 的 code 值返回相应的中文提示。

    参数：
      - exc: UpstreamServiceError 实例。

    返回：
      - str: 中文错误消息。
    """
    messages = {
        "llm_provider_unavailable": (
            "对话模型服务当前不可用，"
            "请稍后重试。"
        ),
        "upstream_rate_limited": (
            "上游模型服务触发限流，"
            "请稍后重试。"
        ),
        "llm_provider_auth_failed": (
            "当前对话模型认证失败，"
            "请联系管理员检查 API Key。"
        ),
        "llm_provider_invalid_model": (
            "当前对话模型名称无效，"
            "请联系管理员检查模型配置。"
        ),
    }
    return messages.get(
        exc.code,
        "对话模型上游服务调用失败，请稍后重试。",
    )


def _build_upstream_error_response(exc):
    """
    根据上游异常构建错误响应（含 Retry-After 头）。

    参数：
      - exc: UpstreamServiceError 实例。

    返回：
      - JsonResponse: 对应上游状态码的 JSON 错误响应。
    """
    code_to_error_type = {
        "llm_provider_unavailable": "provider_unavailable",
        "upstream_rate_limited": "rate_limited",
        "llm_provider_auth_failed": "provider_auth_failed",
        "llm_provider_invalid_model": "provider_invalid_model",
    }
    message = _get_upstream_user_message(exc)
    error_type = code_to_error_type.get(exc.code, "upstream_error")

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
    """
    构建 SSE（Server-Sent Events）格式的事件字符串。

    参数：
      - event: 事件名称（如 step / chunk / done / error）。
      - data: 事件数据（dict 或可 JSON 序列化的对象）。

    返回：
      - str: 符合 SSE 规范的事件字符串（event: xxx\ndata: {...}\n\n）。
    """
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _parse_request_payload(request):
    """
    解析并校验问答请求的参数。

    校验流程：
      1. 解析 JSON 请求体
      2. 提取并校验 question（必填）
      3. 校验 filters（必须是对象）
      4. 校验 session_id（如果提供则必须是整数）

    参数：
      - request: Django HttpRequest 对象。

    返回：
      - tuple: (parsed_dict, error_response)
        如果校验通过，返回 (解析结果字典, None)。
        如果校验失败，返回 (None, JsonResponse 错误对象)。
    """
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
    """
    同步问答接口（POST /chat/ask）。

    类比 SpringBoot：
      - @PostMapping("/ask")
      - @PreAuthorize("hasAuthority('auth.ask_financial_qa')")

    请求体 JSON：
      - question: 用户提问内容（必填）
      - query: 与 question 二选一（必填）
      - filters: 上下文过滤条件（可选）
      - top_k: 检索返回条数（默认 5）
      - session_id: 会话 ID（可选，指定则追记到该会话）

    返回：
      - JsonResponse: 包含 question / answer / citations / answer_mode 等字段的 JSON 对象。

    流程：
      1. 解析和校验请求参数
      2. 如果提供了 session_id，验证用户是否有权访问该会话
      3. 调用 ask_question 服务获取 LLM 回答
      4. 处理可能的配置异常和上游服务异常
    """
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
    """
    流式问答接口（POST /chat/ask/stream）。

    类比 SpringBoot：
      - @PostMapping("/ask/stream")
      - 使用 StreamingHttpResponse + text/event-stream (SSE) 协议
      - 相当于 Spring WebFlux 的 Flux<ServerSentEvent> 返回类型

    请求体 JSON：与 chat_ask_view 相同。

    返回：
      - StreamingHttpResponse: SSE 流式响应，事件类型包括：
          - step: RAG 流水线步骤进度（route / rewrite_query / retrieve / score_filter / build_context）
          - meta: 元数据信息（question / answer_mode / citation_count 等）
          - chunk: LLM 输出的文本片段
          - done: 回答完成事件（包含完整 answer / citations）
          - error: 错误事件

    流程：
      1. 解析和校验请求参数
      2. 如果提供了 session_id，验证用户权限
      3. 调用 stream_question 获取事件迭代器
      4. 将事件转换为 SSE 格式并流式输出
      5. 流内捕获和处理配置/上游异常
    """
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
        """
        内部生成器函数：从事件迭代器中读取事件并转换为 SSE 格式。

        同时捕获流过程中的配置异常和上游异常，将其作为 error 事件发送而非中断连接。
        """
        try:
            for event in event_iterator:
                yield _build_sse_event(event["event"], event["data"])
        except ServiceConfigurationError as exc:
            yield _build_sse_event(
                "error",
                _build_error_payload(
                    message=_get_config_user_message(exc),
                    code=_get_config_user_code(exc),
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
                    "message": _get_upstream_user_message(exc),
                    "provider": exc.provider,
                },
            )

    response = StreamingHttpResponse(stream_response(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache, no-transform"
    response["X-Accel-Buffering"] = "no"
    return response
