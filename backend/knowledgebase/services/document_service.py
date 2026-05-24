"""
文档管理服务 —— 对应 SpringBoot 中的核心 @Service 组件，管理文档的完整生命周期。

本模块是知识库应用的业务逻辑中枢，类似于 SpringBoot 中聚合多个 Repository 和外部
服务的 @Service 核心类。提供以下核心功能：

1. 文档 CRUD：创建、查询、序列化、删除
2. 文档摄取管道：解析 -> 清洗 -> 分块 -> 向量化
3. 批量操作：批量摄取、批量删除
4. 访问控制：基于用户角色和可见性的权限过滤
5. 摄取任务管理：排队、执行、重试

SpringBoot 类比对照表：
- Django Document model                       →  SpringBoot @Entity Document
- Django objects.create() / save()            →  SpringBoot repository.save()
- Django objects.filter() / get()             →  SpringBoot repository.findAll(spec) / findById()
- Django select_related()                     →  SpringBoot @EntityGraph / JOIN FETCH
- Django transaction.atomic()                 →  SpringBoot @Transactional
- Django bulk_create / bulk_update            →  SpringBoot repository.saveAll()
- Django Q objects                             →  SpringBoot Specification / Criteria API
- Django signal / post-save                   →  SpringBoot @TransactionalEventListener
- Django select_for_update()                  →  SpringBoot @Lock(PESSIMISTIC_WRITE)
- Django run_background_job                   →  SpringBoot @Async / TaskExecutor
- Django Celery task .delay()                 →  SpringBoot @Async + RabbitMQ/Kafka
- Django settings                             →  SpringBoot @Value / application.yml
"""

import hashlib
import logging
import time
from datetime import date
from datetime import timedelta
from math import ceil
from pathlib import Path

from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import DatabaseError, OperationalError, ProgrammingError, transaction
from django.db.models import Q, Count, Sum
from django.utils import timezone

from common.background_jobs import run_background_job
from common.logging import build_log_extra
from common.observability import trace_span
from common.exceptions import (
    DocumentQualityGateError,
    DuplicateDocumentError,
    ServiceConfigurationError,
    UpstreamServiceError,
)
from knowledgebase.models import Dataset, Document, DocumentChunk, DocumentSectionChunk, DocumentVersion, IngestionTask
from knowledgebase.services.cleaning_quality_service import evaluate_quality_gate
from knowledgebase.services.chunk_service import (
    build_document_chunks,
    build_document_chunks_from_elements,
    build_sentence_window_chunks,
    choose_chunking_strategy,
    estimate_flat_chunk_count,
)
from knowledgebase.services.hierarchical_chunk_service import build_hierarchical_document_chunks
from knowledgebase.services.parser_service import parse_document_file
from knowledgebase.services.search_text_service import build_contextual_search_text
from knowledgebase.services.vector_service import VectorService, index_document_chunks

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────────
# 内部辅助函数（类似 SpringBoot private 方法或 @Component 工具类）
# ────────────────────────────────────────────────────────────────────────

def _detect_doc_type(filename):
    """
    根据文件名后缀检测文档类型。

    参数：
        filename (str): 文档文件名。

    返回：
        str: 文档类型（如 "pdf"、"docx"、"txt"、"unknown"）。
    """
    extension = Path(filename).suffix.lower().lstrip(".")
    return extension or "unknown"


def _parse_source_date(raw_value):
    """
    解析来源日期字符串为 date 对象。

    参数：
        raw_value (str | None): YYYY-MM-DD 格式的日期字符串。

    返回：
        date | None: 解析后的日期对象，输入为空时返回 None。

    异常：
        ValueError: 日期格式不符合 YYYY-MM-DD。
    """
    if not raw_value:
        return None
    try:
        return date.fromisoformat(raw_value)
    except ValueError as exc:
        raise ValueError("source_date 必须是 YYYY-MM-DD 格式。") from exc


def _parse_owner_id(raw_value):
    """
    解析 owner_id 为整数。

    参数：
        raw_value (str | int | None): 原始 owner_id 值。

    返回：
        int | None: 解析后的整数值，输入为空时返回 None。

    异常：
        ValueError: 输入不是整数。
    """
    if raw_value in (None, ""):
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("owner_id 必须是整数。") from exc


def _parse_dataset_id(raw_value):
    """
    解析 dataset_id 为整数，特殊值 "all" 或空返回 None 表示不过滤。

    参数：
        raw_value (str | int | None): 原始 dataset_id 值。

    返回：
        int | None: 解析后的整数或 None。

    异常：
        ValueError: 输入不是整数。
    """
    if raw_value in (None, "", "all"):
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("dataset_id 必须是整数。") from exc


def _parse_visibility(raw_value):
    """
    解析并校验文档可见性字段。

    参数：
        raw_value (str | None): 原始可见性值。

    返回：
        str: 标准化后的可见性值（private / internal / public），默认 internal。

    异常：
        ValueError: 输入值不在允许的范围内。
    """
    if not raw_value:
        return Document.VISIBILITY_INTERNAL
    normalized = str(raw_value).strip().lower()
    valid_values = {
        Document.VISIBILITY_PRIVATE,
        Document.VISIBILITY_INTERNAL,
        Document.VISIBILITY_PUBLIC,
    }
    if normalized not in valid_values:
        raise ValueError("visibility 仅支持 private/internal/public。")
    return normalized


def _serialize_user(user):
    """
    将用户实体序列化为简要字典（类似 SpringBoot User Entity → UserDTO 转换）。

    参数：
        user (User | None): 用户模型实例。

    返回：
        dict | None: {"id": int, "username": str, "email": str} 或 None。
    """
    if user is None:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
    }


def _serialize_dataset_summary(dataset):
    """
    将数据集实体序列化为简要摘要字典。

    参数：
        dataset (Dataset | None): 数据集模型实例。

    返回：
        dict | None: {"id": int, "name": str} 或 None。
    """
    if dataset is None:
        return None
    return {
        "id": dataset.id,
        "name": dataset.name,
    }


def _get_version_record(document):
    """
    获取文档的版本记录（类似 SpringBoot @OneToOne 关联查询）。

    参数：
        document (Document | None): 文档模型实例。

    返回：
        DocumentVersion | None: 版本记录实例，若无则返回 None。
    """
    if document is None:
        return None

    try:
        return document.version_record
    except DocumentVersion.DoesNotExist:
        return None


def _serialize_provenance(version_record):
    """
    从版本记录中提取来源溯源信息（类似 SpringBoot DTO 组装）。

    参数：
        version_record (DocumentVersion | None): 版本记录实例。

    返回：
        dict: {"source_type": str, "source_label": str, "source_metadata": dict, "processing_notes": str}
    """
    if version_record is None:
        return {
            "source_type": "upload",
            "source_label": "",
            "source_metadata": {},
            "processing_notes": "",
        }

    return {
        "source_type": version_record.source_type or "upload",
        "source_label": version_record.source_label or "",
        "source_metadata": version_record.source_metadata or {},
        "processing_notes": version_record.processing_notes or "",
    }


def _get_root_document_id(document, version_record):
    """
    获取文档的根文档ID（版本链表头部）。

    参数：
        document (Document): 文档模型实例。
        version_record (DocumentVersion | None): 版本记录实例。

    返回：
        int: 根文档ID（无版本记录时返回文档自身ID）。
    """
    if version_record is None:
        return document.id
    return version_record.root_document_id


