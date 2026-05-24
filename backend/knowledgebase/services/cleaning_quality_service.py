"""
质量评分服务 —— 对应 SpringBoot 中的 @Service 组件，负责评估文档清洗后的文本质量。

提供多维度的质量评分：
- 文本长度评分（length）：基于字符数的分段评分
- 符号密度评分（symbol_density）：非字母数字符号的密度检测
- 句子完整性评分（sentence_integrity）：以标点结尾的句子占比
- 问题密度评分（issue_density）：每千字符的清洗问题数

还提供质量门槛（quality gate）机制：block / warning / passed 三个等级，
类似于 SpringBoot 中的断路器模式或网关过滤器。

SpringBoot 类比：
- Django compute_quality_score()    →  SpringBoot @Service 中的评分方法
- Django quality gate 机制          →  SpringBoot Resilience4j CircuitBreaker
- Django settings 阈值配置          →  SpringBoot @Value / application.yml
"""

import re

from django.conf import settings


def compute_quality_score(*, text, issues):
    """
    综合计算文档清洗后的质量分数，输出 0-100 的加权评分。

    四个评分维度及权重：
    - length（文本长度）: 0.20
    - symbol_density（符号密度）: 0.25
    - sentence_integrity（句子完整性）: 0.30
    - issue_density（问题密度）: 0.25

    参数：
        text (str): 清洗后的文本。
        issues (list): 清洗过程中发现的问题列表。

    返回：
        dict: {"score": float (0-100 的加权总分), "signals": dict (各维度评分详情)}。
    """
    signals = {
        "length": _score_text_length(text),
        "symbol_density": _score_symbol_density(text),
        "sentence_integrity": _score_sentence_integrity(text),
        "issue_density": _score_issue_density(text, issues),
    }
    weights = {"length": 0.2, "symbol_density": 0.25, "sentence_integrity": 0.3, "issue_density": 0.25}
    score = round(sum(signals[k] * weights[k] for k in signals), 1)
    return {"score": min(score, 100.0), "signals": signals}


def get_quality_gate_settings():
    """
    获取质量门槛配置参数。

    从 Django settings 读取三个阈值（类似 SpringBoot 从 application.yml 读取 @Value）：
    - KB_CLEANING_MIN_QUALITY_SCORE: 最低质量分阈值（默认 60）
    - KB_CLEANING_WARN_QUALITY_SCORE: 警告质量分阈值（默认 80）
    - KB_CLEANING_BLOCK_BELOW_THRESHOLD: 是否阻止低于阈值的文档入库（默认 True）

    返回：
        dict: 包含 min_quality_score, warn_quality_score, block_below_threshold 的质量门槛配置。
    """
    min_quality_score = float(getattr(settings, "KB_CLEANING_MIN_QUALITY_SCORE", 60.0))
    warn_quality_score = float(getattr(settings, "KB_CLEANING_WARN_QUALITY_SCORE", 80.0))
    block_below_threshold = bool(getattr(settings, "KB_CLEANING_BLOCK_BELOW_THRESHOLD", True))
    if warn_quality_score < min_quality_score:
        warn_quality_score = min_quality_score
    return {
        "min_quality_score": min_quality_score,
        "warn_quality_score": warn_quality_score,
        "block_below_threshold": block_below_threshold,
    }


def evaluate_quality_gate(score):
    """
    评估文档质量分是否通过当前配置的质量门槛。

    门槛等级（类似 SpringBoot 网关过滤器中的限流策略）：
    - "blocked": 质量分低于最低阈值，建议阻止入库（如果 block_below_threshold 为 True）
    - "warning": 质量分低于建议阈值但高于最低阈值，仅告警
    - "passed": 质量分通过当前门槛

    参数：
        score (float): 文档的质量评分（0-100）。

    返回：
        dict: {"score": float, "status": str, "reason": str, "should_block": bool,
               "min_quality_score": float, "warn_quality_score": float, "block_below_threshold": bool}
    """
    quality_gate = get_quality_gate_settings()
    normalized_score = float(score or 0.0)
    if normalized_score < quality_gate["min_quality_score"]:
        status = "blocked" if quality_gate["block_below_threshold"] else "warning"
        reason = (
            f"质量分低于最低阈值 {quality_gate['min_quality_score']:.1f}"
        )
    elif normalized_score < quality_gate["warn_quality_score"]:
        status = "warning"
        reason = (
            f"质量分低于建议阈值 {quality_gate['warn_quality_score']:.1f}"
        )
    else:
        status = "passed"
        reason = "质量分通过当前门槛"

    return {
        **quality_gate,
        "score": normalized_score,
        "status": status,
        "reason": reason,
        "should_block": status == "blocked",
    }


