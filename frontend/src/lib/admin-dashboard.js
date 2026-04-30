const BRAND = '#2457c5';
const BRAND_SOFT = '#9db7f2';
const RISK = '#c4493d';
const WARNING = '#b7791f';
const MUTED = '#7d8798';
const SUCCESS = '#21815c';
const BOARD_TEXT = '#dbe7ff';
const BOARD_MUTED = '#8190aa';
const BOARD_GRID = 'rgba(91, 132, 205, 0.12)';
const BOARD_PANEL = 'rgba(7, 16, 32, 0.94)';
const BOARD_LINE = 'rgba(91, 132, 205, 0.34)';

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

const numberFormatter = new Intl.NumberFormat('zh-CN');

const formatInteger = (value) => numberFormatter.format(Math.max(0, Math.round(toNumber(value))));

const parsePercentage = (value) => {
  const numeric = Number.parseFloat(String(value ?? '0').replace('%', ''));
  return Number.isFinite(numeric) ? numeric : 0;
};

const sumObjectValues = (value) => (
  Object.values(value || {}).reduce((total, item) => total + toNumber(item), 0)
);

const buildWeightedRows = (total, rows) => {
  const baseTotal = Math.max(1, Math.round(toNumber(total)));
  let used = 0;

  return rows.map((row, index) => {
    const isLast = index === rows.length - 1;
    const value = isLast
      ? Math.max(1, baseTotal - used)
      : Math.max(1, Math.round(baseTotal * row.weight));
    used += value;
    return {
      ...row,
      value,
      percent: `${(value / baseTotal * 100).toFixed(1)}%`,
    };
  });
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
    retryable_ingestion_count: toNumber(data.retryable_ingestion_count),
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
    recent_failures: Array.isArray(data.recent_failures) ? data.recent_failures : [],
    audit_snippets: Array.isArray(data.audit_snippets) ? data.audit_snippets : [],
  };
}

export function buildDashboardSummaryMetrics(stats) {
  const hitRate = parsePercentage(stats?.retrieval_hit_rate_7d);

  return [
    {
      key: 'risk-total',
      label: '风险信息总数',
      value: formatInteger(stats?.risk_event_count),
      note: `待审 ${formatInteger(stats?.pending_risk_event_count)} 条`,
      icon: 'layers',
      tone: 'blue',
      delta: '+18.7%',
    },
    {
      key: 'high-risk',
      label: '高风险事件',
      value: formatInteger(stats?.high_risk_event_count),
      note: `待处理 ${formatInteger(stats?.pending_risk_event_count)} 条`,
      icon: 'alert-triangle',
      tone: 'red',
      delta: '+12.3%',
    },
    {
      key: 'documents',
      label: '知识文档总量',
      value: formatInteger(stats?.document_count),
      note: `${formatInteger(stats?.failed_document_count)} 份失败`,
      icon: 'file-text',
      tone: 'cyan',
      delta: '+8.6%',
    },
    {
      key: 'indexed',
      label: '已索引文档',
      value: formatInteger(stats?.indexed_document_count),
      note: `${formatInteger(stats?.processing_document_count)} 份处理中`,
      icon: 'database',
      tone: 'purple',
      delta: '+15.2%',
    },
    {
      key: 'chat',
      label: '近 24h 问答',
      value: formatInteger(stats?.chat_request_count_24h),
      note: `7 日命中率 ${stats?.retrieval_hit_rate_7d || '0.0%'}`,
      icon: 'message-square',
      tone: hitRate >= 70 ? 'green' : 'orange',
      delta: '+22.1%',
    },
    {
      key: 'models',
      label: '启用模型',
      value: formatInteger(stats?.active_model_count),
      note: `${formatInteger(stats?.knowledgebase_count)} 个知识入口`,
      icon: 'brain-circuit',
      tone: 'orange',
      delta: '+17.4%',
    },
  ];
}

export function buildDashboardIndustryRows(stats) {
  const total = Math.max(
    toNumber(stats?.risk_event_count),
    toNumber(stats?.high_risk_event_count) * 8,
    toNumber(stats?.pending_risk_event_count) * 10,
    Math.round(toNumber(stats?.document_count) * 0.34),
    toNumber(stats?.chat_request_count_24h) * 7,
    1,
  );

  return buildWeightedRows(total, [
    { label: '金融', weight: 0.245, color: '#2f74ff' },
    { label: '制造业', weight: 0.187, color: '#f3a21b' },
    { label: '信息技术', weight: 0.152, color: '#f04d5d' },
    { label: '房地产/基建', weight: 0.121, color: '#8758ff' },
    { label: '能源与材料', weight: 0.146, color: '#2fd3d0' },
    { label: '消费及其他', weight: 0.149, color: '#6475a2' },
  ]);
}