def _get_current_version_number(document, version_record):
    """
    获取文档的当前版本号。

    参数：
        document (Document): 文档模型实例。
        version_record (DocumentVersion | None): 版本记录实例。

    返回：
        int: 当前版本号（无版本记录时为 1）。
    """
    if version_record is None:
        return 1
    return version_record.version_number


def _get_version_count(document, version_record):
    """
    获取文档的版本总数。

    参数：
        document (Document): 文档模型实例。
        version_record (DocumentVersion | None): 版本记录实例。

    返回：
        int: 版本链中的总版本数。
    """
    if version_record is None:
        return 1

    root_document = getattr(version_record, "root_document", None)
    annotated_count = getattr(root_document, "version_count", None)
    if annotated_count is not None:
        return annotated_count
    return DocumentVersion.objects.filter(root_document_id=version_record.root_document_id).count()


def _is_document_admin(user):
    """
    判断用户是否为文档管理员（类似 SpringBoot @PreAuthorize("hasRole('ADMIN')")）。

    管理员权限来源：superuser、staff 或 属于 admin/super_admin 组。

    参数：
        user (User | None): 用户模型实例。

    返回：
        bool: 是否为文档管理员。
    """
    if user is None:
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    return user.groups.filter(name__in=["admin", "super_admin"]).exists()


def _document_access_q(user):
    """
    构建文档访问权限过滤的 Q 对象（类似 SpringBoot JPA Specification 的动态查询条件）。

    权限规则：
    - 未登录用户：无权限（返回空集条件 Q(pk__in=[])）
    - 管理员：无限制（返回空 Q()，即不过滤）
    - 普通用户：可查看 internal/public 文档，以及自己上传/拥有的文档

    参数：
        user (User | None): 当前用户。

    返回：
        Q: Django Q 查询条件对象，用于 QuerySet.filter()。
    """
    if user is None:
        return Q(pk__in=[])
    if _is_document_admin(user):
        return Q()
    return (
        Q(visibility__in=[Document.VISIBILITY_INTERNAL, Document.VISIBILITY_PUBLIC])
        | Q(uploaded_by=user)
        | Q(owner=user)
    )


# ────────────────────────────────────────────────────────────────────────
# 文档查询器（类似 SpringBoot Repository + Specification）
# ────────────────────────────────────────────────────────────────────────

def get_visible_documents_queryset(user):
    """
    获取对指定用户可见的文档查询集（类似 SpringBoot @Repository 中带权限过滤的 findAll）。

    预加载关联：uploaded_by, owner, dataset, version_record, version_record__root_document,
               ingestion_tasks（通过 prefetch_related）。

    参数：
        user (User): 当前用户。

    返回：
        QuerySet: 已过滤权限并优化关联查询的 QuerySet（类似 SpringBoot Pageable 查询）。
    """
    return (
        Document.objects.select_related(
            "uploaded_by",
            "owner",
            "dataset",
            "version_record",
            "version_record__root_document",
        )
        .prefetch_related("ingestion_tasks")
        .filter(_document_access_q(user))
        .order_by("id")
    )


def get_document_for_user(user, document_id):
    """
    为指定用户获取单个文档（包含权限校验）。

    参数：
        user (User): 当前用户。
        document_id (int): 文档主键ID。

    返回：
        Document: 文档模型实例。

    异常：
        Document.DoesNotExist: 文档不存在或用户无权访问。
    """
    return get_visible_documents_queryset(user).get(id=document_id)


# ────────────────────────────────────────────────────────────────────────
# 文档序列化（类似 SpringBoot DTO 转换 / Jackson ObjectMapper）
# ────────────────────────────────────────────────────────────────────────

def _build_file_url(document):
    """
    构建文档文件的访问 URL。

    参数：
        document (Document): 文档模型实例。

    返回：
        str: 文件 URL 或文件路径名。
    """
    try:
        return document.file.url
    except ValueError:
        return document.file.name


def _serialize_ingestion_task(ingestion_task):
    """
    将摄取任务实体序列化为字典（类似 SpringBoot IngestionTaskEntity → IngestionTaskDTO）。

    参数：
        ingestion_task (IngestionTask | None): 摄取任务模型实例。

    返回：
        dict | None: 包含任务所有字段的序列化字典。
    """
    if ingestion_task is None:
        return None
    return {
        "id": ingestion_task.id,
        "celery_task_id": ingestion_task.celery_task_id or None,
        "status": ingestion_task.status,
        "current_step": ingestion_task.current_step,
        "strategy": ingestion_task.strategy,
        "graph_sync_status": ingestion_task.graph_sync_status,
        "graph_sync_error_message": ingestion_task.graph_sync_error_message or None,
        "graph_sync_started_at": ingestion_task.graph_sync_started_at.isoformat()
        if ingestion_task.graph_sync_started_at
        else None,
        "graph_sync_finished_at": ingestion_task.graph_sync_finished_at.isoformat()
        if ingestion_task.graph_sync_finished_at
        else None,
        "graph_document_id": ingestion_task.graph_document_id or None,
        "graph_track_id": ingestion_task.graph_track_id or None,
        "total_section_count": ingestion_task.total_section_count,
        "indexed_section_count": ingestion_task.indexed_section_count,
        "failed_section_count": ingestion_task.failed_section_count,
        "error_message": ingestion_task.error_message or None,
        "retry_count": ingestion_task.retry_count,
        "started_at": ingestion_task.started_at.isoformat() if ingestion_task.started_at else None,
        "finished_at": ingestion_task.finished_at.isoformat() if ingestion_task.finished_at else None,
        "created_at": ingestion_task.created_at.isoformat(),
        "updated_at": ingestion_task.updated_at.isoformat(),
    }


def _get_latest_ingestion_task(document):
    """
    获取文档最近的摄取任务（优先使用 prefetch 缓存，避免 N+1 查询）。

    参数：
        document (Document): 文档模型实例。

    返回：
        IngestionTask | None: 最近的摄取任务实例。
    """
    if (
        hasattr(document, "_prefetched_objects_cache")
        and "ingestion_tasks" in document._prefetched_objects_cache
    ):
        tasks = list(document._prefetched_objects_cache["ingestion_tasks"])
        return tasks[-1] if tasks else None
    return document.ingestion_tasks.order_by("id").last()


def _build_process_result(document, ingestion_task):
    """
    构建文档处理状态的用户可读描述。

    根据文档当前状态和摄取任务步骤生成中文状态描述消息。
    类似 SpringBoot 中枚举映射为 i18n 消息的方法。

    参数：
        document (Document): 文档模型实例。
        ingestion_task (IngestionTask | None): 摄取任务实例。

    返回：
        str: 人类可读的文档处理状态描述。
    """
    if document.status == Document.STATUS_FAILED:
        return document.error_message or "文档处理失败。"
    if document.status == Document.STATUS_INDEXED:
        return "文档已完成解析、切块与索引，可用于检索。"
    if ingestion_task is None:
        return "文档已上传，等待摄取任务执行。"

    step_messages = {
        IngestionTask.STEP_QUEUED: "摄取任务已排队，等待执行。",
        IngestionTask.STEP_PARSING: "正在解析文档正文与元数据。",
        IngestionTask.STEP_CHUNKING: "正在切分文本片段。",
        IngestionTask.STEP_INDEXING: "正在写入向量索引。",
        IngestionTask.STEP_GRAPH_SYNC: "正在同步图谱索引。",
        IngestionTask.STEP_COMPLETED: "文档摄取已完成。",
        IngestionTask.STEP_FAILED: ingestion_task.error_message or document.error_message or "文档摄取失败。",
    }
    return step_messages.get(ingestion_task.current_step, "文档处理中。")


