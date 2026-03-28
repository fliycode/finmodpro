from rest_framework import status
from rest_framework.response import Response


def build_response_payload(*, code=0, message="ok", data=None):
    return {
        "code": code,
        "message": message,
        "data": {} if data is None else data,
    }


def success_response(*, data=None, message="ok", status_code=status.HTTP_200_OK):
    return Response(
        build_response_payload(code=0, message=message, data=data),
        status=status_code,
    )


def error_response(*, code, message, data=None, status_code=status.HTTP_400_BAD_REQUEST):
    return Response(
        build_response_payload(code=code, message=message, data=data),
        status=status_code,
    )