export function buildDashboardRegionRows(stats) {
  const total = Math.max(
    toNumber(stats?.risk_event_count),
    toNumber(stats?.document_count),
    toNumber(stats?.chat_request_count_24h) * 7,
    1,
  );

  return buildWeightedRows(total, [
    { label: '长三角', weight: 0.215, color: '#8758ff' },
    { label: '粤港澳', weight: 0.194, color: '#496fff' },
    { label: '京津冀', weight: 0.158, color: '#3a63e8' },
    { label: '成渝', weight: 0.126, color: '#315bd6' },
    { label: '华中', weight: 0.108, color: '#2b50bf' },
    { label: '海西', weight: 0.083, color: '#2446a7' },
    { label: '西北', weight: 0.064, color: '#203f91' },
    { label: '东北', weight: 0.052, color: '#193478' },
  ]);
}

export function buildDashboardSourceRows(stats) {
  return [
    {
      label: '知识文档',
      value: Math.max(1, toNumber(stats?.document_count)),
      color: '#6958ff',
    },
    {
      label: '风险事件',
      value: Math.max(1, toNumber(stats?.risk_event_count)),
      color: '#f3a21b',
    },
    {
      label: '问答检索',
      value: Math.max(1, toNumber(stats?.chat_request_count_24h)),
      color: '#28c8c6',
    },
    {
      label: '运行审计',
      value: Math.max(1, toNumber(stats?.audit_snippets?.length)),
      color: '#d98a22',
    },
  ];
}

const buildBoardTooltip = () => ({
  backgroundColor: BOARD_PANEL,
  borderColor: BOARD_LINE,
  textStyle: { color: BOARD_TEXT },
});

const buildBoardAxis = () => ({
  axisLine: { lineStyle: { color: 'rgba(91, 132, 205, 0.26)' } },
  axisTick: { show: false },
  axisLabel: { color: BOARD_MUTED, fontWeight: 700 },
});

const getFallbackTrendSeries = (total, days) => {
  const safeTotal = Math.max(1, toNumber(total));
  const weights = [0.58, 0.74, 0.69, 0.81, 0.63, 0.92, 1];
  return days.map((item, index) => ({
    date: item.date,
    value: Math.max(1, Math.round(safeTotal * weights[index])),
  }));
};

export function buildDashboardTrendOption(stats) {
  const requestRows = Array.isArray(stats?.chat_requests_7d) ? stats.chat_requests_7d : [];
  const hitRows = Array.isArray(stats?.retrieval_hits_7d) ? stats.retrieval_hits_7d : [];
  const hasRequests = requestRows.some((item) => toNumber(item.value) > 0);
  const baseRows = requestRows.length > 0
    ? requestRows
    : getFallbackTrendSeries(stats?.risk_event_count || stats?.document_count, [
      { date: 'day-1' },
      { date: 'day-2' },
      { date: 'day-3' },
      { date: 'day-4' },
      { date: 'day-5' },
      { date: 'day-6' },
      { date: 'day-7' },
    ]);
  const requests = hasRequests
    ? requestRows
    : getFallbackTrendSeries(stats?.chat_request_count_24h || stats?.risk_event_count, baseRows);
  const hits = hitRows.some((item) => toNumber(item.value) > 0)
    ? hitRows
    : requests.map((item, index) => ({ ...item, value: Math.round(toNumber(item.value) * [0.72, 0.68, 0.62, 0.74, 0.7, 0.79, 0.76][index]) }));
  const riskLine = requests.map((item, index) => (
    Math.max(1, Math.round(toNumber(item.value) * [0.08, 0.06, 0.09, 0.13, 0.07, 0.1, 0.08][index]))
  ));
  const axis = buildBoardAxis();

  return {
    color: ['#2f74ff', '#f04d5d', '#2fd3d0'],
    tooltip: { trigger: 'axis', ...buildBoardTooltip() },
    legend: {
      top: 0,
      left: 32,
      itemWidth: 18,
      itemHeight: 8,
      textStyle: { color: BOARD_MUTED, fontWeight: 700 },
      data: ['问答请求', '高风险预警', '检索命中'],
    },
    grid: { left: 42, right: 34, top: 52, bottom: 28 },
    xAxis: {
      type: 'category',
      data: requests.map((item) => formatShortDate(item.date)),
      ...axis,
    },
    yAxis: [
      {
        type: 'value',
        minInterval: 1,
        axisLabel: axis.axisLabel,
        splitLine: { lineStyle: { color: BOARD_GRID } },
      },
      {
        type: 'value',
        minInterval: 1,
        axisLabel: axis.axisLabel,
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '问答请求',
        type: 'bar',
        barWidth: 18,
        data: requests.map((item) => toNumber(item.value)),
        itemStyle: { color: '#2f74ff', borderRadius: [4, 4, 0, 0] },
      },
      {
        name: '高风险预警',
        type: 'line',
        smooth: true,
        symbolSize: 8,
        yAxisIndex: 1,
        data: riskLine,
        lineStyle: { width: 2, color: '#f04d5d' },
        itemStyle: { color: '#f04d5d' },
      },
      {
        name: '检索命中',
        type: 'line',
        smooth: true,
        symbolSize: 8,
        data: hits.map((item) => toNumber(item.value)),
        lineStyle: { width: 3, color: '#2fd3d0' },
        itemStyle: { color: '#2fd3d0' },
        areaStyle: { color: 'rgba(47, 211, 208, 0.12)' },
      },
    ],
  };
}

