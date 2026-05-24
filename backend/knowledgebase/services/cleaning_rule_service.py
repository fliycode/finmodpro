"""
清洗规则管理服务 —— 对应 SpringBoot 中的 @Service 组件，管理 CleaningRule 实体的 CRUD。

提供清洗规则的完整生命周期管理：
- 查询/列表：按启用状态过滤
- 创建/更新/删除：完整的 CRUD 操作
- 默认规则引导（bootstrap）：系统初始化时自动创建预定义的清洗规则集
- 清洗概览：汇总所有清洗规则状态和最近的清洗结果

SpringBoot 类比：
- Django CleaningRule model              →  SpringBoot @Entity CleaningRule
- Django list_cleaning_rules()           →  SpringBoot cleaningRuleRepository.findAll()
- Django create_cleaning_rule()          →  SpringBoot cleaningRuleRepository.save()
- Django bootstrap_default_cleaning_rules() →  SpringBoot @PostConstruct / CommandLineRunner
- Django get_cleaning_summary()          →  SpringBoot @Service 的聚合统计方法
"""

from django.db.models import Avg

from knowledgebase.models import CleaningRule, DocumentCleaningResult
from knowledgebase.services.cleaning_quality_service import (
    evaluate_quality_gate,
    get_quality_gate_settings,
)

# 系统预定义的默认清洗规则集，按优先级排序
DEFAULT_CLEANING_RULE_DEFINITIONS = (
    {
        "name": "默认：空白清理",
        "rule_type": "clean_whitespace",
        "config": {},
        "enabled": True,
        "priority": 10,
    },
    {
        "name": "默认：编码修复",
        "rule_type": "fix_encoding",
        "config": {},
        "enabled": True,
        "priority": 20,
    },
    {
        "name": "默认：页眉页脚去除",
        "rule_type": "remove_header_footer",
        "config": {"min_occurrence_ratio": 0.5},
        "enabled": True,
        "priority": 30,
    },
    {
        "name": "默认：页码去除",
        "rule_type": "remove_page_numbers",
        "config": {},
        "enabled": True,
        "priority": 40,
    },
    {
        "name": "默认：模板文本去除",
        "rule_type": "remove_boilerplate",
        "config": {},
        "enabled": True,
        "priority": 50,
    },
    {
        "name": "默认：断裂段落合并",
        "rule_type": "group_broken_paragraphs",
        "config": {},
        "enabled": True,
        "priority": 60,
    },
    {
        "name": "默认：精确去重",
        "rule_type": "dedup_exact",
        "config": {"min_length": 20},
        "enabled": True,
        "priority": 70,
    },
)


def list_cleaning_rules(*, enabled_only=False):
    """
    查询清洗规则列表（类似 SpringBoot repository.findAll()）。

    参数：
        enabled_only (bool): 是否仅返回启用的规则，默认 False 返回全部。

    返回：
        list[dict]: 序列化后的清洗规则列表。
    """
    qs = CleaningRule.objects.all()
    if enabled_only:
        qs = qs.filter(enabled=True)
    return [_serialize_rule(r) for r in qs]


def get_cleaning_rule(*, rule_id):
    """
    按主键ID获取单条清洗规则（类似 SpringBoot repository.findById()）。

    参数：
        rule_id (int): 清洗规则主键ID。

    返回：
        CleaningRule: 清洗规则模型实例。
    """
    return CleaningRule.objects.get(id=rule_id)


def create_cleaning_rule(*, name, rule_type, config=None, enabled=True, priority=100, created_by=None):
    """
    创建新的清洗规则（类似 SpringBoot repository.save(new CleaningRule(...))）。

    参数：
        name (str): 规则名称。
        rule_type (str): 规则类型（对应 _RULE_HANDLERS 中的处理器键）。
        config (dict, optional): 规则配置参数。
        enabled (bool): 是否启用，默认 True。
        priority (int): 优先级（数值越小越先执行），默认 100。
        created_by (User | None): 创建者用户。

    返回：
        CleaningRule: 新创建的清洗规则实例。
    """
    return CleaningRule.objects.create(
        name=name,
        rule_type=rule_type,
        config=config or {},
        enabled=enabled,
        priority=priority,
        created_by=created_by,
    )


def update_cleaning_rule(*, rule, **kwargs):
    """
    更新清洗规则的部分字段（类似 SpringBoot repository.save() 的更新操作）。

    参数：
        rule (CleaningRule): 待更新的清洗规则实例。
        **kwargs: 可选更新的字段，支持 name, rule_type, config, enabled, priority。

    返回：
        CleaningRule: 更新后的清洗规则实例。
    """
    for field in ("name", "rule_type", "config", "enabled", "priority"):
        if field in kwargs:
            setattr(rule, field, kwargs[field])
    rule.save()
    return rule


def delete_cleaning_rule(*, rule):
    """
    删除清洗规则（类似 SpringBoot repository.delete(rule)）。

    参数：
        rule (CleaningRule): 待删除的清洗规则实例。
    """
    rule.delete()


