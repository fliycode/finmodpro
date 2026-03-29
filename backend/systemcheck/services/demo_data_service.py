from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from chat.models import ChatMessage, ChatSession
from knowledgebase.models import Document, DocumentChunk, IngestionTask
from rag.models import RetrievalLog
from rbac.services.rbac_service import ROLE_ADMIN, ROLE_MEMBER, seed_roles_and_permissions
from risk.models import RiskEvent, RiskReport


User = get_user_model()

DEMO_ADMIN_USERNAME = "demo-admin"
DEMO_ANALYST_USERNAME = "demo-analyst"
DEMO_PASSWORD = "DemoPass123!"
DEMO_DOCUMENT_SPECS = (
    {
        "title": "2025Q1 流动性风险简报",
        "filename": "demo-q1-liquidity.txt",
        "source_date": date(2025, 3, 31),
        "parsed_text": (
            "FinModPro Holdings 2025Q1 经营现金流转正，但短债覆盖倍数下降，"
            "流动性风险上升。客户回款周期拉长，信用风险有所抬头。"
        ),
        "chunks": (
            "FinModPro Holdings 2025Q1 经营现金流转正，但短债覆盖倍数下降，流动性风险上升。",
            "客户回款周期拉长，信用风险有所抬头，管理层已启动授信收紧与资金调度。",
        ),
    },
    {
        "title": "2025Q2 经营与合规纪要",
        "filename": "demo-q2-ops.txt",
        "source_date": date(2025, 6, 30),
        "parsed_text": (
            "公司二季度收入保持增长，但部分区域项目合规审批延后，"
            "存在阶段性合规与运营风险。"
        ),
        "chunks": (
            "公司二季度收入保持增长，但部分区域项目合规审批延后。",
            "项目上线节奏放缓，存在阶段性合规与运营风险。",
        ),
    },
)


def _delete_demo_files():
    for spec in DEMO_DOCUMENT_SPECS:
        storage_path = f"knowledgebase/documents/{spec['filename']}"
        if default_storage.exists(storage_path):
            default_storage.delete(storage_path)


def _create_demo_user(*, username, email, group_name):
    user = User.objects.create_user(
        username=username,
        password=DEMO_PASSWORD,
        email=email,
    )
    user.groups.add(Group.objects.get(name=group_name))
    return user


def _create_demo_documents():
    documents = []

    for spec in DEMO_DOCUMENT_SPECS:
        document = Document(
            title=spec["title"],
            filename=spec["filename"],
            doc_type="txt",
            status=Document.STATUS_INDEXED,
            source_date=spec["source_date"],
            parsed_text=spec["parsed_text"],
        )
        document.file.save(
            spec["filename"],
            ContentFile(spec["parsed_text"].encode("utf-8")),
            save=False,
        )
        document.save()

        chunks = []
        for chunk_index, chunk_content in enumerate(spec["chunks"]):
            chunks.append(
                DocumentChunk.objects.create(
                    document=document,
                    chunk_index=chunk_index,
                    content=chunk_content,
                    vector_id=f"demo-{document.id}-{chunk_index}",
                    metadata={
                        "document_title": document.title,
                        "doc_type": document.doc_type,
                        "source_date": document.source_date.isoformat(),
                        "page_label": f"page-{chunk_index + 1}",
                        "chunk_index": chunk_index,
                        "demo_seed": True,
                    },
                )
            )

        IngestionTask.objects.create(
            document=document,
            celery_task_id=f"demo-task-{document.id}",
            status=IngestionTask.STATUS_SUCCEEDED,
            started_at=timezone.now(),
            finished_at=timezone.now(),
        )

        documents.append((document, chunks))

    return documents


def _create_demo_chat(analyst_user, primary_document):
    session = ChatSession.objects.create(
        user=analyst_user,
        title="流动性风险演示问答",
        context_filters={"document_id": primary_document.id, "doc_type": primary_document.doc_type},
    )
    ChatMessage.objects.create(
        session=session,
        role=ChatMessage.ROLE_USER,
        content="请总结 2025Q1 的主要风险点。",
    )
    ChatMessage.objects.create(
        session=session,
        role=ChatMessage.ROLE_ASSISTANT,
        content=(
            "2025Q1 主要风险点包括流动性风险上升和信用风险抬头。"
            "证据来自短债覆盖倍数下降、客户回款周期拉长等片段。"
        ),
    )
    return session


