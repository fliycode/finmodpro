<script setup>
import { computed, onMounted, ref } from 'vue';

import { llmGatewayApi } from '../api/llm-gateway.js';
import {
  normalizeGatewayLogs,
  normalizeGatewayLogsSummary,
  normalizeGatewaySummary,
  normalizeGatewayTrace,
} from '../lib/llm-gateway.js';
import { buildBoardAxis, buildBoardTooltip, chartColors } from '../lib/admin-dashboard.js';
import AdminChart from './admin/AdminChart.vue';
import AdminDataTable from './admin/AdminDataTable.vue';
import OpsInspectorDrawer from './admin/ops/OpsInspectorDrawer.vue';
import OpsSectionFrame from './admin/ops/OpsSectionFrame.vue';
import OpsStatusBand from './admin/ops/OpsStatusBand.vue';
import AppSectionCard from './ui/AppSectionCard.vue';

/* ---------- State ---------- */

const logs = ref(normalizeGatewayLogs());
const summary = ref(normalizeGatewayLogsSummary());
const summaryStats = ref(normalizeGatewaySummary());
const trace = ref(normalizeGatewayTrace());
const traceDrawerVisible = ref(false);
const isLoading = ref(false);
const isTraceLoading = ref(false);
const errorMsg = ref('');

const timeWindow = ref('24h');
const modelFilter = ref('');
const statusFilter = ref('');
const page = ref(1);
const pageSize = ref(25);

/* ---------- Options ---------- */

const timeOptions = [
  { label: '1 小时', value: '1h' },
  { label: '6 小时', value: '6h' },
  { label: '24 小时', value: '24h' },
  { label: '7 天', value: '7d' },
];

const statusOptions = [
  { label: '全部状态', value: '' },
  { label: '成功', value: 'success' },
  { label: '失败', value: 'failed' },
];

const modelOptions = computed(() =>
  (summaryStats.value.top_models || []).map((m) => ({
    label: m.alias,
    value: m.alias,
  })),
);

/* ---------- Summary band ---------- */

const summaryItems = computed(() => {
  const traffic = summaryStats.value.traffic || {};
  const gateway = summaryStats.value.gateway || {};
  const errorRate = Number(traffic.error_rate_pct) || 0;
  const avgLatency = Number(summary.value.avg_latency_ms) || 0;

  return [
    {
      key: 'requests',
      label: '总请求',
      value: formatInteger(traffic.request_count),
      icon: 'request-page',
      tone: 'brand',
    },
    {
      key: 'error-rate',
      label: '错误率',
      value: `${errorRate.toFixed(1)}%`,
      icon: 'warning',
      tone: errorRate > 5 ? 'risk' : errorRate > 2 ? 'warning' : 'success',
    },
    {
      key: 'latency',
      label: '平均延迟',
      value: `${avgLatency.toFixed(0)} ms`,
      icon: 'timer',
      tone: avgLatency > 5000 ? 'risk' : avgLatency > 2000 ? 'warning' : 'success',
    },
    {
      key: 'models',
      label: '活跃模型',
      value: String(gateway.active_model_count || 0),
      icon: 'model-training',
      tone: 'accent',
    },
  ];
});

/* ---------- Charts ---------- */

const tokenChartOption = computed(() => {
  const data = tokenUsageByModel.value;
  if (data.length === 0) return {};
  const c = chartColors();
  const axis = buildBoardAxis();

  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...buildBoardTooltip() },
    legend: {
      top: 4,
      textStyle: { color: c.textSecondary, fontSize: 11 },
    },
    grid: { left: 12, right: 16, top: 40, bottom: 8, containLabel: true },
    xAxis: {
      type: 'category',
      data: data.map((d) => d.name),
      axisLabel: { color: c.textSecondary, fontSize: 10, rotate: data.length > 5 ? 20 : 0 },
      axisLine: axis.axisLine,
    },
    yAxis: {
      type: 'value',
      axisLabel: axis.axisLabel,
      splitLine: { lineStyle: { color: c.gridLine } },
    },
    series: [
      {
        name: '输入 Token',
        type: 'bar',
        stack: 'tokens',
        data: data.map((d) => d.input),
        itemStyle: { color: c.brand },
      },
      {
        name: '输出 Token',
        type: 'bar',
        stack: 'tokens',
        data: data.map((d) => d.output),
        itemStyle: { color: c.brandSoft, borderRadius: [4, 4, 0, 0] },
      },
    ],
  };
});