def get_default_cleaning_rule_names():
    """
    获取系统预定义默认规则名称列表。

    返回：
        list[str]: 默认规则名称列表。
    """
    return [definition["name"] for definition in DEFAULT_CLEANING_RULE_DEFINITIONS]


def bootstrap_default_cleaning_rules(*, created_by=None):
    """
    引导初始化默认清洗规则集。

    检查当前数据库中是否已存在各默认规则，仅创建缺失的规则。
    类似 SpringBoot 中的 @PostConstruct 初始化方法或 Flyway 种子数据。

    参数：
        created_by (User | None): 创建者用户，用于新创建规则的 created_by 字段。

    返回：
        dict: {"created_count": int, "existing_count": int, "rules": list[dict]}
            包含新创建数量、已存在数量以及当前数据库中所有默认规则的序列化列表。
    """
    existing_by_name = {
        rule.name: rule
        for rule in CleaningRule.objects.filter(name__in=get_default_cleaning_rule_names())
    }
    created_rules = []
    existing_rules = []

    for definition in DEFAULT_CLEANING_RULE_DEFINITIONS:
        rule = existing_by_name.get(definition["name"])
        if rule is None:
            rule = CleaningRule.objects.create(created_by=created_by, **definition)
            created_rules.append(rule)
        else:
            existing_rules.append(rule)

    return {
        "created_count": len(created_rules),
        "existing_count": len(existing_rules),
        "rules": [
            _serialize_rule(rule)
            for rule in CleaningRule.objects.filter(
                name__in=get_default_cleaning_rule_names()
            ).order_by("priority", "id")
        ],
    }


def get_cleaning_summary(*, recent_limit=5):
    """
    获取清洗系统概览统计，包括规则状态和最近的清洗结果。

    类似 SpringBoot @Service 中聚合多个 Repository 查询的仪表盘统计方法。

    参数：
        recent_limit (int): 最近清洗结果的数量限制，默认 5。

    返回：
        dict: 包含以下字段的概览统计：
            - total_rules: 规则总数
            - enabled_rule_count: 已启用规则数
            - default_rule_total: 预定义默认规则总数
            - default_rule_count: 已初始化的默认规则数
            - enabled_default_rule_count: 已启用的默认规则数
            - default_rules_initialized: 是否所有默认规则都已初始化
            - missing_default_rule_names: 缺失的默认规则名称列表
            - quality_gate: 质量门槛配置
            - recent_result_count: 最近清洗结果数量
            - average_quality_score: 平均质量评分
            - last_cleaned_at: 最近一次清洗时间
            - recent_results: 最近的清洗结果列表
    """
    default_rule_names = get_default_cleaning_rule_names()
    rules = list(CleaningRule.objects.order_by("priority", "id"))
    rules_by_name = {rule.name: rule for rule in rules}
    default_rules = [rules_by_name[name] for name in default_rule_names if name in rules_by_name]
    recent_results_qs = (
        DocumentCleaningResult.objects.select_related("document")
        .order_by("-cleaned_at", "-id")[: max(int(recent_limit or 5), 1)]
    )
    average_quality_score = (
        DocumentCleaningResult.objects.aggregate(avg_quality_score=Avg("quality_score"))["avg_quality_score"]
    )
    recent_results = []
    for result in recent_results_qs:
        recent_results.append(
            {
                "id": result.id,
                "document_id": result.document_id,
                "document_title": result.document.title,
                "quality_score": result.quality_score,
                "quality_gate": evaluate_quality_gate(result.quality_score),
                "cleaned_at": result.cleaned_at.isoformat() if result.cleaned_at else None,
            }
        )

    enabled_rule_count = sum(1 for rule in rules if rule.enabled)
    enabled_default_rule_count = sum(1 for rule in default_rules if rule.enabled)
    latest_result = recent_results[0] if recent_results else None

    return {
        "total_rules": len(rules),
        "enabled_rule_count": enabled_rule_count,
        "default_rule_total": len(default_rule_names),
        "default_rule_count": len(default_rules),
        "enabled_default_rule_count": enabled_default_rule_count,
        "default_rules_initialized": len(default_rules) == len(default_rule_names),
        "missing_default_rule_names": [
            rule_name for rule_name in default_rule_names if rule_name not in rules_by_name
        ],
        "quality_gate": get_quality_gate_settings(),
        "recent_result_count": len(recent_results),
        "average_quality_score": round(float(average_quality_score), 1)
        if average_quality_score is not None
        else None,
        "last_cleaned_at": latest_result["cleaned_at"] if latest_result else None,
        "recent_results": recent_results,
    }


def _serialize_rule(rule):
    """
    将 CleaningRule 实体序列化为字典（类似 SpringBoot Entity → DTO 转换）。

    参数：
        rule (CleaningRule): 清洗规则模型实例。

    返回：
        dict: 包含所有规则字段的序列化字典。
    """
    return {
        "id": rule.id,
        "name": rule.name,
        "rule_type": rule.rule_type,
        "config": rule.config,
        "enabled": rule.enabled,
        "priority": rule.priority,
        "created_by": rule.created_by_id,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }
