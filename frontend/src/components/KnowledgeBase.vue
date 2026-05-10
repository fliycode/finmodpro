<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';

import { kbApi } from '../api/knowledgebase.js';
import KnowledgeBaseTable from './knowledgebase/KnowledgeBaseTable.vue';
import KnowledgeBaseToolbar from './knowledgebase/KnowledgeBaseToolbar.vue';
import AppIcon from './ui/AppIcon.vue';
import { useFlash } from '../lib/flash.js';
import { isIngestionInFlight } from '../lib/knowledgebase-actions.js';
import {
  buildNextSelection,
  buildSelectionAfterBatchDelete,
  summarizeBatchResult,
} from '../lib/knowledgebase-workspace.js';

const props = defineProps({
  showAdminMetrics: {
    type: Boolean,
    default: false,
  },
});

const router = useRouter();

const detailRoutePrefix = computed(() =>
  props.showAdminMetrics ? '/admin/knowledge' : '/workspace/knowledge',
);

const items = ref([]);
const isLoading = ref(false);
const isUploading = ref(false);
const isSubmittingTask = ref(false);
const isLoadingDatasets = ref(false);
const isCreatingDataset = ref(false);
const isDatasetComposerOpen = ref(false);
const selectedDatasetId = ref('all');
const searchKeyword = ref('');
const statusFilter = ref('all');
const timeRange = ref('all');
const checkedDocumentIds = ref([]);
const fileInput = ref(null);
const currentPage = ref(1);
const pagination = ref({ total: 0, page: 1, pageSize: 10, totalPages: 0 });
const datasets = ref([]);
const stats = ref({
  total_datasets: 0,
  total_documents: 0,
  total_vectors: 0,
  total_storage_bytes: 0,
  total_storage_formatted: '0 B',
  indexed_count: 0,
  failed_count: 0,
  processing_count: 0,
  ready_rate: '0%',
});
const isLoadingStats = ref(false);
const datasetForm = ref({
  name: '',
  description: '',
});
const flash = useFlash();

let pollInterval = null;

const statusTone = {
  uploaded: 'neutral',
  queued: 'neutral',
  parsing: 'accent',
  chunking: 'accent',
  indexing: 'accent',
  indexed: 'success',
  failed: 'danger',
};

const decoratedItems = computed(() =>
  items.value.map((item) => ({
    ...item,
    statusTone: statusTone[item.processStep?.code] || 'neutral',
  })),
);

const activeProcessingCount = computed(() =>
  items.value.filter((item) => isIngestionInFlight(item)).length,
);

const summaryCards = computed(() => [
  {
    id: 'datasets',
    label: '数据集总数',
    value: stats.value.total_datasets,
    tone: 'violet',
    icon: 'layers',
  },
  {
    id: 'documents',
    label: '文档总数',
    value: stats.value.total_documents,
    tone: 'blue',
    icon: 'file-text',
  },
  {
    id: 'storage',
    label: '数据总量',
    value: stats.value.total_storage_formatted,
    tone: 'green',
    icon: 'database',
  },
  {
    id: 'vectors',
    label: '向量总数',
    value: Number(stats.value.total_vectors || 0).toLocaleString('zh-CN'),
    tone: 'amber',
    icon: 'zap',
  },
  {
    id: 'ready',
    label: '可检索率',
    value: stats.value.ready_rate,
    delta: `${stats.value.failed_count} 个失败`,
    tone: 'purple',
    icon: 'check',
  },
]);

const activeDataset = computed(() =>
  datasets.value.find((dataset) => String(dataset.id) === String(selectedDatasetId.value)) || null,
);

const fetchDatasets = async () => {
  isLoadingDatasets.value = true;
  try {
    const result = await kbApi.listDatasets();
    datasets.value = result.datasets || [];
    if (
      selectedDatasetId.value !== 'all'
      && !datasets.value.some((dataset) => String(dataset.id) === String(selectedDatasetId.value))
    ) {
      selectedDatasetId.value = 'all';
    }
  } catch (error) {
    console.error('加载数据集失败:', error);
    flash.error(`加载数据集失败：${error.message || '未知错误'}`);
  } finally {
    isLoadingDatasets.value = false;
  }
};

const fetchStats = async () => {
  isLoadingStats.value = true;
  try {
    stats.value = await kbApi.getStats();
  } catch (error) {
    console.error('加载统计数据失败:', error);
  } finally {
    isLoadingStats.value = false;
  }
};