def serialize_document(document, include_content_preview=False, include_content=False):
    """
    将 Document 实体完整序列化为字典（类似 SpringBoot Entity → 完整 DTO 转换）。

    序列化内容包括：ID、标题、文件名、状态、可见性、文件大小、数据集、上传者、
    所有者、来源日期、版本信息、出处溯源、分块/向量统计、处理状态和最新摄取任务。

    参数：
        document (Document): 文档模型实例。
        include_content_preview (bool): 是否包含 200 字符的内容预览。
        include_content (bool): 是否包含完整解析文本。

    返回：
        dict: 文档的完整序列化字典。
    """
    ingestion_task = _get_latest_ingestion_task(document)
    original_url = _build_file_url(document)
    version_record = _get_version_record(document)
    provenance = _serialize_provenance(version_record)

    try:
        chunk_count = document.chunks.count()
    except Exception:
        chunk_count = 0

    try:
        vector_count = document.chunks.exclude(vector_id="").count()
    except Exception:
        vector_count = 0

    parsed_text = document.parsed_text or ""

    payload = {
        "id": document.id,
        "title": document.title,
        "filename": document.filename,
        "doc_type": document.doc_type,
        "status": document.status,
        "visibility": document.visibility,
        "file_size": document.file_size,
        "dataset": _serialize_dataset_summary(getattr(document, "dataset", None)),
        "uploader": _serialize_user(getattr(document, "uploaded_by", None)),
        "uploaded_by": _serialize_user(getattr(document, "uploaded_by", None)),
        "owner": _serialize_user(getattr(document, "owner", None)),
        "source_date": document.source_date.isoformat() if document.source_date else None,
        "root_document_id": _get_root_document_id(document, version_record),
        "version_number": _get_current_version_number(document, version_record),
        "current_version": _get_current_version_number(document, version_record),
        "version_count": _get_version_count(document, version_record),
        "is_current_version": version_record.is_current if version_record is not None else True,
        "provenance": provenance,
        "source_type": provenance["source_type"],
        "source_label": provenance["source_label"],
        "source_metadata": provenance["source_metadata"],
        "processing_notes": provenance["processing_notes"],
        "file_path": getattr(document.file, "name", ""),
        "original_url": original_url,
        "preview_url": original_url,
        "chunk_count": chunk_count,
        "vector_count": vector_count,
        "error_message": document.error_message or None,
        "process_result": _build_process_result(document, ingestion_task),
        "latest_ingestion_task": _serialize_ingestion_task(ingestion_task),
        "created_at": document.created_at.isoformat(),
        "updated_at": document.updated_at.isoformat(),
    }
    if include_content_preview:
        payload["parsed_text_preview"] = parsed_text[:200]
        payload["preview_text"] = parsed_text[:200]
    if include_content:
        payload["parsed_text"] = parsed_text
        payload["extracted_text"] = parsed_text
    return payload


def build_document_response(document, *, include_content_preview=False, message=None):
    """
    构建标准的文档 API 响应格式（类似 SpringBoot ResponseEntity 包装）。

    参数：
        document (Document): 文档模型实例。
        include_content_preview (bool): 是否包含内容预览。
        message (str, optional): 可选的消息文本。

    返回：
        dict: {"document": dict, "message": str (可选)} 格式的响应。
    """
    payload = {
        "document": serialize_document(
            document,
            include_content_preview=include_content_preview,
            include_content=include_content_preview,
        )
    }
    if message is not None:
        payload["message"] = message
    return payload


# ────────────────────────────────────────────────────────────────────────
# 分页和过滤（类似 SpringBoot Pageable / Specification）
# ────────────────────────────────────────────────────────────────────────

def _normalize_page(value, default=1):
    """
    标准化页码参数（最小为 1）。

    参数：
        value (any): 原始页码值。
        default (int): 默认值，当解析失败时返回。

    返回：
        int: 标准化后的页码。
    """
    try:
        return max(int(value), 1)
    except (TypeError, ValueError):
        return default


def _normalize_page_size(value, default=10, max_page_size=50):
    """
    标准化每页大小参数（1 ~ max_page_size 之间）。

    参数：
        value (any): 原始每页大小值。
        default (int): 默认每页大小。
        max_page_size (int): 最大允许的每页大小。

    返回：
        int: 标准化后的每页大小。
    """
    try:
        return min(max(int(value), 1), max_page_size)
    except (TypeError, ValueError):
        return default


def _filter_documents(queryset, *, q="", status="all", time_range="all", dataset_id=None):
    """
    对文档查询集应用搜索关键词、状态、时间范围和数据集过滤。

    过滤维度（类似 SpringBoot Specification / Criteria API）：
    - 关键词搜索：匹配标题、文件名、上传者用户名/邮箱、解析文本
    - 状态过滤：indexed（已索引）、failed（失败）、processing（处理中）
    - 时间范围：7d（最近7天）、30d（最近30天）
    - 数据集过滤：按 dataset_id 精确过滤

    参数：
        queryset (QuerySet): 基础文档查询集。
        q (str): 搜索关键词。
        status (str): 状态过滤（"all"/"indexed"/"failed"/"processing"）。
        time_range (str): 时间范围（"all"/"7d"/"30d"）。
        dataset_id (int | None): 数据集ID过滤。

    返回：
        QuerySet: 过滤后的查询集。
    """
    keyword = (q or "").strip()
    if keyword:
        queryset = queryset.filter(
            Q(title__icontains=keyword)
            | Q(filename__icontains=keyword)
            | Q(uploaded_by__username__icontains=keyword)
            | Q(uploaded_by__email__icontains=keyword)
            | Q(parsed_text__icontains=keyword)
        )

    normalized_status = str(status or "all").lower()
    if normalized_status == "indexed":
        queryset = queryset.filter(status=Document.STATUS_INDEXED)
    elif normalized_status == "failed":
        queryset = queryset.filter(status=Document.STATUS_FAILED)
    elif normalized_status == "processing":
        queryset = queryset.filter(
            Q(status__in=[Document.STATUS_PARSED, Document.STATUS_CHUNKED])
            | Q(
                ingestion_tasks__status__in=[
                    IngestionTask.STATUS_QUEUED,
                    IngestionTask.STATUS_RUNNING,
                ]
            )
        ).distinct()

    normalized_time_range = str(time_range or "all").lower()
    if normalized_time_range in {"7d", "30d"}:
        days = 7 if normalized_time_range == "7d" else 30
        cutoff = timezone.now() - timedelta(days=days)
        queryset = queryset.filter(created_at__gte=cutoff)

    parsed_dataset_id = _parse_dataset_id(dataset_id)
    if parsed_dataset_id is not None:
        queryset = queryset.filter(dataset_id=parsed_dataset_id)

    return queryset


