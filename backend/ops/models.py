"""
Ops 应用的数据模型定义。
类比 SpringBoot: 相当于 JPA 的 @Entity 实体类，定义数据库表结构和字段映射。

定义了三个核心模型:
- SystemMetric: 系统指标数据点（时间序列）
- AlertRule:   告警规则（阈值 + 条件）
- AlertEvent:  告警事件（规则触发后的实例）
"""

from django.conf import settings
from django.db import models


class SystemMetric(models.Model):
    """系统指标模型 —— 存储采集到的系统监控指标数据点。

    类比 SpringBoot: 相当于一个 JPA @Entity 类，映射到 system_metric 表。
    每一条记录代表某个时间点的某个指标值（如 CPU 使用率、内存使用率等），
    类似于 Prometheus 时序数据库中的一个数据点。
    """

    # 指标名称，如 cpu_percent, memory_percent, db_healthy
    # 类比 SpringBoot: 对应 Prometheus 的 metric name
    metric_name = models.CharField(max_length=128, db_index=True)
    # 指标数值
    # 类比 SpringBoot: 对应数据点的 value
    value = models.FloatField()
    # 指标单位，如 %, count, bool
    unit = models.CharField(max_length=32, blank=True, default="")
    # 标签键值对，用于存储额外维度信息（如 total_gb）
    # 类比 SpringBoot: 对应 Prometheus 的 labels
    tags = models.JSONField(default=dict, blank=True)
    # 指标采集时间，建索引以支持按时间范围查询
    # 类比 SpringBoot: 对应时序数据点的时间戳
    collected_at = models.DateTimeField(db_index=True)
    # 记录创建时间（写入数据库的时间）
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """模型元数据配置。

        类比 SpringBoot: 对应 JPA 的 @Table 注解中的索引和排序配置。
        """
        # 按采集时间倒序排列
        ordering = ["-collected_at", "-id"]
        # 复合索引：加速按指标名称和时间范围的查询
        indexes = [
            models.Index(
                fields=["metric_name", "-collected_at"],
                name="ops_metric_name_collected_idx",
            ),
        ]


class AlertRule(models.Model):
    """告警规则模型 —— 定义一条告警的判断条件。

    类比 SpringBoot: 相当于 Prometheus 的 Alerting Rule 或 Grafana 的 Alert Rule。
    每条规则指定：监控哪个指标、用什么比较条件、阈值是多少、触发什么严重级别。
    """

    # ---- 严重级别常量 ----
    # 信息级别：仅供参考，不构成实际告警
    SEVERITY_INFO = "info"
    # 警告级别：需要关注，但非紧急
    SEVERITY_WARNING = "warning"
    # 严重级别：需要立即处理
    SEVERITY_CRITICAL = "critical"
    SEVERITY_CHOICES = (
        (SEVERITY_INFO, "Info"),
        (SEVERITY_WARNING, "Warning"),
        (SEVERITY_CRITICAL, "Critical"),
    )

    # ---- 比较条件常量 ----
    CONDITION_GT = "gt"    # 大于
    CONDITION_LT = "lt"    # 小于
    CONDITION_GTE = "gte"  # 大于等于
    CONDITION_LTE = "lte"  # 小于等于
    CONDITION_EQ = "eq"    # 等于
    CONDITION_CHOICES = (
        (CONDITION_GT, "Greater than"),
        (CONDITION_LT, "Less than"),
        (CONDITION_GTE, "Greater than or equal"),
        (CONDITION_LTE, "Less than or equal"),
        (CONDITION_EQ, "Equal"),
    )

    # 规则名称（唯一），如 "CPU 使用率过高"
    name = models.CharField(max_length=255, unique=True)
    # 要监控的指标名称
    metric_name = models.CharField(max_length=128, db_index=True)
    # 比较条件（gt / lt / gte / lte / eq）
    condition = models.CharField(max_length=8, choices=CONDITION_CHOICES)
    # 阈值，当指标值与阈值满足条件时触发告警
    threshold = models.FloatField()
    # 告警严重级别
    severity = models.CharField(
        max_length=16,
        choices=SEVERITY_CHOICES,
        default=SEVERITY_WARNING,
    )
    # 是否启用此规则
    enabled = models.BooleanField(default=True)
    # 通知渠道列表，如 ["in_app", "email"]
    notification_channels = models.JSONField(default=list, blank=True)
    # 规则描述
    description = models.TextField(blank=True, default="")
    # 创建者，关联用户模型
    # 类比 SpringBoot: 对应 @ManyToOne(fetch = LAZY)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_alert_rules",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    # 创建时间
    created_at = models.DateTimeField(auto_now_add=True)
    # 最后更新时间
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """模型元数据配置。"""
        # 按严重级别排序（critical > warning > info），同级按名称
        ordering = ["severity", "name"]


class AlertEvent(models.Model):
    """告警事件模型 —— 告警规则被触发后生成的实例。

    类比 SpringBoot: 相当于 Prometheus 中一条告警规则的 firing instance。
    每次规则条件满足时创建一个事件，指标恢复正常后自动解决。

    可用状态流转:
    firing -> acknowledged -> resolved
    firing -> resolved (未经确认直接恢复)
    """

    # ---- 事件状态常量 ----
    STATUS_FIRING = "firing"              # 触发中：告警条件满足
    STATUS_RESOLVED = "resolved"          # 已解决：指标恢复正常
    STATUS_ACKNOWLEDGED = "acknowledged"  # 已确认：管理员已知晓
    STATUS_CHOICES = (
        (STATUS_FIRING, "Firing"),
        (STATUS_RESOLVED, "Resolved"),
        (STATUS_ACKNOWLEDGED, "Acknowledged"),
    )

    # 关联的告警规则，级联删除
    rule = models.ForeignKey(
        AlertRule,
        related_name="events",
        on_delete=models.CASCADE,
    )
    # 事件当前状态
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_FIRING,
    )
    # 触发时的指标值（用于事后分析）
    triggered_value = models.FloatField()
    # 触发时间
    triggered_at = models.DateTimeField()
    # 解决时间（指标恢复正常时填充）
    resolved_at = models.DateTimeField(blank=True, null=True)
    # 确认此告警的用户
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="acknowledged_alerts",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    # 记录创建时间
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """模型元数据配置。"""
        # 按触发时间倒序，最新告警优先
        ordering = ["-triggered_at", "-id"]
