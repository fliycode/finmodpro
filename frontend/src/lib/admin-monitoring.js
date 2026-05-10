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

export const METRIC_OPTIONS = [
  { value: 'cpu_percent', label: 'CPU 使用率' },
  { value: 'memory_percent', label: '内存使用率' },
  { value: 'disk_percent', label: '磁盘使用率' },
  { value: 'celery_worker_count', label: 'Celery Worker 数' },
  { value: 'db_healthy', label: '数据库状态' },
  { value: 'redis_healthy', label: 'Redis 状态' },
  { value: 'milvus_healthy', label: 'Milvus 状态' },
];
