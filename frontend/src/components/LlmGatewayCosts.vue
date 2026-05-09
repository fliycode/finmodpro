<script setup>
import { computed, onMounted, reactive, ref } from 'vue';

import { llmGatewayApi } from '../api/llm-gateway.js';
import { llmApi, normalizeModelConfigPayload } from '../api/llm.js';
import {
  normalizeGatewayCostsModels,
  normalizeGatewayCostsSummary,
  normalizeGatewayCostsTimeseries,
} from '../lib/llm-gateway.js';
import OpsCommandDeck from './admin/ops/OpsCommandDeck.vue';
import OpsInspectorDrawer from './admin/ops/OpsInspectorDrawer.vue';
import OpsSectionFrame from './admin/ops/OpsSectionFrame.vue';
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
  const uniqueOptions = new Map();
  normalizeModelConfigPayload(data)
    .forEach((item) => {
      const alias = item.alias || item.model_name;
      if (!alias || uniqueOptions.has(alias)) {
        return;
      }
      uniqueOptions.set(alias, { label: alias, value: alias });
    });
  modelOptions.value = Array.from(uniqueOptions.values());
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
    errorMsg.value = error.message || '加载用量统计失败';
  } finally {
    isLoading.value = false;
  }
};

const metricCards = computed(() => ([
  {
    key: 'total-cost',
    label: '总成本估算',
    value: `$${summary.value.estimated_total_cost.toFixed(4)}`,
    note: `最近刷新：${refreshedAt.value || '尚未刷新'}`,
  },
  {
    key: 'requests',
    label: '请求量',
    value: summary.value.total_requests,
    note: '当前筛选窗口内的请求总数。',
  },
  {
    key: 'input',
    label: '输入 Token',
    value: summary.value.total_request_tokens,
    note: `约 $${summary.value.estimated_input_cost.toFixed(4)}`,
  },
  {
    key: 'output',
    label: '输出 Token',
    value: summary.value.total_response_tokens,
    note: `约 $${summary.value.estimated_output_cost.toFixed(4)}`,
  },
]));

const frameMeta = computed(() => [
  `最近刷新：${refreshedAt.value || '尚未刷新'}`,
  `请求总数：${summary.value.total_requests}`,
  `窗口：${filters.time}`,
]);

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
const pricingGapNotice = computed(() => {
  if (summary.value.total_requests === 0 || summary.value.estimated_total_cost > 0) {
    return '';
  }
  if (summary.value.total_request_tokens === 0 && summary.value.total_response_tokens === 0) {
    return '';
  }
  return '当前窗口已经统计到 Token，但对应模型还没有配置 input/output price per million，因此估算成本仍显示为 0。请到模型总览补齐定价。';
});

onMounted(async () => {
  await fetchModelOptions();
  await fetchCosts();
});
</script>

<template>
  <OpsSectionFrame
    :meta="frameMeta"
  >
    <template #actions>
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
    </template>

    <template #alerts>
      <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />
      <el-alert v-else-if="pricingGapNotice" :title="pricingGapNotice" type="warning" show-icon :closable="false" />
    </template>

    <OpsCommandDeck>
      <AppSectionCard title="成本结构" desc="把输入成本、输出成本和当前最贵模型放在一处判断。" admin>
        <div class="cost-breakdown-grid">
          <article class="cost-breakdown-card">
            <span class="section-kicker">输入成本</span>
            <strong>${{ summary.estimated_input_cost.toFixed(4) }}</strong>
            <p>{{ summary.total_request_tokens }} 输入 Token</p>
          </article>
          <article class="cost-breakdown-card">
            <span class="section-kicker">输出成本</span>
            <strong>${{ summary.estimated_output_cost.toFixed(4) }}</strong>
            <p>{{ summary.total_response_tokens }} 输出 Token</p>
          </article>
          <article class="cost-breakdown-card">
            <span class="section-kicker">最高成本模型</span>
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
    </OpsCommandDeck>

    <OpsInspectorDrawer title="模型占比" desc="按模型展示请求占比、Token 与估算成本。">
      <el-table :data="models.models" stripe>
        <el-table-column prop="alias" label="模型别名" min-width="160" />
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
    </OpsInspectorDrawer>
  </OpsSectionFrame>
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

.section-kicker,
.section-kicker {
  display: block;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.cost-breakdown-card p {
  margin: 8px 0 0;
  color: var(--text-secondary);
}

.cost-breakdown-grid,
.timeseries-list {
  display: grid;
  gap: 0;
}

.cost-breakdown-card,
.timeseries-item {
  padding: 16px 0 0;
  border-top: 1px solid var(--line-soft);
}

.cost-breakdown-card:first-child,
.timeseries-item:first-child {
  padding-top: 0;
  border-top: 0;
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
  .gateway-metric-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .gateway-metric-strip {
    grid-template-columns: 1fr;
  }
}
</style>
