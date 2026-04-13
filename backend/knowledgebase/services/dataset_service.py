from django.db.models import Count

from knowledgebase.models import Dataset


def serialize_dataset(dataset):
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
    if dataset is None:
        return None
    return {
        "id": dataset.id,
        "name": dataset.name,
    }


def list_datasets():
    queryset = Dataset.objects.select_related("owner").annotate(
        document_count=Count("documents")
    )
    return [serialize_dataset(dataset) for dataset in queryset.order_by("id")]


def get_dataset(dataset_id):
    return Dataset.objects.select_related("owner").annotate(
        document_count=Count("documents")
    ).get(id=dataset_id)


def create_dataset(*, name, description="", owner=None):
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
