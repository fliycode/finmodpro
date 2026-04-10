const BRAND = '#2457c5';
const BRAND_SOFT = '#9db7f2';
const RISK = '#c4493d';
const WARNING = '#b7791f';
const MUTED = '#7d8798';
const SUCCESS = '#21815c';

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

const toNumber = (value) => {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : 0;
};

const toneByRiskLevel = {
  low: SUCCESS,
  medium: WARNING,
  high: RISK,
  critical: '#8d2f27',
};

const toneByDocumentStatus = {
  uploaded: MUTED,
  parsed: BRAND_SOFT,
  chunked: BRAND,
  indexed: SUCCESS,
  failed: RISK,
};

export function normalizeDashboardPayload(payload) {
  const data = payload?.data && typeof payload.data === 'object' ? payload.data : payload || {};

  return {
    knowledgebase_count: toNumber(data.knowledgebase_count),
    document_count: toNumber(data.document_count),
    indexed_document_count: toNumber(data.indexed_document_count),
    processing_document_count: toNumber(data.processing_document_count),
    failed_document_count: toNumber(data.failed_document_count),
    risk_event_count: toNumber(data.risk_event_count),
    pending_risk_event_count: toNumber(data.pending_risk_event_count),
    high_risk_event_count: toNumber(data.high_risk_event_count),
    active_model_count: toNumber(data.active_model_count),
    chat_request_count_24h: toNumber(data.chat_request_count_24h),
    retrieval_hit_rate_7d: String(data.retrieval_hit_rate_7d ?? '0.0%'),
    chat_requests_7d: Array.isArray(data.chat_requests_7d) ? data.chat_requests_7d : [],
    retrieval_hits_7d: Array.isArray(data.retrieval_hits_7d) ? data.retrieval_hits_7d : [],
    risk_level_distribution: {
      low: toNumber(data?.risk_level_distribution?.low),
      medium: toNumber(data?.risk_level_distribution?.medium),
      high: toNumber(data?.risk_level_distribution?.high),
      critical: toNumber(data?.risk_level_distribution?.critical),
    },
    document_status_distribution: {
      uploaded: toNumber(data?.document_status_distribution?.uploaded),
      parsed: toNumber(data?.document_status_distribution?.parsed),
      chunked: toNumber(data?.document_status_distribution?.chunked),
      indexed: toNumber(data?.document_status_distribution?.indexed),
      failed: toNumber(data?.document_status_distribution?.failed),
    },
    recent_activity: Array.isArray(data.recent_activity) ? data.recent_activity : [],
  };
}

export function summarizeOperationalPosture(stats) {
  const pendingRisk = toNumber(stats?.pending_risk_event_count);
  const failedDocuments = toNumber(stats?.failed_document_count);
  const hitRate = parseFloat(String(stats?.retrieval_hit_rate_7d ?? '0').replace('%', '')) || 0;

  if (pendingRisk > 0 || failedDocuments > 0) {
    return {
      tone: 'risk',
      label: '优先处理待审风险与失败入库',
      summary: '当前存在需要人工跟进的审核或索引异常，建议先清理积压。',
    };
  }

  if (hitRate < 70) {
    return {
      tone: 'warning',
      label: '重点关注检索命中率',
      summary: '问答链路可用，但近 7 天命中率偏低，建议检查知识资产与召回质量。',
    };
  }

  return {
    tone: 'info',
    label: '平台运行平稳',
    summary: '当前没有明显积压，适合继续推进知识治理与模型运维。',
  };
}

export function buildTrendChartOption(stats) {
  const requests = Array.isArray(stats?.chat_requests_7d) ? stats.chat_requests_7d : [];
  const hits = Array.isArray(stats?.retrieval_hits_7d) ? stats.retrieval_hits_7d : [];

  return {
    color: [BRAND, WARNING],
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, icon: 'circle' },
    grid: { left: 12, right: 18, top: 28, bottom: 44, containLabel: true },
    xAxis: {
      type: 'category',
      data: requests.map((item) => formatShortDate(item.date)),
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
        name: '问答请求',
        type: 'line',
        smooth: true,
        symbolSize: 8,
        data: requests.map((item) => toNumber(item.value)),
      },
      {
        name: '检索命中',
        type: 'line',
        smooth: true,
        symbolSize: 8,
        data: hits.map((item) => toNumber(item.value)),
      },
    ],
  };
}

export function buildRiskDistributionOption(stats) {
  const distribution = stats?.risk_level_distribution || {};
  const rows = [
    { name: '低', key: 'low' },
    { name: '中', key: 'medium' },
    { name: '高', key: 'high' },
    { name: '严重', key: 'critical' },
  ];

  return {
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, icon: 'circle' },
    series: [
      {
        type: 'pie',
        radius: ['48%', '72%'],
        center: ['50%', '46%'],
        label: { color: MUTED },
        data: rows.map((row) => ({
          name: row.name,
          value: toNumber(distribution[row.key]),
          itemStyle: { color: toneByRiskLevel[row.key] },
        })),
      },
    ],
  };
}

export function buildDocumentStatusOption(stats) {
  const distribution = stats?.document_status_distribution || {};
  const rows = [
    { label: '上传', key: 'uploaded' },
    { label: '解析', key: 'parsed' },
    { label: '切块', key: 'chunked' },
    { label: '已索引', key: 'indexed' },
    { label: '失败', key: 'failed' },
  ];

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
      data: rows.map((row) => row.label),
      axisLabel: { color: MUTED },
      axisLine: { lineStyle: { color: '#d9e1eb' } },
    },
    series: [
      {
        type: 'bar',
        barWidth: 16,
        itemStyle: {
          borderRadius: [0, 8, 8, 0],
          color: (params) => toneByDocumentStatus[rows[params.dataIndex]?.key] || BRAND,
        },
        data: rows.map((row) => toNumber(distribution[row.key])),
      },
    ],
  };
}
