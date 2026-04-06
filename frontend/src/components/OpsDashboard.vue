<script setup>
import { ref, onMounted } from "vue";
import { ElMessage } from 'element-plus';
import { opsApi } from "../api/ops.js";
import { dashboardApi } from "../api/dashboard.js";
import AppSectionCard from "./ui/AppSectionCard.vue";

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
    ElMessage.error(errorMsg.value);
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

const metrics = [
  { key: 'knowledgebase_count', label: '知识库数' },
  { key: 'document_count', label: '文档总数' },
  { key: 'risk_event_count', label: '风险事件数' },
  { key: 'pending_risk_event_count', label: '待审核风险数', alert: true },
];
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
      <el-button type="primary" @click="fetchData" :loading="isLoading">刷新数据</el-button>
    </section>

    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />

    <div class="grid">
      <el-card v-for="metric in metrics" :key="metric.key" class="metric-card ui-card ui-card--admin" shadow="hover" :class="{ 'metric-card--alert': metric.alert }">
        <div class="label">{{ metric.label }}</div>
        <div class="value" :class="{ highlight: metric.alert }">{{ dashboardStats[metric.key] !== undefined ? dashboardStats[metric.key] : '--' }}</div>
      </el-card>
    </div>

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
  </div>
</template>

<style scoped>
.admin-page { gap: 26px; }
.grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; }
.metric-card { position: relative; overflow: hidden; padding: 22px; }
.metric-card::after { content: ''; position: absolute; top: 0; left: 0; width: 5px; height: 100%; background: linear-gradient(180deg, #2563eb, #60a5fa); opacity: 0.95; }
.metric-card--alert::after { background: linear-gradient(180deg, #f59e0b, #f97316); }
.metric-card .label { color: #64748b; font-size: 13px; margin-bottom: 10px; font-weight: 600; }
.metric-card .value { font-size: 28px; font-weight: 800; color: #0f172a; margin-bottom: 4px; }
.metric-card .value.highlight { color: #c2410c; }
.log-actions { margin-left: auto; }
.log-count { font-size: 12px; color: #94a3b8; background: rgba(15, 23, 42, 0.04); padding: 6px 10px; border-radius: 999px; }
.logs-section { background: linear-gradient(180deg, #0f172a 0%, #111827 100%); border-radius: 22px; padding: 24px; color: #f8fafc; box-shadow: 0 28px 50px -34px rgba(15, 23, 42, 0.8); border: 1px solid rgba(148, 163, 184, 0.12); }
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
