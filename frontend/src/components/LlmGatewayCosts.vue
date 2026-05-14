<script setup>
import { computed, onMounted, reactive, ref } from 'vue';

import { llmGatewayApi } from '../api/llm-gateway.js';
import { llmApi, normalizeModelConfigPayload } from '../api/llm.js';
import {
  normalizeGatewayCostsModels,
  normalizeGatewayCostsSummary,
  normalizeGatewayCostsTimeseries,
} from '../lib/llm-gateway.js';
import { buildBoardAxis, buildBoardTooltip, chartColors } from '../lib/admin-dashboard.js';
import AdminChart from './admin/AdminChart.vue';
import OpsSectionFrame from './admin/ops/OpsSectionFrame.vue';
import AppIcon from './ui/AppIcon.vue';
import AppSectionCard from './ui/AppSectionCard.vue';

/* ---------- State ---------- */

const summary = ref(normalizeGatewayCostsSummary());
const timeseries = ref(normalizeGatewayCostsTimeseries());
const models = ref(normalizeGatewayCostsModels());
const errorMsg = ref('');
const isLoading = ref(false);
const isSaving = ref(false);
const editDrawerVisible = ref(false);
const modelConfigMap = ref(new Map());

const timeWindow = ref('24h');

const editForm = reactive({
  alias: '',
  input_price_per_million: 0,
  output_price_per_million: 0,
  request_price: 0,
  price_currency: 'USD',
});
let editingConfigId = null;

/* ---------- Options ---------- */

const timeOptions = [
  { label: '1 小时', value: '1h' },
  { label: '6 小时', value: '6h' },
  { label: '24 小时', value: '24h' },
  { label: '7 天', value: '7d' },
];

/* ---------- Summary band ---------- */

const summaryCards = computed(() => {
  const s = summary.value;
  const totalTokens = (s.total_request_tokens || 0) + (s.total_response_tokens || 0);
  const ratio = s.total_response_tokens > 0
    ? (s.total_request_tokens / s.total_response_tokens).toFixed(1)
    : '--';

  return [
    {
      key: 'cost',
      label: '总成本',
      value: s.estimated_total_cost > 0 ? `$${s.estimated_total_cost.toFixed(4)}` : '$0',
      icon: 'pie-chart',
      tone: 'brand',
    },
    {
      key: 'requests',
      label: '总请求',
      value: formatInteger(s.total_requests),
      icon: 'request-page',
      tone: 'accent',
    },
    {
      key: 'tokens',
      label: '总 Token',
      value: formatInteger(totalTokens),
      icon: 'data-usage',
      tone: 'warning',
    },
    {
      key: 'ratio',
      label: '输入/输出比',
      value: ratio === '--' ? '--' : `${ratio}:1`,
      icon: 'frame-inspect',
      tone: 'success',
    },
  ];
});

/* ---------- Charts ---------- */

const hasRequests = computed(() => summary.value.total_requests > 0);
const hasTokens = computed(() => summary.value.total_request_tokens > 0 || summary.value.total_response_tokens > 0);

const costChartOption = computed(() => {
  const input = summary.value.estimated_input_cost;
  const output = summary.value.estimated_output_cost;
  if (input === 0 && output === 0) return {};
  const c = chartColors();

  return {
    tooltip: { trigger: 'item', ...buildBoardTooltip() },
    legend: { bottom: 0, textStyle: { color: c.textSecondary, fontSize: 11 } },
    series: [
      {
        type: 'pie',
        radius: ['42%', '68%'],
        center: ['50%', '44%'],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 6, borderColor: c.surfaceBg, borderWidth: 2 },
        label: { show: false },
        emphasis: { label: { show: true, fontSize: 13, fontWeight: 'bold' } },
        data: [
          { value: input, name: '输入成本', itemStyle: { color: c.brand } },
          { value: output, name: '输出成本', itemStyle: { color: c.brandSoft } },
        ],
      },
    ],
  };
});

const tokenChartOption = computed(() => {
  const input = summary.value.total_request_tokens;
  const output = summary.value.total_response_tokens;
  if (input === 0 && output === 0) return {};
  const c = chartColors();

  return {
    tooltip: { trigger: 'item', ...buildBoardTooltip() },
    legend: { bottom: 0, textStyle: { color: c.textSecondary, fontSize: 11 } },
    series: [
      {
        type: 'pie',
        radius: ['42%', '68%'],
        center: ['50%', '44%'],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 6, borderColor: c.surfaceBg, borderWidth: 2 },
        label: { show: false },
        emphasis: { label: { show: true, fontSize: 13, fontWeight: 'bold' } },
        data: [
          { value: input, name: '输入 Token', itemStyle: { color: c.brand } },
          { value: output, name: '输出 Token', itemStyle: { color: c.brandSoft } },
        ],
      },
    ],
  };
});

