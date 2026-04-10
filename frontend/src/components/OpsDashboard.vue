<script setup>
import { computed, onMounted, ref } from 'vue';
import { ElMessage } from 'element-plus';

import { dashboardApi } from '../api/dashboard.js';
import {
  buildDocumentStatusOption,
  buildRiskDistributionOption,
  buildTrendChartOption,
  normalizeDashboardPayload,
  summarizeOperationalPosture,
} from '../lib/admin-dashboard.js';
import AdminChart from './admin/AdminChart.vue';
import AppSectionCard from './ui/AppSectionCard.vue';

const dashboardStats = ref(normalizeDashboardPayload({}));
const isLoading = ref(true);
const errorMsg = ref('');
const refreshedAt = ref('');

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

const formatActivityType = (type) => {
  const labels = {
    ingestion: '入库任务',
    risk: '风险事件',
    retrieval: '检索记录',
    evaluation: '模型评测',
  };

  return labels[type] || type || '活动';
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

const fetchData = async () => {
  isLoading.value = true;
  errorMsg.value = '';

  try {
    const statsRes = await dashboardApi.getStats();
    dashboardStats.value = normalizeDashboardPayload(statsRes);
    refreshedAt.value = formatTimestamp(Date.now());
  } catch (error) {
    console.error('Dashboard data fetch failed:', error);
    errorMsg.value = '加载管理员总览失败，请稍后重试。';
    ElMessage.error(errorMsg.value);
  } finally {
    isLoading.value = false;
  }
};

onMounted(fetchData);

const posture = computed(() => summarizeOperationalPosture(dashboardStats.value));

const headlineMetrics = computed(() => [
  {
    key: 'documents',
    label: '知识文档',
    value: dashboardStats.value.document_count,
    note: `${dashboardStats.value.indexed_document_count} 份已索引`,
  },
  {
    key: 'pending-risk',
    label: '待审风险',
    value: dashboardStats.value.pending_risk_event_count,
    note: `${dashboardStats.value.high_risk_event_count} 条高风险`,
  },
  {
    key: 'models',
    label: '启用模型',
    value: dashboardStats.value.active_model_count,
    note: '当前参与服务的模型配置',
  },
  {
    key: 'requests',
    label: '近 24h 问答',
    value: dashboardStats.value.chat_request_count_24h,
    note: `命中率 ${dashboardStats.value.retrieval_hit_rate_7d}`,
  },
]);

const focusQueue = computed(() => [
  {
    id: 'pending-risk',
    title: '待审核风险',
    value: dashboardStats.value.pending_risk_event_count,
    desc: '需要人工确认结论与证据链，避免积压进入报告流程。',
    tone: dashboardStats.value.pending_risk_event_count > 0 ? 'risk' : 'neutral',
  },
  {
    id: 'failed-docs',
    title: '失败入库',
    value: dashboardStats.value.failed_document_count,
    desc: '优先处理失败文档，避免影响问答命中与知识资产完整性。',
    tone: dashboardStats.value.failed_document_count > 0 ? 'risk' : 'neutral',
  },
  {
    id: 'processing-docs',
    title: '处理中',
    value: dashboardStats.value.processing_document_count,
    desc: '跟踪解析、切块与索引进度，避免长期卡住。',
    tone: dashboardStats.value.processing_document_count > 0 ? 'warning' : 'neutral',
  },
]);

const operationalSummary = computed(() => [
  {
    id: 'hit-rate',
    label: '近 7 天命中率',
    value: dashboardStats.value.retrieval_hit_rate_7d,
    detail: '按问答检索日志的命中结果统计，用于判断知识可用性。',
  },
  {
    id: 'risk-total',
    label: '风险事件总量',
    value: dashboardStats.value.risk_event_count,
    detail: '包含待审与已审核事件，用于判断审查规模。',
  },
  {
    id: 'knowledgebase-count',
    label: '知识资产分组',
    value: dashboardStats.value.knowledgebase_count,
    detail: '当前平台纳管的知识资产入口数量。',
  },
]);

const trendOption = computed(() => buildTrendChartOption(dashboardStats.value));
const riskOption = computed(() => buildRiskDistributionOption(dashboardStats.value));
const documentOption = computed(() => buildDocumentStatusOption(dashboardStats.value));

const activityItems = computed(() => dashboardStats.value.recent_activity.slice(0, 6));
const evidenceItems = computed(() => dashboardStats.value.recent_activity.slice(0, 10));

const toneClass = (tone) => `is-${tone || 'neutral'}`;
</script>

<template>
  <div class="page-stack admin-page">
    <section class="overview-strip">
      <div class="overview-strip__main">
        <p class="overview-strip__eyebrow">管理员总览</p>
        <div class="overview-strip__headline">
          <h1 class="overview-strip__title">{{ posture.label }}</h1>
          <p class="overview-strip__summary">{{ posture.summary }}</p>
        </div>
        <div class="overview-strip__meta">
          <span>最近刷新：{{ refreshedAt }}</span>
          <span>待审风险：{{ dashboardStats.pending_risk_event_count }}</span>
          <span>失败入库：{{ dashboardStats.failed_document_count }}</span>
          <span>近 24h 问答：{{ dashboardStats.chat_request_count_24h }}</span>
        </div>
      </div>

      <div class="overview-strip__actions">
        <div class="overview-strip__status" :class="toneClass(posture.tone)">
          <span class="overview-strip__status-label">当前判断</span>
          <strong>{{ posture.label }}</strong>
          <p>{{ posture.summary }}</p>
        </div>
        <div class="overview-strip__buttons">
          <el-button type="primary" @click="fetchData" :loading="isLoading">刷新运行状态</el-button>
        </div>
      </div>
    </section>

    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />

    <section class="overview-metrics">
      <article v-for="metric in headlineMetrics" :key="metric.key" class="overview-metric">
        <span class="overview-metric__label">{{ metric.label }}</span>
        <strong class="overview-metric__value">{{ metric.value }}</strong>
        <p class="overview-metric__note">{{ metric.note }}</p>
      </article>
    </section>

    <section class="overview-main">
      <AppSectionCard title="待处理事项" desc="优先用于判断今天需要人工跟进的治理动作。" admin>
        <div class="focus-list">
          <article v-for="item in focusQueue" :key="item.id" class="focus-item" :class="toneClass(item.tone)">
            <div class="focus-item__head">
              <span class="focus-item__title">{{ item.title }}</span>
              <strong class="focus-item__value">{{ item.value }}</strong>
            </div>
            <p class="focus-item__desc">{{ item.desc }}</p>
          </article>
        </div>
      </AppSectionCard>

      <AppSectionCard title="运行摘要" desc="保留管理员真正需要的核心判断，不再使用占位统计。" admin>
        <div class="summary-grid">
          <article v-for="item in operationalSummary" :key="item.id" class="summary-panel">
            <span class="summary-panel__label">{{ item.label }}</span>
            <strong class="summary-panel__value">{{ item.value }}</strong>
            <p class="summary-panel__detail">{{ item.detail }}</p>
          </article>
        </div>
      </AppSectionCard>
    </section>

    <section class="overview-charts">
      <AppSectionCard title="近 7 天请求与命中趋势" desc="用于判断问答规模和知识召回表现是否同步变化。" admin>
        <AdminChart :option="trendOption" height="310px" />
      </AppSectionCard>

      <AppSectionCard title="风险等级分布" desc="快速观察当前风险审查压力主要集中在哪个等级。" admin>
        <AdminChart :option="riskOption" height="310px" />
      </AppSectionCard>

      <AppSectionCard title="文档处理状态" desc="反映知识资产当前是否存在积压、失败或未完成索引。" admin>
        <AdminChart :option="documentOption" height="310px" />
      </AppSectionCard>
    </section>

    <section class="overview-evidence">
      <AppSectionCard title="最近活动" desc="面向治理判断的最新动态。" admin>
        <div v-if="activityItems.length === 0" class="activity-empty">暂无最近活动</div>
        <div v-else class="activity-list">
          <article v-for="(item, index) in activityItems" :key="`${item.timestamp}-${index}`" class="activity-item">
            <span class="activity-item__dot" :class="toneClass(item.tone)" />
            <div class="activity-item__content">
              <div class="activity-item__meta">
                <span>{{ formatActivityType(item.type) }}</span>
                <span>{{ formatTimestamp(item.timestamp) }}</span>
              </div>
              <p>{{ item.message }}</p>
            </div>
          </article>
        </div>
      </AppSectionCard>

      <AppSectionCard title="运行证据" desc="保留最近证据链，方便继续向下追查。" admin>
        <template #header>
          <span class="evidence-count">{{ evidenceItems.length }} 条记录</span>
        </template>

        <div v-if="evidenceItems.length === 0" class="evidence-log-list__empty">暂无运行证据</div>
        <div v-else class="evidence-log-list">
          <article v-for="(item, index) in evidenceItems" :key="`${item.timestamp}-${index}`" class="evidence-log">
            <div class="evidence-log__head">
              <span class="evidence-log__badge" :class="toneClass(item.tone)">{{ formatStatus(item.status) }}</span>
              <span>{{ formatActivityType(item.type) }}</span>
              <span>{{ formatTimestamp(item.timestamp) }}</span>
            </div>
            <p class="evidence-log__message">{{ item.message }}</p>
          </article>
        </div>
      </AppSectionCard>
    </section>
  </div>
</template>

<style scoped>
.admin-page {
  gap: 20px;
}

.overview-strip {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(260px, 0.7fr);
  gap: 18px;
  padding: 22px 24px;
  border-radius: 24px;
  border: 1px solid var(--line-soft);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(247, 250, 252, 0.96));
  box-shadow: var(--shadow-soft);
}

