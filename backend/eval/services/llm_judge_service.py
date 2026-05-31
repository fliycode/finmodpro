
"""
LLM-as-judge service for automated evaluation scoring.

Uses the active chat provider to score RAG answers and refusal quality.
Scoring is done with temperature=0 for consistency.
"""

import json
import re
from llm.services.runtime_service import get_chat_provider
from llm.services.prompt_service import render_prompt

JUDGE_SYSTEM_PROMPT = "你是金融问答质量评估专家。严格输出 JSON，不要额外文本。"


def _extract_json(raw_content):
    """从 LLM 输出中提取 JSON 对象。"""
    raw_content = raw_content.strip()
    try:
        return json.loads(raw_content)
    except json.JSONDecodeError:
        pass
    # 尝试从 markdown 代码块中提取
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # 尝试找到第一个 JSON 对象
    match = re.search(r'\{.*\}', raw_content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None


def judge_rag_answer(*, question, citations_context, answer, expected_answer_type,
                     expected_keywords, expected_sources):
    """
    使用 LLM 评估 RAG 答案质量。

    返回:
        dict: {accuracy, citation_recall, citation_consistency, refusal, overall, rationale}
        如果 LLM 评分失败则返回 None。
    """
    provider = get_chat_provider()
    prompt = render_prompt(
        "eval/judge_rag_answer.txt",
        question=question,
        citations_context=citations_context or "(无可用的参考资料)",
        answer=answer,
        expected_answer_type=expected_answer_type,
        expected_keywords=", ".join(expected_keywords) if expected_keywords else "(无特定关键词要求)",
    )

    try:
        result = provider.chat(
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            options={"temperature": 0},
        )
        scores = _extract_json(result.content)
        if scores:
            return {
                "accuracy": scores.get("accuracy", 0),
                "citation_recall": scores.get("citation_recall", 0),
                "citation_consistency": scores.get("citation_consistency", 0),
                "refusal": scores.get("refusal", 0),
                "overall": scores.get("overall", 0),
                "rationale": scores.get("rationale", ""),
            }
        return None
    except Exception:
        return None


def judge_refusal_quality(*, question, answer, expected_behavior):
    """
    使用 LLM 评估拒答质量。

    返回:
        dict: {boundary_awareness, refusal_appropriateness, transparency, overall, rationale}
        如果 LLM 评分失败则返回 None。
    """
    provider = get_chat_provider()

    try:
        result = provider.chat(
            messages=[
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": render_prompt(
                    "eval/judge_refusal.txt",
                    question=question,
                    answer=answer,
                    expected_behavior=expected_behavior,
                )},
            ],
            options={"temperature": 0},
        )
        scores = _extract_json(result.content)
        if scores:
            return {
                "boundary_awareness": scores.get("boundary_awareness", 0),
                "refusal_appropriateness": scores.get("refusal_appropriateness", 0),
                "transparency": scores.get("transparency", 0),
                "overall": scores.get("overall", 0),
                "rationale": scores.get("rationale", ""),
            }
        return None
    except Exception:
        return None