const timeseriesChartOption = computed(() => {
  const points = timeseries.value.points;
  if (points.length === 0) return {};
  const c = chartColors();
  const axis = buildBoardAxis();

  return {
    tooltip: { trigger: 'axis', ...buildBoardTooltip() },
    grid: { left: 12, right: 16, top: 16, bottom: 8, containLabel: true },
    xAxis: {
      type: 'category',
      data: points.map((p) => p.bucket),
      axisLabel: { color: c.textSecondary, fontSize: 10, rotate: points.length > 12 ? 25 : 0 },
      axisLine: axis.axisLine,
    },
    yAxis: [
      {
        type: 'value',
        name: '成本',
        nameTextStyle: { color: c.textSecondary, fontSize: 10 },
        axisLabel: { color: c.textSecondary, fontSize: 10, formatter: '${value}' },
        splitLine: { lineStyle: { color: c.gridLine } },
      },
      {
        type: 'value',
        name: '请求数',
        nameTextStyle: { color: c.textSecondary, fontSize: 10 },
        axisLabel: { color: c.textSecondary, fontSize: 10 },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '成本',
        type: 'bar',
        data: points.map((p) => p.estimated_cost),
        itemStyle: { color: c.brand, borderRadius: [4, 4, 0, 0] },
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
        lineStyle: { color: c.brandSoft, width: 2 },
        itemStyle: { color: c.brandSoft },
      },
    ],
  };
});

const modelShareChartOption = computed(() => {
  const data = models.value.models.filter((item) => item.request_count > 0);
  if (data.length === 0) return {};
  const c = chartColors();
  const palette = [c.brand, c.brandSoft, c.success, c.warning, c.risk, c.surface2];

  return {
    tooltip: { trigger: 'item', ...buildBoardTooltip() },
    legend: {
      bottom: 0,
      textStyle: { color: c.textSecondary, fontSize: 11 },
    },
    series: [
      {
        type: 'pie',
        radius: ['40%', '68%'],
        center: ['50%', '44%'],
        itemStyle: { borderRadius: 6, borderColor: c.surfaceBg, borderWidth: 2 },
        label: { show: false },
        data: data.map((item, index) => ({
          value: item.request_count,
          name: item.alias,
          itemStyle: { color: palette[index % palette.length] },
        })),
      },
    ],
  };
});

/* ---------- Helpers ---------- */

const formatInteger = (v) => {
  const n = Number(v);
  return Number.isFinite(n) ? new Intl.NumberFormat('zh-CN').format(Math.round(n)) : '0';
};

/* ---------- Data fetching ---------- */

const fetchModelConfigs = async () => {
  try {
    const data = await llmApi.getModelConfigs();
    const configs = normalizeModelConfigPayload(data);
    const map = new Map();
    for (const config of configs) {
      const alias = config.alias || config.model_name;
      if (alias) map.set(alias, config);
    }
    modelConfigMap.value = map;
  } catch {
    /* silently ignore */
  }
};

