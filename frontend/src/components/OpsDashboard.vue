<script setup>
import { computed, onMounted, ref } from 'vue';
import { ElMessage } from 'element-plus';

import { dashboardApi } from '../api/dashboard.js';
import {
  buildDashboardDocumentOption,
  buildDashboardSummaryMetrics,
  buildDashboardTrendOption,
  normalizeDashboardPayload,
} from '../lib/admin-dashboard.js';
import AdminChart from './admin/AdminChart.vue';
import AppIcon from './ui/AppIcon.vue';

const dashboardStats = ref(normalizeDashboardPayload({}));
const isLoading = ref(true);
const errorMsg = ref('');

const numberFormatter = new Intl.NumberFormat('zh-CN');

const formatNumber = (value) => numberFormatter.format(Math.max(0, Math.round(Number(value) || 0)));

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
    retried: '已重试',
    skipped: '已跳过',
  };

  return labels[status] || status || '状态';
};

const formatAuditAction = (action) => {
  const labels = {
    'knowledgebase.ingest': '知识入库',
    'risk.extract': '风险提取',
    'risk.batch_extract': '批量提取',
  };

  return labels[action] || action || '审计事件';
};

const fetchData = async () => {
  isLoading.value = true;
  errorMsg.value = '';

  try {
    const statsRes = await dashboardApi.getStats();
    dashboardStats.value = normalizeDashboardPayload(statsRes);
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
const trendOption = computed(() => buildDashboardTrendOption(dashboardStats.value));
const documentOption = computed(() => buildDashboardDocumentOption(dashboardStats.value));

const auditRows = computed(() => dashboardStats.value.audit_snippets.slice(0, 4).map((item, index) => ({
  id: item.id || `audit-${index}`,
  title: formatAuditAction(item.action),
  actor: item.actor_name || '系统',
  status: formatStatus(item.status),
  statusTone: item.status === 'failed' ? 'is-risk' : 'is-neutral',
  time: formatShortTime(item.created_at),
  summary: item.summary || `${formatAuditAction(item.action)} · ${formatStatus(item.status)}`,
})));

const documentHighlights = computed(() => ([
  {
    label: '处理中',
    value: formatNumber(dashboardStats.value.processing_document_count),
  },
  {
    label: '失败',
    value: formatNumber(dashboardStats.value.failed_document_count),
  },
  {
    label: '可重试入库',
    value: formatNumber(dashboardStats.value.retryable_ingestion_count),
  },
]));
</script>

<template>
  <section class="ops-board" v-loading="isLoading">
    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />

    <section class="ops-board__summary">
      <article
        v-for="metric in summaryMetrics"
        :key="metric.key"
        class="summary-tile"
        :class="`is-${metric.tone}`"
      >
        <div class="summary-tile__head">
          <span class="summary-tile__label">{{ metric.label }}</span>
          <span class="summary-tile__icon">
            <AppIcon :name="metric.icon" />
          </span>
        </div>

        <div class="summary-tile__value-row">
          <strong>{{ metric.value }}</strong>
          <em
            class="summary-tile__delta"
            :class="{
              'is-up': metric.deltaTone === 'up',
              'is-down': metric.deltaTone === 'down',
              'is-neutral': metric.deltaTone === 'neutral',
            }"
          >
            {{ metric.delta }}
          </em>
        </div>

        <p>{{ metric.note }}</p>
      </article>
    </section>

    <section class="ops-board__hero">
      <header class="ops-board__hero-header">
        <div>
          <h2>模型调用趋势 <span class="ops-board__eyebrow">近 7 天</span></h2>
          <p>调用量与审计操作节奏概览。</p>
        </div>

        <div class="ops-board__hero-aside">
          <div class="ops-board__hero-stat">
            <span>调用总量</span>
            <strong>{{ formatNumber(dashboardStats.model_invocation_count_7d) }}</strong>
          </div>
          <div class="ops-board__hero-stat">
            <span>审计操作</span>
            <strong>{{ formatNumber(dashboardStats.audit_operation_count_7d) }}</strong>
          </div>
        </div>
      </header>

      <AdminChart :option="trendOption" height="240px" />
    </section>

    <section class="ops-board__secondary">
      <article class="board-panel">
        <header class="board-panel__header">
          <div>
            <strong>文档处理状态</strong>
            <span>入库管线当前各阶段数量。</span>
          </div>
        </header>

        <AdminChart :option="documentOption" height="180px" />

        <div class="board-panel__metrics">
          <div v-for="item in documentHighlights" :key="item.label" class="board-panel__metric">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </article>

      <article class="board-panel">
        <header class="board-panel__header">
          <div>
            <strong>最近审计操作</strong>
            <span>近期治理动作时间线。</span>
          </div>
        </header>

        <div v-if="auditRows.length > 0" class="audit-feed">
          <article v-for="row in auditRows" :key="row.id" class="audit-feed__item">
            <div class="audit-feed__copy">
              <strong>{{ row.title }}</strong>
              <p>{{ row.actor }} · {{ row.summary }}</p>
            </div>
            <div class="audit-feed__meta">
              <span class="audit-feed__status" :class="row.statusTone">{{ row.status }}</span>
              <time>{{ row.time }}</time>
            </div>
          </article>
        </div>
        <div v-else class="admin-empty-state">近 7 天暂无审计操作</div>
      </article>
    </section>
  </section>
</template>

<style scoped>
.ops-board {
  display: grid;
  gap: 20px;
  color: var(--text-secondary);
}

.ops-board__summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.summary-tile {
  display: grid;
  gap: 12px;
  min-width: 0;
  padding: 18px 20px 16px;
  border: 1px solid var(--line-soft);
  border-radius: var(--radius-card);
  background: var(--surface-1);
  box-shadow: var(--shadow-md);
}

.summary-tile__head,
.summary-tile__value-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.summary-tile__label {
  color: var(--text-primary);
  font-size: 0.8125rem;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.summary-tile__icon {
  width: 30px;
  height: 30px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--brand-soft);
}

.summary-tile__icon :deep(.app-icon) {
  width: 14px;
  height: 14px;
}

.summary-tile strong {
  color: var(--text-primary);
  font-family: var(--heading);
  font-size: 1.5rem;
  line-height: 1;
  font-weight: 600;
}

.summary-tile p {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.8125rem;
  line-height: 1.6;
}

.summary-tile__delta {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 8px;
  border-radius: var(--radius-pill);
  font-size: 0.6875rem;
  font-style: normal;
  font-weight: 700;
  white-space: nowrap;
}

.summary-tile__delta.is-up {
  color: var(--success);
  background: rgba(33, 129, 92, 0.12);
}

.summary-tile__delta.is-down {
  color: var(--risk);
  background: rgba(196, 73, 61, 0.12);
}

.summary-tile__delta.is-neutral {
  color: var(--text-muted);
  background: rgba(125, 135, 152, 0.12);
}

.summary-tile.is-blue .summary-tile__icon {
  color: var(--brand);
}

.summary-tile.is-orange .summary-tile__icon {
  color: var(--warning);
  background: rgba(183, 121, 31, 0.12);
}

.summary-tile.is-cyan .summary-tile__icon {
  color: #5d9fe6;
  background: rgba(93, 159, 230, 0.12);
}

.summary-tile.is-green .summary-tile__icon {
  color: var(--success);
  background: rgba(33, 129, 92, 0.12);
}

.ops-board__hero,
.board-panel {
  padding: 22px;
  border: 1px solid var(--line-soft);
  border-radius: var(--radius-card);
  background: var(--surface-1);
  box-shadow: var(--shadow-md);
}

.ops-board__hero {
  display: grid;
  gap: 14px;
}

.ops-board__hero-header,
.board-panel__header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
}

