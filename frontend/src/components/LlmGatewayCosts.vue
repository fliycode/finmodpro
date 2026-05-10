<script setup>
import { computed, onMounted, reactive, ref } from 'vue';

import { llmGatewayApi } from '../api/llm-gateway.js';
import { llmApi, normalizeModelConfigPayload } from '../api/llm.js';
import {
  normalizeGatewayCostsModels,
  normalizeGatewayCostsSummary,
  normalizeGatewayCostsTimeseries,
} from '../lib/llm-gateway.js';
import AdminChart from './admin/AdminChart.vue';
import OpsSectionFrame from './admin/ops/OpsSectionFrame.vue';

const summary = ref(normalizeGatewayCostsSummary());
const timeseries = ref(normalizeGatewayCostsTimeseries());
const models = ref(normalizeGatewayCostsModels());
const errorMsg = ref('');
const isLoading = ref(false);
const isSaving = ref(false);
const editDrawerVisible = ref(false);

const modelConfigMap = ref(new Map());

const editForm = reactive({
  alias: '',
  input_price_per_million: 0,
  output_price_per_million: 0,
  request_price: 0,
  price_currency: 'USD',
});
let editingConfigId = null;

const fetchModelConfigs = async () => {
  try {
    const data = await llmApi.getModelConfigs();
    const configs = normalizeModelConfigPayload(data);
    const map = new Map();
    for (const config of configs) {
      const alias = config.alias || config.model_name;
      if (alias) {
        map.set(alias, config);
      }
    }
    modelConfigMap.value = map;
  } catch {
    // silently ignore — edit will be unavailable
  }
};

const fetchCosts = async () => {
  isLoading.value = true;
  errorMsg.value = '';
  try {
    const params = { time: '24h' };
    const [summaryPayload, timeseriesPayload, modelsPayload] = await Promise.all([
      llmGatewayApi.getCostsSummary(params),
      llmGatewayApi.getCostsTimeseries(params),
      llmGatewayApi.getCostsModels(params),
    ]);
    summary.value = summaryPayload;
    timeseries.value = timeseriesPayload;
    models.value = modelsPayload;
  } catch (error) {
    errorMsg.value = error.message || '加载用量统计失败';
  } finally {
    isLoading.value = false;
  }
};

const hasRequests = computed(() => summary.value.total_requests > 0);
const hasTokens = computed(() => summary.value.total_request_tokens > 0 || summary.value.total_response_tokens > 0);

const costChartOption = computed(() => {
  const input = summary.value.estimated_input_cost;
  const output = summary.value.estimated_output_cost;
  if (input === 0 && output === 0) {
    return {};
  }
  return {
    tooltip: { trigger: 'item', formatter: '{b}: ${c} ({d}%)' },
    legend: { bottom: 0, textStyle: { color: '#8a95a7', fontSize: 11 } },
    series: [
      {
        type: 'pie',
        radius: ['42%', '68%'],
        center: ['50%', '44%'],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 6, borderColor: 'var(--surface-1)', borderWidth: 2 },
        label: { show: false },
        emphasis: { label: { show: true, fontSize: 13, fontWeight: 'bold' } },
        data: [
          { value: input, name: '输入成本', itemStyle: { color: 'rgba(36,87,197,0.82)' } },
          { value: output, name: '输出成本', itemStyle: { color: 'rgba(36,87,197,0.38)' } },
        ],
      },
    ],
  };
});

const tokenChartOption = computed(() => {
  const input = summary.value.total_request_tokens;
  const output = summary.value.total_response_tokens;
  if (input === 0 && output === 0) {
    return {};
  }
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} Token ({d}%)' },
    legend: { bottom: 0, textStyle: { color: '#8a95a7', fontSize: 11 } },
    series: [
      {
        type: 'pie',
        radius: ['42%', '68%'],
        center: ['50%', '44%'],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 6, borderColor: 'var(--surface-1)', borderWidth: 2 },
        label: { show: false },
        emphasis: { label: { show: true, fontSize: 13, fontWeight: 'bold' } },
        data: [
          { value: input, name: '输入 Token', itemStyle: { color: 'rgba(36,87,197,0.82)' } },
          { value: output, name: '输出 Token', itemStyle: { color: 'rgba(36,87,197,0.38)' } },
        ],
      },
    ],
  };
});

