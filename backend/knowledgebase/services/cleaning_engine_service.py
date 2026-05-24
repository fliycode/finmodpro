"""
清洗引擎服务 —— 对应 SpringBoot 中的 @Service 组件，负责协调文本清洗流程。

作为清洗管道的编排引擎（类似 SpringBoot 的责任链/管道模式），按优先级依次执行
启用的清洗规则，对文档文本进行多阶段清洗处理。每条规则对应一个处理器函数，
规则引擎根据 rule_type 查找并调用对应的 handler。

清洗规则分类：
- 文本清理类（clean_*）：空白清理、编码修复、引号标准化、项目符号去除
- 段落修复类：断裂段落合并
- 冗余去除类（remove_*）：页眉页脚、页码、模板文本、URL/邮箱
- 去重类（dedup_*）：精确去重、近似去重（MinHash + LSH）
- OCR修复类：OCR 伪影修正
- 专有格式化类：财务数字标准化

SpringBoot 类比：
- Django clean_document()                    →  SpringBoot @Service 的管道编排方法
- Django _RULE_HANDLERS dict                 →  SpringBoot Map<String, RuleHandler> / 策略模式
- Django CleaningRule (Django Model)         →  SpringBoot @Entity CleaningRule
- Django objects.filter(enabled=True)        →  SpringBoot repository.findByEnabledTrue()
- Django priority ordering                   →  SpringBoot @Order 或 Sort.by("priority")
"""

import hashlib
import re
import unicodedata

from knowledgebase.models import CleaningRule, DocumentCleaningResult
from knowledgebase.services.cleaning_quality_service import compute_quality_score

# 正则内联标志映射，将字符串标志映射为 re 模块常量
_INLINE_FLAG_MAP = {
    "a": re.ASCII,
    "i": re.IGNORECASE,
    "m": re.MULTILINE,
    "s": re.DOTALL,
    "x": re.VERBOSE,
}

# 匹配正则开头的内联标志 "(?imsx)"
_LEADING_INLINE_FLAGS_RE = re.compile(r"^\(\?([a-zA-Z]+)\)")


def clean_document(*, document):
    """
    清洗单个文档的解析文本，执行所有启用的清洗规则，并保存清洗结果。

    流程：
    1. 按优先级升序获取所有启用的清洗规则
    2. 对文档的 parsed_text 字段执行所有规则
    3. 更新文档的 parsed_text 为清洗后文本
    4. 计算质量评分
    5. 创建 DocumentCleaningResult 记录清洗详情

    类似 SpringBoot 中 @Transactional 的管道处理方法。

    参数：
        document (Document): 待清洗的文档模型实例（类似 JPA @Entity）。

    返回：
        DocumentCleaningResult: 清洗结果实体，包含已应用规则、发现问题、质量评分等信息。
    """
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
    """
    对纯文本执行一系列清洗规则（不涉及文档持久化）。

    按优先级顺序依次应用每条规则，累积 issues 和 rules_applied 信息。
    每条规则的输出作为下一条规则的输入，形成管道处理链。

    参数：
        text (str): 待清洗的原始文本。
        rules (list[CleaningRule], optional): 清洗规则列表。若为 None，则从数据库查询
            所有启用的规则。类似 SpringBoot 中可选的 @Autowired 依赖。

    返回：
        dict: {
            "cleaned_text": str (清洗后的文本),
            "issues": list[dict] (发现的所有问题),
            "rules_applied": list[dict] (实际生效的规则列表),
            "dedup_count": int (去重数量)
        }
    """
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
    """
    将单条清洗规则应用于文本，查找并调用对应的 handler 函数。

    类似 SpringBoot 策略模式中的分发器：
    根据 rule.rule_type 从 _RULE_HANDLERS 映射中查找处理器函数。

    参数：
        text (str): 当前阶段的文本。
        rule (CleaningRule): 清洗规则实例，包含 rule_type（处理器标识）和 config（参数）。

    返回：
        tuple[str, list]: (处理后的文本, 发现的问题列表)。
    """
    handler = _RULE_HANDLERS.get(rule.rule_type)
    if not handler:
        return text, []
    return handler(text=text, config=rule.config, rule_name=rule.name)


# ── 空白清理 ─────────────────────────────────────────────────────────────