const fetchDocuments = async () => {
  isLoading.value = true;
  try {
    const result = await kbApi.listDocuments({
      searchKeyword: searchKeyword.value,
      statusFilter: statusFilter.value,
      timeRange: timeRange.value,
      datasetId: selectedDatasetId.value,
      page: currentPage.value,
      pageSize: pagination.value.pageSize,
    });

    items.value = result.documents || [];
    pagination.value = {
      total: result.total || 0,
      page: result.page || currentPage.value,
      pageSize: result.pageSize || pagination.value.pageSize,
      totalPages: result.totalPages || 0,
    };
    currentPage.value = pagination.value.page;
    checkedDocumentIds.value = checkedDocumentIds.value.filter((id) => items.value.some((item) => item.id === id));
  } catch (error) {
    console.error('加载知识库失败:', error);
    flash.error(`加载知识库失败：${error.message || '未知错误'}`);
  } finally {
    isLoading.value = false;
  }
};

const navigateToDetail = (item) => {
  router.push(`${detailRoutePrefix.value}/documents/${item.id}`);
};

const triggerUpload = () => {
  fileInput.value?.click();
};

const handleFileChange = async (event) => {
  const file = event.target.files?.[0];
  if (!file) return;

  isUploading.value = true;
  try {
    const uploadResult = await kbApi.uploadDocument(file, {
      datasetId: selectedDatasetId.value,
    });
    flash.success(
      selectedDatasetId.value !== 'all'
        ? `文件已上传到"${activeDataset.value?.name || '当前数据集'}"。请启动入库任务。`
        : '文件已上传。请启动入库任务，后台会异步完成解析、切块和向量化。',
    );
    if (uploadResult.document?.id) {
      router.push(`${detailRoutePrefix.value}/documents/${uploadResult.document.id}`);
      return;
    }
    await fetchDatasets();
    await fetchDocuments();
    await fetchStats();
  } catch (error) {
    console.error('上传文档失败:', error);
    flash.error(`上传失败：${error.message || '未知错误'}`);
  } finally {
    isUploading.value = false;
    event.target.value = '';
  }
};

const createDataset = async () => {
  if (!datasetForm.value.name.trim()) {
    flash.error('请输入数据集名称。');
    return;
  }

  isCreatingDataset.value = true;
  try {
    const dataset = await kbApi.createDataset(datasetForm.value);
    flash.success(`数据集"${dataset.name}"已创建。`);
    datasetForm.value = { name: '', description: '' };
    isDatasetComposerOpen.value = false;
    await fetchDatasets();
    selectedDatasetId.value = String(dataset.id);
    currentPage.value = 1;
    await fetchDocuments();
    await fetchStats();
  } catch (error) {
    console.error('创建数据集失败:', error);
    flash.error(`创建数据集失败：${error.message || '未知错误'}`);
  } finally {
    isCreatingDataset.value = false;
  }
};

const startIngestionForDocument = async (documentId) => {
  if (!documentId || isSubmittingTask.value) return;

  isSubmittingTask.value = true;
  try {
    const ingestResult = await kbApi.ingestDocument(documentId);
    flash.success(ingestResult.message || '入库任务已提交。');
    await fetchDocuments();
  } catch (error) {
    console.error('启动入库任务失败:', error);
    flash.error(`启动入库失败：${error.message || '未知错误'}`);
  } finally {
    isSubmittingTask.value = false;
  }
};

const handleRowAction = async ({ item, action }) => {
  if (action === 'view-detail') {
    navigateToDetail(item);
    return;
  }
  if (action === 'reingest') {
    await startIngestionForDocument(item.id);
    return;
  }
  if (action === 'delete') {
    try {
      await kbApi.deleteDocument(item.id);
      flash.success(`文档"${item.title}"已删除。`);
      await fetchDocuments();
      await fetchStats();
    } catch (error) {
      flash.error(`删除失败：${error.message || '未知错误'}`);
    }
  }
};

const toggleRow = (documentId) => {
  checkedDocumentIds.value = buildNextSelection({
    selectedIds: checkedDocumentIds.value,
    toggledId: documentId,
  });
};

const toggleAll = () => {
  if (decoratedItems.value.length === 0) {
    checkedDocumentIds.value = [];
    return;
  }

  const allIds = decoratedItems.value.map((item) => item.id);
  const allChecked = allIds.every((id) => checkedDocumentIds.value.includes(id));
  checkedDocumentIds.value = allChecked ? [] : allIds;
};

const changePage = async (page) => {
  currentPage.value = page;
  await fetchDocuments();
};

