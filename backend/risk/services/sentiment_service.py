import json
import re
from collections import Counter

from knowledgebase.models import Document, DocumentChunk
from knowledgebase.services.document_service import get_visible_documents_queryset
from llm.services.runtime_service import get_chat_provider


SENTIMENT_ORDER = ("positive", "neutral", "negative")
RISK_TENDENCY_ORDER = ("low", "moderate", "elevated", "high")

POSITIVE_KEYWORDS = (
    "改善",
    "增长",
    "提升",
    "回升",
    "稳定",
    "向好",
    "乐观",
    "受益",
    "增长明显",
)
NEGATIVE_KEYWORDS = (
    "下滑",
    "承压",
    "风险",
    "投诉",
    "延迟",
    "下降",
    "亏损",
    "放缓",
    "恶化",
    "波动",
)


def _parse_scope_id(raw_value):
    if raw_value in (None, "", "all"):
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("dataset_id 必须是整数。") from exc


def _normalize_document_ids(raw_ids):
    if raw_ids in (None, "", []):
        return []
    if not isinstance(raw_ids, (list, tuple)):
        raise ValueError("document_ids 必须是整数数组。")

    document_ids = []
    for raw_value in raw_ids:
        if isinstance(raw_value, bool) or not isinstance(raw_value, int):
            raise ValueError("document_ids 必须是整数数组。")
        document_ids.append(raw_value)
    return document_ids


def _get_document_text(document):
    parsed_text = (document.parsed_text or "").strip()
    if parsed_text:
        return parsed_text

    chunks = DocumentChunk.objects.filter(document=document).order_by("chunk_index", "id")
    joined_text = "\n".join(chunk.content for chunk in chunks if chunk.content)
    return joined_text.strip()


def _trim_text(text, limit=3500):
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    return cleaned[:limit]


def _build_prompt(document, text_excerpt):
    dataset_name = document.dataset.name if getattr(document, "dataset", None) else "未分组"
    return (
        "你是金融舆情分析助手。请根据给定文档判断情绪和风险倾向，只返回 JSON，不要输出 markdown 或解释。"
        "\nJSON 结构如下："
        "\n{"
        '\n  "sentiment": "positive|neutral|negative",'
        '\n  "risk_tendency": "low|moderate|elevated|high",'
        '\n  "summary": "一句话总结",'
        '\n  "confidence_score": 0.000,'
        '\n  "evidence": ["证据1", "证据2"]'
        "\n}"
        "\n请优先基于原文证据判断。"
        f"\n文档标题：{document.title}"
        f"\n数据集：{dataset_name}"
        f"\n正文：{text_excerpt}"
    )


def _parse_provider_payload(raw_content):
    try:
        payload = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise ValueError("舆情分析结果不是合法 JSON。") from exc

    if not isinstance(payload, dict):
        raise ValueError("舆情分析结果必须是 JSON 对象。")

    return payload


def _normalize_sentiment(value):
    normalized = str(value or "neutral").strip().lower()
    return normalized if normalized in SENTIMENT_ORDER else "neutral"


def _normalize_risk_tendency(value):
    normalized = str(value or "moderate").strip().lower()
    return normalized if normalized in RISK_TENDENCY_ORDER else "moderate"


def _normalize_evidence(raw_evidence):
    if not isinstance(raw_evidence, (list, tuple)):
        return []
    return [str(item) for item in raw_evidence if str(item).strip()]


def _heuristic_sentiment(text):
    lowered = text.lower()
    positive_hits = sum(1 for keyword in POSITIVE_KEYWORDS if keyword in lowered or keyword in text)
    negative_hits = sum(1 for keyword in NEGATIVE_KEYWORDS if keyword in lowered or keyword in text)

    if negative_hits > positive_hits:
        sentiment = "negative"
    elif positive_hits > negative_hits:
        sentiment = "positive"
    else:
        sentiment = "neutral"

    if negative_hits >= 3:
        risk_tendency = "high"
    elif negative_hits > positive_hits:
        risk_tendency = "elevated"
    elif positive_hits > negative_hits:
        risk_tendency = "low"
    else:
        risk_tendency = "moderate"

    confidence = min(0.55 + abs(positive_hits - negative_hits) * 0.08, 0.92)
    evidence = []
    for keyword in NEGATIVE_KEYWORDS + POSITIVE_KEYWORDS:
        if keyword in text and keyword not in evidence:
            evidence.append(keyword)
        if len(evidence) >= 3:
            break

    summary_source = _trim_text(text, 120)
    return {
        "sentiment": sentiment,
        "risk_tendency": risk_tendency,
        "summary": summary_source,
        "confidence_score": round(confidence, 3),
        "evidence": evidence,
    }


