import hashlib
import re
import unicodedata

from knowledgebase.models import CleaningRule, DocumentCleaningResult
from knowledgebase.services.cleaning_quality_service import compute_quality_score


def clean_document(*, document):
    rules = list(CleaningRule.objects.filter(enabled=True).order_by("priority", "id"))
    original_text = document.parsed_text or ""
    result_data = clean_document_text(text=original_text, rules=rules)

    document.parsed_text = result_data["cleaned_text"]
    document.save(update_fields=["parsed_text", "updated_at"])

    quality = compute_quality_score(text=result_data["cleaned_text"], issues=result_data["issues"])

    return DocumentCleaningResult.objects.create(
        document=document,
        rules_applied=result_data["rules_applied"],
        issues_found=result_data["issues"],
        quality_score=quality["score"],
        quality_signals=quality["signals"],
        original_length=len(original_text),
        cleaned_length=len(result_data["cleaned_text"]),
        dedup_count=result_data["dedup_count"],
    )


def clean_document_text(*, text, rules=None):
    if rules is None:
        rules = list(CleaningRule.objects.filter(enabled=True).order_by("priority", "id"))

    issues = []
    rules_applied = []
    dedup_count = 0

    for rule in rules:
        cleaned, rule_issues = _apply_rule(text, rule)
        if cleaned != text:
            rules_applied.append({"id": rule.id, "name": rule.name, "type": rule.rule_type})
        if rule.rule_type.startswith("dedup"):
            dedup_count += len(rule_issues)
        issues.extend(rule_issues)
        text = cleaned

    return {
        "cleaned_text": text,
        "issues": issues,
        "rules_applied": rules_applied,
        "dedup_count": dedup_count,
    }


def _apply_rule(text, rule):
    handler = _RULE_HANDLERS.get(rule.rule_type)
    if not handler:
        return text, []
    return handler(text=text, config=rule.config, rule_name=rule.name)


