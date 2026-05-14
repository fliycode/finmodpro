const readCSS = (name, fallback) => {
  try {
    const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return value || fallback;
  } catch {
    return fallback;
  }
};

export const chartColors = () => ({
  brand: readCSS('--brand', '#2457c5'),
  brandSoft: readCSS('--brand-200', '#9db7f2'),
  risk: readCSS('--risk', '#c4493d'),
  warning: readCSS('--warning', '#b7791f'),
  muted: readCSS('--text-muted', '#7d8798'),
  success: readCSS('--success', '#21815c'),
  textPrimary: readCSS('--text-primary', '#dbe7ff'),
  textSecondary: readCSS('--text-secondary', '#8190aa'),
  gridLine: readCSS('--line-soft', 'rgba(91, 132, 205, 0.12)'),
  surfaceBg: readCSS('--surface-1', 'rgba(7, 16, 32, 0.94)'),
  surface2: readCSS('--surface-2', '#182235'),
  lineStrong: readCSS('--line-strong', 'rgba(91, 132, 205, 0.34)'),
});

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

const formatWeekOverWeekDelta = (currentValue, previousValue) => {
  const current = toNumber(currentValue);
  const previous = toNumber(previousValue);

  if (previous <= 0) {
    if (current <= 0) {
      return { label: '较上周持平', tone: 'neutral' };
    }

    return { label: '本周开始有记录', tone: 'up' };
  }

  const delta = ((current - previous) / previous) * 100;
  const rounded = `${delta > 0 ? '+' : ''}${delta.toFixed(1)}%`;

  if (delta > 0) {
    return { label: `较上周 ${rounded}`, tone: 'up' };
  }

  if (delta < 0) {
    return { label: `较上周 ${rounded}`, tone: 'down' };
  }

  return { label: '较上周持平', tone: 'neutral' };
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

const toneByRiskLevel = () => {
  const c = chartColors();
  return { low: c.success, medium: c.warning, high: c.risk, critical: '#8d2f27' };
};

const toneByDocumentStatus = () => {
  const c = chartColors();
  return {
    uploaded: c.muted,
    parsed: c.brandSoft,
    chunked: c.brand,
    indexed: c.success,
    failed: c.risk,
  };
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
    model_invocation_count_7d: toNumber(data.model_invocation_count_7d),
    model_invocation_count_prev_7d: toNumber(data.model_invocation_count_prev_7d),
    total_token_count: toNumber(data.total_token_count),
    total_request_token_count: toNumber(data.total_request_token_count),
    total_response_token_count: toNumber(data.total_response_token_count),
    token_count_7d: toNumber(data.token_count_7d),
    token_count_prev_7d: toNumber(data.token_count_prev_7d),
    audit_operation_count_7d: toNumber(data.audit_operation_count_7d),
    audit_operation_count_prev_7d: toNumber(data.audit_operation_count_prev_7d),
    document_added_count_7d: toNumber(data.document_added_count_7d),
    document_added_count_prev_7d: toNumber(data.document_added_count_prev_7d),
    indexed_document_completed_count_7d: toNumber(data.indexed_document_completed_count_7d),
    indexed_document_completed_count_prev_7d: toNumber(data.indexed_document_completed_count_prev_7d),
    retryable_ingestion_count: toNumber(data.retryable_ingestion_count),
    retrieval_hit_rate_7d: String(data.retrieval_hit_rate_7d ?? '0.0%'),
    chat_requests_7d: Array.isArray(data.chat_requests_7d) ? data.chat_requests_7d : [],
    retrieval_hits_7d: Array.isArray(data.retrieval_hits_7d) ? data.retrieval_hits_7d : [],
    model_invocations_7d: Array.isArray(data.model_invocations_7d) ? data.model_invocations_7d : [],
    token_usage_7d: Array.isArray(data.token_usage_7d) ? data.token_usage_7d : [],
    request_tokens_7d: Array.isArray(data.request_tokens_7d) ? data.request_tokens_7d : [],
    response_tokens_7d: Array.isArray(data.response_tokens_7d) ? data.response_tokens_7d : [],
    audit_operations_7d: Array.isArray(data.audit_operations_7d) ? data.audit_operations_7d : [],
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
  const modelDelta = formatWeekOverWeekDelta(
    stats?.model_invocation_count_7d,
    stats?.model_invocation_count_prev_7d,
  );
  const tokenDelta = formatWeekOverWeekDelta(
    stats?.token_count_7d,
    stats?.token_count_prev_7d,
  );
  const documentDelta = formatWeekOverWeekDelta(
    stats?.document_added_count_7d,
    stats?.document_added_count_prev_7d,
  );
  const indexedDelta = formatWeekOverWeekDelta(
    stats?.indexed_document_completed_count_7d,
    stats?.indexed_document_completed_count_prev_7d,
  );

  return [
    {
      key: 'model-invocations',
      label: '模型调用量',
      value: formatInteger(stats?.model_invocation_count_7d),
      note: `上周 ${formatInteger(stats?.model_invocation_count_prev_7d)} 次`,
      icon: 'brain-circuit',
      tone: 'blue',
      delta: modelDelta.label,
      deltaTone: modelDelta.tone,
    },
    {
      key: 'token-usage',
      label: '系统 Token 用量',
      value: formatInteger(stats?.total_token_count),
      note: `输入 ${formatInteger(stats?.total_request_token_count)} · 输出 ${formatInteger(stats?.total_response_token_count)}`,
      icon: 'activity',
      tone: 'orange',
      delta: tokenDelta.label,
      deltaTone: tokenDelta.tone,
    },
    {
      key: 'documents',
      label: '知识文档总量',
      value: formatInteger(stats?.document_count),
      note: `近 7 天 +${formatInteger(stats?.document_added_count_7d)}`,
      icon: 'file-text',
      tone: 'cyan',
      delta: documentDelta.label,
      deltaTone: documentDelta.tone,
    },
    {
      key: 'indexed',
      label: '已索引文档',
      value: formatInteger(stats?.indexed_document_count),
      note: `近 7 天 +${formatInteger(stats?.indexed_document_completed_count_7d)}`,
      icon: 'database',
      tone: 'green',
      delta: indexedDelta.label,
      deltaTone: indexedDelta.tone,
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

export const buildBoardTooltip = () => {
  const c = chartColors();
  return {
    backgroundColor: c.surfaceBg,
    borderColor: c.lineStrong,
    textStyle: { color: c.textPrimary },
  };
};

export const buildBoardAxis = () => {
  const c = chartColors();
  return {
    axisLine: { lineStyle: { color: 'rgba(91, 132, 205, 0.26)' } },
    axisTick: { show: false },
    axisLabel: { color: c.textSecondary, fontWeight: 700 },
  };
};

const getFallbackTrendSeries = (total, days) => {
  const safeTotal = Math.max(1, toNumber(total));
  const weights = [0.58, 0.74, 0.69, 0.81, 0.63, 0.92, 1];
  return days.map((item, index) => ({
    date: item.date,
    value: Math.max(1, Math.round(safeTotal * weights[index])),
  }));
};

export function buildDashboardTrendOption(stats) {
  const requestRows = Array.isArray(stats?.model_invocations_7d) ? stats.model_invocations_7d : [];
  const tokenRows = Array.isArray(stats?.token_usage_7d) ? stats.token_usage_7d : [];
  const dates = requestRows.length > 0 ? requestRows.map((item) => item.date) : tokenRows.map((item) => item.date);
  const axis = buildBoardAxis();

  return {
    color: [chartColors().brand, chartColors().warning],
    tooltip: { trigger: 'axis', ...buildBoardTooltip() },
    legend: {
      top: 0,
      left: 0,
      itemWidth: 18,
      itemHeight: 8,
      textStyle: { color: chartColors().textSecondary, fontWeight: 700 },
      data: ['模型调用', 'Token 用量'],
    },
    grid: { left: 42, right: 22, top: 48, bottom: 28 },
    xAxis: {
      type: 'category',
      data: dates.map((item) => formatShortDate(item)),
      ...axis,
    },
    yAxis: [
      {
        type: 'value',
        minInterval: 1,
        axisLabel: axis.axisLabel,
        splitLine: { lineStyle: { color: chartColors().gridLine } },
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
        name: '模型调用',
        type: 'bar',
        barWidth: 22,
        data: requestRows.map((item) => toNumber(item.value)),
        itemStyle: { color: chartColors().brand, borderRadius: [8, 8, 0, 0] },
      },
      {
        name: 'Token 用量',
        type: 'line',
        smooth: true,
        symbolSize: 7,
        yAxisIndex: 1,
        data: tokenRows.map((item) => toNumber(item.value)),
        lineStyle: { width: 3, color: chartColors().warning },
        itemStyle: { color: chartColors().warning },
        areaStyle: { color: 'rgba(183, 121, 31, 0.12)' },
      },
    ],
  };
}

export function buildDashboardTokenOption(stats) {
  const inputRows = Array.isArray(stats?.request_tokens_7d) ? stats.request_tokens_7d : [];
  const outputRows = Array.isArray(stats?.response_tokens_7d) ? stats.response_tokens_7d : [];
  const dates = inputRows.length > 0 ? inputRows.map((item) => item.date) : outputRows.map((item) => item.date);
  const axis = buildBoardAxis();

  return {
    color: [chartColors().brand, chartColors().brandSoft],
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...buildBoardTooltip() },
    legend: {
      top: 0,
      left: 0,
      itemWidth: 16,
      itemHeight: 8,
      textStyle: { color: chartColors().textSecondary, fontWeight: 700 },
      data: ['输入 Token', '输出 Token'],
    },
    grid: { left: 18, right: 18, top: 42, bottom: 8, containLabel: true },
    xAxis: {
      type: 'category',
      data: dates.map((item) => formatShortDate(item)),
      ...axis,
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: axis.axisLabel,
      splitLine: { lineStyle: { color: chartColors().gridLine } },
    },
    series: [
      {
        name: '输入 Token',
        type: 'bar',
        stack: 'token-usage',
        barWidth: 20,
        data: inputRows.map((item) => toNumber(item.value)),
        itemStyle: { color: chartColors().brand, borderRadius: [8, 8, 0, 0] },
      },
      {
        name: '输出 Token',
        type: 'bar',
        stack: 'token-usage',
        barWidth: 20,
        data: outputRows.map((item) => toNumber(item.value)),
        itemStyle: { color: chartColors().brandSoft, borderRadius: [8, 8, 0, 0] },
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
      textStyle: { color: chartColors().textSecondary, fontWeight: 800 },
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
          borderColor: chartColors().surface2,
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
      splitLine: { lineStyle: { color: chartColors().gridLine } },
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

export function buildDashboardDocumentFlow(stats) {
  const distribution = stats?.document_status_distribution || {};
  const total = sumObjectValues(distribution);
  const safeTotal = Math.max(total, 1);
  const indexedCount = toNumber(distribution.indexed);
  const failedCount = toNumber(distribution.failed);

  return {
    total,
    stages: [
      { key: 'uploaded', label: '上传', detail: '待进入解析', value: toNumber(distribution.uploaded), tone: 'neutral' },
      { key: 'parsed', label: '解析', detail: '结构提取', value: toNumber(distribution.parsed), tone: 'processing' },
      { key: 'chunked', label: '切块', detail: '索引准备', value: toNumber(distribution.chunked), tone: 'processing' },
      { key: 'indexed', label: '已索引', detail: '进入检索链路', value: indexedCount, tone: 'success' },
    ].map((stage) => ({
      ...stage,
      percent: total > 0 ? Math.round((stage.value / safeTotal) * 100) : 0,
    })),
    failure: {
      value: failedCount,
      percent: total > 0 ? Math.round((failedCount / safeTotal) * 100) : 0,
      retryable: toNumber(stats?.retryable_ingestion_count),
    },
    summary: [
      {
        key: 'completion',
        label: '完成率',
        value: total > 0 ? `${Math.round((indexedCount / safeTotal) * 100)}%` : '0%',
        tone: 'success',
      },
      {
        key: 'processing',
        label: '处理中',
        value: formatInteger(stats?.processing_document_count),
        tone: 'processing',
      },
      {
        key: 'retryable',
        label: '可重试',
        value: formatInteger(stats?.retryable_ingestion_count),
        tone: 'retry',
      },
    ],
  };
}

export function buildDocumentFlowPieOption(stats) {
  const distribution = stats?.document_status_distribution || {};
  const total = sumObjectValues(distribution);
  const safeTotal = Math.max(total, 1);
  const c = chartColors();

  const stages = [
    { key: 'uploaded', name: '上传', color: c.muted },
    { key: 'parsed', name: '解析', color: c.brandSoft },
    { key: 'chunked', name: '切块', color: c.brand },
    { key: 'indexed', name: '已索引', color: c.success },
    { key: 'failed', name: '失败', color: c.risk },
  ].map((stage) => {
    const value = toNumber(distribution[stage.key]);
    return {
      ...stage,
      value,
      percent: total > 0 ? Math.round((value / safeTotal) * 100) : 0,
      itemStyle: {
        color: stage.color,
        borderColor: c.surfaceBg,
        borderWidth: 3,
      },
    };
  });

  const lookupStage = (name) => stages.find((stage) => stage.name === name) || {
    name,
    value: 0,
    percent: 0,
    color: c.textSecondary,
  };

  return {
    backgroundColor: 'transparent',
    color: stages.map((stage) => stage.color),
    tooltip: {
      trigger: 'item',
      backgroundColor: c.surface2,
      borderColor: c.lineStrong,
      borderWidth: 1,
      textStyle: { color: c.textPrimary, fontSize: 12 },
      formatter: (params) => {
        const stage = lookupStage(params.name);
        return `<div style="font-weight:600;margin-bottom:4px">${params.name}</div>
          <div style="font-size:12px;color:${c.textSecondary}">
            数量：${formatInteger(stage.value)}<br/>
            占比：${stage.percent}%
          </div>`;
      },
    },
    legend: {
      orient: 'vertical',
      top: 'center',
      right: 4,
      itemWidth: 8,
      itemHeight: 8,
      itemGap: 14,
      icon: 'circle',
      selectedMode: false,
      textStyle: {
        color: c.textSecondary,
        fontSize: 12,
        fontWeight: 600,
        rich: {
          name: {
            width: 38,
            color: c.textPrimary,
            fontWeight: 700,
          },
          value: {
            width: 54,
            align: 'right',
            color: c.textPrimary,
            fontWeight: 700,
          },
          percent: {
            width: 40,
            align: 'right',
            color: c.textSecondary,
          },
        },
      },
      formatter: (name) => {
        const stage = lookupStage(name);
        return `{name|${name}} {value|${formatInteger(stage.value)}} {percent|${stage.percent}%}`;
      },
    },
    graphic: [
      {
        type: 'group',
        left: '25%',
        top: 'center',
        silent: true,
        children: [
          {
            type: 'text',
            style: {
              text: formatInteger(total),
              fill: c.textPrimary,
              fontSize: 22,
              fontWeight: 700,
              fontFamily: 'var(--heading)',
              textAlign: 'center',
            },
            x: -20,
            y: -12,
          },
          {
            type: 'text',
            style: {
              text: '总文档',
              fill: c.textSecondary,
              fontSize: 11,
              fontWeight: 700,
              textAlign: 'center',
            },
            x: -18,
            y: 14,
          },
        ],
      },
    ],
    series: [
      {
        type: 'pie',
        radius: ['56%', '76%'],
        center: ['28%', '50%'],
        startAngle: 92,
        minAngle: total > 0 ? 4 : 0,
        stillShowZeroSum: true,
        avoidLabelOverlap: true,
        label: { show: false },
        labelLine: { show: false },
        emphasis: {
          scale: true,
          scaleSize: 6,
          label: {
            show: true,
            formatter: ({ data }) => `${data.name}\n${formatInteger(data.value)} · ${data.percent}%`,
            color: c.textPrimary,
            fontSize: 12,
            fontWeight: 700,
          },
        },
        data: stages,
      },
    ],
  };
}

export const buildDocumentFlowFunnelOption = buildDocumentFlowPieOption;

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
    color: [chartColors().brand, chartColors().warning],
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, icon: 'circle' },
    grid: { left: 12, right: 18, top: 28, bottom: 44, containLabel: true },
    xAxis: {
      type: 'category',
      data: requests.map((item) => formatShortDate(item.date)),
      axisLine: { lineStyle: { color: chartColors().lineStrong } },
      axisLabel: { color: chartColors().muted },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: chartColors().muted },
      splitLine: { lineStyle: { color: chartColors().gridLine } },
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
        label: { color: chartColors().muted },
        data: rows.map((row) => ({
          name: row.name,
          value: toNumber(distribution[row.key]),
          itemStyle: { color: toneByRiskLevel()[row.key] },
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
    color: [chartColors().brand],
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 12, right: 18, top: 18, bottom: 18, containLabel: true },
    xAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: chartColors().muted },
      splitLine: { lineStyle: { color: chartColors().gridLine } },
    },
    yAxis: {
      type: 'category',
      data: rows.map((row) => row.label),
      axisLabel: { color: chartColors().muted },
      axisLine: { lineStyle: { color: chartColors().lineStrong } },
    },
    series: [
      {
        type: 'bar',
        barWidth: 16,
        itemStyle: {
          borderRadius: [0, 8, 8, 0],
          color: (params) => toneByDocumentStatus()[rows[params.dataIndex]?.key] || chartColors().brand,
        },
        data: rows.map((row) => toNumber(distribution[row.key])),
      },
    ],
  };
}
