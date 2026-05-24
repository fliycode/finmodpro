"""
舆情分析服务 —— 对文档进行情绪分析和风险倾向评估。
类比 SpringBoot: 相当于 @Service 中的 NLP 分析层，
调用 LLM 对文档内容进行情绪（positive/neutral/negative）和
风险倾向（low/moderate/elevated/high）双维度分析。

LLM 不可用时自动降级为基于关键词的启发式分析。
"""

import json
import re
from collections import Counter

from common.observability import trace_span
from knowledgebase.models import Document, DocumentChunk
from knowledgebase.services.document_service import get_visible_documents_queryset
from llm.services.runtime_service import get_chat_provider


# 情绪排序（用于分布统计的一致性）
SENTIMENT_ORDER = ("positive", "neutral", "negative")
# 风险倾向排序
RISK_TENDENCY_ORDER = ("low", "moderate", "elevated", "high")

# 正面关键词
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
# 负面关键词
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
    """
    解析 dataset_id 参数。

    参数:
        raw_value: 原始输入值。

    返回:
        int | None: 解析后的 ID，无效时返回 None。"all" 返回 None（表示全部）。

    抛出:
        ValueError: 当值不是合法整数时。
    """
    if raw_value in (None, "", "all"):
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("dataset_id 必须是整数。") from exc


def _normalize_document_ids(raw_ids):
    """
    解析并校验 document_ids 参数。

    参数:
        raw_ids: 原始输入（None, 空列表, 整数列表）。

    返回:
        list[int]: 规范化的文档 ID 列表。

    抛出:
        ValueError: 当值不是合法整数数组时。
    """
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
    """
    获取文档的完整文本内容。

    优先使用 parsed_text，为空时拼接所有 chunk 的 content。

    参数:
        document (Document): 文档实例。

    返回:
        str: 文档的完整文本。
    """
    parsed_text = (document.parsed_text or "").strip()
    if parsed_text:
        return parsed_text

    chunks = DocumentChunk.objects.filter(document=document).order_by("chunk_index", "id")
    joined_text = "\n".join(chunk.content for chunk in chunks if chunk.content)
    return joined_text.strip()


def _trim_text(text, limit=3500):
    """
    截断文本到指定字符数限制。

    参数:
        text (str): 原始文本。
        limit (int): 字符数上限。

    返回:
        str: 截断后的文本。
    """
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    return cleaned[:limit]


def _build_prompt(document, text_excerpt):
    """
    构建舆情分析的 LLM 提示词。

    参数:
        document (Document): 文档实例。
        text_excerpt (str): 截断后的文本节选。

    返回:
        str: 完整的提示词字符串。
    """
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
    """
    解析 LLM 返回的 JSON 内容。

    参数:
        raw_content (str): LLM 返回的原始字符串。

    返回:
        dict: 解析后的 JSON 对象。

    抛出:
        ValueError: 当内容不是合法 JSON 或不是对象时。
    """
    try:
        payload = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise ValueError("舆情分析结果不是合法 JSON。") from exc

    if not isinstance(payload, dict):
        raise ValueError("舆情分析结果必须是 JSON 对象。")

    return payload


def _normalize_sentiment(value):
    """规范化情绪值到 positive/neutral/negative，无效值默认为 neutral。"""
    normalized = str(value or "neutral").strip().lower()
    return normalized if normalized in SENTIMENT_ORDER else "neutral"


def _normalize_risk_tendency(value):
    """规范化风险倾向值，无效值默认为 moderate。"""
    normalized = str(value or "moderate").strip().lower()
    return normalized if normalized in RISK_TENDENCY_ORDER else "moderate"


def _normalize_evidence(raw_evidence):
    """规范化证据列表为字符串列表。"""
    if not isinstance(raw_evidence, (list, tuple)):
        return []
    return [str(item) for item in raw_evidence if str(item).strip()]


