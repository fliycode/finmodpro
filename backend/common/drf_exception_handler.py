from rest_framework import status
from rest_framework.views import exception_handler

from common.api_response import build_response_payload


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return response

    detail = response.data
    if isinstance(detail, dict):
        message = detail.get("detail") or detail.get("message") or "请求失败。"
    else:
        message = str(detail)

    response.data = build_response_payload(
        code=response.status_code or status.HTTP_400_BAD_REQUEST,
        message=str(message),
        data=detail,
    )
    return response
