<script setup>
import { computed, onMounted, ref } from 'vue';
import { ElMessage } from 'element-plus';

import { dashboardApi } from '../api/dashboard.js';
import { riskApi } from '../api/risk.js';
import { createApiConfig } from '../api/config.js';
import {
  buildDashboardDocumentOption,
  buildDashboardDonutOption,
  buildDashboardRiskLevelOption,
  buildDashboardSourceRows,
  buildDashboardSummaryMetrics,
  buildDashboardTrendOption,
  normalizeDashboardPayload,
} from '../lib/admin-dashboard.js';
import AdminChart from './admin/AdminChart.vue';
import AppIcon from './ui/AppIcon.vue';

const dashboardStats = ref(normalizeDashboardPayload({}));
const audits = ref([]);
const health = ref(null);
const isLoading = ref(true);
const errorMsg = ref('');
const refreshedAt = ref('');

const numberFormatter = new Intl.NumberFormat('zh-CN');

const formatNumber = (value) => numberFormatter.format(Math.max(0, Math.round(Number(value) || 0)));

const formatTimestamp = (value) => {
  if (!value) {
    return '未更新';
  }

  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value));
};

const formatShortTime = (value) => {
  if (!value) {
    return '--';
  }

  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(value));
};

const formatStatus = (status) => {
  const labels = {
    queued: '排队中',
    running: '进行中',
    succeeded: '成功',
    failed: '失败',
    pending: '待处理',
    approved: '已通过',
    rejected: '已驳回',
    hit: '命中',
    miss: '未命中',
  };

  return labels[status] || status || '状态';
};

const formatAuditAction = (action) => {
  const labels = {
    'knowledgebase.ingest': '知识入库',
    'risk.extract': '风险提取',
    'risk.batch_extract': '批量提取',
    'risk.sentiment': '舆情分析',
  };
  return labels[action] || action || '审计事件';
};

const fetchData = async () => {
  isLoading.value = true;
  errorMsg.value = '';

  try {
    const [statsRes, auditRes, healthRes] = await Promise.all([
      dashboardApi.getStats(),
      dashboardApi.getAudits({ limit: 8 }).catch(() => null),
      createApiConfig().fetchJson('/api/systemcheck/health/', { method: 'GET' }).catch(() => null),
    ]);
    dashboardStats.value = normalizeDashboardPayload(statsRes);
    audits.value = Array.isArray(auditRes?.audits)
      ? auditRes.audits
      : dashboardStats.value.audit_snippets;
    health.value = healthRes?.data || healthRes || null;
    refreshedAt.value = formatTimestamp(Date.now());
  } catch (error) {
    console.error('Dashboard data fetch failed:', error);
    errorMsg.value = '加载数据看板失败，请稍后重试。';
    ElMessage.error(errorMsg.value);
  } finally {
    isLoading.value = false;
  }
};

onMounted(fetchData);

const summaryMetrics = computed(() => buildDashboardSummaryMetrics(dashboardStats.value));
const sourceRows = computed(() => buildDashboardSourceRows({
  ...dashboardStats.value,
  audit_snippets: audits.value,
}));

const trendOption = computed(() => buildDashboardTrendOption(dashboardStats.value));
const riskLevelOption = computed(() => buildDashboardRiskLevelOption(dashboardStats.value));
const sourceOption = computed(() => buildDashboardDonutOption(sourceRows.value, ['36%', '50%']));
const documentOption = computed(() => buildDashboardDocumentOption(dashboardStats.value));

const riskLevelRows = computed(() => {
  const distribution = dashboardStats.value.risk_level_distribution || {};
  const high = Number(distribution.high || 0) + Number(distribution.critical || 0);
  const medium = Number(distribution.medium || 0);
  const low = Number(distribution.low || 0);
  const total = Math.max(1, high + medium + low);

  return [
    { label: '高风险', value: high, color: 'var(--risk, #f04d5d)' },
    { label: '中风险', value: medium, color: 'var(--warning, #f3a21b)' },
    { label: '低风险', value: low, color: 'var(--brand, #2f74ff)' },
  ].map((item) => ({
    ...item,
    percent: `${(item.value / total * 100).toFixed(1)}%`,
  }));
});