def _heuristic_sentiment(text):
    """
    基于关键词的启发式情绪分析（LLM 不可用时的降级方案）。

    参数:
        text (str): 待分析文本。

    返回:
        dict: 包含 sentiment, risk_tendency, summary, confidence_score, evidence 的分析结果。
    """
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
    """
    分析单个文档的情绪和风险倾向。

    优先调用 LLM，LLM 失败时降级为启发式关键词匹配。

    参数:
        document (Document): 文档实例。

    返回:
        dict: 包含 document_id, sentiment, risk_tendency, confidence_score, summary, evidence 等字段。
    """
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
    heuristic_fallback = False
    with trace_span(
        "risk.sentiment",
        metadata={"document_id": document.id, "dataset_id": document.dataset_id},
        input_data={"document_title": document.title},
    ) as observation:
        try:
            raw_content = get_chat_provider().chat(
                messages=[
                    {"role": "system", "content": "你是金融舆情分析助手。严格输出 JSON，不要输出 markdown 或额外说明。"},
                    {"role": "user", "content": prompt},
                ],
                options={"temperature": 0},
            ).content
            payload = _parse_provider_payload(raw_content)
            normalized = {
                "sentiment": _normalize_sentiment(payload.get("sentiment")),
                "risk_tendency": _normalize_risk_tendency(payload.get("risk_tendency")),
                "summary": str(payload.get("summary") or text_excerpt[:120]).strip(),
                "confidence_score": round(float(payload.get("confidence_score", 0.0)), 3),
                "evidence": _normalize_evidence(payload.get("evidence")),
            }
        except Exception:
            heuristic_fallback = True
            normalized = _heuristic_sentiment(text_excerpt)

        observation.update(
            output={
                "sentiment": normalized["sentiment"],
                "risk_tendency": normalized["risk_tendency"],
                "heuristic_fallback": heuristic_fallback,
            }
        )

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
    """构建情绪分布统计。"""
    counts = Counter(item["sentiment"] for item in items)
    return [{"key": key, "value": int(counts.get(key, 0))} for key in SENTIMENT_ORDER]


def _build_source_groups(items):
    """构建各文档的情绪分组列表（用于前端可视化）。"""
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
    """
    根据各文档的情绪分布，解析整体情绪。

    规则: 按 (count, priority) 取最优情绪。priority: negative=2, neutral=1, positive=0。

    参数:
        items (list[dict]): 各文档的分析结果。

    返回:
        str: 整体情绪（positive / neutral / negative）。
    """
    if not items:
        return "neutral"

    counts = Counter(item["sentiment"] for item in items)
    priority = {"negative": 2, "neutral": 1, "positive": 0}
    return max(SENTIMENT_ORDER, key=lambda sentiment: (counts.get(sentiment, 0), priority[sentiment]))


def _resolve_overall_risk_tendency(items):
    """
    根据各文档的风险倾向，解析整体风险倾向。

    规则: 取最高优先级倾向。priority: high=3, elevated=2, moderate=1, low=0。

    参数:
        items (list[dict]): 各文档的分析结果。

    返回:
        str: 整体风险倾向。
    """
    if not items:
        return "moderate"

    priority = {"high": 3, "elevated": 2, "moderate": 1, "low": 0}
    return max(
        (item["risk_tendency"] for item in items),
        key=lambda tendency: priority.get(tendency, 0),
    )


def analyze_sentiment_for_documents(*, user, dataset_id=None, document_ids=None):
    """
    对指定范围的文档进行舆情分析。

    类比 SpringBoot: 相当于 @Service 中的批量分析入口方法。

    参数:
        user: 当前请求用户（用于可见文档查询）。
        dataset_id (int, 可选): 数据集 ID，不传则分析所有可见文档。
        document_ids (list[int], 可选): 具体的文档 ID 列表。

    返回:
        dict: {
            "summary": {overall_sentiment, risk_tendency, document_count, positive/neutral/negative_count},
            "distribution": [{key, value}, ...],  # 情绪分布
            "source_groups": [...],               # 各文档详情
            "items": [...],                       # 逐文档分析结果
        }
    """
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