.overview-strip__main,
.overview-strip__actions {
  display: flex;
  flex-direction: column;
}

.overview-strip__main {
  gap: 12px;
}

.overview-strip__actions {
  gap: 14px;
  align-items: stretch;
}

.overview-strip__eyebrow {
  margin: 0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.overview-strip__headline {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.overview-strip__title {
  margin: 0;
  font-size: clamp(28px, 3.3vw, 38px);
  line-height: 1.06;
  color: var(--text-primary);
}

.overview-strip__summary {
  margin: 0;
  max-width: 720px;
  color: var(--text-secondary);
  line-height: 1.65;
}

.overview-strip__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.overview-strip__meta span {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  background: var(--surface-3);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
}

.overview-strip__status {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid var(--line-soft);
  background: var(--surface-2);
}

.overview-strip__status.is-risk {
  border-color: rgba(196, 73, 61, 0.18);
  background: rgba(196, 73, 61, 0.06);
}

.overview-strip__status.is-warning {
  border-color: rgba(183, 121, 31, 0.18);
  background: rgba(183, 121, 31, 0.08);
}

.overview-strip__status.is-info,
.overview-strip__status.is-neutral {
  border-color: rgba(36, 87, 197, 0.12);
  background: rgba(36, 87, 197, 0.05);
}

.overview-strip__status-label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.overview-strip__status strong {
  color: var(--text-primary);
  font-size: 18px;
}

.overview-strip__status p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.overview-strip__buttons {
  display: flex;
  justify-content: flex-end;
}

.overview-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.overview-metric {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 18px 20px;
  border-radius: 20px;
  border: 1px solid var(--line-soft);
  background: var(--surface-2);
  box-shadow: var(--shadow-soft);
}

.overview-metric__label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.overview-metric__value {
  font-size: clamp(28px, 3vw, 34px);
  line-height: 1;
  color: var(--text-primary);
}

.overview-metric__note {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.overview-main,
.overview-evidence {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.overview-charts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}

.focus-list,
.summary-grid {
  display: grid;
  gap: 12px;
}

.focus-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 15px 16px;
  border-radius: 16px;
  border: 1px solid var(--line-soft);
  background: var(--surface-2);
}

.focus-item.is-risk {
  border-color: rgba(196, 73, 61, 0.18);
  background: rgba(196, 73, 61, 0.05);
}

.focus-item.is-warning {
  border-color: rgba(183, 121, 31, 0.18);
  background: rgba(183, 121, 31, 0.07);
}

.focus-item__head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: baseline;
}

.focus-item__title,
.summary-panel__label {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
}

.focus-item__value,
.summary-panel__value {
  color: var(--text-primary);
  font-size: 24px;
  line-height: 1;
}

.focus-item__desc,
.summary-panel__detail {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.summary-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.summary-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 16px;
  border-radius: 16px;
  background: var(--surface-3);
}

.activity-list,
.evidence-log-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.activity-item,
.evidence-log {
  display: flex;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 16px;
  background: var(--surface-3);
}

.activity-item__dot {
  width: 10px;
  height: 10px;
  margin-top: 7px;
  border-radius: 50%;
  flex-shrink: 0;
  background: var(--text-muted);
}

.activity-item__dot.is-risk,
.evidence-log__badge.is-risk {
  background: rgba(196, 73, 61, 0.16);
  color: var(--risk);
}

.activity-item__dot.is-warning,
.evidence-log__badge.is-warning {
  background: rgba(183, 121, 31, 0.16);
  color: var(--warning);
}

.activity-item__dot.is-info,
.activity-item__dot.is-neutral,
.evidence-log__badge.is-info,
.evidence-log__badge.is-neutral {
  background: rgba(36, 87, 197, 0.14);
  color: var(--brand);
}

.activity-item__content {
  min-width: 0;
}

.activity-item__meta,
.evidence-log__head {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 12px;
  color: var(--text-muted);
}

.activity-item__content p,
.evidence-log__message {
  margin: 6px 0 0;
  color: var(--text-primary);
  line-height: 1.6;
}

.evidence-log {
  flex-direction: column;
}

.evidence-log__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 24px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

.evidence-count {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 600;
}

.activity-empty,
.evidence-log-list__empty {
  color: var(--text-muted);
  padding: 8px 0;
}

@media (max-width: 1200px) {
  .overview-metrics,
  .overview-charts,
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 960px) {
  .overview-strip,
  .overview-main,
  .overview-evidence,
  .overview-metrics,
  .overview-charts,
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .overview-strip__buttons {
    justify-content: flex-start;
  }
}
</style>
