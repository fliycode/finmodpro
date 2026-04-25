from pathlib import Path

import requests
from django.conf import settings


def parse_via_unstructured(*, file_path, filename, content_type, strategy):
    """Upload a file to the Unstructured API and return an elements list.

    Calls ``POST /general/v0/general`` with multipart file upload.

    Returns
    -------
    list[dict]
        Unstructured elements, each with ``type``, ``text``, and ``metadata`` keys.

    Raises
    ------
    ValueError
        If the service is unreachable, returns an HTTP error, or returns
        non-JSON data.
    """
    api_url = settings.UNSTRUCTURED_API_URL.rstrip("/")

    # Refuse to run with an empty URL — fail fast instead of hitting a DNS error.
    if not api_url:
        raise ValueError("UNSTRUCTURED_API_URL 未配置。")

    url = f"{api_url}/general/v0/general"

    with Path(file_path).open("rb") as f:
        files = {"files": (filename, f, content_type)}
        params = {"strategy": strategy}
        headers = {}
        if settings.UNSTRUCTURED_API_KEY:
            headers["Authorization"] = f"Bearer {settings.UNSTRUCTURED_API_KEY}"

        try:
            response = requests.post(
                url,
                files=files,
                params=params,
                headers=headers,
                timeout=settings.UNSTRUCTURED_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return response.json()
        except requests.ConnectionError as exc:
            raise ValueError("Unstructured 解析服务不可达。") from exc
        except requests.Timeout as exc:
            raise ValueError("Unstructured 解析请求超时。") from exc
        except requests.HTTPError as exc:
            raise ValueError(
                f"Unstructured 解析失败: HTTP {exc.response.status_code}"
            ) from exc
        except ValueError as exc:
            raise ValueError("Unstructured 返回了无效的 JSON 数据。") from exc