const timeseriesChartOption = computed(() => {
  const points = timeseries.value.points;
  if (points.length === 0) {
    return {};
  }
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 12, right: 16, top: 16, bottom: 8, containLabel: true },
    xAxis: {
      type: 'category',
      data: points.map((p) => p.bucket),
      axisLabel: { color: '#8a95a7', fontSize: 10, rotate: points.length > 12 ? 25 : 0 },
      axisLine: { lineStyle: { color: 'rgba(148,163,184,0.16)' } },
    },
    yAxis: [
      {
        type: 'value',
        name: '成本',
        nameTextStyle: { color: '#8a95a7', fontSize: 10 },
        axisLabel: { color: '#8a95a7', fontSize: 10, formatter: '${value}' },
        splitLine: { lineStyle: { color: 'rgba(148,163,184,0.1)' } },
      },
      {
        type: 'value',
        name: '请求数',
        nameTextStyle: { color: '#8a95a7', fontSize: 10 },
        axisLabel: { color: '#8a95a7', fontSize: 10 },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '成本',
        type: 'bar',
        data: points.map((p) => p.estimated_cost),
        itemStyle: { color: 'rgba(36,87,197,0.72)', borderRadius: [4, 4, 0, 0] },
        barMaxWidth: 32,
      },
      {
        name: '请求数',
        type: 'line',
        yAxisIndex: 1,
        data: points.map((p) => p.request_count),
        smooth: true,
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: { color: 'rgba(91,108,255,0.6)', width: 2 },
        itemStyle: { color: '#5b6cff' },
      },
    ],
  };
});

const openEditDrawer = (model) => {
  const config = modelConfigMap.value.get(model.alias);
  editingConfigId = config?.id ?? null;
  editForm.alias = model.alias;
  editForm.input_price_per_million = Number(config?.input_price_per_million ?? 0);
  editForm.output_price_per_million = Number(config?.output_price_per_million ?? 0);
  editForm.request_price = Number(config?.request_price ?? 0);
  editForm.price_currency = config?.price_currency || 'USD';
  editDrawerVisible.value = true;
};

const savePricing = async () => {
  if (!editingConfigId) {
    return;
  }
  isSaving.value = true;
  try {
    await llmApi.updateModelConfig(editingConfigId, {
      input_price_per_million: Number(editForm.input_price_per_million || 0),
      output_price_per_million: Number(editForm.output_price_per_million || 0),
      request_price: Number(editForm.request_price || 0),
      price_currency: editForm.price_currency,
    });
    editDrawerVisible.value = false;
    await fetchModelConfigs();
    await fetchCosts();
  } catch (error) {
    errorMsg.value = error.message || '保存定价失败';
  } finally {
    isSaving.value = false;
  }
};

onMounted(async () => {
  await fetchModelConfigs();
  await fetchCosts();
});
</script>