const processStats = computed(() => [
  {
    label: '文档总量',
    value: formatNumber(dashboardStats.value.document_count),
    icon: 'file-text',
  },
  {
    label: '已索引文档',
    value: formatNumber(dashboardStats.value.indexed_document_count),
    icon: 'database',
  },
  {
    label: '知识库入口',
    value: formatNumber(dashboardStats.value.knowledgebase_count),
    icon: 'layers',
  },
  {
    label: '近 24h 问答',
    value: formatNumber(dashboardStats.value.chat_request_count_24h),
    icon: 'message-square',
  },
  {
    label: '可重试入库',
    value: formatNumber(dashboardStats.value.retryable_ingestion_count),
    icon: 'refresh',
  },
  {
    label: '审计记录',
    value: formatNumber(audits.value.length),
    icon: 'clipboard',
  },
]);

const topEvents = computed(() => {
  const riskActivityRows = dashboardStats.value.recent_activity
    .filter((item) => item.type === 'risk')
    .slice(0, 5)
    .map((item, index) => {
      const [company = '风险样本'] = String(item.message || '').split(' 产生 ');
      const isHigh = item.tone === 'risk';

      return {
        id: `risk-${index}`,
        title: item.message || '风险事件待核查',
        company,
        level: isHigh ? '高' : '中',
        levelClass: isHigh ? 'is-high' : 'is-mid',
        value: isHigh ? '重点' : '观察',
        time: formatShortTime(item.timestamp),
      };
    });

  const failureRows = dashboardStats.value.recent_failures.slice(0, 3).map((item, index) => ({
    id: `failure-${item.id || index}`,
    title: `文档处理失败：${item.document_title || '未命名文档'}`,
    company: '知识库',
    level: '中',
    levelClass: 'is-mid',
    value: `重试 ${item.retry_count ?? 0}`,
    time: formatShortTime(item.updated_at),
  }));

  const auditRows = audits.value.slice(0, 4).map((item, index) => ({
    id: `audit-${item.id || index}`,
    title: item.summary || formatAuditAction(item.action),
    company: item.actor_name || '系统',
    level: item.status === 'failed' ? '高' : '低',
    levelClass: item.status === 'failed' ? 'is-high' : 'is-low',
    value: formatStatus(item.status),
    time: formatShortTime(item.created_at || item.timestamp),
    audit: item,
  }));

  const rows = [...riskActivityRows, ...failureRows, ...auditRows].slice(0, 10);

  if (rows.length > 0) {
    return rows;
  }

  return [
    {
      id: 'pending-risk',
      title: '待审核风险事件池',
      company: '风险中台',
      level: '高',
      levelClass: 'is-high',
      value: formatNumber(dashboardStats.value.pending_risk_event_count),
      time: '实时',
    },
    {
      id: 'failed-docs',
      title: '失败入库影响知识召回',
      company: '知识库',
      level: '中',
      levelClass: 'is-mid',
      value: formatNumber(dashboardStats.value.failed_document_count),
      time: '实时',
    },
  ];
});

const footerSources = computed(() => [
  '知识库文档',
  '风险提取结果',
  'RAG 检索日志',
  '系统审计记录',
].join('、'));

const retryingId = ref(null);

const isRetryableAudit = (item) => (
  item?.status === 'failed'
  && ['risk.extract', 'risk.batch_extract'].includes(item?.action)
  && String(item?.target_id || '').trim() !== ''
);

const retryAuditAction = async (item) => {
  if (!isRetryableAudit(item) || retryingId.value) {
    return;
  }

  retryingId.value = item.id;
  try {
    if (item.action === 'risk.extract') {
      await riskApi.retryExtractDocument(item.target_id);
    } else {
      const documentIds = String(item.target_id)
        .split(',')
        .map((value) => Number.parseInt(value.trim(), 10))
        .filter((value) => Number.isInteger(value) && value > 0);
      await riskApi.retryBatchExtract(documentIds);
    }

    ElMessage.success('已重新触发风险提取任务。');
    await fetchData();
  } catch (error) {
    console.error('Failed to retry risk audit action:', error);
    ElMessage.error(error?.message || '重新触发失败，请稍后重试。');
  } finally {
    retryingId.value = null;
  }
};
</script>

