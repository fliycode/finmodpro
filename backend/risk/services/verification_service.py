import json
import logging
from datetime import datetime
from decimal import Decimal

from django.conf import settings

from common.exceptions import UpstreamServiceError
from common.observability import trace_span
from llm.services.prompt_service import render_prompt
from llm.services.runtime_service import get_chat_provider
from risk.schemas import get_extraction_response_format, get_verification_response_format
from risk.serializers import parse_risk_extraction_payload
from risk.services.adjudication_service import build_event_enrichment

logger = logging.getLogger(__name__)


class _SafeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

SYSTEM_MESSAGE = "你是金融风险抽取助手。严格输出 JSON，不要输出 markdown 或额外解释。"
VERIFY_SYSTEM_MESSAGE = "你是金融风险抽取的质量审核专家。严格输出 JSON，不要输出 markdown 或额外解释。"


def _call_extraction_llm(*, document, chunk_context, additional_guidance=None):
    provider = get_chat_provider()
    prompt = render_prompt(
        "risk/extract.txt",
        document_title=document.title,
        document_type=document.doc_type,
        chunk_context=chunk_context,
    )
    if additional_guidance:
        prompt += f"\n\n补充指导（来自上一轮验证）：\n{additional_guidance}"

    raw_content = provider.chat(
        messages=[
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": prompt},
        ],
        options={
            "temperature": 0,
            "response_format": get_extraction_response_format(),
            "timeout_seconds": getattr(settings, "RISK_EXTRACTION_LLM_TIMEOUT_SECONDS", 25),
            "transport_retry_attempts": 1,
        },
    ).content

    events = _parse_extraction_output(raw_content)
    return events, raw_content


def _call_verification_llm(*, document, chunk_context, extracted_events):
    provider = get_chat_provider()
    prompt = render_prompt(
        "risk/verify.txt",
        document_title=document.title,
        document_type=document.doc_type,
        chunk_context=chunk_context,
        extracted_events_json=json.dumps({"events": extracted_events}, ensure_ascii=False, indent=2, cls=_SafeEncoder),
    )

    raw_content = provider.chat(
        messages=[
            {"role": "system", "content": VERIFY_SYSTEM_MESSAGE},
            {"role": "user", "content": prompt},
        ],
        options={
            "temperature": 0,
            "response_format": get_verification_response_format(),
            "timeout_seconds": getattr(settings, "RISK_EXTRACTION_LLM_TIMEOUT_SECONDS", 25),
            "transport_retry_attempts": 1,
        },
    ).content

    return _parse_verification_output(raw_content), raw_content


def _parse_extraction_output(raw_content):
    try:
        return parse_risk_extraction_payload(raw_content)
    except Exception as exc:
        raise UpstreamServiceError(
            "风险抽取结果格式非法。",
            status_code=502,
            code="risk_extraction_invalid_output",
        ) from exc


def _parse_verification_output(raw_content):
    normalized = str(raw_content or "").strip()
    if normalized.startswith("```"):
        lines = normalized.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        normalized = "\n".join(lines).strip()

    try:
        payload = json.loads(normalized)
    except json.JSONDecodeError:
        logger.warning("验证 LLM 输出非法 JSON，视为验证通过")
        return {"is_complete": True, "missing_aspects": [], "suggestions": [], "issues_found": []}

    raw_missing = payload.get("missing_aspects", [])
    structured_missing = []
    for item in raw_missing:
        if isinstance(item, dict):
            structured_missing.append({
                "field": str(item.get("field", "unknown")),
                "chunk_id": item.get("chunk_id"),
                "hint": str(item.get("hint", "")),
            })
        elif isinstance(item, str):
            structured_missing.append({
                "field": "unknown",
                "chunk_id": None,
                "hint": item,
            })

    return {
        "is_complete": bool(payload.get("is_complete", True)),
        "missing_aspects": structured_missing,
        "suggestions": list(payload.get("suggestions", [])),
        "issues_found": list(payload.get("issues_found", [])),
    }


def _text_similarity(text_a, text_b):
    if not text_a or not text_b:
        return 0.0

    def bigrams(text):
        text = str(text).strip()
        return set(text[i:i + 2] for i in range(len(text) - 1)) if len(text) >= 2 else {text}

    bg_a = bigrams(text_a)
    bg_b = bigrams(text_b)
    if not bg_a or not bg_b:
        return 0.0
    intersection = len(bg_a & bg_b)
    union = len(bg_a | bg_b)
    return intersection / union if union > 0 else 0.0


def _merge_similar_events(deduplicated_events):
    threshold = getattr(settings, "RISK_EXTRACTION_MERGE_SIMILARITY_THRESHOLD", 0.35)

    groups = {}
    for event in deduplicated_events:
        key = (
            event.get("company_name", "").strip(),
            event.get("risk_type", "").strip().lower(),
        )
        groups.setdefault(key, []).append(event)

    merged = []
    for group_events in groups.values():
        if len(group_events) <= 1:
            merged.extend(group_events)
            continue

        used = set()
        for i, event_a in enumerate(group_events):
            if i in used:
                continue
            best_match = event_a
            for j in range(i + 1, len(group_events)):
                if j in used:
                    continue
                event_b = group_events[j]

                time_a = str(event_a.get("event_time", ""))
                time_b = str(event_b.get("event_time", ""))
                if time_a and time_b and time_a[:7] != time_b[:7]:
                    continue

                should_merge = False

                if time_a and time_b and time_a == time_b:
                    should_merge = True
                else:
                    sim = _text_similarity(
                        event_a.get("summary", "") + event_a.get("evidence_text", ""),
                        event_b.get("summary", "") + event_b.get("evidence_text", ""),
                    )
                    if sim >= threshold:
                        should_merge = True

                if should_merge:
                    used.add(j)
                    # Combine evidence before potential swap
                    evidence_b = event_b.get("evidence_text", "")
                    evidence_best = best_match.get("evidence_text", "")
                    if evidence_b and evidence_b not in evidence_best:
                        combined_evidence = (evidence_best + " " + evidence_b).strip()
                    else:
                        combined_evidence = evidence_best

                    if event_b.get("confidence_score", 0) > best_match.get("confidence_score", 0):
                        best_match = event_b
                    best_match["evidence_text"] = combined_evidence

            merged.append(best_match)

    return merged


