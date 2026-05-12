<script setup>
import { computed, onMounted, ref } from 'vue';

import { ragEvalApi } from '../../../api/rag-eval.js';
import { buildBoardAxis, buildBoardTooltip, chartColors } from '../../../lib/admin-dashboard.js';
import AdminChart from '../AdminChart.vue';
import AdminDataTable from '../AdminDataTable.vue';
import OpsSectionFrame from '../ops/OpsSectionFrame.vue';
import OpsStatusBand from '../ops/OpsStatusBand.vue';
import AppSectionCard from '../../ui/AppSectionCard.vue';

/* ---------- State ---------- */

const mode = ref('all');
const isLoading = ref(false);
const isHistoryLoading = ref(false);
const errorMsg = ref('');
const retrievalResult = ref(null);
const generationResult = ref(null);
const history = ref({ total: 0, eval_records: [], comparison_groups: [] });
const progressPercent = ref(0);
let progressTimer = null;

/* ---------- Summary items ---------- */

const retrievalSummaryItems = computed(() => {
  const s = retrievalResult.value?.summary;
  if (!s) return [];
  return [
    { key: 'recall', label: 'Recall@K', value: formatScore(s.recall_at_k), icon: 'target', tone: 'brand' },
    { key: 'mrr', label: 'MRR', value: formatScore(s.mrr), icon: 'arrow-up-right', tone: 'accent' },
    { key: 'ndcg', label: 'nDCG@K', value: formatScore(s.ndcg_at_k), icon: 'bar-chart-2', tone: 'warning' },
    { key: 'latency', label: '平均延迟', value: formatMs(s.average_latency_ms), icon: 'clock', tone: latencyTone(s.average_latency_ms) },
  ];
});

const generationSummaryItems = computed(() => {
  const s = generationResult.value?.summary;
  if (!s) return [];
  return [
    { key: 'faithfulness', label: '忠实度', value: formatScore(s.avg_faithfulness), icon: 'check-circle', tone: scoreTone(s.avg_faithfulness) },
    { key: 'relevancy', label: '相关性', value: formatScore(s.avg_relevancy), icon: 'crosshair', tone: scoreTone(s.avg_relevancy) },
    { key: 'faithfulness-rate', label: '忠实度通过率', value: formatRate(s.faithfulness_pass_rate), icon: 'shield', tone: 'success' },
    { key: 'latency', label: '检索延迟', value: formatMs(s.avg_retrieval_latency_ms), icon: 'clock', tone: latencyTone(s.avg_retrieval_latency_ms) },
  ];
});

/* ---------- Radar chart ---------- */

const radarChartOption = computed(() => {
  const groups = history.value.comparison_groups;
  if (!groups || groups.length === 0) return {};
  const c = chartColors();
  const indicators = [
    { name: 'QA准确率', max: 1 },
    { name: '抽取准确率', max: 1 },
    { name: '精确率', max: 1 },
    { name: '召回率', max: 1 },
    { name: 'F1', max: 1 },
  ];
  const colorPalette = [c.brand, c.brandSoft, c.warning, c.risk, c.success];

  return {
    tooltip: { ...buildBoardTooltip() },
    legend: {
      bottom: 0,
      textStyle: { color: c.textSecondary, fontSize: 11 },
    },
    radar: {
      indicator: indicators,
      shape: 'polygon',
      axisName: { color: c.textSecondary, fontSize: 10 },
      splitLine: { lineStyle: { color: c.gridLine } },
      splitArea: { show: false },
      axisLine: { lineStyle: { color: c.gridLine } },
    },
    series: [
      {
        type: 'radar',
        data: groups.slice(0, 5).map((g, i) => ({
          name: g.group_name || g.label || `组 ${i + 1}`,
          value: [
            toNumber(g.qa_accuracy),
            toNumber(g.extraction_accuracy),
            toNumber(g.precision),
            toNumber(g.recall),
            toNumber(g.f1),
          ],
          lineStyle: { width: 2, color: colorPalette[i % colorPalette.length] },
          itemStyle: { color: colorPalette[i % colorPalette.length] },
          areaStyle: { color: colorPalette[i % colorPalette.length], opacity: 0.12 },
        })),
      },
    ],
  };
});

