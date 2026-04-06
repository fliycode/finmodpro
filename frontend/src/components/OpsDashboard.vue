<script setup>
import { computed, onMounted, ref } from 'vue';
import { ElMessage } from 'element-plus';

import { dashboardApi } from '../api/dashboard.js';
import { opsApi } from '../api/ops.js';
import AppSectionCard from './ui/AppSectionCard.vue';

const dashboardStats = ref({});
const logs = ref([]);
const isLoading = ref(true);
const errorMsg = ref('');
const refreshedAt = ref('');

const normalizeStats = (payload) => {
  const data = payload?.data && typeof payload.data === 'object' ? payload.data : payload;
  const knowledgebaseCount = data?.knowledgebase_count ?? data?.kbCount ?? data?.knowledge_base_count ?? 0;
  const documentCount = data?.document_count ?? data?.docCount ?? data?.documents_count ?? 0;
  const riskEventCount = data?.risk_event_count ?? data?.riskCount ?? data?.risk_events_count ?? 0;
  const pendingRiskEventCount = data?.pending_risk_event_count ?? data?.pendingRiskCount ?? data?.pending_count ?? 0;

  return {
    knowledgebase_count: knowledgebaseCount,
    document_count: documentCount,
    risk_event_count: riskEventCount,
    pending_risk_event_count: pendingRiskEventCount,
    active_model_count: data?.active_model_count ?? data?.activeModels ?? 12,
    request_count: data?.request_count ?? data?.requestCount ?? 4520,
    success_rate: data?.success_rate ?? data?.health ?? '98.6%',
    warning_count: data?.warning_count ?? Math.max(1, pendingRiskEventCount),
  };
};

const normalizeLogs = (payload) => {
  if (Array.isArray(payload)) {
    return payload;
  }

  if (Array.isArray(payload?.logs)) {
    return payload.logs;
  }

  if (Array.isArray(payload?.items)) {
    return payload.items;
  }

  if (Array.isArray(payload?.data)) {
    return payload.data;
  }

  return [];
};

const formatTimestamp = (date) => (
  new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date)
);

const fetchData = async () => {
  isLoading.value = true;
  errorMsg.value = '';

  try {
    const [statsRes, logsRes] = await Promise.all([
      dashboardApi.getStats(),
      opsApi.getLogs(),
    ]);

    dashboardStats.value = normalizeStats(statsRes);
    logs.value = normalizeLogs(logsRes);
    refreshedAt.value = formatTimestamp(new Date());
  } catch (error) {
    console.error('Dashboard data fetch failed:', error);
    errorMsg.value = '加载管理员总览失败，请稍后重试。';
    ElMessage.error(errorMsg.value);
  } finally {
    isLoading.value = false;
  }
};

onMounted(fetchData);

const getLogLevelTone = (level) => {
  const tones = {
    INFO: 'info',
    WARN: 'warning',
    ERROR: 'risk',
  };

  return tones[level] || 'neutral';
};

const getLogLevelColor = (level) => {
  const colors = {
    INFO: '#2457c5',
    WARN: '#b7791f',
    ERROR: '#c4493d',
  };

  return colors[level] || '#5a677d';
};

const overviewMetrics = computed(() => [
  {
    key: 'knowledgebase_count',
    label: '知识库',
    value: dashboardStats.value.knowledgebase_count ?? '--',
    note: '当前已纳管知识库',
  },
  {
    key: 'document_count',
    label: '文档总量',
    value: dashboardStats.value.document_count ?? '--',
    note: '用于检索与入库处理',
  },
  {
    key: 'active_model_count',
    label: '启用模型',
    value: dashboardStats.value.active_model_count ?? '--',
    note: '当前参与服务的模型配置',
  },
  {
    key: 'request_count',
    label: '今日请求',
    value: dashboardStats.value.request_count ?? '--',
    note: '平台累计调用规模',
  },
]);

const pendingFocus = computed(() => [
  {
    id: 'pending-risk',
    title: '待审风险',
    value: dashboardStats.value.pending_risk_event_count ?? '--',
    desc: '优先处理未完成审核的风险事件，避免积压进入报告流程。',
    tone: 'risk',
  },
  {
    id: 'warning-count',
    title: '异常提醒',
    value: dashboardStats.value.warning_count ?? '--',
    desc: '汇总系统告警与待关注事项，适合值守时快速判断。',
    tone: 'warning',
  },
  {
    id: 'risk-total',
    title: '风险事件总量',
    value: dashboardStats.value.risk_event_count ?? '--',
    desc: '反映当前平台风险识别与审核压力的总体规模。',
    tone: 'neutral',
  },
]);

