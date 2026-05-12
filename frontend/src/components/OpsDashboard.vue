<script setup>
import { computed, onMounted, ref } from 'vue';
import { ElMessage } from 'element-plus';

import { dashboardApi } from '../api/dashboard.js';
import {
  buildDashboardDocumentFlow,
  buildDashboardSummaryMetrics,
  buildDashboardTokenOption,
  buildDashboardTrendOption,
  buildDocumentFlowFunnelOption,
  normalizeDashboardPayload,
} from '../lib/admin-dashboard.js';
import AdminChart from './admin/AdminChart.vue';
import AppIcon from './ui/AppIcon.vue';

const dashboardStats = ref(normalizeDashboardPayload({}));
const isLoading = ref(true);
const errorMsg = ref('');

const numberFormatter = new Intl.NumberFormat('zh-CN');

const formatNumber = (value) => numberFormatter.format(Math.max(0, Math.round(Number(value) || 0)));
const formatPercent = (value) => `${Math.round(Math.max(0, Number(value) || 0))}%`;

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
const documentFlow = computed(() => buildDashboardDocumentFlow(dashboardStats.value));
const documentFunnelOption = computed(() => buildDocumentFlowFunnelOption(dashboardStats.value));
const tokenOption = computed(() => buildDashboardTokenOption(dashboardStats.value));

const tokenHighlights = computed(() => {
  const total7d = Number(dashboardStats.value.token_count_7d) || 0;
  const input = Number(dashboardStats.value.total_request_token_count) || 0;
  const output = Number(dashboardStats.value.total_response_token_count) || 0;
  const total = input + output;
  const requests = Number(dashboardStats.value.model_invocation_count_7d) || 0;

  return [
    {
      label: '近 7 天',
      value: formatNumber(total7d),
      tone: 'processing',
    },
    {
      label: '输出占比',
      value: formatPercent(total > 0 ? (output / total) * 100 : 0),
      tone: 'retry',
    },
    {
      label: '单次均值',
      value: formatNumber(requests > 0 ? total7d / requests : 0),
      tone: 'neutral',
    },
  ];
});
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

    <section class="ops-board__main">
      <article class="ops-board__hero">
        <header class="ops-board__hero-header">
          <div>
            <h2>模型调用与 Token 走势 <span class="ops-board__eyebrow">近 7 天</span></h2>
          </div>

          <div class="ops-board__hero-aside">
            <div class="ops-board__hero-stat">
              <span>近 7 天调用量</span>
              <strong>{{ formatNumber(dashboardStats.model_invocation_count_7d) }}</strong>
            </div>
            <div class="ops-board__hero-stat">
              <span>近 7 天 Token</span>
              <strong>{{ formatNumber(dashboardStats.token_count_7d) }}</strong>
            </div>
          </div>
        </header>

        <AdminChart :option="trendOption" height="280px" />
      </article>

      <article class="board-panel board-panel--token">
        <header class="board-panel__header board-panel__header--stacked">
          <div>
            <strong>Token 近 7 天结构</strong>
          </div>
          <div class="board-panel__badge">
            <AppIcon name="activity" />
            <span>全系统累计 {{ formatNumber(dashboardStats.total_token_count) }}</span>
          </div>
        </header>

        <AdminChart :option="tokenOption" height="220px" />

        <div class="board-panel__metrics board-panel__metrics--token">
          <div v-for="item in tokenHighlights" :key="item.label" class="board-panel__metric" :class="`is-${item.tone}`">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </article>
    </section>

    <section class="ops-board__secondary">
      <article class="board-panel board-panel--document">
        <header class="board-panel__header">
          <div>
            <strong>文档处理状态</strong>
            <span>按入库阶段查看推进情况与异常分叉。</span>
          </div>
          <div class="board-panel__badge">
            <AppIcon name="database" />
            <span>总文档 {{ formatNumber(documentFlow.total) }}</span>
          </div>
        </header>

        <AdminChart :option="documentFunnelOption" height="220px" />

        <div class="document-summary-row">
          <div
            v-for="item in documentFlow.summary"
            :key="item.key"
            class="document-summary-card"
            :class="`is-${item.tone}`"
          >
            <span class="document-summary-card__label">{{ item.label }}</span>
            <strong class="document-summary-card__value">{{ item.value }}</strong>
          </div>
        </div>
      </article>
    </section>
  </section>
</template>