const tokenUsageByModel = computed(() => {
  const map = new Map();
  for (const log of logs.value.logs) {
    const key = log.alias || log.upstream_model || 'unknown';
    const entry = map.get(key) || { input: 0, output: 0 };
    entry.input += log.request_tokens;
    entry.output += log.response_tokens;
    map.set(key, entry);
  }
  return Array.from(map.entries())
    .map(([name, v]) => ({ name, ...v }))
    .sort((a, b) => (b.input + b.output) - (a.input + a.output))
    .slice(0, 10);
});

/* ---------- Helpers ---------- */

const formatInteger = (v) => {
  const n = Number(v);
  return Number.isFinite(n) ? new Intl.NumberFormat('zh-CN').format(Math.round(n)) : '0';
};

const formatTime = (iso) => {
  if (!iso) return '--';
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  } catch {
    return iso;
  }
}

/* ---------- Data fetching ---------- */

const fetchObservability = async () => {
  isLoading.value = true;
  errorMsg.value = '';
  try {
    const params = {
      time: timeWindow.value,
      page: page.value,
      page_size: pageSize.value,
    };
    if (modelFilter.value) params.model = modelFilter.value;
    if (statusFilter.value) params.status = statusFilter.value;

    const [logsPayload, summaryPayload, summaryStatsPayload] = await Promise.all([
      llmGatewayApi.getLogs(params),
      llmGatewayApi.getLogsSummary(params),
      llmGatewayApi.getSummary(),
    ]);
    logs.value = logsPayload;
    summary.value = summaryPayload;
    summaryStats.value = summaryStatsPayload;
  } catch (error) {
    errorMsg.value = error.message || '加载模型日志失败';
  } finally {
    isLoading.value = false;
  }
};

const fetchTrace = async (traceId) => {
  if (!traceId) return;
  isTraceLoading.value = true;
  try {
    trace.value = await llmGatewayApi.getTrace(traceId);
    traceDrawerVisible.value = true;
  } catch (error) {
    errorMsg.value = error.message || '加载 Trace 失败';
  } finally {
    isTraceLoading.value = false;
  }
};

const onTimeChange = () => { page.value = 1; fetchObservability(); };
const onFilterChange = () => { page.value = 1; fetchObservability(); };
const handlePageChange = (p) => { page.value = p; fetchObservability(); };
const handleSizeChange = (s) => { pageSize.value = s; page.value = 1; fetchObservability(); };

onMounted(fetchObservability);
</script>

