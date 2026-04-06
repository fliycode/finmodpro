<script setup>
import { computed, onMounted, ref } from 'vue';
import { ElMessage } from 'element-plus';

import { opsApi } from '../api/ops.js';
import { dashboardApi } from '../api/dashboard.js';
import AppSectionCard from './ui/AppSectionCard.vue';

const dashboardStats = ref({});
const logs = ref([]);
const isLoading = ref(true);
const errorMsg = ref('');

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
  const list = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.logs)
      ? payload.logs
      : Array.isArray(payload?.items)
        ? payload.items
        : Array.isArray(payload?.data)
          ? payload.data
          : [];
  return list;
};

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
  } catch (error) {
    console.error('Dashboard data fetch failed:', error);
    errorMsg.value = '加载仪表盘数据失败，请稍后重试';
    ElMessage.error(errorMsg.value);
  } finally {
    isLoading.value = false;
  }
};

onMounted(fetchData);

const overviewMetrics = computed(() => [
  { key: 'knowledgebase_count', label: '知识库', value: dashboardStats.value.knowledgebase_count ?? '--', trend: '+12%', tone: 'blue' },
  { key: 'document_count', label: '文档总量', value: dashboardStats.value.document_count ?? '--', trend: '+8%', tone: 'cyan' },
  { key: 'risk_event_count', label: '风险事件', value: dashboardStats.value.risk_event_count ?? '--', trend: '+5%', tone: 'violet' },
  { key: 'pending_risk_event_count', label: '待处理事项', value: dashboardStats.value.pending_risk_event_count ?? '--', trend: '需关注', tone: 'orange', alert: true },
]);

const kpiCards = computed(() => [
  { label: '活跃模型', value: dashboardStats.value.active_model_count ?? '--', desc: '当前可用推理配置' },
  { label: '今日请求', value: dashboardStats.value.request_count ?? '--', desc: '累计平台调用量' },
  { label: '成功率', value: dashboardStats.value.success_rate ?? '--', desc: '综合任务完成表现' },
  { label: '预警数', value: dashboardStats.value.warning_count ?? '--', desc: '需人工关注项' },
]);

const quickPanels = computed(() => [
  {
    title: '平台运行态势',
    value: dashboardStats.value.success_rate ?? '98.6%',
    meta: '核心链路稳定',
    bars: [82, 74, 91, 68, 87, 79, 94],
  },
  {
    title: '数据资源热度',
    value: dashboardStats.value.document_count ?? 0,
    meta: '文档与知识持续累积',
    bars: [46, 58, 63, 71, 66, 78, 84],
  },
]);

const recentActivity = computed(() => logs.value.slice(0, 5));

const getLogLevelColor = (level) => {
  const colors = {
    INFO: '#10b981',
    WARN: '#f59e0b',
    ERROR: '#ef4444',
  };
  return colors[level] || '#64748b';
};
</script>

