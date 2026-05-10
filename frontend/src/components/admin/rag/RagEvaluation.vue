<script setup>
import { computed, ref } from 'vue';
import { ElRadioGroup, ElRadioButton, ElButton, ElAlert, ElTag } from 'element-plus';

import { ragEvalApi } from '../../../api/rag-eval.js';
import AdminDataTable from '../AdminDataTable.vue';
import OpsSectionFrame from '../ops/OpsSectionFrame.vue';
import AppSectionCard from '../../ui/AppSectionCard.vue';

const mode = ref('all');
const isLoading = ref(false);
const errorMsg = ref('');
const retrievalResult = ref(null);
const generationResult = ref(null);

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

const retrievalSummaryCards = computed(() => {
  const s = retrievalResult.value?.summary;
  if (!s) return [];
  return [
    { key: 'recall', label: 'Recall@K', value: formatScore(s.recall_at_k) },
    { key: 'mrr', label: 'MRR', value: formatScore(s.mrr) },
    { key: 'ndcg', label: 'nDCG@K', value: formatScore(s.ndcg_at_k) },
    { key: 'latency', label: '平均延迟', value: formatMs(s.average_latency_ms) },
  ];
});

const generationSummaryCards = computed(() => {
  const s = generationResult.value?.summary;
  if (!s) return [];
  return [
    { key: 'faithfulness', label: '平均忠实度', value: formatScore(s.avg_faithfulness) },
    { key: 'relevancy', label: '平均相关性', value: formatScore(s.avg_relevancy) },
    { key: 'faithfulness-rate', label: '忠实度通过率', value: formatRate(s.faithfulness_pass_rate) },
    { key: 'relevancy-rate', label: '相关性通过率', value: formatRate(s.relevancy_pass_rate) },
    { key: 'latency', label: '平均检索延迟', value: formatMs(s.avg_retrieval_latency_ms) },
  ];
});

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

async function handleRun() {
  isLoading.value = true;
  errorMsg.value = '';
  retrievalResult.value = null;
  generationResult.value = null;

  try {
    const data = await ragEvalApi.runEvaluation(mode.value);
    if (data.retrieval) retrievalResult.value = data.retrieval;
    if (data.generation) generationResult.value = data.generation;
  } catch (error) {
    errorMsg.value = error.message || '评测执行失败';
  } finally {
    isLoading.value = false;
  }
}
</script>

<template>
  <OpsSectionFrame title="RAG 评测">
    <template #actions>
      <el-radio-group v-model="mode" size="small">
        <el-radio-button value="retrieval">检索评测</el-radio-button>
        <el-radio-button value="generation">生成评测</el-radio-button>
        <el-radio-button value="all">全部</el-radio-button>
      </el-radio-group>
      <el-button type="primary" :loading="isLoading" @click="handleRun">
        运行评测
      </el-button>
    </template>

    <template #alerts>
      <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" />
    </template>

    <!-- Retrieval section -->
    <template v-if="retrievalResult">
      <AppSectionCard admin title="检索评测摘要">
        <div class="rag-eval__metrics">
          <article v-for="card in retrievalSummaryCards" :key="card.key" class="rag-eval__metric-tile">
            <span class="rag-eval__metric-label">{{ card.label }}</span>
            <strong class="rag-eval__metric-value">{{ card.value }}</strong>
          </article>
        </div>
      </AppSectionCard>

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
      <AppSectionCard admin title="生成评测摘要">
        <div class="rag-eval__metrics">
          <article v-for="card in generationSummaryCards" :key="card.key" class="rag-eval__metric-tile">
            <span class="rag-eval__metric-label">{{ card.label }}</span>
            <strong class="rag-eval__metric-value">{{ card.value }}</strong>
          </article>
        </div>
      </AppSectionCard>

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
.rag-eval__metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
}

.rag-eval__metric-tile {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px 16px;
  border: 1px solid var(--line-soft);
  border-radius: 6px;
  background: var(--surface-2);
}

.rag-eval__metric-label {
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.rag-eval__metric-value {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}
</style>
