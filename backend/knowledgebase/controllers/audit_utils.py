"""
审计日志工具模块 —— 为知识库操作构建标准化审计事件数据 (Audit Payload)。

类比 SpringBoot: 相当于 Spring AOP 的 @Aspect 切面中的日志构建工具类。
在 SpringBoot 中你可能用 AOP 或事件监听器自动记录审计信息，
这里则是由各 controller 手动调用 build_xxx_audit_payload() 函数构造审计数据，
再通过 safe_record_audit_event() 写入审计日志表。

核心职责：
1. 为各业务操作（创建/更新/删除）构建结构化的审计详情 JSON。
2. 安全地写入审计日志——即使数据库暂不可用也不影响主流程。
"""
from django.db import DatabaseError, OperationalError, ProgrammingError

from knowledgebase.models import DocumentVersion
from knowledgebase.services.cleaning_quality_service import evaluate_quality_gate
from systemcheck.services.audit_service import record_audit_event

_MAX_AUDIT_DOCUMENT_IDS = 20  # 审计日志中最多保存的文档 ID 数量
_MAX_AUDIT_KEY_COUNT = 20     # 审计日志中最多保存的配置键数量


def safe_record_audit_event(**kwargs):
    """
    安全地记录审计事件 —— 即使数据库异常也不抛出错误。

    类比 SpringBoot: 相当于带容错保护的 @EventListener 方法，
    在数据库不可用时静默失败，保证主业务流程不受审计日志写入的干扰。

    参数:
        **kwargs: 传递给 record_audit_event() 的关键字参数，
                  包括 actor(操作者)、action(操作名)、target_type(目标类型)、
                  target_id(目标ID)、status(状态)、detail_payload(详情JSON)。

    返回:
        成功时返回 record_audit_event 的返回值，数据库异常时返回 None。
    """
    try:
        return record_audit_event(**kwargs)
    except (OperationalError, ProgrammingError, DatabaseError):
        return None


def build_dataset_audit_payload(*, dataset=None, name="", description="", owner=None):
    """
    构建数据集操作的审计 payload。

    类比 SpringBoot: 相当于构建 @Auditable 注解所需的 audit detail DTO。

    参数:
        dataset:     可选的 Dataset 模型实例，提供时从中提取字段值
        name:        数据集名称（当 dataset 为 None 时使用）
        description: 数据集描述
        owner:       数据集所有者

    返回:
        dict: 包含 name、description_length、owner_id 的审计信息字典。
    """
    if dataset is not None:
        name = dataset.name
        description = dataset.description
        owner = getattr(dataset, "owner", None)

    payload = {
        "name": (name or "").strip(),
        "description_length": len((description or "").strip()),
    }
    if owner is not None:
        payload["owner_id"] = owner.id
    return payload


def build_document_audit_payload(
    *,
    document=None,
    title="",
    filename="",
    doc_type="",
    visibility="",
    dataset=None,
    source_date=None,
    file_size=None,
):
    """
    构建文档操作的审计 payload —— 包含文档的完整元数据快照。

    类比 SpringBoot: 相当于 @PreUpdate/@PreRemove 回调中生成的审计快照 DTO。

    参数:
        document:    可选的 Document 模型实例，提供时优先从中提取字段
        title:       文档标题
        filename:    文件名
        doc_type:    文档类型
        visibility:  可见性
        dataset:     所属数据集
        source_date: 来源日期
        file_size:   文件大小

    返回:
        dict: 包含文档所有关键元数据的审计信息字典，
              包括 title、filename、doc_type、visibility、dataset_id、
              source_date、file_size、status、owner_id、uploader_id 等。
    """
    if document is not None:
        dataset = getattr(document, "dataset", None)
        title = document.title
        filename = document.filename
        doc_type = document.doc_type
        visibility = document.visibility
        source_date = document.source_date
        file_size = document.file_size

    payload = {
        "title": (title or "").strip(),
        "filename": (filename or "").strip(),
        "doc_type": (doc_type or "").strip(),
        "visibility": (visibility or "").strip(),
    }
    if dataset is not None:
        payload["dataset_id"] = dataset.id
        payload["dataset_name"] = dataset.name
    if source_date:
        payload["source_date"] = (
            source_date.isoformat()
            if hasattr(source_date, "isoformat")
            else str(source_date)
        )
    if file_size not in (None, ""):
        payload["file_size"] = int(file_size)
    if document is not None:
        payload["status"] = document.status
        payload["owner_id"] = document.owner_id
        payload["uploader_id"] = document.uploaded_by_id
        version_record = _get_document_version_record(document)
        if version_record is not None:
            payload["root_document_id"] = version_record.root_document_id
            payload["version_number"] = version_record.version_number
    return payload


def build_document_version_audit_payload(
    *,
    root_document=None,
    new_document=None,
    title="",
    file_size=None,
    source_type="",
    source_label="",
    source_metadata=None,
    processing_notes="",
):
    """
    构建文档版本操作的审计 payload。

    类比 SpringBoot: 相当于版本管理操作对应的审计快照 DTO，
    在基础文档审计信息之上补充版本特有的元数据。

    参数:
        root_document:    根文档实例
        new_document:     新版本对应的文档实例
        title:            文档标题
        file_size:        文件大小
        source_type:      来源类型
        source_label:     来源标签
        source_metadata:  来源元数据
        processing_notes: 处理备注

    返回:
        dict: 包含文档版本审计信息的字典，在基础文档 payload 上增加
              root_document_id、version_number、source_type、source_label 等字段。
    """
    payload = build_document_audit_payload(document=new_document or root_document, title=title, file_size=file_size)
    if root_document is not None:
        payload["root_document_id"] = root_document.id

    version_record = _get_document_version_record(new_document) if new_document is not None else None
    if version_record is not None:
        payload["version_number"] = version_record.version_number
        source_type = version_record.source_type
        source_label = version_record.source_label
        source_metadata = version_record.source_metadata
        processing_notes = version_record.processing_notes

    if source_type:
        payload["source_type"] = source_type
    if source_label:
        payload["source_label"] = source_label
    if isinstance(source_metadata, dict) and source_metadata:
        payload["source_metadata_keys"] = sorted(source_metadata.keys())[:_MAX_AUDIT_KEY_COUNT]
    if processing_notes:
        payload["processing_notes_present"] = True
    return payload


def build_cleaning_rule_audit_payload(
    *,
    rule=None,
    name="",
    rule_type="",
    enabled=True,
    priority=100,
    config=None,
):
    """
    构建清洗规则操作的审计 payload。

    类比 SpringBoot: 相当于清洗规则 CRUD 操作的审计快照 DTO。

    参数:
        rule:      可选的 CleaningRule 实例，提供时优先提取字段
        name:      规则名称
        rule_type: 规则类型
        enabled:   是否启用
        priority:  优先级
        config:    规则配置参数

    返回:
        dict: 包含 name、rule_type、enabled、priority、config_keys 的审计信息字典。
    """
    if rule is not None:
        name = rule.name
        rule_type = rule.rule_type
        enabled = rule.enabled
        priority = rule.priority
        config = rule.config

    payload = {
        "name": (name or "").strip(),
        "rule_type": (rule_type or "").strip(),
        "enabled": bool(enabled),
        "priority": int(priority),
    }
    if isinstance(config, dict) and config:
        payload["config_keys"] = sorted(str(key) for key in config.keys())[:_MAX_AUDIT_KEY_COUNT]
    return payload


def build_document_cleaning_audit_payload(*, document, result):
    """
    构建文档清洗操作的审计 payload。

    类比 SpringBoot: 相当于清洗质量评估报告对应的审计快照 DTO。

    参数:
        document: 被清洗的文档实例
        result:   清洗结果实例 (DocumentCleaningResult)

    返回:
        dict: 合并了文档基础信息与清洗质量数据的审计字典，
              包括 rules_applied_count、issues_found_count、quality_score、
              quality_gate_status、original_length、cleaned_length 等。
    """
    quality_gate = evaluate_quality_gate(result.quality_score)
    payload = build_document_audit_payload(document=document)
    payload.update(
        {
            "rules_applied_count": len(result.rules_applied or []),
            "issues_found_count": len(result.issues_found or []),
            "quality_score": result.quality_score,
            "quality_gate_status": quality_gate["status"],
            "quality_gate_min_score": quality_gate["min_quality_score"],
            "quality_gate_warn_score": quality_gate["warn_quality_score"],
            "quality_gate_should_block": quality_gate["should_block"],
            "original_length": result.original_length,
            "cleaned_length": result.cleaned_length,
            "dedup_count": result.dedup_count,
        }
    )
    return payload


def build_document_batch_audit_payload(*, document_ids, result):
    """
    构建批量摄取操作的审计 payload。

    类比 SpringBoot: 相当于批量作业执行结果的审计快照 DTO。

    参数:
        document_ids: 参与批量操作的文档 ID 列表
        result:       批量操作的结果字典，包含 accepted_count/skipped_count/failed_count

    返回:
        dict: 包含文档 ID 汇总和批量操作计数统计的审计字典。
    """
    payload = summarize_document_ids(document_ids)
    payload.update(
        {
            "accepted_count": int(result.get("accepted_count", 0)),
            "skipped_count": int(result.get("skipped_count", 0)),
            "failed_count": int(result.get("failed_count", 0)),
        }
    )
    return payload


def build_document_batch_delete_audit_payload(*, document_ids, result):
    """
    构建批量删除操作的审计 payload。

    类比 SpringBoot: 相当于批量删除作业执行结果的审计快照 DTO。

    参数:
        document_ids: 参与批量操作的文档 ID 列表
        result:       批量删除的结果字典，包含 deleted_count/failed_count

    返回:
        dict: 包含文档 ID 汇总和删除计数统计的审计字典。
    """
    payload = summarize_document_ids(document_ids)
    payload.update(
        {
            "deleted_count": int(result.get("deleted_count", 0)),
            "failed_count": int(result.get("failed_count", 0)),
        }
    )
    return payload


def summarize_document_ids(document_ids):
    """
    汇总文档 ID 列表，生成标准化的审计摘要。

    类比 SpringBoot: 相当于批量操作日志中的 ID 摘要生成器。
    过滤掉非法的 ID 值，截断至 _MAX_AUDIT_DOCUMENT_IDS 上限。

    参数:
        document_ids: 原始文档 ID 列表，可能包含非法值 (bool/非数字)

    返回:
        dict: 包含 document_count（总数量）、document_ids（截断后的 ID 列表）、
              document_id_overflow（超出上限的数量，仅当有溢出时存在）的字典。
    """
    normalized_ids = []
    for document_id in document_ids or []:
        if isinstance(document_id, bool):
            continue
        try:
            normalized_ids.append(int(document_id))
        except (TypeError, ValueError):
            continue

    payload = {
        "document_count": len(normalized_ids),
        "document_ids": normalized_ids[:_MAX_AUDIT_DOCUMENT_IDS],
    }
    overflow = len(normalized_ids) - len(payload["document_ids"])
    if overflow > 0:
        payload["document_id_overflow"] = overflow
    return payload


def _get_document_version_record(document):
    """
    获取文档的版本记录（内部辅助函数）。

    类比 SpringBoot: 相当于 @Entity 的关联导航方法，通过 OneToOneField
    的 related_name 获取关联的 DocumentVersion 记录。

    参数:
        document: Document 实例

    返回:
        DocumentVersion 实例，如果不存在则返回 None。
    """
    try:
        return document.version_record
    except DocumentVersion.DoesNotExist:
        return None
