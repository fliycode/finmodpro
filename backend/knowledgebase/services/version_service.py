"""
版本管理服务 —— 对应 SpringBoot 中的 @Service 组件，管理文档版本的生命周期。

文档版本管理核心功能：
- 获取文档的版本记录
- 获取版本链表中的根文档
- 确保文档有初始版本记录（类似懒加载）
- 创建新版本（文档快照 + 新 Document 实体）
- 构建版本历史响应

版本号从 1 开始单调递增，每个版本创建一个新的 Document 实体，
通过 root_document 字段链接形成版本链表。

SpringBoot 类比：
- Django DocumentVersion model          →  SpringBoot @Entity DocumentVersion
- Django transaction.atomic              →  SpringBoot @Transactional
- Django get_root_document()             →  SpringBoot @Service 链表导航方法
- Django create_new_document_version()   →  SpringBoot @Service 带锁的版本快照方法
- Django select_for_update()             →  SpringBoot @Lock(PESSIMISTIC_WRITE)
"""

import json
from pathlib import Path

from django.db import transaction

from knowledgebase.models import DocumentVersion
from knowledgebase.services.document_service import create_document_from_upload


def get_document_version_record(document):
    """
    获取文档的版本记录（类似 SpringBoot 中通过 @OneToOne 关联查询版本实体）。

    参数：
        document (Document | None): 文档模型实例，可为 None。

    返回：
        DocumentVersion | None: 文档的版本记录，若无则返回 None。
    """
    if document is None:
        return None

    try:
        return document.version_record
    except DocumentVersion.DoesNotExist:
        return None


def get_root_document(document):
    """
    获取版本链表中的根文档（首版文档）。

    如果文档没有版本记录，则返回文档自身（即它本身就是根文档）。
    类似 SpringBoot 中通过 parent 引用遍历到链表头部。

    参数：
        document (Document): 文档模型实例。

    返回：
        Document: 版本链表的根文档。
    """
    version_record = get_document_version_record(document)
    if version_record is None:
        return document
    return version_record.root_document


def ensure_initial_document_version(
    document,
    *,
    source_type="upload",
    source_label="",
    source_metadata=None,
    processing_notes="",
):
    """
    确保文档有初始版本记录（如果已存在则直接返回，类似幂等操作）。

    类似 SpringBoot 中的 "findOrCreate" 模式。

    参数：
        document (Document): 文档模型实例。
        source_type (str): 来源类型，默认 "upload"。表示文档的获取方式（上传、爬取等）。
        source_label (str): 来源标签，如文件名或标题。
        source_metadata (dict, optional): 来源元数据（JSON 对象）。
        processing_notes (str): 处理备注。

    返回：
        DocumentVersion: 已有的或新创建的版本记录。
    """
    version_record = get_document_version_record(document)
    if version_record is not None:
        return version_record

    return DocumentVersion.objects.create(
        root_document=document,
        document=document,
        version_number=1,
        is_current=True,
        source_type=(source_type or "upload").strip() or "upload",
        source_label=(source_label or document.title or document.filename).strip(),
        source_metadata=source_metadata or {},
        processing_notes=processing_notes or "",
    )


def serialize_document_version(version_record):
    """
    将 DocumentVersion 实体序列化为字典（类似 SpringBoot Entity → DTO）。

    参数：
        version_record (DocumentVersion): 版本记录模型实例。

    返回：
        dict: 包含所有版本字段的序列化字典，含 isoformat 格式的创建时间。
    """
    return {
        "document_id": version_record.document_id,
        "version_number": version_record.version_number,
        "is_current": version_record.is_current,
        "source_type": version_record.source_type or "",
        "source_label": version_record.source_label or "",
        "source_metadata": version_record.source_metadata or {},
        "processing_notes": version_record.processing_notes or "",
        "created_at": version_record.created_at.isoformat(),
    }


