<script setup>
import { computed, onMounted, reactive, ref } from 'vue';

import { llmGatewayApi } from '../api/llm-gateway.js';
import { llmApi, normalizeModelConfigPayload } from '../api/llm.js';
import {
  normalizeGatewayErrors,
  normalizeGatewayLogs,
  normalizeGatewayLogsSummary,
  normalizeGatewayTrace,
} from '../lib/llm-gateway.js';
import OpsCommandDeck from './admin/ops/OpsCommandDeck.vue';
import OpsInspectorDrawer from './admin/ops/OpsInspectorDrawer.vue';
import OpsSectionFrame from './admin/ops/OpsSectionFrame.vue';
import OpsStatusBand from './admin/ops/OpsStatusBand.vue';
import AppSectionCard from './ui/AppSectionCard.vue';

const filters = reactive({
  model: '',
  status: '',
  time: '24h',
});

const modelOptions = ref([]);
const logs = ref(normalizeGatewayLogs());
const summary = ref(normalizeGatewayLogsSummary());
const errors = ref(normalizeGatewayErrors());
const trace = ref(normalizeGatewayTrace());
const traceDrawerVisible = ref(false);
const isLoading = ref(false);
const isTraceLoading = ref(false);
const errorMsg = ref('');
const refreshedAt = ref('');
const page = ref(1);
const pageSize = ref(20);

const fetchModelOptions = async () => {
  const data = await llmApi.getModelConfigs();
  modelOptions.value = normalizeModelConfigPayload(data)
    .filter((item) => item.provider === 'litellm')
    .map((item) => ({ label: item.alias || item.model_name, value: item.alias || item.model_name }));
};

const fetchObservability = async () => {
  isLoading.value = true;
  errorMsg.value = '';
  try {
    const params = {
      model: filters.model || undefined,
      status: filters.status || undefined,
      time: filters.time,
      page: page.value,
      page_size: pageSize.value,
    };
    const [logsPayload, summaryPayload, errorsPayload] = await Promise.all([
      llmGatewayApi.getLogs(params),
      llmGatewayApi.getLogsSummary(params),
      llmGatewayApi.getErrors({ time: filters.time }),
    ]);
    logs.value = logsPayload;
    summary.value = summaryPayload;
    errors.value = errorsPayload;
    refreshedAt.value = new Date().toLocaleString();
  } catch (error) {
    errorMsg.value = error.message || '加载日志观测失败';
  } finally {
    isLoading.value = false;
  }
};

