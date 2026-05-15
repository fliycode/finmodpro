import * as XLSX from 'xlsx';

const riskLevelLabels = {
  critical: '严重',
  high: '高',
  medium: '中',
  low: '低',
};

const normalizeInlineText = (value, fallback = '—') => {
  const normalized = String(value || '')
    .replace(/\s+/g, ' ')
    .trim();

  return normalized || fallback;
};

const sanitizeFilenameSegment = (value) => {
  const normalized = String(value || '')
    .trim()
    .replace(/\.[^.]+$/, '')
    .replace(/[\\/:*?"<>|]+/g, '-')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');

  return normalized || 'risk-summary';
};

const formatExportTime = (value) => {
  const date = value instanceof Date ? value : new Date(value || Date.now());
  if (Number.isNaN(date.getTime())) {
    return '';
  }

  const pad = (part) => String(part).padStart(2, '0');

  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

const formatRiskLevel = (level) => riskLevelLabels[level] || normalizeInlineText(level, '未标记');

export function buildRiskSummaryExportDownload({
  documentTitle = '',
  statusText = '',
  detail = '',
  groupedResults = [],
  resultEvents = [],
  createdCount = 0,
  exportedAt = new Date(),
} = {}) {
  const title = normalizeInlineText(documentTitle, '当前文档');
  const grouped = Array.isArray(groupedResults) ? groupedResults : [];
  const events = Array.isArray(resultEvents) ? resultEvents : [];
  const timestamp = formatExportTime(exportedAt);
  const eventCount = events.length;
  const resolvedCreatedCount = Number.isFinite(Number(createdCount))
    ? Math.max(0, Number(createdCount))
    : eventCount;

  const summaryRows = [
    ['风险提取结果'],
    [],
    ['文档', title],
    ['导出时间', timestamp || '未记录'],
    ['提取状态', normalizeInlineText(statusText, '已完成')],
    ['风险类别', `${grouped.length} 类`],
    ['风险事件', `${eventCount} 条`],
    ['本次新增', `${resolvedCreatedCount} 条`],
  ];

  if (String(detail || '').trim()) {
    summaryRows.push(['备注', normalizeInlineText(detail)]);
  }

  summaryRows.push([], ['风险摘要']);

  if (!grouped.length) {
    summaryRows.push(['当前文档未识别到风险事件。']);
  } else {
    summaryRows.push(['序号', '风险分类', '风险等级', '事件数量', '摘要', '证据']);
    grouped.forEach((item, index) => {
      summaryRows.push([
        index + 1,
        normalizeInlineText(item?.key, '未分类风险'),
        formatRiskLevel(item?.dominantLevel),
        Number.isFinite(Number(item?.count)) ? Number(item.count) : 0,
        normalizeInlineText(item?.summary, '暂无摘要'),
        normalizeInlineText(item?.evidence, '暂无证据文本。'),
      ]);
    });
  }

  const eventRows = [['原始事件']];
  if (!events.length) {
    eventRows.push(['无原始事件记录。']);
  } else {
    eventRows.push(['序号', '风险等级', '风险类型', '公司', '日期', '摘要', '证据', '风险判断', '复核状态', '监控点', '引用']);
    events.forEach((item, index) => {
      const watchpoints = Array.isArray(item?.watchpoints) ? item.watchpoints.join('；') : '';
      const citations = Array.isArray(item?.citations)
        ? item.citations.map((e) => normalizeInlineText(e?.page_label || e?.section_label || `chunk ${e?.chunk_id || ''}`)).join('；')
        : '';
      eventRows.push([
        index + 1,
        formatRiskLevel(item?.risk_level),
        normalizeInlineText(item?.risk_type, '未分类风险'),
        normalizeInlineText(item?.company_name, ''),
        normalizeInlineText(item?.event_date, ''),
        normalizeInlineText(item?.summary, '暂无摘要'),
        normalizeInlineText(item?.evidence_text || item?.summary, '暂无证据文本。'),
        normalizeInlineText(item?.why_it_matters, '待补充'),
        item?.requires_human_review ? '建议人工复核' : '可直接进入报告',
        watchpoints,
        citations,
      ]);
    });
  }

  const workbook = XLSX.utils.book_new();

  const wsData = [...summaryRows, [], ...eventRows];
  const worksheet = XLSX.utils.aoa_to_sheet(wsData);
  worksheet['!cols'] = [
    { wch: 6 }, { wch: 18 }, { wch: 10 }, { wch: 10 }, { wch: 6 }, { wch: 40 }, { wch: 50 },
    { wch: 40 }, { wch: 14 }, { wch: 30 }, { wch: 20 },
  ];
  XLSX.utils.book_append_sheet(workbook, worksheet, '风险提取');

  const xlsxBuffer = XLSX.write(workbook, { bookType: 'xlsx', type: 'array' });
  const uint8Array = new Uint8Array(xlsxBuffer);

  return {
    filename: `${sanitizeFilenameSegment(title)}-risk-summary.xlsx`,
    contentType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    content: uint8Array,
  };
}

export function downloadTextFile({ filename, content, contentType = 'text/plain;charset=utf-8' } = {}) {
  if (typeof window === 'undefined') {
    return;
  }

  const blob = new Blob([content || ''], { type: contentType });
  const url = window.URL.createObjectURL(blob);
  const link = window.document.createElement('a');
  link.href = url;
  link.download = filename || 'download.txt';
  window.document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