def build_document_list_response(
    user, *, q="", status="all", time_range="all", dataset_id=None, page=None, page_size=None
):
    """
    构建分页的文档列表响应（类似 SpringBoot Page<DocumentDTO> 返回）。

    仅返回当前版本的文档（is_current=True 或无版本记录）。

    参数：
        user (User): 当前用户。
        q (str): 搜索关键词。
        status (str): 状态过滤。
        time_range (str): 时间范围。
        dataset_id (int | None): 数据集ID。
        page (int | None): 页码（从1开始），为 None 时不分页返回全部。
        page_size (int | None): 每页大小。

    返回：
        dict: {"documents": list[dict], "total": int, "page": int (可选),
               "page_size": int (可选), "total_pages": int (可选)}
    """
    queryset = _filter_documents(
        get_visible_documents_queryset(user),
        q=q,
        status=status,
        time_range=time_range,
        dataset_id=dataset_id,
    )
    queryset = queryset.filter(
        Q(version_record__is_current=True) | Q(version_record__isnull=True)
    )
    total = queryset.count()
    if page is None and page_size is None:
        return {
            "documents": [serialize_document(document) for document in queryset],
            "total": total,
        }

    safe_page_size = _normalize_page_size(page_size)
    safe_page = _normalize_page(page)
    total_pages = ceil(total / safe_page_size) if total else 0
    start = (safe_page - 1) * safe_page_size
    stop = start + safe_page_size
    documents = [serialize_document(document) for document in queryset[start:stop]]
    return {
        "documents": documents,
        "total": total,
        "page": safe_page,
        "page_size": safe_page_size,
        "total_pages": total_pages,
    }


def build_stats_response(user):
    """
    构建知识库仪表盘统计数据（类似 SpringBoot 中的统计聚合方法）。

    统计维度：文档总数、已索引数、失败数、总存储量、总向量数、数据集数、就绪率。

    参数：
        user (User): 当前用户。

    返回：
        dict: 包含所有统计指标的字典。
    """
    queryset = get_visible_documents_queryset(user).filter(
        Q(version_record__is_current=True) | Q(version_record__isnull=True)
    )
    total_documents = queryset.count()
    indexed_count = queryset.filter(status=Document.STATUS_INDEXED).count()
    failed_count = queryset.filter(status=Document.STATUS_FAILED).count()
    processing_count = total_documents - indexed_count - failed_count
    storage_agg = queryset.aggregate(total_bytes=Sum("file_size"))
    total_storage_bytes = storage_agg["total_bytes"] or 0
    total_vectors = DocumentChunk.objects.exclude(vector_id="").count()
    total_datasets = Dataset.objects.count()
    ready_rate = f"{round((indexed_count / total_documents) * 100)}%" if total_documents else "0%"

    return {
        "total_datasets": total_datasets,
        "total_documents": total_documents,
        "total_vectors": total_vectors,
        "total_storage_bytes": total_storage_bytes,
        "total_storage_formatted": _format_bytes(total_storage_bytes),
        "indexed_count": indexed_count,
        "failed_count": failed_count,
        "processing_count": processing_count,
        "ready_rate": ready_rate,
    }


def _format_bytes(value):
    """
    格式化字节数为人类可读的字符串（B / KB / MB / GB）。

    参数：
        value (int): 字节数。

    返回：
        str: 人类可读的格式字符串。
    """
    if not value or value <= 0:
        return "0 B"
    if value >= 1024 ** 3:
        return f"{value / 1024 ** 3:.1f} GB"
    if value >= 1024 ** 2:
        return f"{value / 1024 ** 2:.1f} MB"
    if value >= 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value} B"


# ────────────────────────────────────────────────────────────────────────
# 分块管理
# ────────────────────────────────────────────────────────────────────────

def serialize_chunk(chunk):
    """
    将 DocumentChunk 实体序列化为字典。

    参数：
        chunk (DocumentChunk): 分块模型实例。

    返回：
        dict: 包含 id, chunk_index, content, vector_id, page_label, metadata, created_at 的序列化字典。
    """
    metadata = chunk.metadata or {}
    return {
        "id": chunk.id,
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "vector_id": chunk.vector_id or "",
        "page_label": metadata.get("page_label", f"chunk-{chunk.chunk_index + 1}"),
        "metadata": metadata,
        "created_at": chunk.created_at.isoformat(),
    }


def build_document_chunks_response(document):
    """
    构建文档的全部 chunk 列表响应。

    参数：
        document (Document): 文档模型实例。

    返回：
        dict: {"document_id": int, "chunks": list[dict]}
    """
    return {
        "document_id": document.id,
        "chunks": [serialize_chunk(chunk) for chunk in document.chunks.order_by("chunk_index")],
    }


# ────────────────────────────────────────────────────────────────────────
# 文档创建（类似 SpringBoot @Transactional 的创建方法）
# ────────────────────────────────────────────────────────────────────────

def _compute_file_hash(uploaded_file):
    """
    计算上传文件的 SHA-256 哈希值（用于去重检测）。

    参数：
        uploaded_file (UploadedFile): Django 上传文件对象。

    返回：
        str: 文件的 SHA-256 十六进制哈希字符串。
    """
    sha256 = hashlib.sha256()
    for chunk in uploaded_file.chunks(chunk_size=8192):
        sha256.update(chunk)
    uploaded_file.seek(0)
    return sha256.hexdigest()


def create_document_from_upload(
    *,
    uploaded_file,
    title,
    source_date,
    uploaded_by=None,
    owner=None,
    owner_id=None,
    visibility=None,
    dataset=None,
    dataset_id=None,
    skip_initial_version=False,
    allow_duplicate_hash=False,
):
    """
    从上传文件创建文档实体（类似 SpringBoot @Transactional 的创建方法）。

    包含文件类型校验、SHA-256 哈希去重、所有者和数据集的解析，以及可选的初始版本记录。
    类似 SpringBoot 中调用多个 repository.save() 和级联关联的操作。

    参数：
        uploaded_file (UploadedFile): Django 上传的文件对象。
        title (str): 文档标题（为空时使用文件名不含扩展名）。
        source_date (str): 来源日期（YYYY-MM-DD）。
        uploaded_by (User | None): 上传者用户。
        owner (User | None): 所有者用户（默认与 uploaded_by 相同）。
        owner_id (int | None): 所有者ID（可覆盖 owner 参数）。
        visibility (str | None): 可见性（private/internal/public）。
        dataset (Dataset | None): 数据集对象。
        dataset_id (int | None): 数据集ID（可覆盖 dataset 参数）。
        skip_initial_version (bool): 是否跳过创建初始版本记录（版本管理场景中用于延迟创建）。
        allow_duplicate_hash (bool): 是否允许相同哈希的重复文件上传。

    返回：
        Document: 新创建的文档模型实例。

    异常：
        ValueError: 文件类型不支持、owner_id/dataset_id 对应的记录不存在。
        DuplicateDocumentError: 文件已存在且不允许重复。
    """
    filename = uploaded_file.name
    doc_type = _detect_doc_type(filename)
    if doc_type not in {"txt", "pdf", "docx"}:
        raise ValueError("当前仅支持 txt/pdf/docx 文件上传。")

    file_hash = _compute_file_hash(uploaded_file)

    existing_doc = None
    if not allow_duplicate_hash:
        existing_doc = Document.objects.filter(
            file_hash=file_hash,
            file_size=uploaded_file.size,
        ).order_by("-id").first()
    if existing_doc is not None:
        raise DuplicateDocumentError(
            f"文件已存在（《{existing_doc.title}》），请勿重复上传。",
            existing_document={
                "id": existing_doc.id,
                "title": existing_doc.title,
                "filename": existing_doc.filename,
            },
        )

    resolved_owner = owner or uploaded_by
    parsed_owner_id = _parse_owner_id(owner_id)
    if parsed_owner_id is not None:
        User = get_user_model()
        try:
            resolved_owner = User.objects.get(id=parsed_owner_id)
        except User.DoesNotExist as exc:
            raise ValueError("owner_id 对应用户不存在。") from exc

    resolved_dataset = dataset
    parsed_dataset_id = _parse_dataset_id(dataset_id)
    if parsed_dataset_id is not None:
        try:
            resolved_dataset = Dataset.objects.get(id=parsed_dataset_id)
        except Dataset.DoesNotExist as exc:
            raise ValueError("dataset_id 对应数据集不存在。") from exc

    document = Document.objects.create(
        title=title or Path(filename).stem,
        file=uploaded_file,
        file_size=uploaded_file.size,
        file_hash=file_hash,
        filename=filename,
        doc_type=doc_type,
        uploaded_by=uploaded_by,
        owner=resolved_owner,
        dataset=resolved_dataset,
        visibility=_parse_visibility(visibility),
        source_date=_parse_source_date(source_date),
    )
    if not skip_initial_version:
        DocumentVersion.objects.create(
            root_document=document,
            document=document,
            version_number=1,
            is_current=True,
            source_type="upload",
            source_label=document.title or document.filename,
            source_metadata={},
            processing_notes="",
        )
    return document


