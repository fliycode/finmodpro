import json
import re

import requests
from django.conf import settings

from common.exceptions import ServiceConfigurationError, UpstreamServiceError


_ALLOWED_PATHS = (
    ("GET", re.compile(r"^auth-status$")),
    ("GET", re.compile(r"^health$")),
    ("POST", re.compile(r"^query$")),
    ("POST", re.compile(r"^documents/scan$")),
    ("POST", re.compile(r"^documents/upload$")),
    ("GET", re.compile(r"^documents/status_counts$")),
    ("POST", re.compile(r"^documents/paginated$")),
    ("GET", re.compile(r"^documents/track_status/[^/]+$")),
    ("POST", re.compile(r"^documents/reprocess_failed$")),
    ("POST", re.compile(r"^documents/cancel_pipeline$")),
    ("POST", re.compile(r"^documents/clear_cache$")),
    ("DELETE", re.compile(r"^documents/delete_document$")),
    ("DELETE", re.compile(r"^documents/delete_entity$")),
    ("DELETE", re.compile(r"^documents/delete_relation$")),
    ("GET", re.compile(r"^graphs$")),
    ("GET", re.compile(r"^graph/label/list$")),
    ("GET", re.compile(r"^graph/label/popular$")),
    ("GET", re.compile(r"^graph/label/search$")),
    ("GET", re.compile(r"^graph/entity/exists$")),
    ("POST", re.compile(r"^graph/entity/create$")),
    ("POST", re.compile(r"^graph/entity/edit$")),
    ("POST", re.compile(r"^graph/relation/create$")),
    ("POST", re.compile(r"^graph/relation/edit$")),
    ("POST", re.compile(r"^graph/entities/merge$")),
)


def is_allowed_lightrag_path(*, method, upstream_path):
    normalized_method = str(method or "").upper()
    normalized_path = str(upstream_path or "").strip().strip("/")
    if not normalized_path:
        return False
    return any(
        candidate_method == normalized_method and pattern.fullmatch(normalized_path)
        for candidate_method, pattern in _ALLOWED_PATHS
    )


def _get_base_url():
    base_url = str(getattr(settings, "LIGHTRAG_INTERNAL_URL", "") or "").strip().rstrip("/")
    if not base_url:
        raise ServiceConfigurationError(
            "LightRAG 内部服务地址未配置。",
            code="lightrag_not_configured",
            provider="lightrag",
        )
    return base_url


def _build_error_message(payload, fallback):
    if isinstance(payload, dict):
        for key in ("message", "detail", "error", "status"):
            value = payload.get(key)
            if value:
                return str(value)
    if isinstance(payload, str) and payload.strip():
        return payload
    return fallback


def _parse_response_payload(response):
    content_type = response.headers.get("Content-Type", "")
    if "application/json" in content_type:
        return response.json()
    text = response.text.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def _build_form_data(request_data, request_files):
    form_data = {}
    for key in request_data.keys():
        if key in request_files:
            continue
        values = request_data.getlist(key) if hasattr(request_data, "getlist") else [request_data.get(key)]
        form_data[key] = values if len(values) > 1 else values[0]

    files = []
    for key in request_files.keys():
        uploads = request_files.getlist(key) if hasattr(request_files, "getlist") else [request_files[key]]
        for upload in uploads:
            files.append(
                (
                    key,
                    (
                        upload.name,
                        upload.file,
                        upload.content_type or "application/octet-stream",
                    ),
                )
            )
    return form_data, files


def proxy_lightrag_request(*, method, upstream_path, query_params=None, json_payload=None, request_data=None, request_files=None):
    normalized_method = str(method or "").upper()
    normalized_path = str(upstream_path or "").strip().strip("/")
    if not is_allowed_lightrag_path(method=normalized_method, upstream_path=normalized_path):
        raise ValueError("不支持的 LightRAG 桥接路径。")

    request_kwargs = {
        "method": normalized_method,
        "url": f"{_get_base_url()}/{normalized_path}",
        "params": query_params or {},
        "timeout": getattr(settings, "LIGHTRAG_TIMEOUT_SECONDS", 30),
    }

    if request_files:
        form_data, files = _build_form_data(request_data or {}, request_files)
        request_kwargs["data"] = form_data
        request_kwargs["files"] = files
    elif json_payload is not None:
        request_kwargs["json"] = json_payload
    elif request_data:
        request_kwargs["data"] = request_data

    try:
        response = requests.request(**request_kwargs)
    except requests.ConnectionError as exc:
        raise UpstreamServiceError(
            "LightRAG 服务不可达。",
            status_code=502,
            code="lightrag_unreachable",
            provider="lightrag",
        ) from exc
    except requests.Timeout as exc:
        raise UpstreamServiceError(
            "LightRAG 请求超时。",
            status_code=504,
            code="lightrag_timeout",
            provider="lightrag",
        ) from exc

    payload = _parse_response_payload(response)
    if response.ok:
        return payload

    raise UpstreamServiceError(
        _build_error_message(payload, "LightRAG 请求失败。"),
        status_code=response.status_code,
        code="lightrag_upstream_error",
        provider="lightrag",
    )


def build_lightrag_overview():
    health = proxy_lightrag_request(method="GET", upstream_path="health")
    auth_status = proxy_lightrag_request(method="GET", upstream_path="auth-status")
    status_counts = proxy_lightrag_request(method="GET", upstream_path="documents/status_counts")
    labels = proxy_lightrag_request(
        method="GET",
        upstream_path="graph/label/popular",
        query_params={"limit": 8},
    )

    return {
        "health": health,
        "auth_status": auth_status,
        "status_counts": status_counts,
        "popular_labels": labels if isinstance(labels, list) else [],
    }
