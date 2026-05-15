from decimal import Decimal


LEVEL_BASE_MATERIALITY = {
    "critical": 0.92,
    "high": 0.78,
    "medium": 0.56,
    "low": 0.34,
}

IMPACT_SCOPE_MAP = {
    "liquidity": ["cash_flow", "funding"],
    "credit": ["counterparty", "repayment"],
    "market": ["valuation", "earnings"],
    "compliance": ["regulatory", "reputation"],
    "operation": ["operations", "execution"],
    "litigation": ["legal", "reputation"],
    "governance": ["governance", "controls"],
}

WATCHPOINT_MAP = {
    "liquidity": ["未来三个月现金流覆盖率", "短期债务续作进展"],
    "credit": ["主要债务人履约变化", "应收账款回款周期"],
    "market": ["核心资产价格波动", "利润率与估值敏感项"],
    "compliance": ["监管问询或处罚进展", "内部整改闭环状态"],
    "operation": ["关键业务连续性", "供应链与交付异常"],
    "litigation": ["案件进展与潜在赔付", "诉讼披露是否升级"],
    "governance": ["管理层稳定性", "内控缺陷整改结果"],
}

WHY_IT_MATTERS_MAP = {
    "liquidity": "该信号指向资金周转与短期偿付压力，需要重点跟踪现金流与续作能力。",
    "credit": "该信号指向交易对手或债务履约能力恶化，可能进一步放大回款与减值压力。",
    "market": "该信号会直接影响估值、收益预期或市场波动暴露，需要持续关注敏感因子变化。",
    "compliance": "该信号涉及监管或合规压力，若升级可能同步影响经营稳定性与声誉。",
    "operation": "该信号说明经营执行链路出现脆弱点，可能传导为收入、交付或成本风险。",
    "litigation": "该信号涉及诉讼或法律争议，潜在影响包括赔付、披露升级与声誉受损。",
    "governance": "该信号说明治理或控制层面存在隐患，后续可能放大经营与披露风险。",
}


def _normalize_risk_type(raw_risk_type):
    normalized = str(raw_risk_type or "").strip().lower()
    return normalized or "other"


def _normalize_risk_level(raw_risk_level):
    normalized = str(raw_risk_level or "").strip().lower()
    return normalized or "medium"


def _to_float(value, default=0.0):
    if value in (None, ""):
        return default
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_event_enrichment(*, event_data, chunk=None):
    risk_type = _normalize_risk_type(event_data.get("risk_type"))
    risk_level = _normalize_risk_level(event_data.get("risk_level"))
    confidence_score = max(0.0, min(1.0, _to_float(event_data.get("confidence_score"), default=0.0)))

    base_materiality = LEVEL_BASE_MATERIALITY.get(risk_level, 0.5)
    materiality_score = round(max(0.0, min(1.0, (base_materiality * 0.7) + (confidence_score * 0.3))), 3)
    likelihood_score = round(max(0.0, min(1.0, (confidence_score * 0.65) + (base_materiality * 0.35))), 3)

    impact_scope = event_data.get("impact_scope")
    if not isinstance(impact_scope, list) or not impact_scope:
        impact_scope = IMPACT_SCOPE_MAP.get(risk_type, ["business"])

    watchpoints = event_data.get("watchpoints")
    if not isinstance(watchpoints, list) or not watchpoints:
        watchpoints = WATCHPOINT_MAP.get(risk_type, ["后续公告与原始披露是否升级", "相关经营与财务指标是否恶化"])

    citations = []
    existing_citations = event_data.get("citations")
    if isinstance(existing_citations, list) and existing_citations:
        citations = existing_citations
    elif chunk is not None:
        citations.append(
            {
                "chunk_id": chunk.id,
                "page_label": chunk.metadata.get("page_label", ""),
                "section_label": chunk.metadata.get("section_label") or chunk.metadata.get("section_page_label", ""),
                "quote": event_data.get("evidence_text") or event_data.get("summary") or chunk.content,
            }
        )
    elif event_data.get("chunk_id") is not None:
        citations.append(
            {
                "chunk_id": event_data.get("chunk_id"),
                "page_label": "",
                "section_label": "",
                "quote": event_data.get("evidence_text") or event_data.get("summary") or "",
            }
        )

    requires_human_review = (
        bool(event_data.get("requires_human_review"))
        or risk_level in {"high", "critical"}
        or confidence_score < 0.65
        or not citations
    )
    existing_priority = event_data.get("review_priority")
    if existing_priority in (None, ""):
        review_priority = round(
            min(
                100,
                max(
                    10,
                    int(materiality_score * 60 + likelihood_score * 20 + (20 if requires_human_review else 0)),
                ),
            )
        )
    else:
        review_priority = int(existing_priority)

    return {
        "taxonomy_code": event_data.get("taxonomy_code") or risk_type,
        "citations": citations,
        "materiality_score": event_data.get("materiality_score", materiality_score),
        "likelihood_score": event_data.get("likelihood_score", likelihood_score),
        "impact_scope": impact_scope,
        "why_it_matters": event_data.get("why_it_matters") or WHY_IT_MATTERS_MAP.get(
            risk_type,
            "该信号需要结合后续披露与经营指标判断是否会进一步放大为实质性风险。",
        ),
        "watchpoints": watchpoints,
        "requires_human_review": requires_human_review,
        "review_priority": review_priority,
        "extraction_version": event_data.get("extraction_version") or "v2-foundation",
    }