<template>
  <section class="ops-board" v-loading="isLoading">
    <div class="ops-board__actions">
      <button type="button" class="ops-board__chip">{{ refreshedAt || '等待刷新' }}</button>
      <button type="button" class="ops-board__chip is-primary" @click="fetchData">
        <AppIcon name="refresh" />
        刷新
      </button>
    </div>

    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />

    <section class="ops-board__summary">
      <article
        v-for="metric in summaryMetrics.slice(0, 4)"
        :key="metric.key"
        class="summary-tile"
        :class="`is-${metric.tone}`"
      >
        <span class="summary-tile__icon">
          <AppIcon :name="metric.icon" />
        </span>
        <div>
          <span class="summary-tile__label">{{ metric.label }}</span>
          <strong>{{ metric.value }}</strong>
          <p>{{ metric.note }} <em>{{ metric.delta }}</em></p>
        </div>
      </article>
    </section>

    <div v-if="health" class="ops-board__health">
      <span class="ops-board__health-item" :class="health.checks?.database === 'ok' ? 'is-ok' : 'is-err'">
        <span class="ops-board__health-dot" />
        DB
      </span>
      <span class="ops-board__health-item" :class="health.checks?.redis === 'ok' ? 'is-ok' : 'is-err'">
        <span class="ops-board__health-dot" />
        Redis
      </span>
      <span class="ops-board__health-status">{{ health.status === 'ok' ? '系统正常' : '部分降级' }}</span>
    </div>

    <section class="ops-board__grid">
      <article class="board-panel board-panel--trend">
        <div class="board-panel__header">
          <div>
            <strong>风险趋势分析</strong>
            <span>近 7 天请求、命中与高风险预警</span>
          </div>
          <div class="board-tabs">
            <span class="is-active">近7天</span>
            <span>近30天</span>
            <span>近90天</span>
          </div>
        </div>
        <AdminChart :option="trendOption" height="180px" />
      </article>

      <article class="board-panel board-panel--level">
        <div class="board-panel__header">
          <div>
            <strong>风险等级分布</strong>
            <span>来自后端风险事件等级聚合</span>
          </div>
        </div>
        <div class="risk-level-layout">
          <div class="donut-wrap">
            <AdminChart :option="riskLevelOption" height="150px" />
            <div class="donut-center donut-center--level">
              <strong>{{ formatNumber(dashboardStats.risk_event_count) }}</strong>
              <span>风险信息总数</span>
            </div>
          </div>
          <div class="risk-level-legend">
            <div v-for="row in riskLevelRows" :key="row.label">
              <span :style="{ background: row.color }" />
              <b>{{ row.label }}</b>
              <em>{{ formatNumber(row.value) }}（{{ row.percent }}）</em>
            </div>
          </div>
        </div>
      </article>

      <article class="board-panel board-panel--source">
        <div class="board-panel__header">
          <div>
            <strong>数据来源分布</strong>
            <span>当前平台真实数据面来源</span>
          </div>
        </div>
        <div class="source-layout">
          <div class="donut-wrap">
            <AdminChart :option="sourceOption" height="150px" />
            <div class="donut-center donut-center--source">
              <strong>{{ formatNumber(dashboardStats.document_count + dashboardStats.risk_event_count) }}</strong>
              <span>核心样本量</span>
            </div>
          </div>
          <div class="source-legend">
            <div v-for="row in sourceRows" :key="row.label">
              <span :style="{ background: row.color }" />
              <b>{{ row.label }}</b>
              <em>{{ formatNumber(row.value) }}</em>
            </div>
          </div>
        </div>
      </article>

      <article class="board-panel board-panel--table">
        <div class="board-panel__header">
          <div>
            <strong>高风险事项 TOP10</strong>
            <span>风险活动、失败任务与关键审计合并排序</span>
          </div>
        </div>
        <div class="event-table-wrap">
          <table v-if="topEvents.length > 0" class="event-table">
            <thead>
              <tr>
                <th>事件标题</th>
                <th>涉及对象</th>
                <th>风险等级</th>
                <th>指标</th>
                <th>时间</th>
                <th />
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, index) in topEvents" :key="row.id">
                <td>
                  <span class="event-rank">{{ index + 1 }}</span>
                  {{ row.title }}
                </td>
                <td>{{ row.company }}</td>
                <td><span class="risk-tag" :class="row.levelClass">{{ row.level }}</span></td>
                <td>{{ row.value }}</td>
                <td>{{ row.time }}</td>
                <td>
                  <button
                    v-if="isRetryableAudit(row.audit)"
                    type="button"
                    class="table-action"
                    :disabled="retryingId === row.audit?.id"
                    @click="retryAuditAction(row.audit)"
                  >
                    {{ retryingId === row.audit?.id ? '重试中...' : '重试' }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-else class="admin-empty-state">暂无高风险事项</div>
        </div>
      </article>

      <article class="board-panel board-panel--process">
        <div class="board-panel__header">
          <div>
            <strong>数据处理统计</strong>
            <span>知识入库、检索和审计处理状态</span>
          </div>
        </div>
        <div class="process-grid">
          <div v-for="item in processStats" :key="item.label" class="process-item">
            <span><AppIcon :name="item.icon" /></span>
            <div>
              <b>{{ item.label }}</b>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
        </div>
      </article>

      <article class="board-panel board-panel--documents">
        <div class="board-panel__header">
          <div>
            <strong>文档处理状态</strong>
            <span>解析、切块、索引与失败状态</span>
          </div>
        </div>
        <AdminChart :option="documentOption" height="150px" />
      </article>
    </section>

    <footer class="ops-board__footer">
      <span>数据来源：{{ footerSources }}</span>
      <span>最后更新：{{ refreshedAt || '未更新' }}</span>
    </footer>
  </section>
</template>

<style scoped>
.ops-board {
  display: grid;
  gap: 8px;
  color: var(--text-secondary);
}

.ops-board__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.ops-board__chip {
  height: 28px;
  border: 1px solid var(--line-soft);
  border-radius: 4px;
  background: var(--surface-1);
  color: var(--text-muted);
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 10px;
  font: inherit;
  font-size: 0.6875rem;
  cursor: pointer;
}

.ops-board__chip.is-primary {
  border-color: var(--brand);
  background: var(--brand);
  color: #fff;
  font-weight: 700;
}

/* ── Summary: 1-row compact indicator strip ── */
.ops-board__summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  border: 1px solid var(--line-soft);
  border-radius: 4px;
  background: var(--surface-1);
  overflow: hidden;
}

