<script setup>
import { computed, onMounted, reactive, ref } from 'vue';

import { llmGatewayApi } from '../api/llm-gateway.js';
import { llmApi, normalizeModelConfigPayload } from '../api/llm.js';
import {
  normalizeGatewayCostsModels,
  normalizeGatewayCostsSummary,
  normalizeGatewayCostsTimeseries,
} from '../lib/llm-gateway.js';
import AppSectionCard from './ui/AppSectionCard.vue';

const filters = reactive({
  model: '',
  time: '24h',
});

const modelOptions = ref([]);
const summary = ref(normalizeGatewayCostsSummary());
const timeseries = ref(normalizeGatewayCostsTimeseries());
const models = ref(normalizeGatewayCostsModels());
const errorMsg = ref('');
const isLoading = ref(false);
const refreshedAt = ref('');

const fetchModelOptions = async () => {
  const data = await llmApi.getModelConfigs();
  modelOptions.value = normalizeModelConfigPayload(data)
    .filter((item) => item.provider === 'litellm')
    .map((item) => ({ label: item.alias || item.model_name, value: item.alias || item.model_name }));
};

const fetchCosts = async () => {
  isLoading.value = true;
  errorMsg.value = '';
  try {
    const params = {
      model: filters.model || undefined,
      time: filters.time,
    };
    const [summaryPayload, timeseriesPayload, modelsPayload] = await Promise.all([
      llmGatewayApi.getCostsSummary(params),
      llmGatewayApi.getCostsTimeseries(params),
      llmGatewayApi.getCostsModels(params),
    ]);
    summary.value = summaryPayload;
    timeseries.value = timeseriesPayload;
    models.value = modelsPayload;
    refreshedAt.value = new Date().toLocaleString();
  } catch (error) {
    errorMsg.value = error.message || '加载成本与用量失败';
  } finally {
    isLoading.value = false;
  }
};

const metricCards = computed(() => ([
  {
    key: 'total-cost',
    label: 'Estimated total cost',
    value: `$${summary.value.estimated_total_cost.toFixed(4)}`,
    note: `最近刷新：${refreshedAt.value || '尚未刷新'}`,
  },
  {
    key: 'requests',
    label: 'Requests',
    value: summary.value.total_requests,
    note: '当前筛选窗口内的请求总数。',
  },
  {
    key: 'input',
    label: 'Input tokens',
    value: summary.value.total_request_tokens,
    note: `约 $${summary.value.estimated_input_cost.toFixed(4)}`,
  },
  {
    key: 'output',
    label: 'Output tokens',
    value: summary.value.total_response_tokens,
    note: `约 $${summary.value.estimated_output_cost.toFixed(4)}`,
  },
]));

const maxSeriesRequests = computed(() => {
  const counts = timeseries.value.points.map((item) => item.request_count);
  return counts.length ? Math.max(...counts) : 1;
});

const granularityLabel = computed(() => {
  if (timeseries.value.granularity_minutes) {
    return `${timeseries.value.granularity_minutes} 分钟`;
  }
  if (timeseries.value.granularity_hours) {
    return `${timeseries.value.granularity_hours} 小时`;
  }
  return '未指定';
});

const topCostModel = computed(() => models.value.models[0] || null);

onMounted(async () => {
  await fetchModelOptions();
  await fetchCosts();
});
</script>