<style scoped>
.ops-board {
  display: grid;
  gap: 18px;
  color: var(--text-secondary);
}

.ops-board__summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.summary-tile {
  display: grid;
  gap: 12px;
  min-width: 0;
  padding: 18px 20px 16px;
  border: 1px solid var(--line-soft);
  border-radius: var(--radius-card);
  background: var(--surface-1);
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.summary-tile:hover {
  border-color: var(--line-strong);
  box-shadow: var(--shadow-sm);
}

.summary-tile__head,
.summary-tile__value-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.summary-tile__value-row {
  align-items: flex-end;
  flex-wrap: wrap;
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
  font-size: clamp(1.35rem, 2vw, 1.7rem);
  line-height: 1.05;
  font-weight: 600;
  word-break: break-word;
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
  color: var(--brand);
  background: rgba(36, 87, 197, 0.12);
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
  transition: border-color 0.2s ease;
}

.ops-board__main {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.9fr);
  gap: 16px;
  align-items: start;
}

.ops-board__hero:hover,
.board-panel:hover {
  border-color: var(--line-strong);
}

.ops-board__hero {
  display: grid;
  gap: 14px;
  min-width: 0;
}

.ops-board__hero-header,
.board-panel__header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
}

.ops-board__hero-header h2 {
  margin: 0;
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
  min-width: 196px;
}

.ops-board__hero-stat {
  padding: 12px 14px;
  border-radius: var(--radius-lg);
  background: color-mix(in srgb, var(--brand) 8%, var(--surface-2));
  transition: background 0.2s ease;
}

.ops-board__hero-stat:hover {
  background: color-mix(in srgb, var(--brand) 12%, var(--surface-2));
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
  display: block;
}

.board-panel {
  display: grid;
  gap: 14px;
}

.board-panel--token {
  min-width: 0;
  gap: 16px;
}

.board-panel--document {
  gap: 14px;
}

.board-panel__header strong {
  display: block;
  margin-bottom: 4px;
  color: var(--text-primary);
  font-size: 0.9375rem;
  font-weight: 700;
}

.board-panel__header--stacked {
  align-items: flex-start;
}

.board-panel__badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 32px;
  padding: 0 12px;
  border-radius: var(--radius-pill);
  color: var(--text-primary);
  background: var(--surface-2);
  font-size: 0.75rem;
  font-weight: 700;
}

.board-panel__badge span {
  color: inherit;
  font-size: inherit;
  line-height: inherit;
}

.board-panel__badge :deep(.app-icon) {
  width: 14px;
  height: 14px;
  color: var(--brand);
}

.board-panel__metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.board-panel__metrics--token {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.document-summary-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.document-summary-card {
  display: grid;
  gap: 6px;
  padding: 14px 16px;
  border-radius: var(--radius-lg);
  background: var(--surface-2);
  border: 1px solid transparent;
  transition: border-color 0.2s ease;
}

.document-summary-card:hover {
  border-color: var(--line-soft);
}

.document-summary-card__label {
  color: var(--text-muted);
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.document-summary-card__value {
  color: var(--text-primary);
  font-family: var(--heading);
  font-size: 1.25rem;
  line-height: 1.1;
  font-weight: 600;
}

.document-summary-card.is-success .document-summary-card__value {
  color: var(--success);
}

.document-summary-card.is-processing .document-summary-card__value {
  color: var(--brand);
}

.document-summary-card.is-retry .document-summary-card__value {
  color: var(--warning);
}

.board-panel__metric {
  padding: 12px 14px;
  border-radius: var(--radius-lg);
  background: var(--surface-2);
  transition: background 0.15s ease;
}

.board-panel__metric:hover {
  background: var(--surface-hover);
}

.board-panel__metric.is-risk strong {
  color: var(--risk);
}

.board-panel__metric.is-processing strong {
  color: var(--brand);
}

.board-panel__metric.is-retry strong {
  color: var(--warning);
}

.board-panel__metric.is-neutral strong {
  color: var(--text-primary);
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

@media (max-width: 1320px) {
  .ops-board__summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .ops-board__main {
    grid-template-columns: 1fr;
  }

  .document-summary-row {
    grid-template-columns: repeat(3, minmax(0, 1fr));
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
  .board-panel__header {
    display: grid;
  }

  .ops-board__hero-aside,
  .board-panel__metrics {
    grid-template-columns: 1fr;
  }

  .document-summary-row {
    grid-template-columns: 1fr;
  }
}
</style>
