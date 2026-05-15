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

  const lines = [
    '# 风险提取结果',
    '',
    `- 文档：${title}`,
    `- 导出时间：${timestamp || '未记录'}`,
    `- 提取状态：${normalizeInlineText(statusText, '已完成')}`,
    `- 风险类别：${grouped.length} 类`,
    `- 风险事件：${eventCount} 条`,
    `- 本次新增：${resolvedCreatedCount} 条`,
  ];

  if (String(detail || '').trim()) {
    lines.push(`- 备注：${normalizeInlineText(detail)}`);
  }

  lines.push('', '## 风险摘要', '');

  if (!grouped.length) {
    lines.push('当前文档未识别到风险事件。', '');
  } else {
    grouped.forEach((item, index) => {
      lines.push(
        `### ${index + 1}. ${normalizeInlineText(item?.key, '未分类风险')}`,
        `- 风险等级：${formatRiskLevel(item?.dominantLevel)}`,
        `- 事件数量：${Number.isFinite(Number(item?.count)) ? Number(item.count) : 0} 条`,
        `- 摘要：${normalizeInlineText(item?.summary, '暂无摘要')}`,
        `- 证据：${normalizeInlineText(item?.evidence, '暂无证据文本。')}`,
        '',
      );
    });
  }

  lines.push('## 原始事件', '');

  if (!events.length) {
    lines.push('无原始事件记录。');
  } else {
    events.forEach((item, index) => {
      const meta = [
        formatRiskLevel(item?.risk_level),
        normalizeInlineText(item?.risk_type, '未分类风险'),
      ];

      if (String(item?.company_name || '').trim()) {
        meta.push(normalizeInlineText(item.company_name));
      }

      if (String(item?.event_date || '').trim()) {
        meta.push(normalizeInlineText(item.event_date));
      }

      lines.push(
        `${index + 1}. ${meta.join(' / ')}`,
        `   - 摘要：${normalizeInlineText(item?.summary, '暂无摘要')}`,
        `   - 证据：${normalizeInlineText(item?.evidence_text || item?.summary, '暂无证据文本。')}`,
        `   - 风险判断：${normalizeInlineText(item?.why_it_matters, '待补充')}`,
        `   - 复核状态：${item?.requires_human_review ? '建议人工复核' : '可直接进入报告'}`,
      );
      if (Array.isArray(item?.watchpoints) && item.watchpoints.length) {
        lines.push(`   - 监控点：${item.watchpoints.map((entry) => normalizeInlineText(entry)).join('；')}`);
      }
      if (Array.isArray(item?.citations) && item.citations.length) {
        lines.push(`   - 引用：${item.citations.map((entry) => normalizeInlineText(entry?.page_label || entry?.section_label || `chunk ${entry?.chunk_id || ''}`)).join('；')}`);
      }
    });
  }

  return {
    filename: `${sanitizeFilenameSegment(title)}-risk-summary.md`,
    contentType: 'text/markdown;charset=utf-8',
    content: lines.join('\n'),
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