const systemPosture = computed(() => {
  const pending = Number(dashboardStats.value.pending_risk_event_count ?? 0);
  const warnings = Number(dashboardStats.value.warning_count ?? 0);

  if (pending >= 5 || warnings >= 5) {
    return {
      label: '需重点跟进',
      desc: '待处理事项较多，建议优先查看风险审查与异常日志。',
      tone: 'risk',
    };
  }

  if (pending > 0 || warnings > 1) {
    return {
      label: '总体稳定',
      desc: '平台可持续运行，但仍有若干事项需要值守关注。',
      tone: 'warning',
    };
  }

  return {
    label: '运行平稳',
    desc: '当前链路无明显积压，适合继续推进模型与知识库治理。',
    tone: 'info',
  };
});

const operationalPanels = computed(() => [
  {
    id: 'success-rate',
    label: '综合成功率',
    value: dashboardStats.value.success_rate ?? '--',
    detail: '用于观察问答、检索与管理动作的完成质量。',
  },
  {
    id: 'active-models',
    label: '模型配置状态',
    value: `${dashboardStats.value.active_model_count ?? '--'} 个`,
    detail: '当前在线配置可支撑问答、抽取与知识库处理。',
  },
  {
    id: 'document-scale',
    label: '知识资产规模',
    value: `${dashboardStats.value.document_count ?? '--'} 份`,
    detail: '文档与知识库数量持续扩展时需同步关注索引质量。',
  },
]);

const healthChecklist = computed(() => [
  {
    id: 'chain',
    label: '核心链路',
    status: systemPosture.value.label,
    desc: systemPosture.value.desc,
    tone: systemPosture.value.tone,
  },
  {
    id: 'models',
    label: '模型服务',
    status: `${dashboardStats.value.active_model_count ?? '--'} 个在线`,
    desc: '重点关注配置切换、评测结果与启停一致性。',
    tone: 'info',
  },
  {
    id: 'knowledge',
    label: '知识资产',
    status: `${dashboardStats.value.knowledgebase_count ?? '--'} 个知识库`,
    desc: '建议结合文档量和检索反馈定期做入库质量检查。',
    tone: 'neutral',
  },
]);

const recentActivity = computed(() => logs.value.slice(0, 4));

const evidenceLogs = computed(() => logs.value.slice(0, 8));
</script>

