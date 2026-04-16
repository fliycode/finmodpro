import json
from pathlib import Path
from urllib import request
from urllib.error import HTTPError, URLError

from django.conf import settings


def parse_via_unstructured(*, file_path, filename, content_type, strategy):
    url = f"{settings.UNSTRUCTURED_API_URL.rstrip('/')}/parse"
    payload = json.dumps(
        {
            "filename": filename,
            "content_type": content_type,
            "strategy": strategy,
            "file_path": str(Path(file_path)),
        }
    ).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if settings.UNSTRUCTURED_API_KEY:
        headers["Authorization"] = f"Bearer {settings.UNSTRUCTURED_API_KEY}"

    http_request = request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with request.urlopen(http_request, timeout=settings.UNSTRUCTURED_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise ValueError(f"Unstructured 解析失败: HTTP {exc.code}") from exc
    except URLError as exc:
        raise ValueError("Unstructured 解析服务不可达。") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("Unstructured 返回了无效的 JSON。") from exc