.summary-tile {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-right: 1px solid var(--line-soft);
}

.summary-tile:last-child {
  border-right: 0;
}

.summary-tile__icon {
  width: 24px;
  height: 24px;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--brand);
  background: var(--brand-soft);
}

.summary-tile__icon :deep(.app-icon) {
  width: 13px;
  height: 13px;
}

.summary-tile.is-blue  { color: var(--brand); }
.summary-tile.is-red   { color: var(--risk); }
.summary-tile.is-cyan  { color: var(--info, #52d7e9); }
.summary-tile.is-purple{ color: var(--brand-300, #b16cff); }
.summary-tile.is-green { color: var(--success); }
.summary-tile.is-orange{ color: var(--warning); }

.summary-tile__label {
  color: var(--text-muted);
  font-size: 0.6875rem;
  font-weight: 700;
  white-space: nowrap;
}

.summary-tile strong {
  color: currentColor;
  font-size: 1.125rem;
  line-height: 1.1;
  font-weight: 800;
}

.summary-tile p {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.625rem;
}

.summary-tile em {
  color: var(--success);
  font-style: normal;
  margin-left: 4px;
}

.summary-tile.is-red em,
.summary-tile.is-orange em {
  color: var(--risk);
}

/* ── Health strip ── */
.ops-board__health {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 12px;
  border: 1px solid var(--line-soft);
  border-radius: 4px;
  background: var(--surface-1);
  font-size: 0.6875rem;
}

.ops-board__health-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-weight: 700;
}

.ops-board__health-item.is-ok { color: var(--success); }
.ops-board__health-item.is-err { color: var(--risk); }

.ops-board__health-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.ops-board__health-status {
  margin-left: auto;
  color: var(--text-muted);
}

/* ── Chart grid: 3-col, compact ── */
.ops-board__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  grid-auto-rows: minmax(140px, auto);
  gap: 8px;
}

.board-panel {
  min-width: 0;
  border: 1px solid var(--line-soft);
  border-radius: 4px;
  background: var(--surface-1);
  overflow: hidden;
}

.board-panel--process,
.board-panel--documents {
  min-height: 140px;
}

.board-panel__header {
  min-height: 36px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 0 10px;
}

.board-panel__header div:first-child {
  min-width: 0;
}

.board-panel__header strong {
  display: block;
  color: var(--text-primary);
  font-size: 0.8125rem;
  font-weight: 700;
}

.board-panel__header span {
  display: block;
  color: var(--text-muted);
  font-size: 0.6875rem;
}

.board-tabs {
  display: flex;
  gap: 4px;
  padding: 2px;
  border-radius: 4px;
  border: 1px solid var(--line-soft);
  background: var(--surface-2);
}

.board-tabs span {
  min-height: 22px;
  display: inline-flex;
  align-items: center;
  padding: 0 8px;
  border-radius: 3px;
  color: var(--text-muted);
  font-size: 0.6875rem;
  font-weight: 700;
}

.board-tabs .is-active {
  color: #fff;
  background: var(--brand);
}

/* ── Donut charts ── */
.donut-wrap {
  position: relative;
}

.donut-center {
  position: absolute;
  pointer-events: none;
  text-align: center;
  color: var(--text-primary);
}

.donut-center strong {
  display: block;
  font-size: 1rem;
  line-height: 1.1;
}

.donut-center span {
  display: block;
  margin-top: 2px;
  color: var(--text-muted);
  font-size: 0.625rem;
}

.donut-center--level,
.donut-center--source {
  left: calc(35% - 44px);
  top: 64px;
  width: 88px;
}

.source-legend,
.risk-level-legend {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  min-width: 0;
  color: var(--text-secondary);
  font-size: 0.6875rem;
  font-weight: 700;
}

.source-legend div,
.risk-level-legend div {
  display: grid;
  grid-template-columns: 8px minmax(0, 1fr) auto;
  align-items: center;
  gap: 6px;
}

.source-legend span,
.risk-level-legend span {
  width: 8px;
  height: 8px;
  border-radius: 2px;
}

.source-legend b,
.risk-level-legend b {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-legend em,
.risk-level-legend em {
  color: var(--text-primary);
  font-style: normal;
  white-space: nowrap;
}

.risk-level-layout,
.source-layout {
  display: grid;
  grid-template-columns: minmax(160px, 0.95fr) minmax(130px, 1fr);
  align-items: center;
  padding: 0 10px 10px;
}

/* ── Event table ── */
.event-table-wrap {
  overflow-x: auto;
  padding: 0 8px 8px;
}

.event-table {
  width: 100%;
  min-width: 640px;
  border-collapse: collapse;
  color: var(--text-secondary);
  font-size: 0.6875rem;
}

.event-table th {
  height: 28px;
  color: var(--text-muted);
  font-weight: 700;
  text-align: left;
  border-bottom: 1px solid var(--line-soft);
}

.event-table td {
  height: 28px;
  max-width: 320px;
  border-bottom: 1px solid var(--line-soft);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.event-rank {
  display: inline-grid;
  place-items: center;
  width: 16px;
  height: 16px;
  margin-right: 6px;
  border-radius: 3px;
  background: var(--brand-soft);
  color: var(--brand);
  font-size: 0.625rem;
  font-weight: 800;
}

.risk-tag {
  display: inline-grid;
  place-items: center;
  width: 22px;
  height: 18px;
  border-radius: 3px;
  font-size: 0.6875rem;
  font-weight: 800;
}

.risk-tag.is-high { color: var(--risk); background: rgba(240, 77, 93, 0.12); }
.risk-tag.is-mid  { color: var(--warning); background: rgba(243, 162, 27, 0.12); }
.risk-tag.is-low  { color: var(--success); background: rgba(25, 213, 154, 0.12); }

.table-action {
  border: 0;
  background: transparent;
  color: var(--brand);
  font: inherit;
  font-weight: 700;
  cursor: pointer;
}

.table-action:disabled {
  color: var(--text-muted);
  cursor: not-allowed;
}

/* ── Process stats ── */
.process-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px 10px;
  padding: 6px 10px 10px;
}

.process-item {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
  align-items: center;
  gap: 8px;
}

.process-item > span {
  width: 26px;
  height: 26px;
  border-radius: 4px;
  background: var(--brand-soft);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--brand);
}

.process-item b {
  display: block;
  color: var(--text-muted);
  font-size: 0.6875rem;
  font-weight: 700;
}

.process-item strong {
  display: block;
  color: var(--brand);
  font-size: 1rem;
  line-height: 1.2;
  font-weight: 800;
}

/* ── Footer ── */
.ops-board__footer {
  min-height: 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 12px;
  border: 1px solid var(--line-soft);
  border-radius: 4px;
  background: var(--surface-1);
  color: var(--text-muted);
  font-size: 0.6875rem;
}

/* ── Responsive ── */
@media (max-width: 1320px) {
  .ops-board__summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .summary-tile:nth-child(2n) {
    border-right: 0;
  }
  .ops-board__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .board-panel--table {
    grid-column: span 2;
  }
}

@media (max-width: 900px) {
  .ops-board__grid,
  .risk-level-layout,
  .source-layout {
    grid-template-columns: 1fr;
  }
  .ops-board__summary {
    grid-template-columns: 1fr;
  }
  .summary-tile {
    border-right: 0;
    border-bottom: 1px solid var(--line-soft);
  }
  .board-panel--table {
    grid-column: span 1;
  }
  .process-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .ops-board__footer {
    align-items: flex-start;
    flex-direction: column;
    padding-block: 8px;
  }
}

@media (max-width: 560px) {
  .ops-board__actions,
  .board-panel__header {
    align-items: stretch;
    flex-direction: column;
  }
  .process-grid {
    grid-template-columns: 1fr;
  }
}
</style>