def _clean_whitespace(text, config, rule_name):
    text = re.sub(r"[^\S\r\n]+", " ", text)
    text = re.sub(r"\t", " ", text)
    text = re.sub(r" +\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text, []


def _fix_encoding(text, config, rule_name):
    try:
        import ftfy
        fixed = ftfy.fix_text(text)
        issues = []
        if fixed != text:
            issues.append({"rule": rule_name, "type": "encoding_fix", "detail": "Fixed encoding issues via ftfy"})
        return fixed, issues
    except ImportError:
        return text, []


def _normalize_quotes(text, config, rule_name):
    replacements = {
        "‘": "'", "’": "'",
        "“": '"', "”": '"',
        "′": "'", "″": '"',
        "«": '"', "»": '"',
        "‹": "'", "›": "'",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text, []


def _remove_bullets(text, config, rule_name):
    bullet_pattern = re.compile(r"^[\s]*[●•■◆◇○◎▸►‣⁃·]\s*", re.MULTILINE)
    text = bullet_pattern.sub("", text)
    return text, []


def _group_broken_paragraphs(text, config, rule_name):
    lines = text.split("\n")
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if i + 1 < len(lines) and lines[i + 1].strip() and not line.endswith((".", "。", "!", "！", "?", "？", ":", "：")):
            result.append(line.rstrip() + " " + lines[i + 1].lstrip())
            i += 2
        else:
            result.append(line)
            i += 1
    return "\n".join(result), []


def _remove_header_footer(text, config, rule_name):
    min_ratio = config.get("min_occurrence_ratio", 0.5)
    lines = text.split("\n")
    line_counts = {}
    for line in lines:
        stripped = line.strip()
        if stripped and len(stripped) < 100:
            line_counts[stripped] = line_counts.get(stripped, 0) + 1

    total_pages = max(1, len(lines) / 40)
    repeated = {line for line, count in line_counts.items() if count / total_pages >= min_ratio and count >= 3}
    if not repeated:
        return text, []

    issues = []
    result = []
    for line in lines:
        if line.strip() in repeated:
            issues.append({"rule": rule_name, "type": "header_footer", "detail": f"Removed repeated line: {line.strip()[:60]}"})
        else:
            result.append(line)
    return "\n".join(result), issues


def _remove_page_numbers(text, config, rule_name):
    patterns = config.get("patterns", [
        r"^\s*(page|p\.|第)\s*\d+\s*$",
        r"^\s*\d+\s*/\s*\d+\s*$",
        r"^\s*-\s*\d+\s*-\s*$",
    ])
    combined = re.compile("|".join(f"({p})" for p in patterns), re.IGNORECASE | re.MULTILINE)
    lines = text.split("\n")
    issues = []
    result = []
    for line in lines:
        if combined.fullmatch(line.strip()):
            issues.append({"rule": rule_name, "type": "page_number", "detail": f"Removed page number: {line.strip()}"})
        else:
            result.append(line)
    return "\n".join(result), issues


def _remove_boilerplate(text, config, rule_name):
    patterns = config.get("patterns", [
        r"(?i)all\s+rights\s+reserved",
        r"(?i)copyright\s+\d{4}",
        r"(?i)this\s+(document|report)\s+is\s+(confidential|proprietary)",
        r"(?i)disclaimer:.*",
        r"(?i)免责[条款声明].*",
        r"(?i)版权所有.*",
    ])
    combined = re.compile("|".join(f"({p})" for p in patterns), re.MULTILINE)
    lines = text.split("\n")
    issues = []
    result = []
    for line in lines:
        if combined.search(line.strip()) and len(line.strip()) < 200:
            issues.append({"rule": rule_name, "type": "boilerplate", "detail": f"Removed boilerplate: {line.strip()[:60]}"})
        else:
            result.append(line)
    return "\n".join(result), issues


def _remove_urls_emails(text, config, rule_name):
    url_pattern = re.compile(r"https?://\S+|www\.\S+")
    email_pattern = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
    issues = []
    urls_found = url_pattern.findall(text)
    emails_found = email_pattern.findall(text)
    if urls_found or emails_found:
        issues.append({"rule": rule_name, "type": "url_email", "detail": f"Removed {len(urls_found)} URLs and {len(emails_found)} emails"})
    text = url_pattern.sub("", text)
    text = email_pattern.sub("", text)
    return text, issues


def _dedup_exact(text, config, rule_name):
    min_length = config.get("min_length", 20)
    paragraphs = re.split(r"\n\s*\n", text)
    seen = set()
    issues = []
    result = []
    for para in paragraphs:
        stripped = para.strip()
        if len(stripped) < min_length:
            result.append(para)
            continue
        h = hashlib.sha256(stripped.encode()).hexdigest()
        if h in seen:
            issues.append({"rule": rule_name, "type": "exact_dup", "detail": f"Removed exact duplicate paragraph ({len(stripped)} chars)"})
        else:
            seen.add(h)
            result.append(para)
    return "\n\n".join(result), issues


def _dedup_near(text, config, rule_name):
    threshold = config.get("threshold", 0.85)
    num_perm = config.get("num_perm", 128)
    try:
        from datasketch import MinHash, MinHashLSH
    except ImportError:
        return text, []

    paragraphs = re.split(r"\n\s*\n", text)
    if len(paragraphs) < 2:
        return text, []

    lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
    issues = []
    result = []

    for i, para in enumerate(paragraphs):
        stripped = para.strip()
        if len(stripped) < 30:
            result.append(para)
            continue

        mh = MinHash(num_perm=num_perm)
        for j in range(0, len(stripped), 3):
            mh.update(stripped[j:j+3].encode())

        try:
            matches = lsh.query(mh)
            if matches:
                issues.append({"rule": rule_name, "type": "near_dup", "detail": f"Removed near-duplicate paragraph ({len(stripped)} chars)"})
                continue
        except Exception:
            pass

        try:
            lsh.insert(f"para_{i}", mh)
        except Exception:
            pass
        result.append(para)

    return "\n\n".join(result), issues


def _fix_ocr_artifacts(text, config, rule_name):
    substitutions = config.get("substitutions", {"rn": "m", "l": "1"})
    issues = []
    for old, new in substitutions.items():
        count = text.count(old)
        if count > 0:
            text = text.replace(old, new)
            issues.append({"rule": rule_name, "type": "ocr_fix", "detail": f"Replaced '{old}' → '{new}' ({count} occurrences)"})
    return text, issues


def _normalize_financial_numbers(text, config, rule_name):
    target = config.get("target_format", "us")
    pattern = re.compile(r"(?<!\d)(\d{1,3}(?:,\d{3})+(?:\.\d+)?)(?!\d)")
    matches = pattern.findall(text)
    if not matches:
        return text, []
    return text, []


_RULE_HANDLERS = {
    "clean_whitespace": _clean_whitespace,
    "fix_encoding": _fix_encoding,
    "normalize_quotes": _normalize_quotes,
    "remove_bullets": _remove_bullets,
    "group_broken_paragraphs": _group_broken_paragraphs,
    "remove_header_footer": _remove_header_footer,
    "remove_page_numbers": _remove_page_numbers,
    "remove_boilerplate": _remove_boilerplate,
    "remove_urls_emails": _remove_urls_emails,
    "dedup_exact": _dedup_exact,
    "dedup_near": _dedup_near,
    "fix_ocr_artifacts": _fix_ocr_artifacts,
    "normalize_financial_numbers": _normalize_financial_numbers,
}
