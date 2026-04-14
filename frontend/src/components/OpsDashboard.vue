<script setup>
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';

import { dashboardApi } from '../api/dashboard.js';
import {
  buildOperationalBanner,
  buildDocumentStatusOption,
  hasOperationalQueueItems,
  buildRiskDistributionOption,
  buildTrendChartOption,
  normalizeDashboardPayload,
} from '../lib/admin-dashboard.js';
import AdminChart from './admin/AdminChart.vue';
import AppSectionCard from './ui/AppSectionCard.vue';

const router = useRouter();
const dashboardStats = ref(normalizeDashboardPayload({}));
const audits = ref([]);
const isLoading = ref(true);
const errorMsg = ref('');
const refreshedAt = ref('');
const activitySection = ref(null);
const evidenceSection = ref(null);

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
    const [statsRes, auditRes] = await Promise.all([
      dashboardApi.getStats(),
      dashboardApi.getAudits({ limit: 6 }).catch(() => null),
    ]);
    dashboardStats.value = normalizeDashboardPayload(statsRes);
    audits.value = Array.isArray(auditRes?.audits)
      ? auditRes.audits
      : dashboardStats.value.audit_snippets;
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
const banner = computed(() => buildOperationalBanner(dashboardStats.value));
const hasQueueItems = computed(() => hasOperationalQueueItems(dashboardStats.value));

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
  {
    key: 'retryable-ingestion',
    label: '可重试入库',
    value: dashboardStats.value.retryable_ingestion_count,
    note: '失败任务可重新进入入库流程',
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
    label: '检索命中率',
    value: dashboardStats.value.retrieval_hit_rate_7d,
    detail: '命中偏低时优先查看评测结果与模型配置。',
  },
  {
    id: 'risk-total',
    label: '风险审查规模',
    value: dashboardStats.value.risk_event_count,
    detail: '结合待审数量判断是否需要人工加速审核。',
  },
  {
    id: 'knowledgebase-count',
    label: '知识资产入口',
    value: dashboardStats.value.knowledgebase_count,
    detail: '关注当前纳管范围是否覆盖主要知识来源。',
  },
  {
    id: 'audit-events',
    label: '审计摘要',
    value: audits.value.length,
    detail: '关键操作已写入轻量审计记录，便于回溯。 ',
  },
]);

const trendOption = computed(() => buildTrendChartOption(dashboardStats.value));
const riskOption = computed(() => buildRiskDistributionOption(dashboardStats.value));
const documentOption = computed(() => buildDocumentStatusOption(dashboardStats.value));

const activityItems = computed(() => dashboardStats.value.recent_activity.slice(0, 6));
const evidenceItems = computed(() => dashboardStats.value.recent_activity.slice(0, 10));
const failureItems = computed(() => dashboardStats.value.recent_failures.slice(0, 6));
const auditItems = computed(() => audits.value.slice(0, 6));

const formatAuditAction = (action) => {
  const labels = {
    'knowledgebase.ingest': '知识入库',
    'risk.extract': '风险提取',
    'risk.batch_extract': '批量提取',
    'risk.sentiment': '舆情分析',
  };
  return labels[action] || action || '审计事件';
};

const toneClass = (tone) => `is-${tone || 'neutral'}`;
const sectionRefs = {
  'activity-section': activitySection,
  'evidence-section': evidenceSection,
};

const handleBannerAction = async (action) => {
  if (action?.to) {
    await router.push(action.to);
    return;
  }

  const targetRef = sectionRefs[action?.target];
  targetRef?.value?.scrollIntoView({ behavior: 'smooth', block: 'start' });
};
</script>

