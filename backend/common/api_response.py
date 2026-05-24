"""
统一 API 响应格式

所有业务 Controller 返回的 JSON 都使用此格式: {code, message, data}
code=0 表示成功，非0表示错误。

SpringBoot 类比: 自定义 Result<T> 或 ApiResponse 类，包含 code/message/data 三个字段。
"""

from rest_framework import status
from rest_framework.response import Response


def build_response_payload(*, code=0, message="ok", data=None):
    """构建 API 响应的 JSON 数据体。

    返回 {code, message, data} 字典，所有 Controller 应使用此函数包装响应。

    参数:
        code:   业务状态码，0=成功，非0=错误
        message: 可读的提示消息
        data:   响应数据，默认为空字典
    """
    return {
        "code": code,
        "message": message,
        "data": {} if data is None else data,
    }


def success_response(*, data=None, message="ok", status_code=status.HTTP_200_OK):
    """构建成功响应 (code=0)。

    参数:
        data: 响应数据体
        message: 成功消息
        status_code: HTTP 状态码，默认 200
    """
    return Response(
        build_response_payload(code=0, message=message, data=data),
        status=status_code,
    )


def error_response(*, code, message, data=None, status_code=status.HTTP_400_BAD_REQUEST):
    """构建错误响应 (code≠0)。

    参数:
        code: 业务错误码（必填）
        message: 错误描述
        data: 附加错误详情
        status_code: HTTP 状态码
    """
    return Response(
        build_response_payload(code=code, message=message, data=data),
        status=status_code,
    )
