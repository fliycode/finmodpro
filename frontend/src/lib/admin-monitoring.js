const toNumber = (v, fallback = 0) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
};

const safeStr = (v, fallback = '') => (v != null ? String(v) : fallback);

export function normalizeMonitoringPayload(payload) {
  if (!payload || typeof payload !== 'object') {
    return { metrics: {}, firingAlerts: 0, collectedAt: null };
  }
  return {
    metrics: payload.metrics || {},
    firingAlerts: toNumber(payload.firing_alerts),
    collectedAt: safeStr(payload.collected_at),
  };
}

export function normalizeMetricTimeSeries(payload) {
  if (!payload || typeof payload !== 'object') {
    return { metricName: '', hours: 24, dataPoints: [] };
  }
  return {
    metricName: safeStr(payload.metric_name),
    hours: toNumber(payload.hours, 24),
    dataPoints: Array.isArray(payload.data_points)
      ? payload.data_points.map((p) => ({
          value: toNumber(p.value),
          unit: safeStr(p.unit),
          collectedAt: safeStr(p.collected_at),
        }))
      : [],
  };
}

export function buildServiceStatusCards(metrics) {
  const services = [
    { key: 'db_healthy', label: '数据库', icon: 'database' },
    { key: 'redis_healthy', label: 'Redis', icon: 'cache' },
    { key: 'milvus_healthy', label: 'Milvus', icon: 'vector' },
  ];

  return services.map((s) => {
    const metric = metrics[s.key];
    const healthy = metric && metric.value === 1;
    return {
      ...s,
      status: healthy ? 'healthy' : 'down',
      label: s.label,
      detail: healthy ? '正常' : '异常',
      tone: healthy ? 'success' : 'risk',
      collectedAt: metric?.collected_at || null,
    };
  });
}

export function buildResourceGauges(metrics) {
  const gauges = [
    { key: 'cpu_percent', label: 'CPU 使用率', unit: '%' },
    { key: 'memory_percent', label: '内存使用率', unit: '%' },
    { key: 'disk_percent', label: '磁盘使用率', unit: '%' },
  ];

  return gauges.map((g) => {
    const metric = metrics[g.key];
    const value = metric ? toNumber(metric.value) : 0;
    let tone = 'success';
    if (value > 90) tone = 'risk';
    else if (value > 70) tone = 'warning';

    return {
      ...g,
      value,
      tone,
      tags: metric?.tags || {},
      collectedAt: metric?.collected_at || null,
    };
  });
}

export function buildCeleryStatus(metrics) {
  const metric = metrics.celery_worker_count;
  const count = metric ? toNumber(metric.value) : 0;
  return {
    count,
    status: count > 0 ? 'healthy' : 'down',
    tone: count > 0 ? 'success' : 'risk',
    collectedAt: metric?.collected_at || null,
  };
}

export function buildMetricTimeSeriesOption(series, cssVar) {
  const getVar = (name) => {
    try {
      return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || '#999';
    } catch {
      return '#999';
    }
  };

  const brand = cssVar || getVar('--brand') || '#2457c5';
  const lineSoft = getVar('--line-soft') || '#e5e7eb';
  const textSecondary = getVar('--text-secondary') || '#6b7280';

  const xData = series.dataPoints.map((p) => {
    const d = new Date(p.collectedAt);
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  });
  const yData = series.dataPoints.map((p) => p.value);

  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 48, right: 16, top: 32, bottom: 32 },
    xAxis: {
      type: 'category',
      data: xData,
      axisLine: { lineStyle: { color: lineSoft } },
      axisLabel: { color: textSecondary, fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      splitLine: { lineStyle: { color: lineSoft } },
      axisLabel: { color: textSecondary, fontSize: 11 },
    },
    series: [
      {
        type: 'line',
        data: yData,
        smooth: true,
        symbol: 'circle',
        symbolSize: 4,
        lineStyle: { color: brand, width: 2 },
        itemStyle: { color: brand },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: brand + '33' },
              { offset: 1, color: brand + '05' },
            ],
          },
        },
      },
    ],
  };
}

export function normalizeAlertRule(rule) {
  return {
    id: toNumber(rule.id),
    name: safeStr(rule.name),
    metricName: safeStr(rule.metric_name),
    condition: safeStr(rule.condition),
    threshold: toNumber(rule.threshold),
    severity: safeStr(rule.severity, 'warning'),
    enabled: rule.enabled !== false,
    notificationChannels: rule.notification_channels || [],
    description: safeStr(rule.description),
    createdBy: rule.created_by,
    createdAt: safeStr(rule.created_at),
    updatedAt: safeStr(rule.updated_at),
  };
}

export function normalizeAlertEvent(event) {
  return {
    id: toNumber(event.id),
    ruleId: toNumber(event.rule_id),
    ruleName: safeStr(event.rule_name),
    severity: safeStr(event.severity, 'warning'),
    metricName: safeStr(event.metric_name),
    condition: safeStr(event.condition),
    threshold: toNumber(event.threshold),
    status: safeStr(event.status, 'firing'),
    triggeredValue: toNumber(event.triggered_value),
    triggeredAt: safeStr(event.triggered_at),
    resolvedAt: safeStr(event.resolved_at),
    notificationChannels: Array.isArray(event.notification_channels) ? event.notification_channels : [],
    acknowledgedBy: event.acknowledged_by,
    acknowledgedByName: safeStr(event.acknowledged_by_name),
    createdAt: safeStr(event.created_at),
  };
}

