"""
风险提取的 JSON Schema 定义。
类比 SpringBoot: 相当于 API 请求/响应的 JSON Schema 或 OpenAPI 规范定义，
用于指导 LLM 输出规范化的结构化 JSON 数据。
"""

# 风险提取阶段的 JSON 输出格式约束（告知 LLM 输出应为 JSON 对象）
RISK_EXTRACTION_JSON_SCHEMA = {
    "type": "json_object",
}

# 风险验证阶段的 JSON 输出格式约束
RISK_VERIFICATION_JSON_SCHEMA = {
    "type": "json_object",
}


def get_extraction_response_format():
    """
    获取风险提取阶段的 LLM 响应格式约束。

    返回:
        dict: {"type": "json_object"}，指示 LLM 输出 JSON 对象。
    """
    return RISK_EXTRACTION_JSON_SCHEMA


def get_verification_response_format():
    """
    获取风险验证阶段的 LLM 响应格式约束。

    返回:
        dict: {"type": "json_object"}，指示 LLM 输出 JSON 对象。
    """
    return RISK_VERIFICATION_JSON_SCHEMA