<template>
  <div class="page-stack admin-page">
    <section class="overview-banner" :class="toneClass(banner.tone)">
      <div class="overview-banner__copy">
        <p class="overview-banner__eyebrow">{{ banner.eyebrow }}</p>
        <h1 class="overview-banner__title">{{ banner.title }}</h1>
        <p class="overview-banner__summary">{{ banner.summary }}</p>
        <div class="overview-banner__meta">
          <span>最近刷新：{{ refreshedAt }}</span>
          <span>待审风险：{{ dashboardStats.pending_risk_event_count }}</span>
          <span>失败入库：{{ dashboardStats.failed_document_count }}</span>
          <span>近 24h 问答：{{ dashboardStats.chat_request_count_24h }}</span>
        </div>
      </div>

      <div class="overview-banner__actions">
        <el-button
          v-for="action in banner.actions"
          :key="action.id"
          :type="action.to ? 'primary' : 'default'"
          @click="handleBannerAction(action)"
        >
          {{ action.label }}
        </el-button>
        <el-button @click="fetchData" :loading="isLoading">刷新运行状态</el-button>
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

    <section class="overview-primary-chart">
      <AppSectionCard title="近 7 天请求与命中趋势" desc="用于判断问答规模和知识召回表现是否同步变化。" admin>
        <AdminChart :option="trendOption" height="320px" />
      </AppSectionCard>
    </section>

    <section class="overview-main">
      <AppSectionCard title="待处理事项" desc="优先用于判断今天需要人工跟进的治理动作。" admin>
        <div v-if="!hasQueueItems" class="focus-empty-state">
          <div class="focus-empty-state__icon">✓</div>
          <div class="focus-empty-state__body">
            <strong>暂无待办事项，系统运行健康。</strong>
            <p>当前没有需要人工立即处理的审核或入库积压。</p>
          </div>
        </div>
        <div v-else class="focus-list">
          <article v-for="item in focusQueue" :key="item.id" class="focus-item" :class="toneClass(item.tone)">
            <div class="focus-item__head">
              <span class="focus-item__title">{{ item.title }}</span>
              <strong class="focus-item__value">{{ item.value }}</strong>
            </div>
            <p class="focus-item__desc">{{ item.desc }}</p>
          </article>
        </div>
      </AppSectionCard>

      <AppSectionCard title="运行摘要" desc="把关键指标转成下一步治理动作，而不是重复结论。" admin>
        <div class="summary-grid">
          <article v-for="item in operationalSummary" :key="item.id" class="summary-panel">
            <span class="summary-panel__label">{{ item.label }}</span>
            <strong class="summary-panel__value">{{ item.value }}</strong>
            <p class="summary-panel__detail">{{ item.detail }}</p>
          </article>
        </div>
      </AppSectionCard>
    </section>

    <section class="overview-secondary">
      <AppSectionCard title="最近失败任务" desc="优先查看可重试的失败入库与处理异常。" admin>
        <div v-if="failureItems.length === 0" class="failure-empty-state">暂无失败任务</div>
        <div v-else class="failure-list">
          <article v-for="item in failureItems" :key="item.id" class="failure-item">
            <div class="failure-item__head">
              <strong>{{ item.document_title }}</strong>
              <span>{{ formatTimestamp(item.updated_at) }}</span>
            </div>
            <p class="failure-item__meta">
              步骤：{{ formatStatus(item.current_step) }} · 重试次数：{{ item.retry_count ?? 0 }}
            </p>
            <p class="failure-item__message">{{ item.error_message || '失败详情未提供。' }}</p>
          </article>
        </div>
      </AppSectionCard>

      <AppSectionCard title="审计摘要" desc="展示最近平台关键动作与执行结果。" admin>
        <div v-if="auditItems.length === 0" class="failure-empty-state">暂无审计记录</div>
        <div v-else class="audit-list">
          <article v-for="item in auditItems" :key="item.id" class="audit-item">
            <div class="audit-item__head">
              <span class="evidence-log__badge" :class="toneClass(item.status === 'failed' ? 'risk' : 'info')">
                {{ formatStatus(item.status) }}
              </span>
              <strong>{{ formatAuditAction(item.action) }}</strong>
            </div>
            <p class="audit-item__meta">
              {{ item.actor_name || '系统' }} · {{ item.target_type }} / {{ item.target_id || '--' }}
            </p>
            <p class="audit-item__message">{{ item.summary }}</p>
          </article>
        </div>
      </AppSectionCard>
    </section>

    <section class="overview-charts">
      <AppSectionCard title="风险等级分布" desc="快速观察当前风险审查压力主要集中在哪个等级。" admin>
        <AdminChart :option="riskOption" height="310px" />
      </AppSectionCard>

      <AppSectionCard title="文档处理状态" desc="反映知识资产当前是否存在积压、失败或未完成索引。" admin>
        <AdminChart :option="documentOption" height="310px" />
      </AppSectionCard>
    </section>

    <section class="overview-evidence">
      <div ref="activitySection" class="overview-evidence__column">
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
      </div>

      <div ref="evidenceSection" class="overview-evidence__column">
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
      </div>
    </section>
  </div>
