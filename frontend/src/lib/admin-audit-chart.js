const readCSS = (name, fallback) => {
  try {
    const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return value || fallback;
  } catch {
    return fallback;
  }
};

const chartColors = () => ({
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
  if (!raw || typeof raw !== 'string') return '--';
  const parts = raw.split('-');
  return parts.length === 3 ? `${parts[1]}-${parts[2]}` : raw;
};

const toNumber = (value) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
};

const buildBoardTooltip = () => {
  const c = chartColors();
  return {
    backgroundColor: c.surfaceBg,
    borderColor: c.lineStrong,
    textStyle: { color: c.textPrimary },
  };
};

const buildBoardAxis = () => {
  const c = chartColors();
  return {
    axisLine: { lineStyle: { color: 'rgba(91, 132, 205, 0.26)' } },
    axisTick: { show: false },
    axisLabel: { color: c.textSecondary, fontWeight: 700 },
  };
};

export function buildAuditTrendOption(dailyData) {
  const rows = Array.isArray(dailyData) ? dailyData : [];
  const c = chartColors();
  const axis = buildBoardAxis();

  return {
    color: [c.success, c.risk, c.warning, c.muted],
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...buildBoardTooltip() },
    legend: {
      top: 0,
      left: 0,
      itemWidth: 16,
      itemHeight: 8,
      textStyle: { color: c.textSecondary, fontWeight: 700 },
      data: ['成功', '失败', '已重试', '已跳过'],
    },
    grid: { left: 12, right: 18, top: 42, bottom: 8, containLabel: true },
    xAxis: {
      type: 'category',
      data: rows.map((item) => formatShortDate(item.date)),
      ...axis,
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: axis.axisLabel,
      splitLine: { lineStyle: { color: c.gridLine } },
    },
    series: [
      {
        name: '成功',
        type: 'bar',
        stack: 'audit',
        barWidth: 20,
        data: rows.map((item) => toNumber(item.succeeded ?? item.value ?? 0)),
        itemStyle: { color: c.success, borderRadius: [0, 0, 0, 0] },
      },
      {
        name: '失败',
        type: 'bar',
        stack: 'audit',
        barWidth: 20,
        data: rows.map((item) => toNumber(item.failed ?? 0)),
        itemStyle: { color: c.risk },
      },
      {
        name: '已重试',
        type: 'bar',
        stack: 'audit',
        barWidth: 20,
        data: rows.map((item) => toNumber(item.retried ?? 0)),
        itemStyle: { color: c.warning },
      },
      {
        name: '已跳过',
        type: 'bar',
        stack: 'audit',
        barWidth: 20,
        data: rows.map((item) => toNumber(item.skipped ?? 0)),
        itemStyle: { color: c.muted, borderRadius: [8, 8, 0, 0] },
      },
    ],
  };
}