def _deduplicate_events(events_list):
    seen = set()
    exact_deduplicated = []
    for event in events_list:
        key = (
            event.get("company_name"),
            event.get("risk_type"),
            str(event.get("event_time", "")),
            event.get("chunk_id"),
        )
        if key not in seen:
            seen.add(key)
            exact_deduplicated.append(event)

    return _merge_similar_events(exact_deduplicated)


def _adjudicate_events(events):
    return [
        {
            **event,
            **build_event_enrichment(event_data=event),
        }
        for event in events
    ]


def run_extraction_with_verification(*, document, chunks, max_rounds=None, on_stage_update=None):
    if max_rounds is None:
        max_rounds = getattr(settings, "RISK_EXTRACTION_MAX_ROUNDS", 2)

    from risk.services.extraction_service import _build_chunk_context

    chunk_context = _build_chunk_context(chunks)
    all_events = []
    total_llm_calls = 0
    verification_passed = False
    round_details = []

    with trace_span(
        "risk.verification_loop",
        metadata={"max_rounds": max_rounds, "chunk_count": len(chunks)},
    ) as observation:
        for round_num in range(1, max_rounds + 1):
            if callable(on_stage_update):
                on_stage_update(
                    step="extracting_signals",
                    progress=min(78, 62 + (round_num - 1) * 8),
                    message=f"正在执行第 {round_num} 轮证据抽取。",
                )
            additional_guidance = None
            if round_num > 1 and not verification_passed:
                missing = last_verification.get("missing_aspects", [])
                suggestions = last_verification.get("suggestions", [])
                issues = last_verification.get("issues_found", [])
                parts = []
                if missing:
                    missing_descriptions = []
                    for item in missing:
                        if isinstance(item, dict):
                            hint = item.get("hint", "")
                            field = item.get("field", "")
                            chunk_ref = f" (chunk_id={item['chunk_id']})" if item.get("chunk_id") else ""
                            missing_descriptions.append(f"[{field}]{chunk_ref}: {hint}")
                        else:
                            missing_descriptions.append(str(item))
                    parts.append("遗漏方面：\n" + "\n".join(f"- {m}" for m in missing_descriptions))
                if issues:
                    parts.append("发现问题：" + "；".join(issues))
                if suggestions:
                    parts.append("建议：" + "；".join(suggestions))
                additional_guidance = "\n".join(parts) if parts else None

            events, raw_extract = _call_extraction_llm(
                document=document,
                chunk_context=chunk_context,
                additional_guidance=additional_guidance,
            )
            total_llm_calls += 1
            if callable(on_stage_update):
                on_stage_update(
                    step="adjudicating",
                    progress=min(84, 70 + (round_num - 1) * 6),
                    message=f"正在执行第 {round_num} 轮风险判读。",
                )
            adjudicated_events = _adjudicate_events(events)
            all_events.extend(adjudicated_events)

            round_info = {
                "round": round_num,
                "events_count": len(events),
                "human_review_count": sum(1 for item in adjudicated_events if item.get("requires_human_review")),
            }
            round_details.append(round_info)

            if round_num >= max_rounds:
                break

            try:
                if callable(on_stage_update):
                    on_stage_update(
                        step="verifying",
                        progress=min(86, 74 + (round_num - 1) * 6),
                        message=f"正在校验第 {round_num} 轮判读结果。",
                    )
                verification, raw_verify = _call_verification_llm(
                    document=document,
                    chunk_context=chunk_context,
                    extracted_events=all_events,
                )
                total_llm_calls += 1
            except Exception:
                logger.warning("验证 LLM 调用失败，视为验证通过", exc_info=True)
                verification = {"is_complete": True, "missing_aspects": [], "suggestions": []}
                raw_verify = ""

            verification_passed = verification["is_complete"]
            last_verification = verification
            round_info["verification"] = {
                "is_complete": verification["is_complete"],
                "missing_aspects": verification["missing_aspects"],
            }

            if verification_passed:
                break

        if max_rounds == 1:
            verification_passed = True

        all_events = _deduplicate_events(all_events)
        if callable(on_stage_update):
            on_stage_update(
                step="routing_review",
                progress=88,
                message="正在整理需人工复核的风险事件。",
            )

        pipeline_metadata = {
            "rounds_completed": round_num,
            "verification_passed": verification_passed,
            "total_llm_calls": total_llm_calls,
            "round_details": round_details,
            "human_review_count": sum(1 for item in all_events if item.get("requires_human_review")),
            "schema_version": "v2-foundation",
        }

        observation.update(output={
            "rounds_completed": round_num,
            "verification_passed": verification_passed,
            "total_llm_calls": total_llm_calls,
            "total_events": len(all_events),
        })

    return all_events, pipeline_metadata