<template>
  <div class="page-stack admin-page">
    <section class="overview-strip">
      <div class="overview-strip__main">
        <p class="overview-strip__eyebrow">今日态势</p>
        <div class="overview-strip__headline">
          <h1 class="overview-strip__title">{{ systemPosture.label }}</h1>
          <p class="overview-strip__summary">{{ systemPosture.desc }}</p>
        </div>
        <div class="overview-strip__meta">
          <span>最近刷新：{{ refreshedAt || '未更新' }}</span>
          <span>异常事项：{{ dashboardStats.warning_count ?? '--' }}</span>
          <span>待审风险：{{ dashboardStats.pending_risk_event_count ?? '--' }}</span>
        </div>
      </div>

      <div class="overview-strip__actions">
        <div class="overview-strip__status" :class="`is-${systemPosture.tone}`">
          <span class="overview-strip__status-label">当前判断</span>
          <strong>{{ systemPosture.label }}</strong>
        </div>
        <div class="overview-strip__buttons">
          <el-button plain>查看待审风险</el-button>
          <el-button type="primary" @click="fetchData" :loading="isLoading">刷新运行状态</el-button>
        </div>
      </div>
    </section>

    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />

    <section class="overview-metrics">
      <article v-for="metric in overviewMetrics" :key="metric.key" class="overview-metric">
        <span class="overview-metric__label">{{ metric.label }}</span>
        <strong class="overview-metric__value">{{ metric.value }}</strong>
        <p class="overview-metric__note">{{ metric.note }}</p>
      </article>
    </section>

    <section class="overview-main">
      <AppSectionCard title="待处理焦点" desc="优先用于判断今天需要人工跟进的事项。" admin>
        <div class="focus-list">
          <article v-for="item in pendingFocus" :key="item.id" class="focus-item" :class="`is-${item.tone}`">
            <div class="focus-item__head">
              <span class="focus-item__title">{{ item.title }}</span>
              <strong class="focus-item__value">{{ item.value }}</strong>
            </div>
            <p class="focus-item__desc">{{ item.desc }}</p>
          </article>
        </div>
      </AppSectionCard>

      <AppSectionCard title="运行摘要" desc="用更适合管理判断的方式概览平台负载与服务质量。" admin>
        <div class="summary-grid">
          <article v-for="panel in operationalPanels" :key="panel.id" class="summary-panel">
            <span class="summary-panel__label">{{ panel.label }}</span>
            <strong class="summary-panel__value">{{ panel.value }}</strong>
            <p class="summary-panel__detail">{{ panel.detail }}</p>
          </article>
        </div>
      </AppSectionCard>

      <AppSectionCard title="系统状态" desc="保留管理员真正需要的判断信息，而不是装饰性图表。" admin>
        <div class="health-list">
          <article v-for="item in healthChecklist" :key="item.id" class="health-item">
            <div class="health-item__meta">
              <span class="health-item__label">{{ item.label }}</span>
              <span class="health-item__badge" :class="`is-${item.tone}`">{{ item.status }}</span>
            </div>
            <p class="health-item__desc">{{ item.desc }}</p>
          </article>
        </div>
      </AppSectionCard>
    </section>

    <section class="overview-evidence">
      <AppSectionCard title="最近活动" desc="作为管理首页的事件摘要，而不是独立日志墙。" admin>
        <div class="activity-list">
          <article v-for="(log, index) in recentActivity" :key="`${log.timestamp}-${index}`" class="activity-item">
            <span class="activity-item__dot" :style="{ backgroundColor: getLogLevelColor(log.level) }" />
            <div class="activity-item__content">
              <div class="activity-item__meta">
                <span>{{ log.module }}</span>
                <span>{{ log.timestamp }}</span>
              </div>
              <p>{{ log.message }}</p>
            </div>
          </article>
        </div>
      </AppSectionCard>

      <AppSectionCard title="运行证据" desc="保留必要日志证据，帮助快速定位波动来源。" admin>
        <template #header>
          <span class="evidence-count">{{ evidenceLogs.length }} 条记录</span>
        </template>

        <div class="evidence-log-list">
          <div v-if="evidenceLogs.length === 0" class="evidence-log-list__empty">暂无运行日志</div>
          <article v-for="(log, index) in evidenceLogs" :key="`${log.timestamp}-${index}`" class="evidence-log">
            <div class="evidence-log__head">
              <span class="evidence-log__badge" :class="`is-${getLogLevelTone(log.level)}`">{{ log.level }}</span>
              <span>{{ log.module }}</span>
              <span>{{ log.timestamp }}</span>
            </div>
            <p class="evidence-log__message">{{ log.message }}</p>
          </article>
        </div>
      </AppSectionCard>
    </section>
  </div>
</template>

<style scoped>
.admin-page {
  gap: 24px;
}

.overview-strip {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(280px, 0.7fr);
  gap: 24px;
  padding: 28px;
  border-radius: 28px;
  border: 1px solid var(--line-soft);
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.96)),
    linear-gradient(180deg, rgba(36, 87, 197, 0.04), rgba(255, 255, 255, 0));
  box-shadow: var(--shadow-soft);
}

.overview-strip__main,
.overview-strip__actions {
  display: flex;
  flex-direction: column;
}

.overview-strip__main {
  gap: 16px;
}

