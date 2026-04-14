<script setup>
import { computed, onMounted, ref, watch } from 'vue';

import { kbApi } from '../api/knowledgebase.js';
import { sentimentApi } from '../api/sentiment.js';
import { useFlash } from '../lib/flash.js';
import AppSectionCard from './ui/AppSectionCard.vue';

const flash = useFlash();

const datasets = ref([]);
const documents = ref([]);
const selectedDatasetId = ref('all');
const selectedDocumentIds = ref([]);
const result = ref(null);
const isLoadingScope = ref(false);
const isAnalyzing = ref(false);

const sentimentToneMap = {
  positive: 'success',
  neutral: 'info',
  negative: 'danger',
};

const riskToneMap = {
  low: 'success',
  moderate: 'warning',
  elevated: 'danger',
  high: 'danger',
};

const selectedDatasetLabel = computed(() => {
  if (selectedDatasetId.value === 'all') {
    return '全部数据集';
  }
  return datasets.value.find((item) => String(item.id) === String(selectedDatasetId.value))?.name || '当前数据集';
});

const fetchScope = async () => {
  isLoadingScope.value = true;
  try {
    const [datasetPayload, documentPayload] = await Promise.all([
      kbApi.listDatasets(),
      kbApi.listDocuments({
        datasetId: selectedDatasetId.value === 'all' ? '' : selectedDatasetId.value,
        pageSize: 100,
      }),
    ]);
    datasets.value = datasetPayload.datasets || [];
    documents.value = documentPayload.documents || [];
    selectedDocumentIds.value = selectedDocumentIds.value.filter((id) =>
      documents.value.some((item) => item.id === id),
    );
  } catch (error) {
    flash.error(error.message || '加载舆情分析范围失败');
  } finally {
    isLoadingScope.value = false;
  }
};

const runAnalysis = async () => {
  isAnalyzing.value = true;
  try {
    result.value = await sentimentApi.analyze({
      dataset_id: selectedDatasetId.value === 'all' ? undefined : Number(selectedDatasetId.value),
      document_ids: selectedDocumentIds.value.length > 0 ? selectedDocumentIds.value : undefined,
    });
    flash.success('舆情分析完成');
  } catch (error) {
    flash.error(error.message || '舆情分析失败');
  } finally {
    isAnalyzing.value = false;
  }
};

watch(selectedDatasetId, () => {
  result.value = null;
  fetchScope();
});

onMounted(fetchScope);
</script>

<template>
  <div class="sentiment-page">
    <AppSectionCard
      title="分析范围"
      desc="按数据集或指定文档生成舆情倾向与风险倾向摘要，优先复用现有知识资产。"
    >
      <div class="sentiment-controls">
        <label class="sentiment-field">
          <span>数据集</span>
          <el-select v-model="selectedDatasetId" :loading="isLoadingScope">
            <el-option label="全部数据集" value="all" />
            <el-option
              v-for="dataset in datasets"
              :key="dataset.id"
              :label="dataset.name"
              :value="String(dataset.id)"
            />
          </el-select>
        </label>

        <label class="sentiment-field sentiment-field--wide">
          <span>文档范围</span>
          <el-select
            v-model="selectedDocumentIds"
            multiple
            clearable
            collapse-tags
            collapse-tags-tooltip
            :loading="isLoadingScope"
            placeholder="不选则分析当前范围内全部文档"
          >
            <el-option
              v-for="document in documents"
              :key="document.id"
              :label="document.title"
              :value="document.id"
            />
          </el-select>
        </label>

        <div class="sentiment-actions">
          <el-button type="primary" :loading="isAnalyzing" @click="runAnalysis">开始分析</el-button>
          <span class="sentiment-hint">
            当前范围：{{ selectedDatasetLabel }} / {{ selectedDocumentIds.length || documents.length || 0 }} 份文档
          </span>
        </div>
      </div>
    </AppSectionCard>

    <AppSectionCard
      title="分析结论"
      desc="结果来自后端生成，包含整体情绪、风险倾向和逐文档证据。"
    >
      <div v-if="!result" class="sentiment-empty">请选择范围后开始分析。</div>
      <div v-else class="sentiment-results">
        <section class="sentiment-summary">
          <article class="sentiment-metric">
            <span>整体情绪</span>
            <el-tag :type="sentimentToneMap[result.summary?.overall_sentiment] || 'info'">
              {{ result.summary?.overall_sentiment || '--' }}
            </el-tag>
          </article>
          <article class="sentiment-metric">
            <span>风险倾向</span>
            <el-tag :type="riskToneMap[result.summary?.risk_tendency] || 'warning'">
              {{ result.summary?.risk_tendency || '--' }}
            </el-tag>
          </article>
          <article class="sentiment-metric">
            <span>文档数</span>
            <strong>{{ result.summary?.document_count ?? 0 }}</strong>
          </article>
        </section>

        <section class="sentiment-distribution">
          <article
            v-for="item in result.distribution || []"
            :key="item.key"
            class="sentiment-distribution__item"
          >
            <span>{{ item.key }}</span>
            <strong>{{ item.value }}</strong>
          </article>
        </section>

        <el-table :data="result.items || []" stripe>
          <el-table-column prop="document_title" label="文档" min-width="180" />
          <el-table-column label="情绪" width="120">
            <template #default="{ row }">
              <el-tag :type="sentimentToneMap[row.sentiment] || 'info'">{{ row.sentiment }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="风险倾向" width="140">
            <template #default="{ row }">
              <el-tag :type="riskToneMap[row.risk_tendency] || 'warning'">{{ row.risk_tendency }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="summary" label="摘要" min-width="280" show-overflow-tooltip />
          <el-table-column label="证据" min-width="220">
            <template #default="{ row }">
              <div class="sentiment-evidence">
                <el-tag v-for="item in row.evidence || []" :key="item" size="small" effect="plain">
                  {{ item }}
                </el-tag>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </AppSectionCard>
  </div>
</template>

<style scoped>
.sentiment-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.sentiment-controls {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.sentiment-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sentiment-field--wide {
  grid-column: span 2;
}

.sentiment-actions {
  grid-column: span 2;
  display: flex;
  align-items: center;
  gap: 12px;
}

.sentiment-hint,
.sentiment-empty {
  color: var(--text-secondary);
}

.sentiment-results {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.sentiment-summary,
.sentiment-distribution {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}

.sentiment-metric,
.sentiment-distribution__item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 16px;
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: var(--surface-2);
}

.sentiment-metric span,
.sentiment-distribution__item span {
  color: var(--text-muted);
  font-size: 12px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.sentiment-metric strong,
.sentiment-distribution__item strong {
  color: var(--text-primary);
  font-size: 24px;
}

.sentiment-evidence {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

@media (max-width: 900px) {
  .sentiment-controls,
  .sentiment-summary,
  .sentiment-distribution {
    grid-template-columns: 1fr;
  }

  .sentiment-field--wide,
  .sentiment-actions {
    grid-column: span 1;
  }

  .sentiment-actions {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