<template>
  <div class="page-stack admin-page">
    <section class="dashboard-hero">
      <div class="dashboard-hero__content">
        <div class="dashboard-hero__eyebrow">Admin / Dashboard</div>
        <h1 class="dashboard-hero__title">仪表盘</h1>
        <p class="dashboard-hero__subtitle">集中查看平台运行、数据资产、风险待办与系统动态。</p>
      </div>
      <div class="dashboard-hero__actions">
        <div class="dashboard-hero__badge">
          <span class="dashboard-hero__badge-label">当前状态</span>
          <strong>稳定运行</strong>
        </div>
        <el-button type="primary" @click="fetchData" :loading="isLoading">刷新数据</el-button>
      </div>
    </section>

    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />

    <section class="dashboard-grid dashboard-grid--metrics">
      <article
        v-for="metric in overviewMetrics"
        :key="metric.key"
        class="dashboard-metric"
        :class="[`dashboard-metric--${metric.tone}`, { 'is-alert': metric.alert }]"
      >
        <div class="dashboard-metric__top">
          <span class="dashboard-metric__label">{{ metric.label }}</span>
          <span class="dashboard-metric__trend">{{ metric.trend }}</span>
        </div>
        <div class="dashboard-metric__value">{{ metric.value }}</div>
      </article>
    </section>

    <section class="dashboard-grid dashboard-grid--main">
      <AppSectionCard title="核心指标" desc="从模型、请求、成功率与预警数观察平台总体表现。" admin>
        <div class="dashboard-kpi-grid">
          <article v-for="card in kpiCards" :key="card.label" class="dashboard-kpi-card">
            <span class="dashboard-kpi-card__label">{{ card.label }}</span>
            <strong class="dashboard-kpi-card__value">{{ card.value }}</strong>
            <span class="dashboard-kpi-card__desc">{{ card.desc }}</span>
          </article>
        </div>
      </AppSectionCard>

      <AppSectionCard title="运行看板" desc="以更视觉化的方式呈现平台节奏与资源热度。" admin>
        <div class="dashboard-panel-stack">
          <article v-for="panel in quickPanels" :key="panel.title" class="dashboard-mini-panel">
            <div class="dashboard-mini-panel__header">
              <div>
                <h3>{{ panel.title }}</h3>
                <p>{{ panel.meta }}</p>
              </div>
              <strong>{{ panel.value }}</strong>
            </div>
            <div class="dashboard-mini-panel__bars">
              <span v-for="(bar, index) in panel.bars" :key="`${panel.title}-${index}`" :style="{ height: `${bar}%` }" />
            </div>
          </article>
        </div>
      </AppSectionCard>
    </section>

    <section class="dashboard-grid dashboard-grid--bottom">
      <AppSectionCard title="最近动态" desc="保留更像仪表盘的近期事件摘要。" admin>
        <div class="dashboard-activity-list">
          <article v-for="(log, index) in recentActivity" :key="`${log.timestamp}-${index}`" class="dashboard-activity-item">
            <div class="dashboard-activity-item__dot" :style="{ backgroundColor: getLogLevelColor(log.level) }" />
            <div class="dashboard-activity-item__content">
              <div class="dashboard-activity-item__meta">
                <span>{{ log.module }}</span>
                <span>{{ log.timestamp }}</span>
              </div>
              <p>{{ log.message }}</p>
            </div>
          </article>
        </div>
      </AppSectionCard>

      <AppSectionCard title="实时系统日志" desc="用于快速定位运行状态、错误和服务波动。" admin>
        <template #header>
          <div class="log-actions">
            <span class="log-count">{{ logs.length }} 条记录</span>
          </div>
        </template>

        <div class="logs-section">
          <div class="logs-container">
            <div v-if="logs.length === 0" class="logs-empty">暂无系统日志</div>
            <div v-for="(log, index) in logs" :key="index" class="log-line">
              <span class="log-time">[{{ log.timestamp }}]</span>
              <span class="log-level" :style="{ color: getLogLevelColor(log.level) }">{{ log.level }}</span>
              <span class="log-module">[{{ log.module }}]</span>
              <span class="log-msg">{{ log.message }}</span>
            </div>
          </div>
        </div>
      </AppSectionCard>
    </section>
  </div>
</template>

<style scoped>
.admin-page {
  gap: 24px;
}