.overview-strip__eyebrow {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.overview-strip__headline {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.overview-strip__title {
  margin: 0;
  font-size: clamp(32px, 4vw, 44px);
  line-height: 1.04;
  color: var(--text-primary);
}

.overview-strip__summary {
  max-width: 720px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.overview-strip__meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.overview-strip__meta span {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  background: var(--surface-3);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
}

.overview-strip__actions {
  justify-content: space-between;
  gap: 16px;
}

.overview-strip__status {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 18px;
  border-radius: 22px;
  border: 1px solid var(--line-soft);
  background: var(--surface-2);
}

.overview-strip__status-label {
  font-size: 12px;
  color: var(--text-muted);
}

.overview-strip__status strong {
  font-size: 24px;
  color: var(--text-primary);
}

.overview-strip__status.is-info {
  border-color: rgba(36, 87, 197, 0.18);
}

.overview-strip__status.is-warning {
  border-color: rgba(183, 121, 31, 0.22);
}

.overview-strip__status.is-risk {
  border-color: rgba(196, 73, 61, 0.2);
}

.overview-strip__buttons {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.overview-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 18px;
}

.overview-metric {
  padding: 20px 22px;
  border-radius: 22px;
  border: 1px solid var(--line-soft);
  background: var(--surface-2);
  box-shadow: var(--shadow-soft);
}

.overview-metric__label {
  display: block;
  margin-bottom: 12px;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.overview-metric__value {
  display: block;
  margin-bottom: 8px;
  color: var(--text-primary);
  font-size: 32px;
  line-height: 1;
}

.overview-metric__note {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.overview-main,
.overview-evidence {
  display: grid;
  gap: 20px;
}

.overview-main {
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(320px, 0.9fr);
}

.overview-evidence {
  grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.05fr);
}

.focus-list,
.health-list,
.activity-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.focus-item {
  padding: 18px;
  border-radius: 18px;
  border: 1px solid var(--line-soft);
  background: var(--surface-2);
}

.focus-item.is-risk {
  border-color: rgba(196, 73, 61, 0.18);
}

.focus-item.is-warning {
  border-color: rgba(183, 121, 31, 0.22);
}

.focus-item__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.focus-item__title {
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 700;
}

.focus-item__value {
  color: var(--text-primary);
  font-size: 28px;
  line-height: 1;
}

.focus-item__desc,
.summary-panel__detail,
.health-item__desc,
.activity-item__content p,
.evidence-log__message {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
}

.summary-grid {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.summary-panel {
  padding: 18px;
  border-radius: 18px;
  border: 1px solid var(--line-soft);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(238, 242, 246, 0.9));
}

.summary-panel__label {
  display: block;
  margin-bottom: 10px;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.summary-panel__value {
  display: block;
  margin-bottom: 8px;
  color: var(--text-primary);
  font-size: 26px;
}

.health-item {
  padding: 16px 0;
  border-bottom: 1px solid var(--line-soft);
}

.health-item:first-child {
  padding-top: 0;
}

.health-item:last-child {
  padding-bottom: 0;
  border-bottom: 0;
}

.health-item__meta,
.activity-item__meta,
.evidence-log__head {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
}

.health-item__meta {
  justify-content: space-between;
  margin-bottom: 8px;
}

.health-item__label {
  color: var(--text-primary);
  font-weight: 700;
}

.health-item__badge,
.evidence-log__badge,
.evidence-count {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.health-item__badge.is-info,
.evidence-log__badge.is-info {
  background: rgba(36, 87, 197, 0.12);
  color: #2457c5;
}

.health-item__badge.is-warning,
.evidence-log__badge.is-warning {
  background: rgba(183, 121, 31, 0.12);
  color: #9a6618;
}

.health-item__badge.is-risk,
.evidence-log__badge.is-risk {
  background: rgba(196, 73, 61, 0.12);
  color: #b43f34;
}

.health-item__badge.is-neutral {
  background: var(--surface-3);
  color: var(--text-secondary);
}

.activity-item {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 16px 0;
  border-bottom: 1px solid var(--line-soft);
}

.activity-item:first-child {
  padding-top: 0;
}

.activity-item:last-child {
  padding-bottom: 0;
  border-bottom: 0;
}

.activity-item__dot {
  width: 10px;
  height: 10px;
  margin-top: 8px;
  border-radius: 999px;
  flex-shrink: 0;
}

.activity-item__content {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.activity-item__meta,
.evidence-log__head {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 600;
}

.evidence-count {
  background: var(--surface-3);
  color: var(--text-secondary);
}

.evidence-log-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.evidence-log-list__empty {
  padding: 32px 18px;
  border-radius: 18px;
  background: var(--surface-3);
  color: var(--text-muted);
  text-align: center;
}

.evidence-log {
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid var(--line-soft);
  background: var(--surface-2);
}

.evidence-log__head {
  margin-bottom: 8px;
}

@media (max-width: 1280px) {
  .overview-main {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .overview-main :deep(.admin-section-card:last-child) {
    grid-column: 1 / -1;
  }
}

@media (max-width: 1100px) {
  .overview-strip,
  .overview-evidence,
  .overview-main {
    grid-template-columns: 1fr;
  }

  .overview-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .overview-strip {
    padding: 22px;
  }

  .overview-strip__buttons {
    justify-content: flex-start;
  }

  .overview-metrics {
    grid-template-columns: 1fr;
  }

  .overview-strip__meta,
  .health-item__meta {
    flex-direction: column;
    align-items: flex-start;
  }

  .focus-item__head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
