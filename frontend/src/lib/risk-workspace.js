const BRAND = '#2457c5';
const BRAND_SOFT = '#9db7f2';
const RISK = '#c4493d';
const WARNING = '#b7791f';
const SUCCESS = '#21815c';
const MUTED = '#7d8798';

const toNumber = (value) => {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : 0;
};

const formatShortDate = (raw) => {
  if (!raw || typeof raw !== 'string') {
    return '--';
  }

  const parts = raw.split('-');
  if (parts.length !== 3) {
    return raw;
  }

  return `${parts[1]}-${parts[2]}`;
};

const riskLabelMap = {
  low: '低',
  medium: '中',
  high: '高',
  critical: '严重',
};

const riskToneMap = {
  low: SUCCESS,
  medium: WARNING,
  high: RISK,
  critical: '#8d2f27',
};

export function normalizeRiskAnalytics(payload) {
  const data = payload?.data && typeof payload.data === 'object' ? payload.data : payload || {};
  const summary = data?.summary || {};

  return {
    summary: {
      total_events: toNumber(summary.total_events),
      high_risk_events: toNumber(summary.high_risk_events),
      pending_reviews: toNumber(summary.pending_reviews),
      unique_companies: toNumber(summary.unique_companies),
      document_count: toNumber(summary.document_count),
    },
    risk_level_distribution: Array.isArray(data.risk_level_distribution) ? data.risk_level_distribution : [],
    risk_type_distribution: Array.isArray(data.risk_type_distribution) ? data.risk_type_distribution : [],
    review_status_distribution: Array.isArray(data.review_status_distribution) ? data.review_status_distribution : [],
    trend: Array.isArray(data.trend) ? data.trend : [],
    top_companies: Array.isArray(data.top_companies) ? data.top_companies : [],
  };
}

export function buildRiskLevelChartOption(analytics) {
  const rows = analytics?.risk_level_distribution || [];
  return {
    color: rows.map((row) => riskToneMap[row.key] || BRAND),
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, icon: 'circle' },
    series: [
      {
        type: 'pie',
        radius: ['48%', '72%'],
        center: ['50%', '46%'],
        label: { color: MUTED },
        data: rows.map((row) => ({
          name: riskLabelMap[row.key] || row.key,
          value: toNumber(row.value),
        })),
      },
    ],
  };
}

export function buildRiskTypeChartOption(analytics) {
  const rows = analytics?.risk_type_distribution || [];
  return {
    color: [BRAND],
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 12, right: 18, top: 18, bottom: 18, containLabel: true },
    xAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: MUTED },
      splitLine: { lineStyle: { color: '#e9edf3' } },
    },
    yAxis: {
      type: 'category',
      data: rows.map((row) => row.key),
      axisLabel: { color: MUTED },
      axisLine: { lineStyle: { color: '#d9e1eb' } },
    },
    series: [
      {
        type: 'bar',
        barWidth: 16,
        itemStyle: {
          borderRadius: [0, 8, 8, 0],
          color: BRAND_SOFT,
        },
        data: rows.map((row) => toNumber(row.value)),
      },
    ],
  };
}

export function buildRiskTrendChartOption(analytics) {
  const rows = analytics?.trend || [];
  return {
    color: [BRAND],
    tooltip: { trigger: 'axis' },
    grid: { left: 12, right: 18, top: 28, bottom: 24, containLabel: true },
    xAxis: {
      type: 'category',
      data: rows.map((row) => formatShortDate(row.date)),
      axisLine: { lineStyle: { color: '#d9e1eb' } },
      axisLabel: { color: MUTED },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: MUTED },
      splitLine: { lineStyle: { color: '#e9edf3' } },
    },
    series: [
      {
        name: '风险事件',
        type: 'line',
        smooth: true,
        symbolSize: 8,
        data: rows.map((row) => toNumber(row.value)),
      },
    ],
  };
}