def build_document_versions_response(document):
    """
    构建文档的全部版本历史响应。

    类似 SpringBoot @Service 中聚合版本链表数据的方法。

    参数：
        document (Document): 文档模型实例。

    返回：
        dict: {
            "document_id": int (根文档 ID),
            "current_version": int (当前版本号),
            "versions": list[dict] (版本历史列表，按版本号降序)
        }
    """
    root_document = get_root_document(document)
    version_records = list(
        DocumentVersion.objects.filter(root_document=root_document)
        .select_related("document")
        .order_by("-version_number", "-id")
    )
    current_version = next(
        (record.version_number for record in version_records if record.is_current),
        version_records[0].version_number if version_records else 1,
    )
    return {
        "document_id": root_document.id,
        "current_version": current_version,
        "versions": [serialize_document_version(record) for record in version_records],
    }


def parse_source_metadata(raw_value):
    """
    解析来源元数据：将原始值（None/空/JSON字符串/字典）解析为 dict。

    参数：
        raw_value (str | dict | None): 原始元数据值。

    返回：
        dict: 解析后的元数据字典。

    异常：
        ValueError: 输入不是合法的 JSON 字符串或非 JSON 对象。
    """
    if raw_value in (None, ""):
        return {}
    if isinstance(raw_value, dict):
        return raw_value

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError("source_metadata 必须是合法 JSON。") from exc

    if not isinstance(parsed, dict):
        raise ValueError("source_metadata 必须是 JSON 对象。")
    return parsed


@transaction.atomic
def create_new_document_version(
    *,
    document,
    uploaded_file,
    uploaded_by,
    title="",
    source_date="",
    source_type="upload",
    source_label="",
    source_metadata=None,
    processing_notes="",
):
    """
    创建文档的新版本（在数据库事务中原子执行）。

    流程（类似 SpringBoot @Transactional 的版本快照操作）：
    1. 获取根文档（版本链表头部）。
    2. 对现有版本记录加悲观锁（select_for_update），防止并发冲突。
    3. 确定下一个版本号（当前最大版本号 + 1）。
    4. 将旧版本标记为 is_current=False。
    5. 调用 create_document_from_upload 创建新的 Document 实体（即版本快照）。
    6. 创建新的 DocumentVersion 记录，链接到根文档。

    加锁逻辑类似于 SpringBoot 的 @Lock(PESSIMISTIC_WRITE)。

    参数：
        document (Document): 当前文档（用于定位版本链表）。
        uploaded_file (UploadedFile): 新版本的文件对象。
        uploaded_by (User): 上传者用户实例。
        title (str): 文档标题，默认为文件名（不含扩展名）。
        source_date (str): 来源日期（YYYY-MM-DD 格式）。
        source_type (str): 来源类型。
        source_label (str): 来源标签。
        source_metadata (dict, optional): 来源元数据。
        processing_notes (str): 处理备注。

    返回：
        Document: 新创建的文档版本实体，已关联 version_record。
    """
    root_document = get_root_document(document)
    existing_versions = list(
        DocumentVersion.objects.select_for_update()
        .filter(root_document=root_document)
        .order_by("-version_number", "-id")
    )
    if not existing_versions:
        existing_versions = [ensure_initial_document_version(root_document)]

    next_version_number = existing_versions[0].version_number + 1
    DocumentVersion.objects.filter(root_document=root_document, is_current=True).update(
        is_current=False
    )

    new_document = create_document_from_upload(
        uploaded_file=uploaded_file,
        title=title or Path(uploaded_file.name).stem,
        source_date=source_date,
        uploaded_by=uploaded_by,
        owner=root_document.owner,
        visibility=root_document.visibility,
        dataset=root_document.dataset,
        skip_initial_version=True,
        allow_duplicate_hash=True,
    )

    version_record = DocumentVersion.objects.create(
        root_document=root_document,
        document=new_document,
        version_number=next_version_number,
        is_current=True,
        source_type=(source_type or "upload").strip() or "upload",
        source_label=(source_label or new_document.title or new_document.filename).strip(),
        source_metadata=source_metadata or {},
        processing_notes=(processing_notes or "").strip(),
    )
    new_document.version_record = version_record
    return new_document