.dashboard-hero {
  display: flex;
  align-items: stretch;
  justify-content: space-between;
  gap: 20px;
  padding: 28px 30px;
  border-radius: 28px;
  background: linear-gradient(135deg, #0f172a 0%, #172554 52%, #2563eb 100%);
  color: #eff6ff;
  box-shadow: 0 28px 54px -34px rgba(15, 23, 42, 0.65);
}

.dashboard-hero__content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.dashboard-hero__eyebrow {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: rgba(191, 219, 254, 0.92);
}

.dashboard-hero__title {
  margin: 0;
  font-size: 34px;
  line-height: 1.1;
  color: #f8fafc;
}

.dashboard-hero__subtitle {
  margin: 0;
  color: rgba(226, 232, 240, 0.82);
  line-height: 1.75;
}

.dashboard-hero__actions {
  display: flex;
  align-items: flex-end;
  gap: 14px;
  flex-wrap: wrap;
}

.dashboard-hero__badge {
  min-width: 132px;
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(10px);
}

.dashboard-hero__badge-label {
  display: block;
  font-size: 12px;
  color: rgba(191, 219, 254, 0.82);
  margin-bottom: 6px;
}

.dashboard-grid {
  display: grid;
  gap: 20px;
}

.dashboard-grid--metrics {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.dashboard-grid--main,
.dashboard-grid--bottom {
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr);
}

.dashboard-metric {
  position: relative;
  overflow: hidden;
  padding: 22px;
  border-radius: 22px;
  background: linear-gradient(180deg, #ffffff, #f8fafc);
  border: 1px solid rgba(226, 232, 240, 0.9);
  box-shadow: 0 20px 34px -28px rgba(15, 23, 42, 0.28);
}

.dashboard-metric::after {
  content: '';
  position: absolute;
  inset: auto 0 0 0;
  height: 4px;
  opacity: 0.9;
}

.dashboard-metric--blue::after { background: linear-gradient(90deg, #2563eb, #60a5fa); }
.dashboard-metric--cyan::after { background: linear-gradient(90deg, #0891b2, #67e8f9); }
.dashboard-metric--violet::after { background: linear-gradient(90deg, #7c3aed, #c4b5fd); }
.dashboard-metric--orange::after { background: linear-gradient(90deg, #f59e0b, #fb923c); }

.dashboard-metric__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 16px;
}

.dashboard-metric__label {
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
}

.dashboard-metric__trend {
  font-size: 12px;
  color: #2563eb;
  background: #eff6ff;
  border-radius: 999px;
  padding: 5px 9px;
}

.dashboard-metric.is-alert .dashboard-metric__trend {
  color: #c2410c;
  background: #fff7ed;
}

.dashboard-metric__value {
  font-size: 34px;
  font-weight: 800;
  color: #0f172a;
}

.dashboard-kpi-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.dashboard-kpi-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 18px;
  border-radius: 18px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
  border: 1px solid rgba(191, 219, 254, 0.58);
}

.dashboard-kpi-card__label {
  font-size: 13px;
  color: #64748b;
  font-weight: 700;
}

.dashboard-kpi-card__value {
  font-size: 26px;
  color: #0f172a;
}

.dashboard-kpi-card__desc {
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
}

.dashboard-panel-stack {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.dashboard-mini-panel {
  padding: 18px;
  border-radius: 18px;
  background: linear-gradient(135deg, #eff6ff, #ffffff);
  border: 1px solid rgba(191, 219, 254, 0.8);
}

.dashboard-mini-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 18px;
}

.dashboard-mini-panel__header h3 {
  margin: 0 0 6px;
  font-size: 17px;
  color: #0f172a;
}

.dashboard-mini-panel__header p {
  color: #64748b;
  font-size: 13px;
}

.dashboard-mini-panel__header strong {
  font-size: 24px;
  color: #1d4ed8;
}

.dashboard-mini-panel__bars {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  height: 80px;
}

.dashboard-mini-panel__bars span {
  flex: 1;
  border-radius: 999px 999px 6px 6px;
  background: linear-gradient(180deg, #60a5fa, #2563eb);
  min-height: 18px;
}

.dashboard-activity-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.dashboard-activity-item {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 14px 0;
  border-bottom: 1px solid rgba(226, 232, 240, 0.8);
}

.dashboard-activity-item:last-child {
  border-bottom: 0;
  padding-bottom: 0;
}

.dashboard-activity-item__dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  margin-top: 6px;
  flex-shrink: 0;
}

.dashboard-activity-item__content {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.dashboard-activity-item__meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  color: #64748b;
  font-size: 12px;
  font-weight: 600;
}

.dashboard-activity-item__content p {
  margin: 0;
  color: #0f172a;
  line-height: 1.6;
}

.log-actions {
  margin-left: auto;
}

.log-count {
  font-size: 12px;
  color: #94a3b8;
  background: rgba(15, 23, 42, 0.04);
  padding: 6px 10px;
  border-radius: 999px;
}

.logs-section {
  background: linear-gradient(180deg, #0f172a 0%, #111827 100%);
  border-radius: 22px;
  padding: 24px;
  color: #f8fafc;
  box-shadow: 0 28px 50px -34px rgba(15, 23, 42, 0.8);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.logs-container {
  font-family: 'Fira Code', monospace;
  font-size: 12px;
  line-height: 1.7;
  max-height: 460px;
  overflow-y: auto;
  padding-right: 8px;
}

.logs-container::-webkit-scrollbar {
  width: 6px;
}

.logs-container::-webkit-scrollbar-track {
  background: transparent;
}

.logs-container::-webkit-scrollbar-thumb {
  background: rgba(255,255,255,0.12);
  border-radius: 10px;
}

.log-line {
  margin-bottom: 8px;
  display: flex;
  gap: 8px;
  white-space: pre-wrap;
  word-break: break-all;
  padding: 6px 0;
  border-bottom: 1px dashed rgba(148, 163, 184, 0.08);
}

.log-time {
  color: #64748b;
  flex-shrink: 0;
}

.log-level {
  font-weight: 700;
  min-width: 45px;
  flex-shrink: 0;
}

.log-module {
  color: #a78bfa;
  flex-shrink: 0;
}

.log-msg {
  color: #e2e8f0;
}

.logs-empty {
  text-align: center;
  padding: 40px;
  color: #64748b;
}

@media (max-width: 1200px) {
  .dashboard-grid--metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .dashboard-grid--main,
  .dashboard-grid--bottom {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .dashboard-grid--metrics,
  .dashboard-kpi-grid {
    grid-template-columns: 1fr;
  }

  .dashboard-hero {
    flex-direction: column;
  }
}
</style>