<template>
  <OpsSectionFrame>
    <template #alerts>
      <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />
    </template>

    <div class="cost-chart-grid">
      <section class="cost-chart-panel">
        <header class="cost-chart-panel__head">
          <h3 class="cost-chart-panel__title">成本结构</h3>
          <p class="cost-chart-panel__desc">输入与输出成本占比</p>
        </header>
        <div v-if="summary.estimated_total_cost > 0" class="cost-structure-wrap">
          <AdminChart :option="costChartOption" height="220px" />
          <div class="cost-structure-leader">
            <span class="cost-kicker">总成本</span>
            <strong class="cost-leader-num">${{ summary.estimated_total_cost.toFixed(4) }}</strong>
            <p class="cost-leader-meta">{{ summary.total_request_tokens }} 输入 · {{ summary.total_response_tokens }} 输出</p>
          </div>
        </div>
        <div v-else-if="hasTokens" class="cost-structure-wrap">
          <AdminChart :option="tokenChartOption" height="220px" />
          <div class="cost-structure-leader">
            <span class="cost-kicker">Token 消耗</span>
            <strong class="cost-leader-num">{{ summary.total_request_tokens + summary.total_response_tokens }}</strong>
            <p class="cost-leader-meta">尚未配置定价</p>
          </div>
        </div>
        <div v-else class="cost-empty">当前窗口暂无请求数据</div>
      </section>

      <section class="cost-chart-panel">
        <header class="cost-chart-panel__head">
          <h3 class="cost-chart-panel__title">时间分布</h3>
          <p class="cost-chart-panel__desc">{{ timeseries.granularity_minutes ? timeseries.granularity_minutes + ' 分钟粒度' : timeseries.granularity_hours ? timeseries.granularity_hours + ' 小时粒度' : '自动粒度' }}</p>
        </header>
        <AdminChart v-if="timeseries.points.length > 0" :option="timeseriesChartOption" height="240px" />
        <div v-else class="cost-empty">当前窗口暂无时间序列</div>
      </section>
    </div>

    <section class="cost-models">
      <header class="cost-models__head">
        <div>
          <h3 class="cost-models__title">模型占比</h3>
          <p class="cost-models__desc">按模型展示请求占比、Token 与估算成本</p>
        </div>
      </header>
      <el-table :data="models.models" class="cost-model-table" :header-cell-style="{ background: 'var(--surface-3)', color: 'var(--text-secondary)', fontWeight: 600, fontSize: '11px', letterSpacing: '0.04em', textTransform: 'uppercase' }">
        <el-table-column prop="alias" label="模型别名" min-width="160" />
        <el-table-column prop="request_count" label="请求数" width="90" align="right" />
        <el-table-column prop="request_share_pct" label="占比" width="80" align="right">
          <template #default="{ row }">
            {{ row.request_share_pct }}%
          </template>
        </el-table-column>
        <el-table-column label="输入 / 输出 Token" min-width="150" align="right">
          <template #default="{ row }">
            <span class="cost-token-pair">{{ row.total_request_tokens }} <span class="cost-token-sep">/</span> {{ row.total_response_tokens }}</span>
          </template>
        </el-table-column>
        <el-table-column label="总成本" width="110" align="right">
          <template #default="{ row }">
            <span class="cost-value">${{ row.estimated_total_cost.toFixed(4) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="" width="70" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEditDrawer(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-drawer v-model="editDrawerVisible" size="420px" title="编辑模型定价" destroy-on-close>
      <div v-if="editForm.alias" class="edit-pricing-panel">
        <div class="edit-pricing-field">
          <span class="cost-kicker">模型别名</span>
          <strong>{{ editForm.alias }}</strong>
        </div>
        <el-form label-position="top" class="edit-pricing-form">
          <el-form-item label="输入价格 (per million tokens)">
            <el-input-number v-model="editForm.input_price_per_million" :min="0" :step="0.01" controls-position="right" style="width: 100%;" />
          </el-form-item>
          <el-form-item label="输出价格 (per million tokens)">
            <el-input-number v-model="editForm.output_price_per_million" :min="0" :step="0.01" controls-position="right" style="width: 100%;" />
          </el-form-item>
          <el-form-item label="单次请求价格">
            <el-input-number v-model="editForm.request_price" :min="0" :step="0.001" controls-position="right" style="width: 100%;" />
          </el-form-item>
          <el-form-item label="货币">
            <el-select v-model="editForm.price_currency" style="width: 100%;">
              <el-option label="USD" value="USD" />
              <el-option label="CNY" value="CNY" />
              <el-option label="EUR" value="EUR" />
            </el-select>
          </el-form-item>
        </el-form>
        <div class="edit-pricing-actions">
          <el-button @click="editDrawerVisible = false">取消</el-button>
          <el-button type="primary" :loading="isSaving" @click="savePricing">保存</el-button>
        </div>
      </div>
    </el-drawer>
  </OpsSectionFrame>
</template>

<style scoped>
/* ---- Chart Grid ---- */

.cost-chart-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.cost-chart-panel {
  border: 1px solid var(--line-soft);
  border-radius: 6px;
  background: var(--surface-2);
  padding: 20px 22px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.cost-chart-panel__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.cost-chart-panel__title {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.01em;
}

.cost-chart-panel__desc {
  margin: 0;
  font-size: 11px;
  color: var(--text-muted);
}

/* ---- Cost Structure ---- */

.cost-structure-wrap {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 16px;
  align-items: center;
}

.cost-structure-leader {
  text-align: right;
}

.cost-kicker {
  display: block;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.cost-leader-num {
  display: block;
  margin-top: 6px;
  font-size: 24px;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: -0.02em;
  line-height: 1;
}

.cost-leader-meta {
  margin: 8px 0 0;
  font-size: 11px;
  color: var(--text-secondary);
}

.cost-empty {
  padding: 32px 0;
  text-align: center;
  font-size: 12px;
  color: var(--text-muted);
}

/* ---- Model Table ---- */

.cost-models {
  border: 1px solid var(--line-soft);
  border-radius: 6px;
  background: var(--surface-2);
  overflow: hidden;
}

.cost-models__head {
  padding: 16px 20px 12px;
  border-bottom: 1px solid var(--line-soft);
}

.cost-models__title {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.01em;
}

.cost-models__desc {
  margin: 4px 0 0;
  font-size: 11px;
  color: var(--text-muted);
}

.cost-model-table {
  width: 100%;
}

.cost-token-pair {
  font-variant-numeric: tabular-nums;
}

.cost-token-sep {
  color: var(--text-muted);
  margin: 0 2px;
}

.cost-value {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--text-primary);
}

/* ---- Edit Drawer ---- */

.edit-pricing-panel {
  display: grid;
  gap: 20px;
}

.edit-pricing-field strong {
  display: block;
  margin-top: 6px;
  font-size: 16px;
  color: var(--text-primary);
}

.edit-pricing-form {
  margin-top: 8px;
}

.edit-pricing-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--line-soft);
}

/* ---- Responsive ---- */

@media (max-width: 900px) {
  .cost-chart-grid {
    grid-template-columns: 1fr;
  }

  .cost-structure-wrap {
    grid-template-columns: 1fr;
  }

  .cost-structure-leader {
    text-align: left;
  }
}
</style>