<template>
  <div class="page-stack gateway-page">
    <section class="page-hero gateway-page__hero gateway-page__hero--costs">
      <div>
        <div class="page-hero__eyebrow">LLM Gateway / Cost & Usage</div>
        <h1 class="page-hero__title">Cost / Usage</h1>
        <p class="page-hero__subtitle">
          用 token、估算成本、时间分布和模型占比解释“钱花在哪、量出在哪、是输入贵还是输出贵”。
        </p>
      </div>

      <div class="gateway-page__hero-actions">
        <el-select v-model="filters.model" clearable placeholder="按 alias 筛选" style="width: 180px;">
          <el-option v-for="item in modelOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="filters.time" style="width: 120px;">
          <el-option label="1h" value="1h" />
          <el-option label="24h" value="24h" />
          <el-option label="7d" value="7d" />
          <el-option label="30d" value="30d" />
        </el-select>
        <el-button :loading="isLoading" @click="fetchCosts">刷新</el-button>
      </div>
    </section>

    <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />

    <section class="gateway-metric-strip">
      <article v-for="metric in metricCards" :key="metric.key" class="gateway-metric-card">
        <span class="gateway-metric-card__label">{{ metric.label }}</span>
        <strong class="gateway-metric-card__value">{{ metric.value }}</strong>
        <p class="gateway-metric-card__note">{{ metric.note }}</p>
      </article>
    </section>

    <div class="cost-grid">
      <AppSectionCard title="成本结构" desc="把输入成本、输出成本和当前最贵路由放在一处判断。" admin>
        <div class="cost-breakdown-grid">
          <article class="cost-breakdown-card">
            <span class="section-kicker">Input cost</span>
            <strong>${{ summary.estimated_input_cost.toFixed(4) }}</strong>
            <p>{{ summary.total_request_tokens }} input tokens</p>
          </article>
          <article class="cost-breakdown-card">
            <span class="section-kicker">Output cost</span>
            <strong>${{ summary.estimated_output_cost.toFixed(4) }}</strong>
            <p>{{ summary.total_response_tokens }} output tokens</p>
          </article>
          <article class="cost-breakdown-card">
            <span class="section-kicker">Top cost model</span>
            <strong>{{ topCostModel?.alias || '暂无' }}</strong>
            <p v-if="topCostModel">${{ topCostModel.estimated_total_cost.toFixed(4) }} · {{ topCostModel.request_share_pct }}%</p>
            <p v-else>当前窗口暂无模型成本数据</p>
          </article>
        </div>
      </AppSectionCard>

      <AppSectionCard title="时间分布" :desc="`当前粒度：${granularityLabel}`" admin>
        <div v-if="timeseries.points.length === 0" class="admin-empty-state">当前窗口暂无成本时间序列</div>
        <div v-else class="timeseries-list">
          <article v-for="point in timeseries.points" :key="point.bucket" class="timeseries-item">
            <div class="timeseries-item__head">
              <strong>{{ point.bucket }}</strong>
              <span>{{ point.request_count }} 次 · ${{ point.estimated_cost.toFixed(4) }}</span>
            </div>
            <div class="timeseries-item__track">
              <span class="timeseries-item__fill" :style="{ width: `${(point.request_count / maxSeriesRequests) * 100}%` }" />
            </div>
          </article>
        </div>
      </AppSectionCard>
    </div>

    <AppSectionCard title="模型占比" desc="按模型展示请求占比、token 与估算成本，便于后续治理热门高成本路由。" admin>
      <el-table :data="models.models" stripe>
        <el-table-column prop="alias" label="Alias" min-width="160" />
        <el-table-column prop="request_count" label="请求数" width="110" />
        <el-table-column prop="request_share_pct" label="请求占比" width="110">
          <template #default="{ row }">
            {{ row.request_share_pct }}%
          </template>
        </el-table-column>
        <el-table-column label="Token" min-width="170">
          <template #default="{ row }">
            {{ row.total_request_tokens }} / {{ row.total_response_tokens }}
          </template>
        </el-table-column>
        <el-table-column label="输入成本" width="120">
          <template #default="{ row }">
            ${{ row.estimated_input_cost.toFixed(4) }}
          </template>
        </el-table-column>
        <el-table-column label="输出成本" width="120">
          <template #default="{ row }">
            ${{ row.estimated_output_cost.toFixed(4) }}
          </template>
        </el-table-column>
        <el-table-column label="总成本" width="120">
          <template #default="{ row }">
            ${{ row.estimated_total_cost.toFixed(4) }}
          </template>
        </el-table-column>
      </el-table>
    </AppSectionCard>
  </div>
</template>

<style scoped>
.gateway-page__hero--costs {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(244, 247, 252, 0.94)),
    radial-gradient(circle at top right, rgba(36, 87, 197, 0.08), transparent 38%);
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
.cost-breakdown-card,
.timeseries-item {
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

.gateway-metric-card__note,
.cost-breakdown-card p {
  margin: 8px 0 0;
  color: var(--text-secondary);
}

.cost-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}

.cost-breakdown-grid,
.timeseries-list {
  display: grid;
  gap: 12px;
}

.cost-breakdown-card strong {
  display: block;
  margin-top: 10px;
  font-size: 22px;
  color: var(--text-primary);
}

.timeseries-item__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.timeseries-item__track {
  height: 10px;
  margin-top: 10px;
  border-radius: 999px;
  background: var(--surface-3);
  overflow: hidden;
}

.timeseries-item__fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, rgba(36, 87, 197, 0.28), rgba(36, 87, 197, 0.82));
}

@media (max-width: 1120px) {
  .gateway-metric-strip,
  .cost-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .gateway-metric-strip,
  .cost-grid {
    grid-template-columns: 1fr;
  }
}
</style>
