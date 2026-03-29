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
  <div class="ops-shell">
    <div class="header">
      <div class="title-group">
        <h3>工作台大盘</h3>
        <span class="badge">管理员模式</span>
      </div>
      <button class="refresh-btn" @click="fetchData" :disabled="isLoading">
        {{ isLoading ? '刷新中...' : '刷新数据' }}
      </button>
    </div>

    <div v-if="errorMsg" class="error-state">{{ errorMsg }}</div>

    <div class="grid">
      <div class="metric-card">
        <div class="label">知识库数</div>
        <div class="value">{{ dashboardStats.knowledgebase_count !== undefined ? dashboardStats.knowledgebase_count : '--' }}</div>
      </div>
      <div class="metric-card">
        <div class="label">文档总数</div>
        <div class="value">{{ dashboardStats.document_count !== undefined ? dashboardStats.document_count : '--' }}</div>
      </div>
      <div class="metric-card">
        <div class="label">风险事件数</div>
        <div class="value">{{ dashboardStats.risk_event_count !== undefined ? dashboardStats.risk_event_count : '--' }}</div>
      </div>
      <div class="metric-card">
        <div class="label">待审核风险数</div>
        <div class="value highlight">{{ dashboardStats.pending_risk_event_count !== undefined ? dashboardStats.pending_risk_event_count : '--' }}</div>
      </div>
    </div>

    <div class="logs-section">
      <div class="logs-header">
        <h4>实时系统日志</h4>
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
.ops-shell { display: flex; flex-direction: column; gap: 24px; }
.header { display: flex; align-items: center; justify-content: space-between; }
.title-group { display: flex; align-items: center; gap: 12px; }
.header h3 { margin: 0; color: #1e293b; }
.badge { background: #fee2e2; color: #991b1b; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 700; text-transform: uppercase; }
.refresh-btn { padding: 8px 16px; background: white; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 13px; cursor: pointer; transition: all 0.2s; }
.refresh-btn:hover { background: #f8fafc; border-color: #cbd5e1; }

.error-state { padding: 12px; background: #fef2f2; color: #ef4444; border-radius: 8px; font-size: 14px; text-align: center; border: 1px solid #fca5a5; }

.grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; }
.metric-card { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); position: relative; overflow: hidden; }
.metric-card::after { content: ''; position: absolute; top: 0; left: 0; width: 4px; height: 100%; background: #6366f1; opacity: 0.5; }
.metric-card .label { color: #64748b; font-size: 13px; margin-bottom: 8px; font-weight: 500; }
.metric-card .value { font-size: 24px; font-weight: 700; color: #1e293b; margin-bottom: 4px; }
.metric-card .value.highlight { color: #f59e0b; }

.logs-section { background: #1e293b; border-radius: 12px; padding: 24px; color: #f8fafc; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
.logs-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 12px; }
.logs-header h4 { margin: 0; font-size: 16px; color: #e2e8f0; }
.log-count { font-size: 12px; color: #94a3b8; }

.logs-container { font-family: 'Fira Code', monospace; font-size: 12px; line-height: 1.6; max-height: 400px; overflow-y: auto; padding-right: 8px; }
.logs-container::-webkit-scrollbar { width: 6px; }
.logs-container::-webkit-scrollbar-track { background: transparent; }
.logs-container::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 10px; }

.log-line { margin-bottom: 6px; display: flex; gap: 8px; white-space: pre-wrap; word-break: break-all; }
.log-time { color: #64748b; flex-shrink: 0; }
.log-level { font-weight: 700; min-width: 45px; flex-shrink: 0; }
.log-module { color: #a855f7; flex-shrink: 0; }
.log-msg { color: #e2e8f0; }
.logs-empty { text-align: center; padding: 40px; color: #64748b; }

@media (max-width: 1200px) {
  .grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 640px) {
  .grid { grid-template-columns: 1fr; }
}
</style>