const handleBatchIngest = async () => {
  if (checkedDocumentIds.value.length === 0) return;

  try {
    const payload = await kbApi.batchIngestDocuments(checkedDocumentIds.value);
    flash.success(summarizeBatchResult(payload, '批量重新入库'));
    await fetchDocuments();
  } catch (error) {
    console.error('批量入库失败:', error);
    flash.error(`批量入库失败：${error.message || '未知错误'}`);
  }
};

const handleBatchDelete = async () => {
  if (checkedDocumentIds.value.length === 0) return;

  try {
    const payload = await kbApi.batchDeleteDocuments(checkedDocumentIds.value);
    flash.success(summarizeBatchResult(payload, '批量删除'));
    const deletedIds = (payload.results || [])
      .filter((item) => item.status === 'deleted')
      .map((item) => item.document_id);
    checkedDocumentIds.value = buildSelectionAfterBatchDelete(checkedDocumentIds.value, deletedIds);
    await fetchDocuments();
    await fetchStats();
  } catch (error) {
    console.error('批量删除失败:', error);
    flash.error(`批量删除失败：${error.message || '未知错误'}`);
  }
};

const startPolling = () => {
  pollInterval = setInterval(async () => {
    if (activeProcessingCount.value === 0) return;
    try {
      await fetchDocuments();
      await fetchStats();
    } catch (error) {
      console.error('轮询知识库失败:', error);
    }
  }, 3000);
};

watch([searchKeyword, statusFilter, timeRange, selectedDatasetId], async () => {
  currentPage.value = 1;
  await fetchDocuments();
});

onMounted(async () => {
  await fetchDatasets();
  await fetchDocuments();
  await fetchStats();
  startPolling();
});

onUnmounted(() => {
  if (pollInterval) {
    clearInterval(pollInterval);
  }
});
</script>

<template>
  <div :class="['kb-page', { 'kb-page--admin': showAdminMetrics }]">
    <input ref="fileInput" type="file" hidden @change="handleFileChange" />

    <section class="kb-overview">
      <div class="kb-overview__stats">
        <article
          v-for="card in summaryCards"
          :key="card.id"
          :class="['stat-card', `stat-card--${card.tone}`]"
        >
          <span class="stat-card__icon" aria-hidden="true">
            <AppIcon :name="card.icon" :width="20" :height="20" />
          </span>
          <div class="stat-card__body">
            <span class="stat-label">{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
            <small v-if="card.delta">{{ card.delta }}</small>
          </div>
        </article>
      </div>
    </section>

    <section class="kb-ledger-panel">
      <KnowledgeBaseToolbar
        :search-keyword="searchKeyword"
        :status-filter="statusFilter"
        :time-range="timeRange"
        :datasets="datasets"
        :selected-dataset-id="selectedDatasetId"
        :is-uploading="isUploading"
        @update:search-keyword="searchKeyword = $event"
        @update:status-filter="statusFilter = $event"
        @update:time-range="timeRange = $event"
        @update:selected-dataset-id="selectedDatasetId = $event"
        @create-dataset="isDatasetComposerOpen = !isDatasetComposerOpen"
        @upload="triggerUpload"
      />

      <section v-if="isDatasetComposerOpen" class="kb-dataset-composer">
        <div class="kb-dataset-composer__copy">
          <p class="eyebrow">Dataset composer</p>
          <h3>创建一个新的知识数据集</h3>
          <p>
            用于组织上传文档、限定检索范围，并为后续问答与风险抽取提供稳定的数据边界。
          </p>
        </div>
        <div class="kb-dataset-composer__form">
          <input
            v-model="datasetForm.name"
            class="kb-search"
            type="text"
            placeholder="例如：2025 年报数据集"
          />
          <textarea
            v-model="datasetForm.description"
            class="kb-textarea"
            rows="3"
            placeholder="补充该数据集的用途、来源或适用场景"
          />
          <div class="kb-dataset-composer__actions">
            <button
              class="kb-secondary-btn"
              :disabled="isCreatingDataset"
              @click="isDatasetComposerOpen = false"
            >
              取消
            </button>
            <button
              class="kb-primary-btn"
              :disabled="isCreatingDataset"
              @click="createDataset"
            >
              {{ isCreatingDataset ? '创建中...' : '创建数据集' }}
            </button>
          </div>
        </div>
      </section>

      <div v-if="checkedDocumentIds.length > 0" class="kb-batchbar">
        <span>已选择 {{ checkedDocumentIds.length }} 个文档</span>
        <div class="kb-batchbar__actions">
          <button class="kb-secondary-btn" @click="handleBatchIngest">批量重新入库</button>
          <button class="kb-danger-btn" @click="handleBatchDelete">批量删除</button>
        </div>
      </div>

      <KnowledgeBaseTable
        :items="decoratedItems"
        :checked-ids="checkedDocumentIds"
        :is-loading="isLoading"
        :page="pagination.page"
        :total-pages="pagination.totalPages"
        :total="pagination.total"
        @navigate="navigateToDetail"
        @toggle-row="toggleRow"
        @toggle-all="toggleAll"
        @row-action="handleRowAction"
        @change-page="changePage"
      />
    </section>
  </div>
</template>

<style scoped>
.kb-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
  color: var(--text-secondary);
}

