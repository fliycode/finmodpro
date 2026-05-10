from knowledgebase.models import CleaningRule


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