def _clean_whitespace(text, config, rule_name):
    """
    标准化空白字符：将多个连续非换行空白合并为单个空格，去除制表符，
    清理行尾空白，将三个以上的连续换行合并为两个换行。

    参数：
        text (str): 输入文本。
        config (dict): 规则配置（未使用，保留接口一致性）。
        rule_name (str): 规则名称。

    返回：
        tuple[str, list]: (清理后的文本, 空问题列表)。
    """
    text = re.sub(r"[^\S\r\n]+", " ", text)
    text = re.sub(r"\t", " ", text)
    text = re.sub(r" +\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text, []


# ── 编码修复 ─────────────────────────────────────────────────────────────

def _fix_encoding(text, config, rule_name):
    """
    使用 ftfy 库修复文本中的编码问题（如乱码、Moji-bake 等）。

    参数：
        text (str): 输入文本。
        config (dict): 规则配置（未使用）。
        rule_name (str): 规则名称。

    返回：
        tuple[str, list]: (修复后的文本, 发现的问题列表)。
    """
    try:
        import ftfy
        fixed = ftfy.fix_text(text)
        issues = []
        if fixed != text:
            issues.append({"rule": rule_name, "type": "encoding_fix", "detail": "Fixed encoding issues via ftfy"})
        return fixed, issues
    except ImportError:
        return text, []


# ── 引号标准化 ───────────────────────────────────────────────────────────

def _normalize_quotes(text, config, rule_name):
    """
    将各种 Unicode 引号字符替换为标准 ASCII 引号。

    替换映射：弯引号/全角引号/法语引号 → ASCII 单双引号。

    参数：
        text (str): 输入文本。
        config (dict): 规则配置（未使用）。
        rule_name (str): 规则名称。

    返回：
        tuple[str, list]: (标准化后的文本, 空问题列表)。
    """
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


# ── 项目符号去除 ─────────────────────────────────────────────────────────

def _remove_bullets(text, config, rule_name):
    """
    去除行首的项目符号字符（●、•、■、◆、◇、○、◎、▸ 等）。

    参数：
        text (str): 输入文本。
        config (dict): 规则配置（未使用）。
        rule_name (str): 规则名称。

    返回：
        tuple[str, list]: (去除项目符号后的文本, 空问题列表)。
    """
    bullet_pattern = re.compile(r"^[\s]*[●•■◆◇○◎▸►‣⁃\xb7]\s*", re.MULTILINE)
    text = bullet_pattern.sub("", text)
    return text, []


# ── 断裂段落合并 ─────────────────────────────────────────────────────────

def _group_broken_paragraphs(text, config, rule_name):
    """
    合并被错误换行打断的段落：如果一行不是以标点结尾且下一行非空，则将两行合并。

    参数：
        text (str): 输入文本。
        config (dict): 规则配置（未使用）。
        rule_name (str): 规则名称。

    返回：
        tuple[str, list]: (段落合并后的文本, 空问题列表)。
    """
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


# ── 页眉页脚去除 ─────────────────────────────────────────────────────────

def _remove_header_footer(text, config, rule_name):
    """
    检测并移除重复出现的页眉/页脚文本。
    统计每行在预估页数中的出现频率，超过 min_occurrence_ratio 阈值的行视为页眉页脚。

    参数：
        text (str): 输入文本。
        config (dict): 包含 "min_occurrence_ratio"（最小出现比例，默认 0.5）的配置。
        rule_name (str): 规则名称。

    返回：
        tuple[str, list]: (去除页眉页脚后的文本, 发现的问题列表)。
    """
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


# ── 页码去除 ─────────────────────────────────────────────────────────────

def _remove_page_numbers(text, config, rule_name):
    """
    检测并移除独立成行的页码文本（如 "Page 1"、"第 3 页"、"1/10"、"- 5 -" 等模式）。

    参数：
        text (str): 输入文本。
        config (dict): 包含 "patterns"（页码模式列表）的配置。
        rule_name (str): 规则名称。

    返回：
        tuple[str, list]: (去除页码后的文本, 发现的问题列表)。
    """
    patterns = config.get("patterns", [
        r"^\s*(page|p\.|第)\s*\d+\s*$",
        r"^\s*\d+\s*/\s*\d+\s*$",
        r"^\s*-\s*\d+\s*-\s*$",
    ])
    compiled_patterns = _compile_patterns(
        patterns,
        base_flags=re.IGNORECASE | re.MULTILINE,
    )
    lines = text.split("\n")
    issues = []
    result = []
    for line in lines:
        stripped_line = line.strip()
        if any(pattern.fullmatch(stripped_line) for pattern in compiled_patterns):
            issues.append({"rule": rule_name, "type": "page_number", "detail": f"Removed page number: {line.strip()}"})
        else:
            result.append(line)
    return "\n".join(result), issues


# ── 模板文本去除 ─────────────────────────────────────────────────────────

def _remove_boilerplate(text, config, rule_name):
    """
    检测并移除模板化的冗余文本（如版权声明、免责声明、保密声明等）。

    参数：
        text (str): 输入文本。
        config (dict): 包含 "patterns"（模板文本正则列表）的配置。
        rule_name (str): 规则名称。

    返回：
        tuple[str, list]: (去除模板文本后的文本, 发现的问题列表)。
    """
    patterns = config.get("patterns", [
        r"(?i)all\s+rights\s+reserved",
        r"(?i)copyright\s+\d{4}",
        r"(?i)this\s+(document|report)\s+is\s+(confidential|proprietary)",
        r"(?i)disclaimer:.*",
        r"(?i)免责[条声明].*",
        r"(?i)版权所有.*",
    ])
    compiled_patterns = _compile_patterns(patterns, base_flags=re.MULTILINE)
    lines = text.split("\n")
    issues = []
    result = []
    for line in lines:
        stripped_line = line.strip()
        if any(pattern.search(stripped_line) for pattern in compiled_patterns) and len(stripped_line) < 200:
            issues.append({"rule": rule_name, "type": "boilerplate", "detail": f"Removed boilerplate: {stripped_line[:60]}"})
        else:
            result.append(line)
    return "\n".join(result), issues


# ── URL 和邮箱去除 ───────────────────────────────────────────────────────

def _remove_urls_emails(text, config, rule_name):
    """
    检测并移除文本中的 URL 链接和邮箱地址。

    参数：
        text (str): 输入文本。
        config (dict): 规则配置（未使用）。
        rule_name (str): 规则名称。

    返回：
        tuple[str, list]: (去除 URL/邮箱后的文本, 发现的问题列表)。
    """
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


# ── 精确去重（SHA-256 哈希） ─────────────────────────────────────────────

def _dedup_exact(text, config, rule_name):
    """
    按自然段（空行分隔）进行精确去重：对每个段落计算 SHA-256 哈希，
    重复的哈希值对应的段落被移除。

    参数：
        text (str): 输入文本。
        config (dict): 包含 "min_length"（最短段落阈值，默认 20 字符）的配置。
        rule_name (str): 规则名称。

    返回：
        tuple[str, list]: (去重后的文本, 发现的问题列表)。
    """
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


# ── 近似去重（MinHash + LSH） ────────────────────────────────────────────

def _dedup_near(text, config, rule_name):
    """
    使用 MinHash + LSH（局部敏感哈希）进行近似去重。
    对段落计算 MinHash 签名，通过 LSH 索引检测相似度超过 threshold 的近似重复段落。

    参数：
        text (str): 输入文本。
        config (dict): 包含以下配置：
            - "threshold" (float, 默认 0.85): Jaccard 相似度阈值。
            - "num_perm" (int, 默认 128): MinHash 的排列数（哈希签名维度）。
        rule_name (str): 规则名称。

    返回：
        tuple[str, list]: (去重后的文本, 发现的问题列表)。
    """
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


# ── OCR 伪影修复 ─────────────────────────────────────────────────────────

def _fix_ocr_artifacts(text, config, rule_name):
    """
    修复 OCR（光学字符识别）产生的常见伪影，如 "rn" 被误识别为 "m" 等。

    参数：
        text (str): 输入文本。
        config (dict): 包含 "substitutions"（替换映射，默认 {"rn": "m", "l": "1"}）的配置。
        rule_name (str): 规则名称。

    返回：
        tuple[str, list]: (修复后的文本, 发现的问题列表)。
    """
    substitutions = config.get("substitutions", {"rn": "m", "l": "1"})
    issues = []
    for old, new in substitutions.items():
        count = text.count(old)
        if count > 0:
            text = text.replace(old, new)
            issues.append({"rule": rule_name, "type": "ocr_fix", "detail": f"Replaced '{old}' → '{new}' ({count} occurrences)"})
    return text, issues


# ── 财务数字标准化 ───────────────────────────────────────────────────────

def _normalize_financial_numbers(text, config, rule_name):
    """
    检测并标准化财务数字格式（如千分位逗号分隔的数字）。
    当前为占位实现，仅检测匹配而不做实际转换。

    参数：
        text (str): 输入文本。
        config (dict): 包含 "target_format"（目标格式，默认 "us"）的配置。
        rule_name (str): 规则名称。

    返回：
        tuple[str, list]: (原文（未修改）, 空问题列表)。
    """
    target = config.get("target_format", "us")
    pattern = re.compile(r"(?<!\d)(\d{1,3}(?:,\d{3})+(?:\.\d+)?)(?!\d)")
    matches = pattern.findall(text)
    if not matches:
        return text, []
    return text, []


# ── 正则编译辅助 ─────────────────────────────────────────────────────────

def _compile_patterns(patterns, *, base_flags=0):
    """
    将字符串模式列表编译为正则表达式列表，支持内联标志 "^(?imsx)"。

    参数：
        patterns (list[str]): 正则表达式字符串列表。
        base_flags (int, optional): 基础正则标志（如 re.IGNORECASE | re.MULTILINE）。

    返回：
        list[re.Pattern]: 编译后的正则表达式对象列表。
    """
    compiled_patterns = []

    for raw_pattern in patterns:
        pattern = raw_pattern
        flags = base_flags

        while True:
            match = _LEADING_INLINE_FLAGS_RE.match(pattern)
            if not match:
                break

            for flag in match.group(1).lower():
                flags |= _INLINE_FLAG_MAP.get(flag, 0)
            pattern = pattern[match.end():]

        compiled_patterns.append(re.compile(pattern, flags))

    return compiled_patterns


# ── 规则处理器映射表（类似 SpringBoot 策略模式中的 Map<RuleType, Handler>） ──

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
