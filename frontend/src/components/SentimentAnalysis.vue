<script setup>
import { computed, onMounted, ref, watch } from 'vue';

import { kbApi } from '../api/knowledgebase.js';
import { sentimentApi } from '../api/sentiment.js';
import { useFlash } from '../lib/flash.js';
import DossierPageShell from './workspace/dossier/DossierPageShell.vue';
import DossierEvidenceStack from './workspace/dossier/DossierEvidenceStack.vue';

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
    <DossierPageShell title="舆情分析" eyebrow="Sentiment dossier">
      <template #summary>
        <section class="sentiment-panel">
          <header class="sentiment-panel__header">
            <p>Conclusion first</p>
            <h3>分析结论</h3>
          </header>

          <div v-if="!result" class="sentiment-empty">请选择范围后开始分析。</div>
          <div v-else class="sentiment-results">
            <section class="sentiment-summary">
              <article class="sentiment-metric sentiment-metric--lead">
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
          </div>
        </section>
      </template>

      <template #evidence>
        <DossierEvidenceStack>
          <section class="sentiment-panel">
            <header class="sentiment-panel__header">
              <p>Evidence second</p>
              <h3>逐文档证据</h3>
            </header>

            <div v-if="result">
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
            <div v-else class="sentiment-empty sentiment-empty--secondary">结论生成后，这里会展示逐文档的摘要与证据。</div>
          </section>
        </DossierEvidenceStack>
      </template>

      <template #actions>
        <section class="sentiment-panel sentiment-panel--actions">
          <header class="sentiment-panel__header">
            <p>Actions last</p>
            <h3>分析范围</h3>
          </header>

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

            <label class="sentiment-field">
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
        </section>
      </template>
    </DossierPageShell>
  </div>
</template>

<style scoped>
.sentiment-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.sentiment-panel {
  border: 1px solid rgba(95, 69, 35, 0.14);
  border-radius: 22px;
  background: rgba(251, 246, 237, 0.94);
  box-shadow: 0 18px 52px -42px rgba(80, 54, 20, 0.28);
  padding: 20px;
}

.sentiment-panel__header {
  margin-bottom: 16px;
}

.sentiment-panel__header p {
  margin: 0 0 6px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #8b7358;
}

.sentiment-panel__header h3 {
  margin: 0;
  color: #2f2418;
  letter-spacing: -0.02em;
}

.sentiment-empty,
.sentiment-hint {
  color: #6f5a42;
}

.sentiment-empty--secondary {
  padding: 12px 0;
}

.sentiment-results {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.sentiment-summary {
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) repeat(2, minmax(0, 0.9fr));
  gap: 12px;
}

.sentiment-distribution {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.sentiment-metric,
.sentiment-distribution__item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  border: 1px solid rgba(95, 69, 35, 0.12);
  border-radius: 16px;
  background: rgba(255, 251, 245, 0.96);
}

.sentiment-metric span,
.sentiment-distribution__item span {
  color: #8b7358;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.sentiment-metric strong,
.sentiment-distribution__item strong {
  color: #2f2418;
  font-size: 24px;
}

.sentiment-controls {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sentiment-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sentiment-field span {
  color: #8b7358;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.sentiment-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
}

.sentiment-evidence {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

@media (max-width: 1000px) {
  .sentiment-summary,
  .sentiment-distribution {
    grid-template-columns: 1fr;
  }
}
</style>