def _analyze_document(document):
    raw_text = _get_document_text(document)
    text_excerpt = _trim_text(raw_text)

    if not text_excerpt:
        return {
            "document_id": document.id,
            "document_title": document.title,
            "dataset_id": document.dataset_id,
            "dataset_name": document.dataset.name if getattr(document, "dataset", None) else "",
            "sentiment": "neutral",
            "risk_tendency": "moderate",
            "confidence_score": 0.0,
            "summary": "文档暂无可分析内容。",
            "evidence": [],
            "excerpt": "",
        }

    prompt = _build_prompt(document, text_excerpt)
    try:
        raw_content = get_chat_provider().chat(
            messages=[
                {
                    "role": "system",
                    "content": "你是金融舆情分析助手。严格输出 JSON，不要输出 markdown 或额外说明。",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            options={"temperature": 0},
        )
        payload = _parse_provider_payload(raw_content)
        normalized = {
            "sentiment": _normalize_sentiment(payload.get("sentiment")),
            "risk_tendency": _normalize_risk_tendency(payload.get("risk_tendency")),
            "summary": str(payload.get("summary") or text_excerpt[:120]).strip(),
            "confidence_score": round(float(payload.get("confidence_score", 0.0)), 3),
            "evidence": _normalize_evidence(payload.get("evidence")),
        }
    except Exception:
        normalized = _heuristic_sentiment(text_excerpt)

    return {
        "document_id": document.id,
        "document_title": document.title,
        "dataset_id": document.dataset_id,
        "dataset_name": document.dataset.name if getattr(document, "dataset", None) else "",
        "sentiment": normalized["sentiment"],
        "risk_tendency": normalized["risk_tendency"],
        "confidence_score": normalized["confidence_score"],
        "summary": normalized["summary"],
        "evidence": normalized["evidence"],
        "excerpt": text_excerpt[:240],
    }


def _build_distribution(items):
    counts = Counter(item["sentiment"] for item in items)
    return [{"key": key, "value": int(counts.get(key, 0))} for key in SENTIMENT_ORDER]


def _build_source_groups(items):
    groups = []
    for item in items:
        groups.append(
            {
                "key": item["document_title"],
                "value": 1,
                "sentiment": item["sentiment"],
                "risk_tendency": item["risk_tendency"],
                "document_id": item["document_id"],
            }
        )
    return groups


def _resolve_overall_sentiment(items):
    if not items:
        return "neutral"

    counts = Counter(item["sentiment"] for item in items)
    priority = {"negative": 2, "neutral": 1, "positive": 0}
    return max(SENTIMENT_ORDER, key=lambda sentiment: (counts.get(sentiment, 0), priority[sentiment]))


def _resolve_overall_risk_tendency(items):
    if not items:
        return "moderate"

    priority = {"high": 3, "elevated": 2, "moderate": 1, "low": 0}
    return max(
        (item["risk_tendency"] for item in items),
        key=lambda tendency: priority.get(tendency, 0),
    )


def analyze_sentiment_for_documents(*, user, dataset_id=None, document_ids=None):
    parsed_dataset_id = _parse_scope_id(dataset_id)
    parsed_document_ids = _normalize_document_ids(document_ids)

    queryset = get_visible_documents_queryset(user).select_related("dataset")
    if parsed_dataset_id is not None:
        queryset = queryset.filter(dataset_id=parsed_dataset_id)
    if parsed_document_ids:
        queryset = queryset.filter(id__in=parsed_document_ids)

    documents = list(queryset.order_by("id"))
    items = [_analyze_document(document) for document in documents]
    distribution = _build_distribution(items)

    return {
        "summary": {
            "overall_sentiment": _resolve_overall_sentiment(items),
            "risk_tendency": _resolve_overall_risk_tendency(items),
            "document_count": len(items),
            "positive_count": int(sum(1 for item in items if item["sentiment"] == "positive")),
            "neutral_count": int(sum(1 for item in items if item["sentiment"] == "neutral")),
            "negative_count": int(sum(1 for item in items if item["sentiment"] == "negative")),
        },
        "distribution": distribution,
        "source_groups": _build_source_groups(items),
        "items": items,
    }