const fetchTrace = async (traceId) => {
  if (!traceId) {
    return;
  }
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

const refreshAll = async () => {
  page.value = 1;
  await fetchObservability();
};

const metricCards = computed(() => ([
  {
    key: 'requests',
    label: '请求量',
    value: summary.value.total_requests,
    note: `最近刷新：${refreshedAt.value || '尚未刷新'}`,
  },
  {
    key: 'error-rate',
    label: '错误率',
    value: `${summary.value.error_rate_pct}%`,
    note: `失败请求 ${errors.value.total_failed_requests} 次`,
  },
  {
    key: 'latency',
    label: '平均延迟',
    value: `${summary.value.avg_latency_ms} ms`,
    note: '当前筛选窗口下的平均耗时。',
  },
  {
    key: 'error-types',
    label: '错误类型',
    value: errors.value.error_types.length,
    note: '用于区分是配额、路由还是上游异常。',
  },
]));

const frameMeta = computed(() => [
  `最近刷新：${refreshedAt.value || '尚未刷新'}`,
  `日志总量：${logs.value.total}`,
  `窗口：${filters.time}`,
]);

const maxLatencyBucket = computed(() => {
  const counts = summary.value.latency_buckets.map((item) => item.count);
  return counts.length ? Math.max(...counts) : 1;
});

const handlePageChange = async (nextPage) => {
  page.value = nextPage;
  await fetchObservability();
};

onMounted(async () => {
  await fetchModelOptions();
  await fetchObservability();
});
</script>

<template>
  <OpsSectionFrame
    eyebrow="War room / Logs & observability"
    title="Logs / Observability"
    summary="用 request 级摘要表格、错误分析、延迟分布和 trace 入口，回答“哪条路由在出错、为什么错、一次请求走了什么链路”。"
    :meta="frameMeta"
  >
    <template #actions>
      <div class="gateway-page__hero-actions">
        <el-select v-model="filters.model" clearable placeholder="按 alias 筛选" style="width: 180px;">
          <el-option v-for="item in modelOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="filters.status" clearable placeholder="状态" style="width: 140px;">
          <el-option label="成功" value="success" />
          <el-option label="失败" value="failed" />
        </el-select>
        <el-select v-model="filters.time" style="width: 120px;">
          <el-option label="1h" value="1h" />
          <el-option label="24h" value="24h" />
          <el-option label="7d" value="7d" />
          <el-option label="30d" value="30d" />
        </el-select>
        <el-button :loading="isLoading" @click="refreshAll">应用筛选</el-button>
      </div>
    </template>

    <template #alerts>
      <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />
    </template>

    <template #status-band>
      <OpsStatusBand :items="metricCards" />
    </template>

    <OpsCommandDeck>
      <AppSectionCard title="错误分析" desc="把错误类型聚合和最近错误样本并排展示，便于先判断主因再下钻具体请求。" admin>
        <div class="analysis-grid">
          <div class="analysis-column">
            <span class="section-kicker">Error types</span>
            <div v-if="errors.error_types.length === 0" class="admin-empty-state">当前筛选窗口暂无失败类型</div>
            <div v-else class="analysis-list">
              <article v-for="item in errors.error_types" :key="item.error_code" class="analysis-list__item">
                <strong>{{ item.error_code }}</strong>
                <span>{{ item.count }} 次</span>
              </article>
            </div>
          </div>
          <div class="analysis-column">
            <span class="section-kicker">Recent errors</span>
            <div v-if="errors.recent_errors.length === 0" class="admin-empty-state">暂无最近错误</div>
            <div v-else class="analysis-list">
              <article v-for="item in errors.recent_errors.slice(0, 6)" :key="`${item.trace_id}-${item.time}`" class="analysis-list__item analysis-list__item--stack">
                <strong>{{ item.alias }}</strong>
                <span>{{ item.error_code || 'unknown' }}</span>
                <span class="muted-text">{{ item.time }}</span>
              </article>
            </div>
          </div>
        </div>
      </AppSectionCard>

      <AppSectionCard title="Latency 分布" desc="用简洁柱带而不是真趋势图展示当前窗口的延迟密度。" admin>
        <div class="latency-list">
          <article v-for="item in summary.latency_buckets" :key="item.label" class="latency-list__item">
            <div class="latency-list__head">
              <strong>{{ item.label }}</strong>
              <span>{{ item.count }}</span>
            </div>
            <div class="latency-list__track">
              <span class="latency-list__fill" :style="{ width: `${(item.count / maxLatencyBucket) * 100}%` }" />
            </div>
          </article>
        </div>
      </AppSectionCard>
    </OpsCommandDeck>

    <OpsInspectorDrawer title="Request log" desc="保留请求级别摘要，不暴露原始 prompt / response。">
      <el-table :data="logs.logs" stripe>
        <el-table-column prop="time" label="时间" min-width="165" />
        <el-table-column prop="alias" label="Alias" min-width="130" />
        <el-table-column prop="upstream_model" label="Upstream" min-width="160" />
        <el-table-column prop="capability" label="Capability" width="100" />
        <el-table-column prop="stage" label="Stage" width="100" />
        <el-table-column prop="latency_ms" label="Latency" width="110" />
        <el-table-column label="Token" width="140">
          <template #default="{ row }">
            {{ row.request_tokens }} / {{ row.response_tokens }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'failed' ? 'danger' : 'success'" effect="plain">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="错误" min-width="150">
          <template #default="{ row }">
            {{ row.error_code || row.error_message || '--' }}
          </template>
        </el-table-column>
        <el-table-column label="Trace" min-width="150" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.trace_id" link type="primary" :loading="isTraceLoading" @click="fetchTrace(row.trace_id)">
              {{ row.trace_id }}
            </el-button>
            <span v-else class="muted-text">未登记</span>
          </template>
        </el-table-column>
      </el-table>

      <div class="gateway-pagination">
        <el-pagination
          background
          layout="prev, pager, next"
          :total="logs.total"
          :page-size="pageSize"
          :current-page="page"
          @current-change="handlePageChange"
        />
      </div>
    </OpsInspectorDrawer>

    <el-drawer v-model="traceDrawerVisible" size="520px" title="Trace 明细" destroy-on-close>
      <div class="trace-panel">
        <div class="trace-panel__meta">
          <strong>{{ trace.trace_id || '未登记 Trace' }}</strong>
          <span>{{ trace.started_at }} → {{ trace.ended_at }}</span>
        </div>
        <div class="trace-panel__list">
          <article v-for="item in trace.logs" :key="`${item.time}-${item.alias}-${item.stage}`" class="trace-step">
            <div class="trace-step__head">
              <strong>{{ item.alias }}</strong>
              <el-tag :type="item.status === 'failed' ? 'danger' : 'success'" effect="plain">{{ item.status }}</el-tag>
            </div>
            <p>{{ item.upstream_model || '未登记上游模型' }}</p>
            <p class="muted-text">Stage: {{ item.stage || 'direct' }} · {{ item.latency_ms }} ms</p>
            <p class="muted-text">Token: {{ item.request_tokens }} / {{ item.response_tokens }}</p>
          </article>
        </div>
      </div>
    </el-drawer>
  </OpsSectionFrame>
</template>

<style scoped>
.gateway-page__hero--observability {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(243, 247, 252, 0.94)),
    radial-gradient(circle at top right, rgba(36, 87, 197, 0.1), transparent 36%);
}

.gateway-page__hero-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}

.gateway-metric-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.gateway-metric-card,
.analysis-list__item,
.trace-step {
  padding: 18px;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  background: var(--surface-1);
}

.gateway-metric-card__label,
.section-kicker {
  display: block;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.gateway-metric-card__value {
  display: block;
  margin-top: 8px;
  color: var(--text-primary);
  font-size: 28px;
}

.gateway-metric-card__note {
  margin: 8px 0 0;
  color: var(--text-secondary);
}

.observability-grid,
.analysis-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}

.analysis-column {
  display: grid;
  gap: 12px;
}

.analysis-list,
.latency-list,
.trace-panel__list {
  display: grid;
  gap: 12px;
}

.analysis-list__item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.analysis-list__item--stack {
  display: grid;
}

.latency-list__item {
  display: grid;
  gap: 8px;
}

.latency-list__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.latency-list__track {
  height: 10px;
  border-radius: 999px;
  background: var(--surface-3);
  overflow: hidden;
}

.latency-list__fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, rgba(36, 87, 197, 0.28), rgba(36, 87, 197, 0.82));
}

.gateway-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.trace-panel {
  display: grid;
  gap: 16px;
}

.trace-panel__meta {
  display: grid;
  gap: 4px;
}

.trace-step__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.trace-step p {
  margin: 8px 0 0;
}

@media (max-width: 1120px) {
  .gateway-metric-strip,
  .observability-grid,
  .analysis-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .gateway-metric-strip,
  .observability-grid,
  .analysis-grid {
    grid-template-columns: 1fr;
  }
}
</style>