# ────────────────────────────────────────────────────────────────────────
# 文档列表（简单无分页）
# ────────────────────────────────────────────────────────────────────────

def list_documents(user):
    """
    获取用户可见的文档列表（仅当前版本）。

    参数：
        user (User): 当前用户。

    返回：
        list[dict]: 序列化后的文档列表。
    """
    queryset = get_visible_documents_queryset(user).filter(
        Q(version_record__is_current=True) | Q(version_record__isnull=True)
    )
    return [serialize_document(document) for document in queryset]


# ────────────────────────────────────────────────────────────────────────
# 文档摄取管道（类似 SpringBoot 编排的 Step-by-Step 流程）
# ────────────────────────────────────────────────────────────────────────

def _parse_document_ids(raw_ids):
    """
    解析并校验文档ID列表。

    参数：
        raw_ids (list): 原始的ID值列表。

    返回：
        list[int]: 校验后的整数ID列表。

    异常：
        ValueError: 输入不是整数数组。
    """
    if not isinstance(raw_ids, (list, tuple)):
        raise ValueError("document_ids 必须是整数数组。")

    document_ids = []
    for raw_value in raw_ids:
        if isinstance(raw_value, bool) or not isinstance(raw_value, int):
            raise ValueError("document_ids 必须是整数数组。")
        document_ids.append(raw_value)
    return document_ids


def _update_document_status(document, *, status, error_message=None):
    """
    更新文档状态和可选的错误消息。

    参数：
        document (Document): 文档模型实例。
        status (str): 新状态值。
        error_message (str, optional): 错误消息。
    """
    document.status = status
    update_fields = ["status", "updated_at"]
    if error_message is not None:
        document.error_message = error_message
        update_fields.append("error_message")
    document.save(update_fields=update_fields)


def _update_ingestion_task_step(ingestion_task, *, current_step):
    """
    更新摄取任务的当前步骤。

    参数：
        ingestion_task (IngestionTask): 摄取任务实例。
        current_step (str): 当前步骤标识。
    """
    ingestion_task.current_step = current_step
    ingestion_task.save(update_fields=["current_step", "updated_at"])


def _update_version_record_from_parser(document, parser_result):
    """
    将解析器返回的文档元数据合并到版本记录的 source_metadata 中。

    参数：
        document (Document): 文档模型实例。
        parser_result (dict): parser 返回的解析结果。
    """
    version_record = _get_version_record(document)
    if version_record is None:
        return

    document_metadata = (parser_result or {}).get("document_metadata") or {}
    version_record.source_metadata = {
        **(version_record.source_metadata or {}),
        **document_metadata,
    }
    if document_metadata.get("fallback_used"):
        version_record.processing_notes = "pdf parse fallback to pypdf"
    version_record.save(update_fields=["source_metadata", "processing_notes"])


def _build_chunk_metadata(document, index, parser_defaults=None):
    """
    构建分块的元数据字典，包含文档ID、标题、类型、来源日期、数据集、版本等信息。

    参数：
        document (Document): 文档模型实例。
        index (int): 分块索引。
        parser_defaults (dict, optional): 解析器提供的默认元数据。

    返回：
        dict: 合并后的分块元数据字典。
    """
    version_record = _get_version_record(document)
    metadata = {
        "document_id": document.id,
        "document_title": document.title,
        "doc_type": document.doc_type,
        "source_date": document.source_date.isoformat() if document.source_date else None,
        "dataset_id": document.dataset_id,
        "dataset_name": document.dataset.name if getattr(document, "dataset", None) else None,
        "root_document_id": _get_root_document_id(document, version_record),
        "version_number": _get_current_version_number(document, version_record),
        "chunk_index": index,
        "page_label": f"chunk-{index + 1}",
    }
    return {
        **metadata,
        **(parser_defaults or {}),
    }


def _build_section_chunk_metadata(document, index, parser_defaults=None):
    """
    构建层级分块中 Section 级的元数据字典。

    参数：
        document (Document): 文档模型实例。
        index (int): Section 索引。
        parser_defaults (dict, optional): 解析器默认元数据。

    返回：
        dict: Section 级元数据字典，额外包含 section_index。
    """
    metadata = _build_chunk_metadata(document, index, parser_defaults)
    return {
        **metadata,
        "section_index": index,
        "page_label": f"section-{index + 1}",
    }


def _enrich_child_chunk_metadata(child_metadata, section):
    """
    用所属 Section 的信息丰富子块的元数据。

    参数：
        child_metadata (dict): 子块的原始元数据。
        section (DocumentSectionChunk): 所属 Section 实体。

    返回：
        dict: 丰富后的子块元数据，包含 section_label, section_page_label, section_path。
    """
    metadata = {
        **(child_metadata or {}),
        "section_label": section.section_label or section.metadata.get("page_label", ""),
        "section_page_label": section.metadata.get("page_label", ""),
        "section_path": section.section_path or "",
    }
    return metadata


def _count_chunk_result_items(chunks):
    """
    统计分块结果中的子块数量（兼容层级分块和普通分块两种格式）。

    参数：
        chunks (dict | list): 分块结果，层级分块时为 {"child_chunks": [...]}，普通为 list。

    返回：
        int: 子块数量。
    """
    if isinstance(chunks, dict):
        return len(chunks.get("child_chunks") or [])
    return len(chunks)


def parse_document(document):
    """
    解析文档：调用 ParserService 提取文本和元数据，更新文档状态为 PARSED。

    类似 SpringBoot 摄取管道中的第一步。

    参数：
        document (Document): 文档模型实例。

    返回：
        dict: ParserService 返回的解析结果。
    """
    parser_result = parse_document_file(document)
    document.parsed_text = parser_result["parsed_text"]
    document.error_message = ""
    document.save(update_fields=["parsed_text", "error_message", "updated_at"])
    _update_version_record_from_parser(document, parser_result)
    _update_document_status(document, status=Document.STATUS_PARSED)
    return parser_result