/* ---------- Table columns ---------- */

const retrievalColumns = [
  { key: 'name', label: '用例名称', prop: 'name', minWidth: '160' },
  { key: 'query', label: '查询', prop: 'query', minWidth: '200' },
  { key: 'recall_at_k', label: 'Recall@K', prop: 'recall_at_k', minWidth: '100', sortable: true },
  { key: 'mrr', label: 'MRR', prop: 'mrr', minWidth: '80', sortable: true },
  { key: 'ndcg_at_k', label: 'nDCG@K', prop: 'ndcg_at_k', minWidth: '100', sortable: true },
  { key: 'latency_ms', label: '延迟 (ms)', prop: 'latency_ms', minWidth: '100', sortable: true },
  { key: 'result_count', label: '结果数', prop: 'result_count', minWidth: '80' },
];

const generationColumns = [
  { key: 'name', label: '用例名称', prop: 'name', minWidth: '160' },
  { key: 'query', label: '查询', prop: 'query', minWidth: '200' },
  { key: 'answer', label: '生成回答', prop: 'answer', minWidth: '260' },
  { key: 'faithfulness_score', label: '忠实度', prop: 'faithfulness_score', minWidth: '90', sortable: true },
  { key: 'relevancy_score', label: '相关性', prop: 'relevancy_score', minWidth: '90', sortable: true },
  { key: 'faithfulness_passing', label: '忠实度通过', prop: 'faithfulness_passing', minWidth: '110', slot: 'faithfulness-passing' },
  { key: 'relevancy_passing', label: '相关性通过', prop: 'relevancy_passing', minWidth: '110', slot: 'relevancy-passing' },
  { key: 'retrieval_latency_ms', label: '检索延迟 (ms)', prop: 'retrieval_latency_ms', minWidth: '120', sortable: true },
];

/* ---------- Helpers ---------- */

function toNumber(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function formatScore(value) {
  if (value === null || value === undefined) return '--';
  return (Number(value) * 100).toFixed(1) + '%';
}

function formatRate(value) {
  if (value === null || value === undefined) return '--';
  return (Number(value) * 100).toFixed(0) + '%';
}

function formatMs(value) {
  if (value === null || value === undefined) return '--';
  return Number(value).toFixed(0) + ' ms';
}

function formatTime(iso) {
  if (!iso) return '--';
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  } catch {
    return iso;
  }
}

function latencyTone(ms) {
  if (ms > 3000) return 'risk';
  if (ms > 1000) return 'warning';
  return 'success';
}

function scoreTone(score) {
  if (score < 0.5) return 'risk';
  if (score < 0.75) return 'warning';
  return 'success';
}

function statusTagType(status) {
  if (status === 'SUCCESS' || status === 'success') return 'success';
  if (status === 'FAILURE' || status === 'failure' || status === 'FAILED') return 'danger';
  return 'info';
}

function statusLabel(status) {
  if (status === 'SUCCESS' || status === 'success') return '成功';
  if (status === 'FAILURE' || status === 'failure' || status === 'FAILED') return '失败';
  if (status === 'PENDING' || status === 'pending') return '等待中';
  if (status === 'RUNNING' || status === 'running') return '运行中';
  return status || '--';
}

/* ---------- Data fetching ---------- */

const fetchHistory = async () => {
  isHistoryLoading.value = true;
  try {
    const data = await ragEvalApi.getEvaluationHistory();
    history.value = data || { total: 0, eval_records: [], comparison_groups: [] };
  } catch {
    /* silently ignore */
  } finally {
    isHistoryLoading.value = false;
  }
};

const startProgress = () => {
  progressPercent.value = 0;
  clearInterval(progressTimer);
  progressTimer = setInterval(() => {
    if (progressPercent.value < 90) {
      progressPercent.value += Math.random() * 8 + 2;
      if (progressPercent.value > 90) progressPercent.value = 90;
    }
  }, 1500);
};

const stopProgress = () => {
  clearInterval(progressTimer);
  progressTimer = null;
  progressPercent.value = 100;
};

