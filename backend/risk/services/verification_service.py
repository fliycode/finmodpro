import json
import logging
from datetime import datetime
from decimal import Decimal

from django.conf import settings

from common.exceptions import UpstreamServiceError
from common.observability import trace_span
from llm.services.prompt_service import render_prompt
from llm.services.runtime_service import get_chat_provider
from risk.serializers import parse_risk_extraction_payload

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

    return {
        "is_complete": bool(payload.get("is_complete", True)),
        "missing_aspects": list(payload.get("missing_aspects", [])),
        "suggestions": list(payload.get("suggestions", [])),
        "issues_found": list(payload.get("issues_found", [])),
    }


def _deduplicate_events(events_list):
    seen = set()
    deduplicated = []
    for event in events_list:
        key = (
            event.get("company_name"),
            event.get("risk_type"),
            str(event.get("event_time", "")),
            event.get("chunk_id"),
        )
        if key not in seen:
            seen.add(key)
            deduplicated.append(event)
    return deduplicated


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
                    step="extracting",
                    progress=min(78, 62 + (round_num - 1) * 8),
                    message=f"正在执行第 {round_num} 轮风险抽取。",
                )
            additional_guidance = None
            if round_num > 1 and not verification_passed:
                missing = last_verification.get("missing_aspects", [])
                suggestions = last_verification.get("suggestions", [])
                parts = []
                if missing:
                    parts.append("遗漏方面：" + "；".join(missing))
                if suggestions:
                    parts.append("建议：" + "；".join(suggestions))
                additional_guidance = "\n".join(parts) if parts else None

            events, raw_extract = _call_extraction_llm(
                document=document,
                chunk_context=chunk_context,
                additional_guidance=additional_guidance,
            )
            total_llm_calls += 1
            all_events.extend(events)

            round_info = {"round": round_num, "events_count": len(events)}
            round_details.append(round_info)

            if round_num >= max_rounds:
                break

            try:
                if callable(on_stage_update):
                    on_stage_update(
                        step="verifying",
                        progress=min(86, 74 + (round_num - 1) * 6),
                        message=f"正在校验第 {round_num} 轮抽取结果。",
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

        pipeline_metadata = {
            "rounds_completed": round_num,
            "verification_passed": verification_passed,
            "total_llm_calls": total_llm_calls,
            "round_details": round_details,
        }

        observation.update(output={
            "rounds_completed": round_num,
            "verification_passed": verification_passed,
            "total_llm_calls": total_llm_calls,
            "total_events": len(all_events),
        })

    return all_events, pipeline_metadata