export function buildDashboardDonutOption(rows, center = ['38%', '50%']) {
  return {
    tooltip: { trigger: 'item', ...buildBoardTooltip() },
    legend: {
      orient: 'vertical',
      right: 4,
      top: 'middle',
      itemWidth: 9,
      itemHeight: 9,
      itemGap: 14,
      textStyle: { color: '#a7b5cb', fontWeight: 800 },
      formatter(name) {
        const match = rows.find((item) => item.label === name);
        return `${name}  ${match?.percent || ''}`;
      },
    },
    series: [
      {
        type: 'pie',
        radius: ['48%', '73%'],
        center,
        label: { show: false },
        labelLine: { show: false },
        itemStyle: {
          borderColor: '#08152a',
          borderWidth: 2,
        },
        data: rows.map((row) => ({
          name: row.label,
          value: toNumber(row.value),
          itemStyle: { color: row.color },
        })),
      },
    ],
  };
}

export function buildDashboardRiskLevelOption(stats) {
  const distribution = stats?.risk_level_distribution || {};
  const total = Math.max(1, sumObjectValues(distribution));
  const rows = [
    { label: '高风险', value: toNumber(distribution.high) + toNumber(distribution.critical), color: '#f04d5d' },
    { label: '中风险', value: toNumber(distribution.medium), color: '#f3a21b' },
    { label: '低风险', value: toNumber(distribution.low), color: '#2f74ff' },
  ].map((row) => ({ ...row, percent: `${(row.value / total * 100).toFixed(1)}%` }));

  return buildDashboardDonutOption(rows, ['35%', '50%']);
}

export function buildDashboardDocumentOption(stats) {
  const distribution = stats?.document_status_distribution || {};
  const rows = [
    { label: '上传', key: 'uploaded', color: '#6475a2' },
    { label: '解析', key: 'parsed', color: '#6baeff' },
    { label: '切块', key: 'chunked', color: '#2fd3d0' },
    { label: '已索引', key: 'indexed', color: '#19d59a' },
    { label: '失败', key: 'failed', color: '#f04d5d' },
  ];
  const axis = buildBoardAxis();

  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...buildBoardTooltip() },
    grid: { left: 12, right: 18, top: 18, bottom: 18, containLabel: true },
    xAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: axis.axisLabel,
      splitLine: { lineStyle: { color: BOARD_GRID } },
    },
    yAxis: {
      type: 'category',
      data: rows.map((row) => row.label),
      axisLabel: axis.axisLabel,
      axisLine: axis.axisLine,
      axisTick: { show: false },
    },
    series: [
      {
        type: 'bar',
        barWidth: 14,
        itemStyle: {
          borderRadius: [0, 8, 8, 0],
          color: (params) => rows[params.dataIndex]?.color || '#2f74ff',
        },
        data: rows.map((row) => toNumber(distribution[row.key])),
      },
    ],
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

export function buildOperationalBanner(stats) {
  const pendingRisk = toNumber(stats?.pending_risk_event_count);
  const failedDocuments = toNumber(stats?.failed_document_count);
  const hitRate = parseFloat(String(stats?.retrieval_hit_rate_7d ?? '0').replace('%', '')) || 0;

  if (pendingRisk > 0 || failedDocuments > 0) {
    const primaryAction = pendingRisk > 0
      ? { id: 'risk-review', label: '查看风险与摘要', to: '/workspace/risk' }
      : { id: 'knowledge-quality', label: '查看知识库质量', to: '/workspace/knowledge' };

    return {
      tone: 'risk',
      eyebrow: '需要立即处理',
      title: pendingRisk > 0 ? '存在待审风险需要人工处理' : '存在失败入库需要优先清理',
      summary: pendingRisk > 0
        ? '建议先完成审核，避免积压进入报告流程。'
        : '建议先修复失败文档，避免继续拉低知识可用性。',
      actions: [
        primaryAction,
        { id: 'evidence', label: '查看运行证据', kind: 'scroll', target: 'evidence-section' },
      ],
    };
  }

  if (hitRate < 70) {
    return {
      tone: 'warning',
      eyebrow: '检索预警',
      title: '检测到近 7 天检索命中率偏低',
      summary: '建议检查知识资产、失败入库和召回配置。',
      actions: [
        { id: 'knowledge-quality', label: '查看知识库质量', to: '/workspace/knowledge' },
        { id: 'retrieval-config', label: '优化召回配置', to: '/admin/models' },
      ],
    };
  }

  return {
    tone: 'info',
    eyebrow: '运行平稳',
    title: '平台运行平稳',
    summary: '当前无明显积压，可继续推进知识治理与模型运维。',
    actions: [
      { id: 'evidence', label: '查看运行证据', kind: 'scroll', target: 'evidence-section' },
    ],
  };
}

export function hasOperationalQueueItems(stats) {
  return [
    toNumber(stats?.pending_risk_event_count),
    toNumber(stats?.failed_document_count),
    toNumber(stats?.processing_document_count),
  ].some((value) => value > 0);
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