const handleRun = async () => {
  isLoading.value = true;
  errorMsg.value = '';
  retrievalResult.value = null;
  generationResult.value = null;
  startProgress();

  try {
    const data = await ragEvalApi.runEvaluationWithPolling(mode.value);
    stopProgress();
    if (data.retrieval) retrievalResult.value = data.retrieval;
    if (data.generation) generationResult.value = data.generation;
    await fetchHistory();
  } catch (error) {
    stopProgress();
    errorMsg.value = error.message || '评测执行失败';
  } finally {
    isLoading.value = false;
  }
};

onMounted(fetchHistory);
</script>

<template>
  <OpsSectionFrame>
    <template #actions>
      <el-radio-group v-model="mode" size="small">
        <el-radio-button value="retrieval">检索评测</el-radio-button>
        <el-radio-button value="generation">生成评测</el-radio-button>
        <el-radio-button value="all">全部</el-radio-button>
      </el-radio-group>
      <el-button type="primary" :loading="isLoading" @click="handleRun">运行评测</el-button>
      <el-button :loading="isHistoryLoading" @click="fetchHistory">刷新历史</el-button>
    </template>

    <template #alerts>
      <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />
    </template>

    <!-- Running progress -->
    <div v-if="isLoading" class="rag-progress">
      <el-progress :percentage="Math.round(progressPercent)" :stroke-width="8" :format="() => progressPercent < 90 ? '评测运行中…' : '等待后端返回结果…'" />
    </div>

    <!-- Evaluation history -->
    <AppSectionCard admin title="评测历史" desc="历史评测记录及多组对比">
      <AdminDataTable
        :data="history.eval_records"
        :loading="isHistoryLoading"
        :show-search="false"
        :show-pagination="true"
        row-key="id"
      >
        <el-table-column label="时间" min-width="140">
          <template #default="{ row }">{{ formatTime(row.created_at || row.time) }}</template>
        </el-table-column>
        <el-table-column prop="eval_target" label="目标" min-width="120" />
        <el-table-column prop="mode" label="模式" width="90" />
        <el-table-column prop="task_type" label="任务类型" width="100" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" effect="plain" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="QA准确率" width="100" align="right" sortable>
          <template #default="{ row }">{{ formatScore(row.qa_accuracy) }}</template>
        </el-table-column>
        <el-table-column label="F1" width="80" align="right" sortable>
          <template #default="{ row }">{{ formatScore(row.f1) }}</template>
        </el-table-column>
      </AdminDataTable>
    </AppSectionCard>

    <!-- Radar comparison -->
    <AppSectionCard v-if="history.comparison_groups && history.comparison_groups.length > 0" admin title="评测对比" desc="多组评测指标雷达图对比">
      <AdminChart :option="radarChartOption" height="300px" />
    </AppSectionCard>

    <!-- Retrieval section -->
    <template v-if="retrievalResult">
      <OpsStatusBand :items="retrievalSummaryItems" compact />

      <AppSectionCard admin title="检索评测明细">
        <AdminDataTable
          :data="retrievalResult.cases"
          :columns="retrievalColumns"
          :show-search="false"
          row-key="name"
        />
      </AppSectionCard>
    </template>

    <!-- Generation section -->
    <template v-if="generationResult">
      <OpsStatusBand :items="generationSummaryItems" compact />

      <AppSectionCard admin title="生成评测明细">
        <AdminDataTable
          :data="generationResult.cases"
          :columns="generationColumns"
          :show-search="false"
          row-key="name"
        >
          <template #faithfulness-passing="{ row }">
            <el-tag :type="row.faithfulness_passing ? 'success' : 'danger'" size="small">
              {{ row.faithfulness_passing ? '通过' : '未通过' }}
            </el-tag>
          </template>
          <template #relevancy-passing="{ row }">
            <el-tag :type="row.relevancy_passing ? 'success' : 'danger'" size="small">
              {{ row.relevancy_passing ? '通过' : '未通过' }}
            </el-tag>
          </template>
        </AdminDataTable>
      </AppSectionCard>
    </template>
  </OpsSectionFrame>
</template>

<style scoped>
.rag-progress {
  padding: 8px 0;
}
</style>