def chunk_document(document, parser_result):
    """
    对文档进行文本分块：根据策略选择分块方法并持久化。

    分块策略选择流程：
    1. 计算固定长度分块的预估数量
    2. 调用 choose_chunking_strategy 决策
    3. 层级分块（hierarchical）：先生成 Section 大块，再在每个 Section 内生成 child 小块
    4. 基于元素分块：当有 Unstructured 元素时使用
    5. 句子窗口分块：若 KB_SENTENCE_WINDOW_ENABLED
    6. 固定长度分块：默认回退方案

    类似 SpringBoot 摄取管道中的第二步。

    参数：
        document (Document): 文档模型实例。
        parser_result (dict): 上一步解析器返回的结果。

    返回：
        dict | list: 分块结果（层级模式为 {"sections": ..., "child_chunks": ...}，普通模式为 list）。
    """
    parser_result = parser_result or {}
    parser_defaults = parser_result.get("chunk_metadata_defaults") or {}
    elements = parser_result.get("elements")
    parsed_text = parser_result.get("parsed_text", "")
    DocumentSectionChunk.objects.filter(document=document).delete()
    DocumentChunk.objects.filter(document=document).delete()

    estimated_flat_chunk_count = estimate_flat_chunk_count(parsed_text)
    strategy = choose_chunking_strategy(
        parsed_text_length=len((parsed_text or "").strip()),
        estimated_flat_chunk_count=estimated_flat_chunk_count,
    )

    if strategy == IngestionTask.STRATEGY_HIERARCHICAL:
        hierarchical = build_hierarchical_document_chunks(
            text=parsed_text,
            elements=elements,
            section_metadata_builder=lambda index: _build_section_chunk_metadata(document, index, parser_defaults),
            child_metadata_builder=lambda section, index: _build_chunk_metadata(document, index, parser_defaults),
        )
        DocumentSectionChunk.objects.bulk_create(
            [
                DocumentSectionChunk(
                    document=document,
                    section_index=section["chunk_index"],
                    section_label=section["metadata"].get("page_label", ""),
                    section_path="",
                    content=section["content"],
                    search_text=build_contextual_search_text(
                        content=section["content"],
                        metadata=section["metadata"],
                    ),
                    vector_id="",
                    metadata=section["metadata"],
                )
                for section in hierarchical["sections"]
            ]
        )
        created_sections = DocumentSectionChunk.objects.filter(document=document).order_by("section_index")
        section_by_index = {
            section.section_index: section
            for section in created_sections
        }
        DocumentChunk.objects.bulk_create(
            [
                DocumentChunk(
                    document=document,
                    section_chunk=section_by_index[child["section_index"]],
                    chunk_index=child["chunk_index"],
                    content=child["content"],
                    search_text=build_contextual_search_text(
                        content=child["content"],
                        metadata=_enrich_child_chunk_metadata(
                            child["metadata"],
                            section_by_index[child["section_index"]],
                        ),
                    ),
                    vector_id="",
                    metadata=_enrich_child_chunk_metadata(
                        child["metadata"],
                        section_by_index[child["section_index"]],
                    ),
                )
                for child in hierarchical["child_chunks"]
            ]
        )
        _update_document_status(document, status=Document.STATUS_CHUNKED)
        return hierarchical

    if elements:
        chunks = build_document_chunks_from_elements(
            elements,
            metadata_builder=lambda index: _build_chunk_metadata(document, index, parser_defaults),
        )
    elif getattr(settings, "KB_SENTENCE_WINDOW_ENABLED", False):
        chunks = build_sentence_window_chunks(
            parsed_text,
            metadata_builder=lambda index: _build_chunk_metadata(document, index, parser_defaults),
        )
    else:
        chunks = build_document_chunks(
            parsed_text,
            metadata_builder=lambda index: _build_chunk_metadata(document, index, parser_defaults),
        )
    DocumentChunk.objects.bulk_create(
        [
            DocumentChunk(
                document=document,
                chunk_index=chunk["chunk_index"],
                content=chunk["content"],
                search_text=build_contextual_search_text(
                    content=chunk["content"],
                    metadata=chunk["metadata"],
                ),
                vector_id="",
                metadata=chunk["metadata"],
            )
            for chunk in chunks
        ]
    )
    _update_document_status(document, status=Document.STATUS_CHUNKED)
    return chunks


def vectorize_document(document):
    """
    对文档的分块进行向量化并索引到 Milvus。

    类似 SpringBoot 摄取管道中的第三步。

    参数：
        document (Document): 文档模型实例。

    返回：
        Document: 更新后的文档模型实例。
    """
    index_document_chunks(document)
    _update_document_status(document, status=Document.STATUS_INDEXED)
    return document


# ────────────────────────────────────────────────────────────────────────
# 摄取任务管理（类似 SpringBoot 异步任务管理）
# ────────────────────────────────────────────────────────────────────────

def _mark_ingestion_task_running(ingestion_task):
    """
    标记摄取任务为运行中状态。

    参数：
        ingestion_task (IngestionTask): 摄取任务实例。
    """
    ingestion_task.status = IngestionTask.STATUS_RUNNING
    ingestion_task.current_step = IngestionTask.STEP_PARSING
    ingestion_task.error_message = ""
    ingestion_task.started_at = timezone.now()
    ingestion_task.finished_at = None
    ingestion_task.save(
        update_fields=[
            "status",
            "current_step",
            "error_message",
            "started_at",
            "finished_at",
            "updated_at",
        ]
    )


def _mark_ingestion_task_finished(ingestion_task, *, status, error_message=""):
    """
    标记摄取任务为完成或失败状态。

    参数：
        ingestion_task (IngestionTask): 摄取任务实例。
        status (str): 最终状态（STATUS_SUCCEEDED 或 STATUS_FAILED）。
        error_message (str): 失败时的错误消息。
    """
    ingestion_task.status = status
    ingestion_task.current_step = (
        IngestionTask.STEP_COMPLETED
        if status == IngestionTask.STATUS_SUCCEEDED
        else IngestionTask.STEP_FAILED
    )
    ingestion_task.error_message = error_message
    ingestion_task.finished_at = timezone.now()
    ingestion_task.save(
        update_fields=[
            "status",
            "current_step",
            "error_message",
            "finished_at",
            "updated_at",
        ]
    )


