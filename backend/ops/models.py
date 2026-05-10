from django.conf import settings
from django.db import models


class SystemMetric(models.Model):
    metric_name = models.CharField(max_length=128, db_index=True)
    value = models.FloatField()
    unit = models.CharField(max_length=32, blank=True, default="")
    tags = models.JSONField(default=dict, blank=True)
    collected_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-collected_at", "-id"]
        indexes = [
            models.Index(
                fields=["metric_name", "-collected_at"],
                name="ops_metric_name_collected_idx",
            ),
        ]


class AlertRule(models.Model):
    SEVERITY_INFO = "info"
    SEVERITY_WARNING = "warning"
    SEVERITY_CRITICAL = "critical"
    SEVERITY_CHOICES = (
        (SEVERITY_INFO, "Info"),
        (SEVERITY_WARNING, "Warning"),
        (SEVERITY_CRITICAL, "Critical"),
    )

    CONDITION_GT = "gt"
    CONDITION_LT = "lt"
    CONDITION_GTE = "gte"
    CONDITION_LTE = "lte"
    CONDITION_EQ = "eq"
    CONDITION_CHOICES = (
        (CONDITION_GT, "Greater than"),
        (CONDITION_LT, "Less than"),
        (CONDITION_GTE, "Greater than or equal"),
        (CONDITION_LTE, "Less than or equal"),
        (CONDITION_EQ, "Equal"),
    )

    name = models.CharField(max_length=255, unique=True)
    metric_name = models.CharField(max_length=128, db_index=True)
    condition = models.CharField(max_length=8, choices=CONDITION_CHOICES)
    threshold = models.FloatField()
    severity = models.CharField(
        max_length=16,
        choices=SEVERITY_CHOICES,
        default=SEVERITY_WARNING,
    )
    enabled = models.BooleanField(default=True)
    notification_channels = models.JSONField(default=list, blank=True)
    description = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_alert_rules",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["severity", "name"]


class AlertEvent(models.Model):
    STATUS_FIRING = "firing"
    STATUS_RESOLVED = "resolved"
    STATUS_ACKNOWLEDGED = "acknowledged"
    STATUS_CHOICES = (
        (STATUS_FIRING, "Firing"),
        (STATUS_RESOLVED, "Resolved"),
        (STATUS_ACKNOWLEDGED, "Acknowledged"),
    )

    rule = models.ForeignKey(
        AlertRule,
        related_name="events",
        on_delete=models.CASCADE,
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_FIRING,
    )
    triggered_value = models.FloatField()
    triggered_at = models.DateTimeField()
    resolved_at = models.DateTimeField(blank=True, null=True)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="acknowledged_alerts",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-triggered_at", "-id"]
