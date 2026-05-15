RISK_EXTRACTION_JSON_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "risk_extraction_result",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "events": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "company_name": {
                                "type": "string",
                                "description": "涉及风险事件的公司全称，必须来自原文",
                            },
                            "risk_type": {
                                "type": "string",
                                "enum": [
                                    "liquidity",
                                    "credit",
                                    "market",
                                    "compliance",
                                    "operation",
                                    "litigation",
                                    "governance",
                                    "other",
                                ],
                                "description": "风险分类英文短词",
                            },
                            "risk_level": {
                                "type": "string",
                                "enum": ["low", "medium", "high", "critical"],
                                "description": "风险严重程度",
                            },
                            "event_time": {
                                "type": ["string", "null"],
                                "description": "ISO 8601 时间字符串；若无法判断则为 null",
                            },
                            "summary": {
                                "type": "string",
                                "description": "对风险事件的一句话中文摘要",
                            },
                            "evidence_text": {
                                "type": "string",
                                "description": "从原文直接引用的证据文本",
                            },
                            "confidence_score": {
                                "type": "number",
                                "minimum": 0.0,
                                "maximum": 1.0,
                                "description": "抽取置信度，0.000 到 1.000",
                            },
                            "chunk_id": {
                                "type": ["integer", "null"],
                                "description": "来源切块 ID，来自输入中的 [chunk_id=...] 标记",
                            },
                            "why_it_matters": {
                                "type": "string",
                                "description": "该风险事件的实质影响分析，说明为什么值得关注",
                            },
                            "impact_scope": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "影响维度列表，如 cash_flow, funding, counterparty 等",
                            },
                            "watchpoints": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "后续需要监控的关键指标或进展，2-4 条",
                            },
                            "citations": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "chunk_id": {"type": "integer"},
                                        "quote": {"type": "string"},
                                    },
                                    "required": ["chunk_id", "quote"],
                                },
                                "description": "证据引用列表",
                            },
                        },
                        "required": [
                            "company_name",
                            "risk_type",
                            "risk_level",
                            "summary",
                            "evidence_text",
                            "confidence_score",
                        ],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["events"],
            "additionalProperties": False,
        },
    },
}


RISK_VERIFICATION_JSON_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "risk_verification_result",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "is_complete": {
                    "type": "boolean",
                    "description": "所有切块中的风险事件是否已被完整抽取",
                },
                "missing_aspects": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "field": {
                                "type": "string",
                                "description": "缺失维度：coverage/evidence/chunk_id/classification/duplicate/enrichment",
                            },
                            "chunk_id": {
                                "type": ["integer", "null"],
                                "description": "关联的切块 ID",
                            },
                            "hint": {
                                "type": "string",
                                "description": "对缺失内容的具体描述",
                            },
                        },
                        "required": ["field", "hint"],
                    },
                    "description": "遗漏的风险事件或字段维度",
                },
                "suggestions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "改进建议",
                },
                "issues_found": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "发现的具体问题",
                },
            },
            "required": ["is_complete", "missing_aspects", "suggestions", "issues_found"],
            "additionalProperties": False,
        },
    },
}


def get_extraction_response_format():
    return RISK_EXTRACTION_JSON_SCHEMA


def get_verification_response_format():
    return RISK_VERIFICATION_JSON_SCHEMA
