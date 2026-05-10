<script setup>
import { computed, onMounted, ref } from 'vue';

import { llmGatewayApi } from '../api/llm-gateway.js';
import {
  normalizeGatewayCostsModels,
  normalizeGatewayCostsSummary,
  normalizeGatewayCostsTimeseries,
} from '../lib/llm-gateway.js';
import AdminChart from './admin/AdminChart.vue';
import OpsInspectorDrawer from './admin/ops/OpsInspectorDrawer.vue';
import OpsSectionFrame from './admin/ops/OpsSectionFrame.vue';
import AppSectionCard from './ui/AppSectionCard.vue';

const summary = ref(normalizeGatewayCostsSummary());
const timeseries = ref(normalizeGatewayCostsTimeseries());
const models = ref(normalizeGatewayCostsModels());
const errorMsg = ref('');
const isLoading = ref(false);
const editingModel = ref(null);
const editDrawerVisible = ref(false);

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
  editingModel.value = { ...model };
  editDrawerVisible.value = true;
};

onMounted(fetchCosts);
</script>

<template>
  <OpsSectionFrame>
    <template #actions>
      <el-button :loading="isLoading" @click="fetchCosts">刷新</el-button>
    </template>

    <template #alerts>
      <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />
    </template>

    <div class="cost-chart-grid">
      <AppSectionCard title="成本结构" desc="输入与输出成本占比，以及当前窗口最高成本模型。" admin>
        <div v-if="summary.estimated_total_cost > 0" class="cost-structure-wrap">
          <AdminChart :option="costChartOption" height="240px" />
          <div class="cost-structure-leader">
            <span class="section-kicker">总成本</span>
            <strong>${{ summary.estimated_total_cost.toFixed(4) }}</strong>
            <p>{{ summary.total_request_tokens }} 输入 · {{ summary.total_response_tokens }} 输出</p>
          </div>
        </div>
        <div v-else class="admin-empty-state">当前窗口暂无成本数据</div>
      </AppSectionCard>

      <AppSectionCard title="时间分布" :desc="`粒度：${timeseries.granularity_minutes ? timeseries.granularity_minutes + ' 分钟' : timeseries.granularity_hours ? timeseries.granularity_hours + ' 小时' : '自动'}`" admin>
        <AdminChart v-if="timeseries.points.length > 0" :option="timeseriesChartOption" height="260px" />
        <div v-else class="admin-empty-state">当前窗口暂无时间序列</div>
      </AppSectionCard>
    </div>

    <OpsInspectorDrawer title="模型占比" desc="按模型展示请求占比、Token 与估算成本。">
      <el-table :data="models.models" stripe border class="cost-model-table">
        <el-table-column prop="alias" label="模型别名" min-width="160" />
        <el-table-column prop="request_count" label="请求数" width="100" />
        <el-table-column prop="request_share_pct" label="请求占比" width="100">
          <template #default="{ row }">
            {{ row.request_share_pct }}%
          </template>
        </el-table-column>
        <el-table-column label="Token" min-width="160">
          <template #default="{ row }">
            {{ row.total_request_tokens }} / {{ row.total_response_tokens }}
          </template>
        </el-table-column>
        <el-table-column label="输入成本" width="110">
          <template #default="{ row }">
            ${{ row.estimated_input_cost.toFixed(4) }}
          </template>
        </el-table-column>
        <el-table-column label="输出成本" width="110">
          <template #default="{ row }">
            ${{ row.estimated_output_cost.toFixed(4) }}
          </template>
        </el-table-column>
        <el-table-column label="总成本" width="110">
          <template #default="{ row }">
            ${{ row.estimated_total_cost.toFixed(4) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEditDrawer(row)">
              编辑
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </OpsInspectorDrawer>

    <el-drawer v-model="editDrawerVisible" size="420px" title="编辑模型定价" destroy-on-close>
      <div v-if="editingModel" class="edit-pricing-panel">
        <div class="edit-pricing-field">
          <span class="section-kicker">模型别名</span>
          <strong>{{ editingModel.alias }}</strong>
        </div>
        <div class="edit-pricing-field">
          <span class="section-kicker">当前请求占比</span>
          <p>{{ editingModel.request_share_pct }}% · {{ editingModel.request_count }} 次请求</p>
        </div>
        <div class="edit-pricing-field">
          <span class="section-kicker">Token 统计</span>
          <p>输入 {{ editingModel.total_request_tokens }} · 输出 {{ editingModel.total_response_tokens }}</p>
        </div>
        <div class="edit-pricing-field">
          <span class="section-kicker">当前估算成本</span>
          <p>输入 ${{ editingModel.estimated_input_cost.toFixed(4) }} · 输出 ${{ editingModel.estimated_output_cost.toFixed(4) }} · 总计 ${{ editingModel.estimated_total_cost.toFixed(4) }}</p>
        </div>
        <el-alert type="info" :closable="false" show-icon>
          定价配置需到「模型总览」页面设置 input/output price per million。
        </el-alert>
      </div>
    </el-drawer>
  </OpsSectionFrame>
</template>

<style scoped>
.cost-chart-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0;
  border: 1px solid var(--line-soft);
  border-radius: 28px;
  background: var(--surface-1);
  overflow: hidden;
}

.cost-chart-grid :deep(.admin-section-card) {
  min-height: 100%;
  padding: 24px 26px;
  border-left: 1px solid var(--line-soft);
  background: transparent;
}

.cost-chart-grid :deep(.admin-section-card:first-child) {
  border-left: 0;
}

.cost-structure-wrap {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 20px;
  align-items: center;
}

.cost-structure-leader {
  text-align: right;
}

.cost-structure-leader strong {
  display: block;
  margin-top: 8px;
  font-size: 22px;
  color: var(--text-primary);
}

.cost-structure-leader p {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--text-secondary);
}

.section-kicker {
  display: block;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.cost-model-table {
  width: 100%;
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

.edit-pricing-field p {
  margin: 6px 0 0;
  color: var(--text-secondary);
}

@media (max-width: 900px) {
  .cost-chart-grid {
    grid-template-columns: 1fr;
  }

  .cost-chart-grid :deep(.admin-section-card) {
    border-left: 0;
    border-top: 1px solid var(--line-soft);
  }

  .cost-chart-grid :deep(.admin-section-card:first-child) {
    border-top: 0;
  }

  .cost-structure-wrap {
    grid-template-columns: 1fr;
  }

  .cost-structure-leader {
    text-align: left;
  }
}
</style>