.ops-board__hero-header h2 {
  margin: 0 0 4px;
  color: var(--text-primary);
  font-family: var(--heading);
  font-size: 1.25rem;
  line-height: 1.3;
  font-weight: 600;
}

.ops-board__hero-header p,
.board-panel__header span {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.8125rem;
  line-height: 1.5;
}

.ops-board__eyebrow {
  color: var(--brand);
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  vertical-align: middle;
}

.ops-board__hero-aside {
  display: grid;
  gap: 12px;
  min-width: 168px;
}

.ops-board__hero-stat {
  padding: 10px 14px;
  border-radius: var(--radius-lg);
  background: rgba(36, 87, 197, 0.08);
}

.ops-board__hero-stat span {
  display: block;
  color: var(--text-muted);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.ops-board__hero-stat strong {
  display: block;
  margin-top: 4px;
  color: var(--text-primary);
  font-size: 1.25rem;
  line-height: 1.1;
  font-weight: 600;
}

.ops-board__secondary {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr);
  gap: 16px;
}

.board-panel {
  display: grid;
  gap: 14px;
}

.board-panel__header strong {
  display: block;
  margin-bottom: 4px;
  color: var(--text-primary);
  font-size: 0.9375rem;
  font-weight: 700;
}

.board-panel__metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.board-panel__metric {
  padding: 10px 14px;
  border-radius: var(--radius-lg);
  background: var(--surface-2);
}

.board-panel__metric span {
  display: block;
  color: var(--text-muted);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.board-panel__metric strong {
  display: block;
  margin-top: 4px;
  color: var(--text-primary);
  font-size: 1.125rem;
  line-height: 1.1;
  font-weight: 600;
}

.audit-feed {
  display: grid;
  gap: 12px;
}

.audit-feed__item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 12px 14px;
  border-radius: var(--radius-lg);
  background: var(--surface-2);
}

.audit-feed__copy {
  min-width: 0;
}

.audit-feed__copy strong {
  display: block;
  color: var(--text-primary);
  font-size: 0.9375rem;
  font-weight: 700;
}

.audit-feed__copy p {
  margin: 6px 0 0;
  color: var(--text-muted);
  font-size: 0.8125rem;
  line-height: 1.5;
}

.audit-feed__meta {
  display: grid;
  justify-items: end;
  gap: 8px;
}

.audit-feed__meta time {
  color: var(--text-muted);
  font-size: 0.75rem;
}

.audit-feed__status {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: var(--radius-pill);
  font-size: 0.75rem;
  font-weight: 700;
}

.audit-feed__status.is-risk {
  color: var(--risk);
  background: rgba(196, 73, 61, 0.12);
}

.audit-feed__status.is-neutral {
  color: var(--text-secondary);
  background: rgba(125, 135, 152, 0.12);
}

@media (max-width: 1320px) {
  .ops-board__summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .ops-board__secondary {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .ops-board {
    gap: 16px;
  }

  .ops-board__summary {
    grid-template-columns: 1fr;
  }

  .ops-board__hero,
  .board-panel {
    padding: 20px;
  }

  .ops-board__hero-header,
  .board-panel__header,
  .audit-feed__item {
    grid-template-columns: 1fr;
  }

  .ops-board__hero-header,
  .board-panel__header {
    display: grid;
  }

  .ops-board__hero-aside,
  .board-panel__metrics {
    grid-template-columns: 1fr;
  }

  .audit-feed__meta {
    justify-items: start;
  }
}
</style>
