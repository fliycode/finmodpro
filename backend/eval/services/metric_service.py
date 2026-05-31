
"""
Evaluation metric computation utilities.

All functions are pure: they take inputs and return computed values.
No side effects, no database access.
"""


def precision_recall_f1(tp, fp, fn):
    """计算精确率、召回率和F1值。"""
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def answer_accuracy(correct_count, total):
    """计算回答准确率。"""
    return correct_count / total if total > 0 else 0.0


def citation_recall(actual_sources, expected_sources):
    """
    计算引用召回率: |actual ∩ expected| / |expected|.
    actual_sources 和 expected_sources 为 source ID 的集合或列表。
    """
    if not expected_sources:
        return 1.0
    actual_set = set(actual_sources) if actual_sources else set()
    expected_set = set(expected_sources)
    return len(actual_set & expected_set) / len(expected_set)


def citation_consistency(supported_count, total_claims):
    """计算引用一致率: supported_claims / total_claims."""
    if total_claims == 0:
        return 1.0
    return supported_count / total_claims


def mean_and_std(values):
    """计算均值和标准差。"""
    if not values:
        return {"mean": 0.0, "std": 0.0}
    n = len(values)
    mean = sum(values) / n
    if n < 2:
        return {"mean": mean, "std": 0.0}
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    return {"mean": round(mean, 4), "std": round(variance ** 0.5, 4)}


def exact_match(predicted, expected):
    """精确匹配（大小写和空白标准化后）。"""
    if not predicted or not expected:
        return False
    return predicted.strip().lower() == expected.strip().lower()


def fuzzy_match(predicted, expected, threshold=0.85):
    """
    模糊匹配：基于字符级Jaccard相似度。
    对中文公司名称特别有用（如'华远地产' vs '华远地产股份有限公司'）。
    """
    if not predicted or not expected:
        return False
    p_set = set(predicted.strip())
    e_set = set(expected.strip())
    if not p_set or not e_set:
        return False
    intersection = len(p_set & e_set)
    union = len(p_set | e_set)
    similarity = intersection / union if union > 0 else 0
    return similarity >= threshold


def substring_overlap_ratio(text, reference):
    """
    计算text中有多大比例的内容与reference重叠。
    用于评估证据提取质量。
    """
    if not text or not reference:
        return 0.0
    text_set = set(text)
    ref_set = set(reference)
    if not ref_set:
        return 0.0
    return len(text_set & ref_set) / len(ref_set)


def field_completeness(present_fields, required_fields):
    """计算字段完整率。"""
    if not required_fields:
        return 1.0
    return len(set(present_fields) & set(required_fields)) / len(required_fields)


def safe_divide(numerator, denominator):
    """安全除法。"""
    if denominator == 0:
        return 0.0
    return numerator / denominator
