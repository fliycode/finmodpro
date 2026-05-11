from django.db.models import Avg

from knowledgebase.models import CleaningRule, DocumentCleaningResult
from knowledgebase.services.cleaning_quality_service import (
    evaluate_quality_gate,
    get_quality_gate_settings,
)

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
    qs = CleaningRule.objects.all()
    if enabled_only:
        qs = qs.filter(enabled=True)
    return [_serialize_rule(r) for r in qs]


def get_cleaning_rule(*, rule_id):
    return CleaningRule.objects.get(id=rule_id)


def create_cleaning_rule(*, name, rule_type, config=None, enabled=True, priority=100, created_by=None):
    return CleaningRule.objects.create(
        name=name,
        rule_type=rule_type,
        config=config or {},
        enabled=enabled,
        priority=priority,
        created_by=created_by,
    )


def update_cleaning_rule(*, rule, **kwargs):
    for field in ("name", "rule_type", "config", "enabled", "priority"):
        if field in kwargs:
            setattr(rule, field, kwargs[field])
    rule.save()
    return rule


def delete_cleaning_rule(*, rule):
    rule.delete()


def get_default_cleaning_rule_names():
    return [definition["name"] for definition in DEFAULT_CLEANING_RULE_DEFINITIONS]


def bootstrap_default_cleaning_rules(*, created_by=None):
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
