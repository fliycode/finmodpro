"""
数据集服务 —— 对应 SpringBoot 中的 @Service 组件，提供 Dataset 实体的 CRUD 操作。

Dataset（数据集）是文档的逻辑分组容器，类似于 SpringBoot JPA 应用中
对某个 @Entity 的 Repository + Service 封装。

SpringBoot 类比：
- Django Dataset model                →  SpringBoot @Entity Dataset
- Django Dataset.objects.create()     →  SpringBoot datasetRepository.save()
- Django Dataset.objects.get(id=...)  →  SpringBoot datasetRepository.findById()
- Django select_related + annotate    →  SpringBoot @EntityGraph + COUNT 聚合查询
"""

from django.db.models import Count

from knowledgebase.models import Dataset


def serialize_dataset(dataset):
    """
    将 Dataset 实体序列化为字典（类似 SpringBoot DTO 转换）。

    参数：
        dataset (Dataset): 数据集模型实例，可带有预取的 owner 和 document_count 属性。

    返回：
        dict: 包含 id, name, description, owner（嵌套用户信息）, document_count,
              创建/更新时间 的序列化字典。
    """
    owner = getattr(dataset, "owner", None)
    document_count = getattr(dataset, "document_count", None)
    if document_count is None:
        document_count = dataset.documents.count()

    return {
        "id": dataset.id,
        "name": dataset.name,
        "description": dataset.description or "",
        "owner": {
            "id": owner.id,
            "username": owner.username,
            "email": owner.email,
        }
        if owner is not None
        else None,
        "document_count": document_count,
        "created_at": dataset.created_at.isoformat(),
        "updated_at": dataset.updated_at.isoformat(),
    }


def serialize_dataset_summary(dataset):
    """
    将 Dataset 实体序列化为简要摘要（仅 id 和 name），用于嵌套引用。

    参数：
        dataset (Dataset | None): 数据集模型实例，可为 None。

    返回：
        dict | None: {"id": int, "name": str} 或 None。
    """
    if dataset is None:
        return None
    return {
        "id": dataset.id,
        "name": dataset.name,
    }


def list_datasets():
    """
    查询所有数据集列表，预加载 owner 关联并统计文档数。

    类似 SpringBoot 中的 repository.findAll() 配合 @EntityGraph 和 COUNT 聚合。

    返回：
        list[dict]: 序列化后的数据集列表，按 id 升序排列。
    """
    queryset = Dataset.objects.select_related("owner").annotate(
        document_count=Count("documents")
    )
    return [serialize_dataset(dataset) for dataset in queryset.order_by("id")]


def get_dataset(dataset_id):
    """
    按主键ID获取单个数据集（类似 SpringBoot repository.findById()）。

    参数：
        dataset_id (int): 数据集主键ID。

    返回：
        Dataset: 数据集模型实例，已预加载 owner 并注解 document_count。
    """
    return Dataset.objects.select_related("owner").annotate(
        document_count=Count("documents")
    ).get(id=dataset_id)


def create_dataset(*, name, description="", owner=None):
    """
    创建新数据集（类似 SpringBoot @Transactional 下的 repository.save()）。

    参数：
        name (str): 数据集名称（必填，去首尾空白）。
        description (str, optional): 数据集描述。
        owner (User | None): 数据集所有者（用户实体）。

    返回：
        Dataset: 新创建的数据集模型实例。

    异常：
        ValueError: 名称为空或同名数据集已存在。
    """
    normalized_name = (name or "").strip()
    if not normalized_name:
        raise ValueError("name 为必填项。")
    if Dataset.objects.filter(name=normalized_name).exists():
        raise ValueError("同名数据集已存在。")

    return Dataset.objects.create(
        name=normalized_name,
        description=(description or "").strip(),
        owner=owner,
    )