def _create_demo_retrieval_log(primary_document, primary_chunk):
    return RetrievalLog.objects.create(
        query="2025Q1 主要风险点",
        top_k=3,
        filters={"document_id": primary_document.id},
        result_count=2,
        source=RetrievalLog.SOURCE_CHAT_ASK,
        metadata={
            "demo_seed": True,
            "document_ids": [primary_document.id],
            "chunk_ids": [primary_chunk.id],
        },
        duration_ms=42,
    )


def _create_demo_risk_data(documents):
    first_document, first_chunks = documents[0]
    second_document, second_chunks = documents[1]

    approved_event = RiskEvent.objects.create(
        company_name="FinModPro Holdings",
        risk_type="liquidity",
        risk_level=RiskEvent.LEVEL_HIGH,
        event_time=timezone.now(),
        summary="短债覆盖倍数下降，流动性压力上升。",
        evidence_text=first_chunks[0].content,
        confidence_score=Decimal("0.930"),
        review_status=RiskEvent.STATUS_APPROVED,
        document=first_document,
        chunk=first_chunks[0],
        metadata={"demo_seed": True},
    )
    pending_event = RiskEvent.objects.create(
        company_name="FinModPro Holdings",
        risk_type="compliance",
        risk_level=RiskEvent.LEVEL_MEDIUM,
        event_time=timezone.now(),
        summary="部分区域项目合规审批延后。",
        evidence_text=second_chunks[0].content,
        confidence_score=Decimal("0.760"),
        review_status=RiskEvent.STATUS_PENDING,
        document=second_document,
        chunk=second_chunks[0],
        metadata={"demo_seed": True},
    )

    company_report = RiskReport.objects.create(
        scope_type=RiskReport.SCOPE_COMPANY,
        title="FinModPro Holdings 演示风险报告",
        company_name="FinModPro Holdings",
        summary="演示报告汇总了流动性与合规两类重点风险。",
        content=(
            "1. 流动性风险：短债覆盖倍数下降，需持续关注资金调度。"
            "\n2. 合规风险：区域项目审批节奏放缓，需加强流程跟踪。"
        ),
        source_metadata={
            "demo_seed": True,
            "event_ids": [approved_event.id, pending_event.id],
            "document_ids": [first_document.id, second_document.id],
        },
    )

    return approved_event, pending_event, company_report


@transaction.atomic
def seed_demo_data():
    seed_roles_and_permissions()

    ChatSession.objects.filter(user__username__in=[DEMO_ADMIN_USERNAME, DEMO_ANALYST_USERNAME]).delete()
    RetrievalLog.objects.filter(metadata__demo_seed=True).delete()
    RiskReport.objects.filter(source_metadata__demo_seed=True).delete()
    RiskEvent.objects.filter(metadata__demo_seed=True).delete()
    IngestionTask.objects.filter(document__filename__in=[spec["filename"] for spec in DEMO_DOCUMENT_SPECS]).delete()
    DocumentChunk.objects.filter(document__filename__in=[spec["filename"] for spec in DEMO_DOCUMENT_SPECS]).delete()
    Document.objects.filter(filename__in=[spec["filename"] for spec in DEMO_DOCUMENT_SPECS]).delete()
    User.objects.filter(username__in=[DEMO_ADMIN_USERNAME, DEMO_ANALYST_USERNAME]).delete()
    _delete_demo_files()

    admin_user = _create_demo_user(
        username=DEMO_ADMIN_USERNAME,
        email="demo-admin@example.com",
        group_name=ROLE_ADMIN,
    )
    analyst_user = _create_demo_user(
        username=DEMO_ANALYST_USERNAME,
        email="demo-analyst@example.com",
        group_name=ROLE_MEMBER,
    )

    documents = _create_demo_documents()
    primary_document, primary_chunks = documents[0]
    chat_session = _create_demo_chat(analyst_user, primary_document)
    retrieval_log = _create_demo_retrieval_log(primary_document, primary_chunks[0])
    approved_event, pending_event, company_report = _create_demo_risk_data(documents)

    return {
        "users": [admin_user.username, analyst_user.username],
        "documents": [document.id for document, _ in documents],
        "chat_session_id": chat_session.id,
        "retrieval_log_id": retrieval_log.id,
        "risk_event_ids": [approved_event.id, pending_event.id],
        "risk_report_id": company_report.id,
        "default_password": DEMO_PASSWORD,
    }