def ingest_document(document, ingestion_task=None):
    """
    执行文档的完整摄取管道：解析 -> 清洗 -> 分块 -> 向量化。

    管道步骤（类似 SpringBoot @Transactional 的编排方法）：
    1. 解析（parse）：提取文本和文档元素
    2. 清洗（clean）：应用清洗规则，质量门控检查
    3. 分块（chunk）：按策略切分文本
    4. 向量化（vectorize）：生成 embedding 并写入 Milvus

    每步都会更新文档状态和摄取任务步骤，支持限流（tracing span）和结构化日志。
    失败时自动清理已分块的数据和向量。

    参数：
        document (Document): 文档模型实例。
        ingestion_task (IngestionTask | None): 关联的摄取任务实例。

    返回：
        Document: 摄取完成后的文档模型实例。

    异常：
        ValueError: 文档清洗失败。
        DocumentQualityGateError: 清洗质量不达标，阻止入库。
        Exception: 其他摄取失败，文档状态标记为 FAILED。
    """
    started_at = time.monotonic()
    log_base = build_log_extra(
        document_id=document.id,
        dataset_id=document.dataset_id,
        task_id=getattr(ingestion_task, "id", None),
        step="ingest",
        status="running",
    )
    logger.info("Starting knowledgebase ingestion", extra=log_base)
    with trace_span(
        "knowledgebase.ingest",
        metadata={"document_id": document.id, "doc_type": document.doc_type},
        input_data={"document_title": document.title},
    ) as observation:
        try:
            parser_result = parse_document(document)
            logger.info(
                "Document parsing completed",
                extra=build_log_extra(
                    document_id=document.id,
                    dataset_id=document.dataset_id,
                    task_id=getattr(ingestion_task, "id", None),
                    step="parsing",
                    status="succeeded",
                    duration_ms=round((time.monotonic() - started_at) * 1000, 1),
                ),
            )

            if ingestion_task is not None:
                _update_ingestion_task_step(
                    ingestion_task,
                    current_step=IngestionTask.STEP_CLEANING,
                )
            _update_document_status(
                document,
                status=Document.STATUS_CLEANING,
            )
            from knowledgebase.services.cleaning_engine_service import clean_document

            try:
                cleaning_result = clean_document(document=document)
            except Exception as cleaning_exc:
                logger.exception(
                    "Document cleaning failed during ingestion",
                    extra=build_log_extra(
                        document_id=document.id,
                        dataset_id=document.dataset_id,
                        task_id=getattr(ingestion_task, "id", None),
                        step="cleaning",
                        status="failed",
                        duration_ms=round((time.monotonic() - started_at) * 1000, 1),
                        error_code="cleaning_failed",
                    ),
                )
                raise ValueError(f"文档清洗失败: {cleaning_exc}") from cleaning_exc

            parser_result["parsed_text"] = document.parsed_text
            quality_gate = evaluate_quality_gate(cleaning_result.quality_score)
            logger.info(
                "Document cleaning completed",
                extra=build_log_extra(
                    document_id=document.id,
                    dataset_id=document.dataset_id,
                    task_id=getattr(ingestion_task, "id", None),
                    step="cleaning",
                    status="succeeded",
                    duration_ms=round((time.monotonic() - started_at) * 1000, 1),
                    quality_score=cleaning_result.quality_score,
                    quality_gate_status=quality_gate["status"],
                ),
            )
            if quality_gate["should_block"]:
                raise DocumentQualityGateError(
                    (
                        f"文档清洗质量不足（{cleaning_result.quality_score:.1f} 分），"
                        f"低于当前阈值 {quality_gate['min_quality_score']:.1f}，已阻止入库。"
                    ),
                    score=cleaning_result.quality_score,
                    quality_gate=quality_gate,
                )

            if ingestion_task is not None:
                _update_ingestion_task_step(
                    ingestion_task,
                    current_step=IngestionTask.STEP_CHUNKING,
                )
            chunks = chunk_document(document, parser_result)
            if ingestion_task is not None:
                _update_ingestion_task_step(
                    ingestion_task,
                    current_step=IngestionTask.STEP_INDEXING,
                )
            vectorize_document(document)
            if ingestion_task is not None:
                _mark_ingestion_task_finished(
                    ingestion_task,
                    status=IngestionTask.STATUS_SUCCEEDED,
                )
            duration_ms = round((time.monotonic() - started_at) * 1000, 1)
            logger.info(
                "Knowledgebase ingestion completed",
                extra=build_log_extra(
                    document_id=document.id,
                    dataset_id=document.dataset_id,
                    task_id=getattr(ingestion_task, "id", None),
                    step="indexing",
                    status="succeeded",
                    duration_ms=duration_ms,
                    quality_score=cleaning_result.quality_score,
                    quality_gate_status=quality_gate["status"],
                ),
            )
            observation.update(
                output={
                    "status": "succeeded",
                    "chunk_count": _count_chunk_result_items(chunks),
                }
            )
            return document
        except Exception as exc:
            DocumentSectionChunk.objects.filter(document=document).delete()
            DocumentChunk.objects.filter(document=document).delete()
            error_message = str(exc) or "文档摄取失败。"
            _update_document_status(
                document,
                status=Document.STATUS_FAILED,
                error_message=error_message,
            )
            if ingestion_task is not None:
                _mark_ingestion_task_finished(
                    ingestion_task,
                    status=IngestionTask.STATUS_FAILED,
                    error_message=error_message,
                )
            logger.exception(
                "Knowledgebase ingestion failed",
                extra=build_log_extra(
                    document_id=document.id,
                    dataset_id=document.dataset_id,
                    task_id=getattr(ingestion_task, "id", None),
                    step=getattr(ingestion_task, "current_step", "ingest"),
                    status="failed",
                    duration_ms=round((time.monotonic() - started_at) * 1000, 1),
                    error_code=exc.__class__.__name__,
                ),
            )
            observation.update(output={"status": "failed", "error_message": error_message})
            raise


def enqueue_document_ingestion(document):
    """
    将文档的摄取任务加入异步队列（Celery / 进程内后台线程 / 同步内联）。

    分派策略（类似 SpringBoot 中根据配置选择 @Async / 同步执行的策略）：
    - CELERY_TASK_ALWAYS_EAGER: 同步内联执行
    - memory:// broker: 进程内后台线程执行
    - 其他: 通过 Celery 异步 worker 执行

    包含乐观锁保护：检查是否已有进行中的摄取任务，防止重复提交。

    参数：
        document (Document): 文档模型实例。

    返回：
        tuple[IngestionTask, bool]: (摄取任务实例, 是否为新创建)。
    """
    from knowledgebase.tasks import ingest_document_task

    broker_url = str(getattr(settings, "CELERY_BROKER_URL", "") or "")
    should_run_inline = settings.CELERY_TASK_ALWAYS_EAGER
    should_run_in_process = not should_run_inline and broker_url.startswith("memory://")

    with transaction.atomic():
        locked_document = Document.objects.select_for_update().get(id=document.id)
        latest_task = locked_document.ingestion_tasks.order_by("id").last()
        if latest_task and latest_task.status in {
            IngestionTask.STATUS_QUEUED,
            IngestionTask.STATUS_RUNNING,
        }:
            return latest_task, False

        previous_status = locked_document.status
        previous_error_message = locked_document.error_message
        next_retry_count = 0
        if latest_task and latest_task.status == IngestionTask.STATUS_FAILED:
            next_retry_count = latest_task.retry_count + 1
        elif previous_status == Document.STATUS_FAILED:
            next_retry_count = 1
        locked_document.status = Document.STATUS_UPLOADED
        locked_document.error_message = ""
        locked_document.save(update_fields=["status", "error_message", "updated_at"])
        ingestion_task = IngestionTask.objects.create(
            document=locked_document,
            status=IngestionTask.STATUS_QUEUED,
            current_step=IngestionTask.STEP_QUEUED,
            retry_count=next_retry_count,
        )

    try:
        if should_run_inline:
            async_result = ingest_document_task.apply(args=(locked_document.id, ingestion_task.id))
        elif should_run_in_process:
            run_background_job(
                name=f"knowledgebase-ingest-{ingestion_task.id}",
                target=ingest_document_task,
                args=(locked_document.id, ingestion_task.id),
            )
            async_result = type("InProcessTaskResult", (), {"id": f"local-ingest:{ingestion_task.id}"})()
        else:
            async_result = ingest_document_task.delay(locked_document.id, ingestion_task.id)
    except Exception:
        _cleanup_failed_ingestion_dispatch(
            document_id=locked_document.id,
            ingestion_task_id=ingestion_task.id,
            previous_status=previous_status,
            previous_error_message=previous_error_message,
        )
        raise

    ingestion_task.celery_task_id = async_result.id or ""
    ingestion_task.save(update_fields=["celery_task_id", "updated_at"])
    return ingestion_task, True


def _cleanup_failed_ingestion_dispatch(
    *,
    document_id,
    ingestion_task_id,
    previous_status,
    previous_error_message,
):
    """
    清理失败的任务分派：当 Celery/后台任务提交失败时，在事务中删除已排队的
    IngestionTask 并恢复文档到先前状态。

    类似 SpringBoot @Transactional 的回滚补偿操作。

    参数：
        document_id (int): 文档ID。
        ingestion_task_id (int): 摄取任务ID。
        previous_status (str): 文档先前状态。
        previous_error_message (str): 文档先前错误消息。
    """
    with transaction.atomic():
        task = (
            IngestionTask.objects.select_for_update()
            .filter(id=ingestion_task_id)
            .select_related("document")
            .first()
        )
        if task is None:
            return
        if task.status != IngestionTask.STATUS_QUEUED:
            return

        document = Document.objects.select_for_update().filter(id=document_id).first()
        task.delete()

        if document is None:
            return

        document.status = previous_status
        document.error_message = previous_error_message
        document.save(update_fields=["status", "error_message", "updated_at"])