</template>

<style scoped>
.admin-page {
  gap: 20px;
}

.overview-banner {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 22px;
  border-radius: 24px;
  border: 1px solid var(--line-soft);
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.98), rgba(255, 255, 255, 0.96));
  box-shadow: var(--shadow-soft);
}

.overview-banner.is-warning {
  border-color: rgba(183, 121, 31, 0.2);
  background: linear-gradient(180deg, rgba(255, 247, 224, 0.98), rgba(255, 251, 240, 0.95));
}

.overview-banner.is-risk {
  border-color: rgba(196, 73, 61, 0.18);
  background: linear-gradient(180deg, rgba(255, 240, 238, 0.98), rgba(255, 247, 245, 0.95));
}

.overview-banner.is-info,
.overview-banner.is-neutral {
  border-color: rgba(36, 87, 197, 0.14);
  background: linear-gradient(180deg, rgba(240, 246, 255, 0.98), rgba(248, 251, 255, 0.95));
}

.overview-banner__copy,
.overview-banner__actions {
  display: flex;
  flex-direction: column;
}

.overview-banner__copy {
  gap: 10px;
  min-width: 0;
}

.overview-banner__actions {
  align-items: flex-end;
  justify-content: flex-start;
  gap: 10px;
  flex-shrink: 0;
}

.overview-banner__eyebrow {
  margin: 0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.overview-banner__title {
  margin: 0;
  font-size: clamp(26px, 3vw, 34px);
  line-height: 1.08;
  color: var(--text-primary);
}

.overview-banner__summary {
  margin: 0;
  max-width: 720px;
  color: var(--text-secondary);
  line-height: 1.65;
}

.overview-banner__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.overview-banner__meta span {
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

.overview-banner__actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

.overview-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.overview-primary-chart {
  display: block;
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
.overview-secondary,
.overview-evidence {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.overview-charts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.focus-list,
.summary-grid,
.failure-list,
.audit-list {
  display: grid;
  gap: 12px;
}

.failure-item,
.audit-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 15px 16px;
  border-radius: 16px;
  border: 1px solid var(--line-soft);
  background: var(--surface-2);
}

.failure-item__head,
.audit-item__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.failure-item__head span,
.failure-item__meta,
.audit-item__meta,
.audit-item__message {
  color: var(--text-secondary);
}

.failure-item__message {
  margin: 0;
  color: var(--text-primary);
}

.failure-empty-state {
  color: var(--text-secondary);
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

.focus-empty-state {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  padding: 16px;
  border-radius: 16px;
  background: rgba(33, 129, 92, 0.08);
  border: 1px solid rgba(33, 129, 92, 0.16);
}

.focus-empty-state__icon {
  width: 28px;
  height: 28px;
  border-radius: 999px;
  background: rgba(33, 129, 92, 0.14);
  color: var(--success);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 800;
  flex-shrink: 0;
}

.focus-empty-state__body {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.focus-empty-state__body strong {
  color: var(--text-primary);
  font-size: 15px;
}

.focus-empty-state__body p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
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

.overview-evidence__column {
  min-width: 0;
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
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .overview-banner {
    flex-direction: column;
  }

  .overview-banner__actions {
    align-items: flex-start;
    flex-direction: row;
    flex-wrap: wrap;
  }
}

@media (max-width: 960px) {
  .overview-main,
  .overview-evidence,
  .overview-metrics,
  .overview-charts,
  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
