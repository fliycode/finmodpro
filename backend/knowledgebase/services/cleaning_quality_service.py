import re


def compute_quality_score(*, text, issues):
    signals = {
        "length": _score_text_length(text),
        "symbol_density": _score_symbol_density(text),
        "sentence_integrity": _score_sentence_integrity(text),
        "issue_density": _score_issue_density(text, issues),
    }
    weights = {"length": 0.2, "symbol_density": 0.25, "sentence_integrity": 0.3, "issue_density": 0.25}
    score = round(sum(signals[k] * weights[k] for k in signals), 1)
    return {"score": min(score, 100.0), "signals": signals}


def _score_text_length(text):
    length = len(text)
    if length >= 5000:
        return 100
    if length >= 1000:
        return 70 + (length - 1000) / 4000 * 30
    if length >= 100:
        return 30 + (length - 100) / 900 * 40
    return max(length / 100 * 30, 0)


def _score_symbol_density(text):
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


_SENTENCE_END_RE = re.compile(r"[.!?。！？]\s*$")
_UNCLOSED_PAREN_RE = re.compile(r"[(\[{（【]")


def _score_sentence_integrity(text):
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
        "cleaned_at": result.cleaned_at.isoformat() if result.cleaned_at else None,
    }