<template>
  <OpsSectionFrame>
    <template #actions>
      <el-radio-group v-model="timeWindow" size="small" @change="onTimeChange">
        <el-radio-button v-for="opt in timeOptions" :key="opt.value" :value="opt.value">
          {{ opt.label }}
        </el-radio-button>
      </el-radio-group>
      <el-select v-model="modelFilter" clearable placeholder="全部模型" size="small" style="width: 160px;" @change="onFilterChange">
        <el-option v-for="opt in modelOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
      </el-select>
      <el-select v-model="statusFilter" clearable placeholder="全部状态" size="small" style="width: 120px;" @change="onFilterChange">
        <el-option v-for="opt in statusOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
      </el-select>
    </template>

    <template #alerts>
      <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />
    </template>

    <OpsStatusBand :items="summaryItems" />

    <div class="obs-chart-grid">
      <AppSectionCard title="Token 用量" icon="data-usage" admin>
        <AdminChart v-if="tokenUsageByModel.length > 0" :option="tokenChartOption" height="260px" />
        <div v-else class="admin-empty-state">当前窗口暂无请求数据</div>
      </AppSectionCard>
    </div>

    <OpsInspectorDrawer title="请求摘要" icon="frame-inspect" :eyebrow="''">
      <AdminDataTable
        :data="logs.logs"
        :loading="isLoading"
        :current-page="page"
        :page-size="pageSize"
        :total="logs.total"
        :page-sizes="[10, 25, 50, 100]"
        :show-search="false"
        row-key="request_id"
        @update:current-page="handlePageChange"
        @update:page-size="handleSizeChange"
      >
        <el-table-column label="时间" min-width="158">
          <template #default="{ row }">{{ formatTime(row.time) }}</template>
        </el-table-column>
        <el-table-column prop="alias" label="模型别名" min-width="120" />
        <el-table-column prop="capability" label="类型" width="90" />
        <el-table-column prop="latency_ms" label="延迟" width="90">
          <template #default="{ row }">{{ row.latency_ms }} ms</template>
        </el-table-column>
        <el-table-column label="Token" width="130">
          <template #default="{ row }">{{ row.request_tokens }} / {{ row.response_tokens }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'failed' ? 'danger' : 'success'" effect="plain" size="small">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="错误" min-width="130">
          <template #default="{ row }">
            <span v-if="row.error_code || row.error_message">{{ row.error_code || row.error_message }}</span>
            <span v-else class="muted-text">--</span>
          </template>
        </el-table-column>
        <el-table-column label="Trace" width="100" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.trace_id" link type="primary" size="small" :loading="isTraceLoading" @click="fetchTrace(row.trace_id)">
              查看
            </el-button>
            <span v-else class="muted-text">--</span>
          </template>
        </el-table-column>
      </AdminDataTable>
    </OpsInspectorDrawer>

    <el-drawer v-model="traceDrawerVisible" size="520px" title="Trace 明细" destroy-on-close>
      <div class="trace-panel">
        <div class="trace-panel__meta">
          <strong>{{ trace.trace_id || '未登记 Trace' }}</strong>
          <span>{{ formatTime(trace.started_at) }} &rarr; {{ formatTime(trace.ended_at) }}</span>
        </div>
        <div class="trace-panel__list">
          <article v-for="item in trace.logs" :key="`${item.time}-${item.alias}-${item.stage}`" class="trace-step">
            <div class="trace-step__head">
              <strong>{{ item.alias }}</strong>
              <el-tag :type="item.status === 'failed' ? 'danger' : 'success'" effect="plain" size="small">{{ item.status }}</el-tag>
            </div>
            <p>{{ item.upstream_model || '未登记上游模型' }}</p>
            <p class="muted-text">{{ item.stage || 'direct' }} · {{ item.latency_ms }} ms · Token: {{ item.request_tokens }} / {{ item.response_tokens }}</p>
          </article>
        </div>
      </div>
    </el-drawer>
  </OpsSectionFrame>
</template>

<style scoped>
.obs-chart-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0;
  border: 1px solid var(--line-soft);
  border-radius: 28px;
  background: var(--surface-1);
  overflow: hidden;
}

.obs-chart-grid :deep(.admin-section-card) {
  min-height: 100%;
  padding: 24px 26px;
  border-left: 1px solid var(--line-soft);
  background: transparent;
}

.obs-chart-grid :deep(.admin-section-card:first-child) {
  border-left: 0;
}

.trace-panel {
  display: grid;
  gap: 16px;
}

.trace-panel__meta {
  display: grid;
  gap: 4px;
}

.trace-step {
  padding: 14px 0 0;
  border-top: 1px solid var(--line-soft);
}

.trace-step:first-child {
  padding-top: 0;
  border-top: 0;
}

.trace-step__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.trace-step p {
  margin: 8px 0 0;
}

@media (max-width: 900px) {
  .obs-chart-grid {
    grid-template-columns: 1fr;
  }

  .obs-chart-grid :deep(.admin-section-card) {
    border-left: 0;
    border-top: 1px solid var(--line-soft);
  }

  .obs-chart-grid :deep(.admin-section-card:first-child) {
    border-top: 0;
  }
}
</style>
