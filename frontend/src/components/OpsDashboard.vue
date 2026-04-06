<script setup>
import { ref, onMounted } from "vue";
import { opsApi } from "../api/ops.js";
import { dashboardApi } from "../api/dashboard.js";

const dashboardStats = ref({});
const logs = ref([]);
const isLoading = ref(true);
const errorMsg = ref("");

const fetchData = async () => {
  isLoading.value = true;
  errorMsg.value = "";
  try {
    const [statsRes, logsRes] = await Promise.all([
      dashboardApi.getStats(),
      opsApi.getLogs()
    ]);
    dashboardStats.value = statsRes || {};
    logs.value = logsRes || [];
  } catch (error) {
    console.error("Dashboard data fetch failed:", error);
    errorMsg.value = "加载大盘数据失败，请重试";
  } finally {
    isLoading.value = false;
  }
};

onMounted(fetchData);

const getLogLevelColor = (level) => {
  const colors = {
    INFO: '#10b981',
    WARN: '#f59e0b',
    ERROR: '#ef4444'
  };
  return colors[level] || '#64748b';
};
</script>

<template>
  <div class="page-stack admin-page">
    <section class="page-hero page-hero--admin">
      <div>
        <div class="page-hero__eyebrow">Admin / Overview</div>
        <h1 class="page-hero__title">管理控制台总览</h1>
        <p class="page-hero__subtitle">
          后台页面强化控制台感：更深的底色、更强的状态信息和更明确的监控反馈，用来和业务工作区形成明显区隔。
        </p>
      </div>
      <button class="refresh-btn refresh-btn--hero" @click="fetchData" :disabled="isLoading">
        {{ isLoading ? '刷新中...' : '刷新数据' }}
      </button>
    </section>

    <div v-if="errorMsg" class="error-state">{{ errorMsg }}</div>

    <div class="grid">
      <div class="metric-card ui-card ui-card--admin">
        <div class="label">知识库数</div>
        <div class="value">{{ dashboardStats.knowledgebase_count !== undefined ? dashboardStats.knowledgebase_count : '--' }}</div>
      </div>
      <div class="metric-card ui-card ui-card--admin">
        <div class="label">文档总数</div>
        <div class="value">{{ dashboardStats.document_count !== undefined ? dashboardStats.document_count : '--' }}</div>
      </div>
      <div class="metric-card ui-card ui-card--admin">
        <div class="label">风险事件数</div>
        <div class="value">{{ dashboardStats.risk_event_count !== undefined ? dashboardStats.risk_event_count : '--' }}</div>
      </div>
      <div class="metric-card ui-card ui-card--admin metric-card--alert">
        <div class="label">待审核风险数</div>
        <div class="value highlight">{{ dashboardStats.pending_risk_event_count !== undefined ? dashboardStats.pending_risk_event_count : '--' }}</div>
      </div>
    </div>

    <div class="logs-section">
      <div class="logs-header">
        <div>
          <h4>实时系统日志</h4>
          <p class="logs-subtitle">用于快速定位运行状态、错误和服务波动。</p>
        </div>
        <div class="log-actions">
          <span class="log-count">{{ logs.length }} 条记录</span>
        </div>
      </div>
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
  </div>
</template>

<style scoped>
.admin-page { gap: 26px; }
.error-state { padding: 14px 16px; background: #fef2f2; color: #ef4444; border-radius: 14px; font-size: 14px; text-align: center; border: 1px solid #fca5a5; }
.grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; }
.metric-card { position: relative; overflow: hidden; padding: 22px; }
.metric-card::after { content: ''; position: absolute; top: 0; left: 0; width: 5px; height: 100%; background: linear-gradient(180deg, #2563eb, #60a5fa); opacity: 0.95; }
.metric-card--alert::after { background: linear-gradient(180deg, #f59e0b, #f97316); }
.metric-card .label { color: #64748b; font-size: 13px; margin-bottom: 10px; font-weight: 600; }
.metric-card .value { font-size: 28px; font-weight: 800; color: #0f172a; margin-bottom: 4px; }
.metric-card .value.highlight { color: #c2410c; }
.refresh-btn { padding: 10px 16px; background: white; border: 1px solid #dbe4f0; border-radius: 10px; font-size: 13px; cursor: pointer; transition: all 0.2s; font-weight: 700; }
.refresh-btn:hover { background: #f8fafc; border-color: #cbd5e1; }
.refresh-btn--hero { background: rgba(255, 255, 255, 0.12); color: #f8fafc; border-color: rgba(255,255,255,0.2); }
.refresh-btn--hero:hover { background: rgba(255,255,255,0.18); }
.logs-section { background: linear-gradient(180deg, #0f172a 0%, #111827 100%); border-radius: 22px; padding: 24px; color: #f8fafc; box-shadow: 0 28px 50px -34px rgba(15, 23, 42, 0.8); border: 1px solid rgba(148, 163, 184, 0.12); }
.logs-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 18px; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 14px; gap: 16px; }
.logs-header h4 { margin: 0; font-size: 18px; color: #e2e8f0; }
.logs-subtitle { margin-top: 6px; font-size: 13px; color: rgba(148, 163, 184, 0.88); }
.log-count { font-size: 12px; color: #94a3b8; background: rgba(255,255,255,0.06); padding: 6px 10px; border-radius: 999px; }
.logs-container { font-family: 'Fira Code', monospace; font-size: 12px; line-height: 1.7; max-height: 460px; overflow-y: auto; padding-right: 8px; }
.logs-container::-webkit-scrollbar { width: 6px; }
.logs-container::-webkit-scrollbar-track { background: transparent; }
.logs-container::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.12); border-radius: 10px; }
.log-line { margin-bottom: 8px; display: flex; gap: 8px; white-space: pre-wrap; word-break: break-all; padding: 6px 0; border-bottom: 1px dashed rgba(148, 163, 184, 0.08); }
.log-time { color: #64748b; flex-shrink: 0; }
.log-level { font-weight: 700; min-width: 45px; flex-shrink: 0; }
.log-module { color: #a78bfa; flex-shrink: 0; }
.log-msg { color: #e2e8f0; }
.logs-empty { text-align: center; padding: 40px; color: #64748b; }
@media (max-width: 1200px) {
  .grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 640px) {
  .grid { grid-template-columns: 1fr; }
}
</style>