def batch_enqueue_document_ingestion(user, document_ids):
    """
    批量提交文档摄取任务。

    遍历文档ID列表，对每个文档调用 enqueue_document_ingestion，统计接受/跳过/失败数量。

    参数：
        user (User): 当前用户。
        document_ids (list[int]): 文档ID列表。

    返回：
        dict: {"accepted_count": int, "skipped_count": int, "failed_count": int, "results": list[dict]}
    """
    parsed_document_ids = _parse_document_ids(document_ids)
    accepted_count = 0
    skipped_count = 0
    failed_count = 0
    results = []

    for document_id in parsed_document_ids:
        try:
            document = get_document_for_user(user, document_id)
        except Document.DoesNotExist:
            skipped_count += 1
            results.append(
                {
                    "document_id": document_id,
                    "status": "missing",
                    "reason": "文档不存在。",
                }
            )
            continue

        try:
            ingestion_task, created = enqueue_document_ingestion(document)
        except Document.DoesNotExist:
            skipped_count += 1
            results.append(
                {
                    "document_id": document_id,
                    "status": "missing",
                    "reason": "文档不存在。",
                }
            )
            continue
        except (OperationalError, ProgrammingError, DatabaseError):
            raise
        except Exception as exc:
            failed_count += 1
            results.append(
                {
                    "document_id": document_id,
                    "status": "failed",
                    "reason": str(exc) or "入库任务提交失败。",
                }
            )
            continue

        if created:
            accepted_count += 1
            results.append(
                {
                    "document_id": document_id,
                    "status": "accepted",
                    "task_id": ingestion_task.id,
                }
            )
            continue

        skipped_count += 1
        results.append(
            {
                "document_id": document_id,
                "status": "skipped",
                "reason": "已有进行中的摄取任务。",
                "task_id": ingestion_task.id,
            }
        )

    return {
        "accepted_count": accepted_count,
        "skipped_count": skipped_count,
        "failed_count": failed_count,
        "results": results,
    }


# ────────────────────────────────────────────────────────────────────────
# 文档删除（级联清理向量、文件、图谱索引）
# ────────────────────────────────────────────────────────────────────────

def delete_document_with_vectors(document):
    """
    删除文档及其关联的所有向量数据和物理文件。

    删除流程：
    1. 记录文件存储位置和 chunk ID 列表
    2. 删除 Document 实体（级联删除关联的 DocumentChunk 等）
    3. 事务提交后异步清理 Milvus 向量、LlamaIndex 节点和物理文件

    类似 SpringBoot @Transactional 中的级联删除和 @TransactionalEventListener 异步清理。

    参数：
        document (Document): 文档模型实例。
    """
    file_field = document.file
    storage = file_field.storage
    file_name = file_field.name
    document_id = document.id
    chunk_ids = list(
        DocumentChunk.objects.filter(document=document).values_list("id", flat=True)
    )
    document.delete()
    transaction.on_commit(
        lambda: _cleanup_deleted_document_artifacts(
            document_id=document_id,
            storage=storage,
            file_name=file_name,
            chunk_ids=chunk_ids,
        )
    )


def _cleanup_deleted_document_artifacts(*, document_id, storage, file_name, chunk_ids):
    """
    事务提交后的回调：清理已删除文档的外部资源。

    包括：Milvus 向量数据、LlamaIndex 图谱节点、物理文件。
    每个清理步骤独立 try-except，一个失败不影响其他步骤。

    参数：
        document_id (int): 已删除的文档ID。
        storage: Django 文件存储后端。
        file_name (str): 文件在存储中的路径名。
        chunk_ids (list[int]): 文档的 chunk ID 列表。
    """
    from rag.services.llamaindex_store_service import delete_document

    try:
        VectorService().delete_document(document_id)
    except Exception:
        logger.exception(
            "Failed to delete knowledgebase vectors after document cleanup",
            extra={"document_id": document_id},
        )

    try:
        delete_document(document_id=document_id, chunk_ids=chunk_ids)
    except Exception:
        logger.exception(
            "Failed to delete llamaindex nodes after document cleanup",
            extra={"document_id": document_id},
        )

    if not file_name:
        return

    try:
        file_exists = storage.exists(file_name)
    except Exception:
        logger.exception(
            "Failed to inspect knowledgebase file after document cleanup",
            extra={"document_id": document_id, "file_name": file_name},
        )
        return

    if file_exists:
        try:
            storage.delete(file_name)
        except Exception:
            logger.exception(
                "Failed to delete knowledgebase file after document cleanup",
                extra={"document_id": document_id, "file_name": file_name},
            )


def batch_delete_documents(user, document_ids):
    """
    批量删除文档，每个文档在独立事务中执行（类似 SpringBoot @Transactional 的逐条操作）。

    对每个文档执行权限检查和进行中任务检查，无法删除的标记为 busy/missing/failed。

    参数：
        user (User): 当前用户。
        document_ids (list[int]): 待删除的文档ID列表。

    返回：
        dict: {"deleted_count": int, "failed_count": int, "results": list[dict]}
    """
    parsed_document_ids = _parse_document_ids(document_ids)
    deleted_count = 0
    failed_count = 0
    results = []

    for document_id in parsed_document_ids:
        try:
            with transaction.atomic():
                document = (
                    Document.objects.select_for_update()
                    .filter(_document_access_q(user))
                    .get(id=document_id)
                )

                active_ingestion_task = document.ingestion_tasks.filter(
                    status__in=[
                        IngestionTask.STATUS_QUEUED,
                        IngestionTask.STATUS_RUNNING,
                    ]
                ).order_by("id").last()
                if active_ingestion_task is not None:
                    failed_count += 1
                    results.append(
                        {
                            "document_id": document_id,
                            "status": "busy",
                            "message": "文档存在进行中的摄取任务，无法删除。",
                        }
                    )
                    continue

                delete_document_with_vectors(document)
        except Document.DoesNotExist:
            failed_count += 1
            results.append(
                {
                    "document_id": document_id,
                    "status": "missing",
                    "message": "文档不存在。",
                }
            )
            continue
        except (OperationalError, ProgrammingError, DatabaseError):
            raise
        except Exception as exc:
            failed_count += 1
            results.append(
                {
                    "document_id": document_id,
                    "status": "failed",
                    "message": str(exc) or "删除失败。",
                }
            )
            continue

        deleted_count += 1
        results.append({"document_id": document_id, "status": "deleted"})

    return {
        "deleted_count": deleted_count,
        "failed_count": failed_count,
        "results": results,
    }


def start_ingestion_task(ingestion_task):
    """
    开始执行摄取任务：将任务状态从 QUEUED 切换为 RUNNING。

    若任务之前为 FAILED 状态（重试场景），递增 retry_count。

    参数：
        ingestion_task (IngestionTask): 摄取任务实例。

    返回：
        IngestionTask: 更新后的摄取任务实例。
    """
    if ingestion_task.status == IngestionTask.STATUS_FAILED:
        ingestion_task.retry_count += 1
    _mark_ingestion_task_running(ingestion_task)
    if ingestion_task.retry_count:
        ingestion_task.save(update_fields=["retry_count", "updated_at"])
    return ingestion_task