export const SEVERITY_LABELS = {
  info: '提示',
  warning: '警告',
  critical: '严重',
};

export const SEVERITY_TONES = {
  info: 'info',
  warning: 'warning',
  critical: 'risk',
};

export const CONDITION_LABELS = {
  gt: '大于',
  lt: '小于',
  gte: '大于等于',
  lte: '小于等于',
  eq: '等于',
};

export const STATUS_LABELS = {
  firing: '触发中',
  resolved: '已恢复',
  acknowledged: '已确认',
};

export const STATUS_TONES = {
  firing: 'risk',
  resolved: 'success',
  acknowledged: 'info',
};

export const SEVERITY_ORDER = {
  critical: 3,
  warning: 2,
  info: 1,
};

export const STATUS_PRIORITY_ORDER = {
  firing: 3,
  acknowledged: 2,
  resolved: 1,
};

export const METRIC_OPTIONS = [
  { value: 'cpu_percent', label: 'CPU 使用率' },
  { value: 'memory_percent', label: '内存使用率' },
  { value: 'disk_percent', label: '磁盘使用率' },
  { value: 'celery_worker_count', label: 'Celery Worker 数' },
  { value: 'db_healthy', label: '数据库状态' },
  { value: 'redis_healthy', label: 'Redis 状态' },
  { value: 'milvus_healthy', label: 'Milvus 状态' },
];

export const DEFAULT_ALERT_NOTIFICATION_CHANNELS = Object.freeze(['in_app']);

export const ALERT_NOTIFICATION_CHANNEL_OPTIONS = Object.freeze([
  { value: 'in_app', label: '站内通知' },
]);

export const ALERT_RULE_TEMPLATES = Object.freeze([
  {
    name: 'CPU 使用率过高',
    metric_name: 'cpu_percent',
    condition: 'gte',
    threshold: 85,
    severity: 'critical',
    enabled: true,
    notification_channels: [...DEFAULT_ALERT_NOTIFICATION_CHANNELS],
    description: '当 CPU 使用率持续偏高时，通过站内告警提醒管理员及时排查。',
  },
  {
    name: '内存使用率过高',
    metric_name: 'memory_percent',
    condition: 'gte',
    threshold: 85,
    severity: 'warning',
    enabled: true,
    notification_channels: [...DEFAULT_ALERT_NOTIFICATION_CHANNELS],
    description: '用于发现内存占用持续上升或潜在泄漏。',
  },
  {
    name: '磁盘使用率过高',
    metric_name: 'disk_percent',
    condition: 'gte',
    threshold: 80,
    severity: 'critical',
    enabled: true,
    notification_channels: [...DEFAULT_ALERT_NOTIFICATION_CHANNELS],
    description: '磁盘余量不足时尽早预警，避免影响上传、解析和索引任务。',
  },
  {
    name: 'Celery Worker 不可用',
    metric_name: 'celery_worker_count',
    condition: 'lt',
    threshold: 1,
    severity: 'critical',
    enabled: true,
    notification_channels: [...DEFAULT_ALERT_NOTIFICATION_CHANNELS],
    description: '当异步任务执行器不可用时，提醒管理员检查队列和 worker 状态。',
  },
]);

export function getMetricLabel(metricName) {
  return METRIC_OPTIONS.find((option) => option.value === metricName)?.label || metricName || '-';
}

export function getNotificationChannelLabel(channel) {
  return ALERT_NOTIFICATION_CHANNEL_OPTIONS.find((option) => option.value === channel)?.label || channel || '-';
}

export function summarizeAlertEvents(events) {
  return (Array.isArray(events) ? events : []).reduce((summary, event) => {
    const status = safeStr(event.status);
    summary.all += 1;
    if (status && summary[status] !== undefined) {
      summary[status] += 1;
    }
    return summary;
  }, {
    all: 0,
    firing: 0,
    acknowledged: 0,
    resolved: 0,
  });
}

export function summarizeAlertSeverities(events) {
  return (Array.isArray(events) ? events : []).reduce((summary, event) => {
    const severity = safeStr(event.severity);
    if (severity && summary[severity] !== undefined) {
      summary[severity] += 1;
    }
    return summary;
  }, {
    critical: 0,
    warning: 0,
    info: 0,
  });
}

export function sortAlertEventsByPriority(events) {
  return [...(Array.isArray(events) ? events : [])].sort((left, right) => {
    const statusDelta = (STATUS_PRIORITY_ORDER[right.status] || 0) - (STATUS_PRIORITY_ORDER[left.status] || 0);
    if (statusDelta !== 0) {
      return statusDelta;
    }

    const severityDelta = (SEVERITY_ORDER[right.severity] || 0) - (SEVERITY_ORDER[left.severity] || 0);
    if (severityDelta !== 0) {
      return severityDelta;
    }

    return safeStr(right.triggeredAt || right.triggered_at).localeCompare(
      safeStr(left.triggeredAt || left.triggered_at),
    );
  });
}

export function formatAlertTime(isoStr) {
  if (!isoStr) {
    return '-';
  }

  const date = new Date(isoStr);
  if (Number.isNaN(date.getTime())) {
    return '-';
  }

  return `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}
