"""
DRF 自定义异常处理器 — 将所有异常输出转换为统一的 API 响应格式

Django REST Framework 内部有默认的异常处理器，此函数将其包装，
使得所有异常都输出 {code, message, data} 格式的 JSON。

SpringBoot 类比: @ControllerAdvice + @ExceptionHandler 全局异常处理。
"""

from rest_framework import status
from rest_framework.views import exception_handler

from common.api_response import build_response_payload


def custom_exception_handler(exc, context):
    """自定义 DRF 异常处理函数。

    先调用 DRF 默认异常处理器获取标准 response，再将其格式化为统一格式。
    如果默认处理器不识别该异常（返回 None），则不做处理，交给 Django 内置处理。

    参数:
        exc: 抛出的异常实例
        context: DRF 上下文（包含 view、request 等）
    返回:
        Response 对象，其 data 已转换为 {code, message, data} 格式
    """
    # 调用 DRF 默认异常处理器
    response = exception_handler(exc, context)
    if response is None:
        return response

    detail = response.data
    if isinstance(detail, dict):
        # 提取 DRF 错误详情中的 message
        message = detail.get("detail") or detail.get("message") or "请求失败。"
    else:
        message = str(detail)

    # 将原始数据包装为统一响应格式
    response.data = build_response_payload(
        code=response.status_code or status.HTTP_400_BAD_REQUEST,
        message=str(message),
        data=detail,
    )
    return response
