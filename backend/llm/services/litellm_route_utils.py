DASHSCOPE_PROVIDER = "dashscope"


def normalize_upstream_model_name(*, provider, model_name):
    normalized_model_name = (model_name or "").strip()
    if not normalized_model_name:
        return ""

    normalized_provider = (provider or "").strip()
    if "/" in normalized_model_name:
        prefix, _, bare_model_name = normalized_model_name.partition("/")
        if prefix == DASHSCOPE_PROVIDER:
            return f"openai/{bare_model_name}"
        return normalized_model_name

    if normalized_provider == DASHSCOPE_PROVIDER:
        return f"openai/{normalized_model_name}"
    return f"{normalized_provider or 'openai'}/{normalized_model_name}"