.kb-overview {
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.eyebrow {
  margin: 0 0 8px;
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--brand);
}

.kb-overview h2,
.kb-dataset-composer h3 {
  margin: 0;
  font-family: 'DM Sans', 'Noto Sans SC', sans-serif;
  font-size: 1.25rem;
  font-weight: 600;
  line-height: 1.35;
  color: var(--text-primary);
  letter-spacing: -0.01em;
}

.kb-dataset-composer p {
  margin: 10px 0 0;
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  color: var(--text-secondary);
  line-height: 1.6;
}

.kb-overview__stats {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 72px;
  padding: 12px 16px;
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: color-mix(in srgb, var(--surface-2) 88%, var(--brand-soft));
}

.stat-card__icon {
  width: 36px;
  height: 36px;
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: var(--surface-3);
  color: var(--brand);
}

.stat-card--violet .stat-card__icon {
  background: rgba(68, 49, 141, 0.1);
  color: #44318d;
}

.stat-card--green .stat-card__icon {
  background: rgba(31, 122, 100, 0.1);
  color: #1f7a64;
}

.stat-card--amber .stat-card__icon {
  background: rgba(138, 90, 32, 0.1);
  color: #8a5a20;
}

.stat-card--purple .stat-card__icon {
  background: rgba(75, 53, 126, 0.1);
  color: #4b357e;
}

.stat-card__body {
  min-width: 0;
}

.stat-label {
  display: block;
  color: var(--text-muted);
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.02em;
  margin-bottom: 4px;
}

.stat-card strong {
  display: block;
  color: var(--text-primary);
  font-family: 'DM Sans', 'Noto Sans SC', sans-serif;
  font-size: clamp(17px, 1.8vw, 20px);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  line-height: 1.15;
}

.stat-card small {
  display: block;
  margin-top: 4px;
  color: var(--text-muted);
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 11px;
}

.kb-ledger-panel {
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  background: var(--surface-2);
  box-shadow: var(--shadow-md);
  overflow: hidden;
}

.kb-dataset-composer {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, 0.95fr);
  gap: 20px;
  margin: 0 18px 18px;
  padding: 18px;
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: var(--surface-2);
  box-shadow: var(--shadow-md);
}

.kb-dataset-composer__form {
  display: grid;
  gap: 12px;
}

.kb-search,
.kb-textarea {
  width: 100%;
  border: 1px solid var(--line-strong);
  border-radius: 12px;
  padding: 12px 14px;
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 14px;
  color: var(--text-primary);
  background: var(--surface-3);
}

.kb-textarea {
  resize: vertical;
}

.kb-dataset-composer__actions,
.kb-batchbar__actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.kb-dataset-composer__actions {
  justify-content: flex-end;
}

.kb-batchbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 16px;
  margin: 0 16px 14px;
  border: 1px solid var(--line-soft);
  border-radius: 12px;
  background: var(--surface-2);
  box-shadow: var(--shadow-sm);
}

.kb-batchbar span {
  color: var(--text-primary);
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-weight: 600;
  font-size: 13px;
}

.kb-primary-btn,
.kb-secondary-btn,
.kb-danger-btn {
  min-height: 36px;
  padding: 0 16px;
  border-radius: 10px;
  font-family: 'PingFang SC', 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.kb-primary-btn {
  border: 1px solid var(--brand);
  background: var(--brand);
  color: #fff;
}

.kb-secondary-btn {
  border: 1px solid var(--line-strong);
  background: var(--surface-2);
  color: var(--text-primary);
}

.kb-danger-btn {
  border: 1px solid rgba(181, 58, 58, 0.18);
  background: rgba(181, 58, 58, 0.08);
  color: #9b3131;
}

@media (max-width: 1180px) {
  .kb-dataset-composer {
    grid-template-columns: 1fr;
  }

  .kb-overview__stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .kb-overview__stats {
    grid-template-columns: 1fr;
  }

  .kb-batchbar {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