const fetchCosts = async () => {
  isLoading.value = true;
  errorMsg.value = '';
  try {
    const params = { time: timeWindow.value };
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

const onTimeChange = () => fetchCosts();

/* ---------- Edit pricing ---------- */

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
  if (!editingConfigId) return;
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
    <template #actions>
      <el-radio-group v-model="timeWindow" size="small" @change="onTimeChange">
        <el-radio-button v-for="opt in timeOptions" :key="opt.value" :value="opt.value">
          {{ opt.label }}
        </el-radio-button>
      </el-radio-group>
    </template>

    <template #alerts>
      <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />
    </template>

    <div class="cost-summary-grid">
      <article
        v-for="item in summaryCards"
        :key="item.key"
        class="cost-summary-card"
        :class="`is-${item.tone}`"
      >
        <span class="cost-summary-card__icon">
          <AppIcon :name="item.icon" />
        </span>
        <div class="cost-summary-card__copy">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </div>
      </article>
    </div>

    <div class="cost-chart-grid">
      <AppSectionCard title="成本结构" desc="输入与输出成本占比" icon="pie-chart" admin>
        <AdminChart v-if="summary.estimated_total_cost > 0" :option="costChartOption" height="220px" />
        <div v-else-if="hasTokens" class="cost-empty-hint">尚未配置定价，仅展示 Token 消耗</div>
        <div v-else class="cost-empty">当前窗口暂无请求数据</div>
      </AppSectionCard>

      <AppSectionCard title="Token 消耗" desc="输入与输出 Token 占比" icon="data-usage" admin>
        <AdminChart v-if="hasTokens" :option="tokenChartOption" height="220px" />
        <div v-else class="cost-empty">当前窗口暂无 Token 数据</div>
      </AppSectionCard>
    </div>

    <AppSectionCard title="时间分布" icon="activity" :desc="timeseries.granularity_minutes ? timeseries.granularity_minutes + ' 分钟粒度' : timeseries.granularity_hours ? timeseries.granularity_hours + ' 小时粒度' : '自动粒度'" admin>
      <AdminChart v-if="timeseries.points.length > 0" :option="timeseriesChartOption" height="240px" />
      <div v-else class="cost-empty">当前窗口暂无时间序列</div>
    </AppSectionCard>

    <AppSectionCard title="模型占比" icon="model-training" desc="按模型展示请求占比、Token 与估算成本" admin>
      <template v-if="models.models.length > 0">
        <AdminChart :option="modelShareChartOption" height="260px" />
        <div class="cost-model-table">
        <el-table :data="models.models" size="small" stripe v-loading="isLoading" empty-text="当前窗口暂无模型分布数据">
        <el-table-column prop="alias" label="模型别名" min-width="160" sortable />
        <el-table-column label="请求数" width="96" align="right" sortable>
          <template #default="{ row }">{{ formatInteger(row.request_count) }}</template>
        </el-table-column>
        <el-table-column prop="request_share_pct" label="占比" width="80" align="right">
          <template #default="{ row }">{{ row.request_share_pct }}%</template>
        </el-table-column>
        <el-table-column label="输入 / 输出 Token" min-width="150" align="right">
          <template #default="{ row }">
            <span class="cost-token-pair">{{ formatInteger(row.total_request_tokens) }} <span class="cost-token-sep">/</span> {{ formatInteger(row.total_response_tokens) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="总成本" width="110" align="right" sortable>
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
        </div>
      </template>
      <div v-else class="cost-empty">当前窗口暂无模型分布数据</div>
    </AppSectionCard>

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
.cost-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.cost-summary-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 18px;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  background: var(--surface-1);
}

.cost-summary-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 12px;
  border: 1px solid rgba(157, 173, 196, 0.18);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-primary);
  flex-shrink: 0;
}

.cost-summary-card__copy {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.cost-summary-card__copy span {
  font-size: 12px;
  color: var(--text-secondary);
}

.cost-summary-card__copy strong {
  color: var(--text-primary);
  font-size: 1.45rem;
  line-height: 1.05;
  letter-spacing: -0.04em;
}

.cost-summary-card.is-brand .cost-summary-card__icon {
  color: var(--brand);
}

.cost-summary-card.is-accent .cost-summary-card__icon {
  color: #4aa5a5;
}

.cost-summary-card.is-warning .cost-summary-card__icon {
  color: var(--warning);
}

.cost-summary-card.is-success .cost-summary-card__icon {
  color: var(--success);
}

.cost-chart-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.cost-chart-grid :deep(.admin-section-card) {
  min-height: 100%;
  padding: 24px 26px;
  border: 1px solid var(--line-soft);
  border-radius: 28px;
  background: var(--surface-1);
}

.cost-empty {
  padding: 32px 0;
  text-align: center;
  font-size: 12px;
  color: var(--text-muted);
}

.cost-empty-hint {
  padding: 32px 0;
  text-align: center;
  font-size: 12px;
  color: var(--text-secondary);
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

.cost-model-table :deep(.el-table) {
  --el-table-border-color: var(--line-soft);
  --el-table-header-bg-color: transparent;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  overflow: hidden;
}

.cost-model-table :deep(.el-table__inner-wrapper::before) {
  display: none;
}

.cost-model-table :deep(.el-table th.el-table__cell) {
  height: 44px;
  padding-block: 6px;
  color: var(--text-muted);
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  background: transparent;
}

.cost-model-table :deep(.el-table td.el-table__cell) {
  padding-block: 10px;
}

.cost-model-table :deep(.el-table th.el-table__cell .cell),
.cost-model-table :deep(.el-table td.el-table__cell .cell) {
  padding-inline: 14px;
}

.cost-kicker {
  display: block;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--text-muted);
}

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

@media (max-width: 900px) {
  .cost-summary-grid,
  .cost-chart-grid {
    grid-template-columns: 1fr;
  }
}
</style>