def _score_text_length(text):
    """
    评估文本长度维度：长度越长分数越高（分段线性评分）。

    参数：
        text (str): 输入文本。

    返回：
        float: 0-100 的长度评分。
    """
    length = len(text)
    if length >= 5000:
        return 100
    if length >= 1000:
        return 70 + (length - 1000) / 4000 * 30
    if length >= 100:
        return 30 + (length - 100) / 900 * 40
    return max(length / 100 * 30, 0)


def _score_symbol_density(text):
    """
    评估符号密度维度：非字母数字且非空格/标点的特殊符号占比，密度越低分数越高。

    参数：
        text (str): 输入文本。

    返回：
        float: 0-100 的符号密度评分。
    """
    if not text:
        return 0
    symbol_chars = sum(1 for c in text if not c.isalnum() and not c.isspace() and c not in ".,;:!?-—()[]{}\"'/")
    ratio = symbol_chars / len(text)
    if ratio <= 0.05:
        return 100
    if ratio <= 0.1:
        return 80
    if ratio <= 0.2:
        return 50
    return max(20, 100 - ratio * 400)


# 句子结尾标点正则（中英文）
_SENTENCE_END_RE = re.compile(r"[.!?。！？]\s*$")
# 未闭合括号正则
_UNCLOSED_PAREN_RE = re.compile(r"[(\[{（【]")


def _score_sentence_integrity(text):
    """
    评估句子完整性维度：以句末标点结尾的行数占比，占比越高分数越高。

    参数：
        text (str): 输入文本。

    返回：
        float: 0-100 的句子完整性评分。
    """
    if not text:
        return 0
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if not lines:
        return 0
    complete = sum(1 for line in lines if _SENTENCE_END_RE.search(line))
    ratio = complete / len(lines)
    if ratio >= 0.8:
        return 100
    if ratio >= 0.5:
        return 70
    if ratio >= 0.3:
        return 40
    return 20


def _score_issue_density(text, issues):
    """
    评估问题密度维度：每千字符的清洗问题数，问题越少分数越高。

    参数：
        text (str): 输入文本。
        issues (list): 清洗过程中发现的问题列表。

    返回：
        float: 0-100 的问题密度评分。
    """
    if not text:
        return 0
    length = len(text)
    count = len(issues)
    if count == 0:
        return 100
    density = count / (length / 1000)
    if density <= 1:
        return 90
    if density <= 3:
        return 70
    if density <= 5:
        return 50
    return max(10, 100 - density * 10)


def serialize_cleaning_result(result):
    """
    将 DocumentCleaningResult 实体（类似 SpringBoot JPA Entity）序列化为字典。

    参数：
        result (DocumentCleaningResult): 文档清洗结果模型实例。

    返回：
        dict: 包含清洗结果所有字段的字典，含序列化后的质量门槛评估结果。
    """
    return {
        "id": result.id,
        "document_id": result.document_id,
        "rules_applied": result.rules_applied,
        "issues_found": result.issues_found,
        "quality_score": result.quality_score,
        "quality_signals": result.quality_signals,
        "original_length": result.original_length,
        "cleaned_length": result.cleaned_length,
        "dedup_count": result.dedup_count,
        "quality_gate": evaluate_quality_gate(result.quality_score),
        "cleaned_at": result.cleaned_at.isoformat() if result.cleaned_at else None,
    }
