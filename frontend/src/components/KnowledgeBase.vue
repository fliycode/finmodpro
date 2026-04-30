<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';

import { kbApi } from '../api/knowledgebase.js';
import KnowledgeBaseDetailPanel from './knowledgebase/KnowledgeBaseDetailPanel.vue';
import KnowledgeBaseMetricsRail from './knowledgebase/KnowledgeBaseMetricsRail.vue';
import KnowledgeBasePreviewModal from './knowledgebase/KnowledgeBasePreviewModal.vue';
import KnowledgeBaseTable from './knowledgebase/KnowledgeBaseTable.vue';
import KnowledgeBaseToolbar from './knowledgebase/KnowledgeBaseToolbar.vue';
import { useFlash } from '../lib/flash.js';
import { getDocumentRowActions, getIngestionAction, isIngestionInFlight } from '../lib/knowledgebase-actions.js';
import {
  buildChunkExpansionState,
  buildEmptyDetailState,
  buildNextSelection,
  buildPreviewState,
  buildSelectionAfterBatchDelete,
  summarizeBatchResult,
} from '../lib/knowledgebase-workspace.js';

const props = defineProps({
  showAdminMetrics: {
    type: Boolean,
    default: false,
  },
});

const items = ref([]);
const isLoading = ref(false);
const isUploading = ref(false);
const isUploadingVersion = ref(false);
const isSubmittingTask = ref(false);
const isLoadingDatasets = ref(false);
const isCreatingDataset = ref(false);
const isDatasetComposerOpen = ref(false);
const selectedDocumentId = ref('');
const selectedDocumentDetail = ref(null);
const isLoadingDetail = ref(false);
const selectedDatasetId = ref('all');
const searchKeyword = ref('');
const statusFilter = ref('all');
const timeRange = ref('all');
const checkedDocumentIds = ref([]);
const fileInput = ref(null);
const versionFileInput = ref(null);
const currentPage = ref(1);
const pagination = ref({ total: 0, page: 1, pageSize: 10, totalPages: 0 });
const isPreviewOpen = ref(false);
const activeTab = ref('processing');
const datasets = ref([]);
const versionHistory = ref([]);
const isLoadingVersions = ref(false);
const chunks = ref([]);
const isLoadingChunks = ref(false);
const expandedChunkIds = ref([]);
const datasetForm = ref({
  name: '',
  description: '',
});
const flash = useFlash();
const emptyDetailState = buildEmptyDetailState();

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

const parseSizeToBytes = (value) => {
  const match = String(value || '').match(/^([\d.]+)\s*(B|KB|MB|GB)$/i);
  if (!match) {
    return 0;
  }

  const amount = Number(match[1]);
  const unit = match[2].toUpperCase();
  const multiplier = {
    B: 1,
    KB: 1024,
    MB: 1024 ** 2,
    GB: 1024 ** 3,
  }[unit] || 1;

  return Number.isFinite(amount) ? amount * multiplier : 0;
};

const formatBytes = (bytes) => {
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return '0 B';
  }

  if (bytes >= 1024 ** 3) {
    return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
  }

  if (bytes >= 1024 ** 2) {
    return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  }

  if (bytes >= 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  return `${Math.round(bytes)} B`;
};

const decoratedItems = computed(() =>
  items.value.map((item) => ({
    ...item,
    statusTone: statusTone[item.processStep?.code] || 'neutral',
    rowActions: getDocumentRowActions(item),
  })),
);

const selectedDocument = computed(() => {
  if (selectedDocumentDetail.value?.id === selectedDocumentId.value) {
    return {
      ...selectedDocumentDetail.value,
      statusTone: statusTone[selectedDocumentDetail.value.processStep?.code] || 'neutral',
    };
  }

  const item = items.value.find((entry) => entry.id === selectedDocumentId.value);
  return item
    ? { ...item, statusTone: statusTone[item.processStep?.code] || 'neutral' }
    : null;
});

const selectedIngestionAction = computed(() => getIngestionAction(selectedDocument.value));
const previewState = computed(() => buildPreviewState(selectedDocument.value));

const activeProcessingCount = computed(() =>
  items.value.filter((item) => isIngestionInFlight(item)).length,
);

const indexedCount = computed(() =>
  items.value.filter((item) => item.isSearchReady).length,
);

const failedCount = computed(() =>
  items.value.filter((item) => item.status === 'failed').length,
);

const totalVectorCount = computed(() =>
  items.value.reduce((sum, item) => sum + Number(item.vectorCount || 0), 0),
);

const totalStorageBytes = computed(() =>
  items.value.reduce((sum, item) => sum + parseSizeToBytes(item.size), 0),
);

const readyRate = computed(() => {
  if (decoratedItems.value.length === 0) {
    return '0%';
  }

  return `${Math.round((indexedCount.value / decoratedItems.value.length) * 100)}%`;
});

const pageModeLabel = computed(() => (props.showAdminMetrics ? '管理员知识库' : '工作区知识库'));

const summaryCards = computed(() => [
  {
    id: 'datasets',
    label: '知识库总数',
    value: datasets.value.length,
    delta: isLoadingDatasets.value ? '同步中' : '数据集',
    tone: 'violet',
  },
  {
    id: 'documents',
    label: '文档总数',
    value: pagination.value.total,
    delta: `${decoratedItems.value.length} 条当前页`,
    tone: 'blue',
  },
  {
    id: 'storage',
    label: '数据总量',
    value: formatBytes(totalStorageBytes.value),
    delta: '当前筛选估算',
    tone: 'green',
  },
  {
    id: 'vectors',
    label: '向量总数',
    value: totalVectorCount.value.toLocaleString('zh-CN'),
    delta: '当前页向量',
    tone: 'amber',
  },
  {
    id: 'ready',
    label: '可检索率',
    value: readyRate.value,
    delta: `${failedCount.value} 个失败`,
    tone: 'purple',
  },
]);

const activeDataset = computed(() =>
  datasets.value.find((dataset) => String(dataset.id) === String(selectedDatasetId.value)) || null,
);

const taskHintText = computed(() => {
  if (isIngestionInFlight(selectedDocument.value)) {
    return '任务已启动，后台正在执行解析、切块和向量写入，完成后列表与详情会自动刷新。';
  }

  return `上传只保存原始文件；点击“${selectedIngestionAction.value?.label || '启动入库'}”后，后台才会异步完成解析、切块和写入向量库。`;
});

const syncSelectionWithPage = () => {
  if (!selectedDocumentId.value) {
    selectedDocumentDetail.value = null;
    versionHistory.value = [];
    return;
  }

  if (!items.value.some((item) => item.id === selectedDocumentId.value)) {
    selectedDocumentId.value = '';
    selectedDocumentDetail.value = null;
    versionHistory.value = [];
    chunks.value = [];
    expandedChunkIds.value = [];
  }
};

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
    syncSelectionWithPage();
  } catch (error) {
    console.error('加载知识库失败:', error);
    flash.error(`加载知识库失败：${error.message || '未知错误'}`);
  } finally {
    isLoading.value = false;
  }
};

const refreshSelectedDocument = async () => {
  if (!selectedDocumentId.value) {
    selectedDocumentDetail.value = null;
    return;
  }
  isLoadingDetail.value = true;
  try {
    selectedDocumentDetail.value = await kbApi.getDocumentDetail(selectedDocumentId.value);
  } catch (error) {
    console.error('加载文档详情失败:', error);
    selectedDocumentDetail.value = items.value.find((item) => item.id === selectedDocumentId.value) || null;
  } finally {
    isLoadingDetail.value = false;
  }
};

const refreshSelectedChunks = async () => {
  if (!selectedDocumentId.value) {
    chunks.value = [];
    return;
  }

  isLoadingChunks.value = true;
  try {
    chunks.value = await kbApi.getDocumentChunks(selectedDocumentId.value);
  } catch (error) {
    console.error('加载切块详情失败:', error);
    chunks.value = [];
  } finally {
    isLoadingChunks.value = false;
  }
};

const refreshSelectedVersions = async () => {
  if (!selectedDocument.value?.rootDocumentId) {
    versionHistory.value = [];
    return;
  }

  isLoadingVersions.value = true;
  try {
    const payload = await kbApi.listDocumentVersions(selectedDocument.value.rootDocumentId);
    versionHistory.value = payload.versions || [];
  } catch (error) {
    console.error('加载版本记录失败:', error);
    versionHistory.value = [];
  } finally {
    isLoadingVersions.value = false;
  }
};

const triggerUpload = () => {
  fileInput.value?.click();
};

const triggerVersionUpload = () => {
  if (!selectedDocument.value) {
    flash.error('请先选择一个文档后再上传新版本。');
    return;
  }
  versionFileInput.value?.click();
};

const handleFileChange = async (event) => {
  const file = event.target.files?.[0];
  if (!file) {
    return;
  }

  isUploading.value = true;
  try {
    const uploadResult = await kbApi.uploadDocument(file, {
      datasetId: selectedDatasetId.value,
    });
    if (uploadResult.document?.id) {
      selectedDocumentId.value = uploadResult.document.id;
      selectedDocumentDetail.value = uploadResult.document;
      activeTab.value = 'processing';
    }
    flash.success(
      selectedDatasetId.value !== 'all'
        ? `文件已上传到“${activeDataset.value?.name || '当前数据集'}”。请启动入库任务。`
        : '文件已上传。请启动入库任务，后台会异步完成解析、切块和向量化。',
    );
    await fetchDatasets();
    await fetchDocuments();
    await refreshSelectedDocument();
    await refreshSelectedVersions();
    await refreshSelectedChunks();
  } catch (error) {
    console.error('上传文档失败:', error);
    flash.error(`上传失败：${error.message || '未知错误'}`);
  } finally {
    isUploading.value = false;
    event.target.value = '';
  }
};

const handleVersionFileChange = async (event) => {
  const file = event.target.files?.[0];
  if (!file || !selectedDocument.value) {
    return;
  }

  isUploadingVersion.value = true;
  try {
    const result = await kbApi.uploadNewVersion(
      selectedDocument.value.rootDocumentId,
      file,
      {
        title: file.name,
        sourceLabel: file.name,
        sourceMetadata: {
          replaced_document_id: selectedDocument.value.id,
          dataset_id: selectedDocument.value.dataset?.id || null,
        },
      },
    );
    if (result.document?.id) {
      selectedDocumentId.value = result.document.id;
      selectedDocumentDetail.value = result.document;
      activeTab.value = 'versions';
    }
    flash.success(result.message || '新版本已上传。');
    await fetchDatasets();
    await fetchDocuments();
    await refreshSelectedDocument();
    await refreshSelectedVersions();
    await refreshSelectedChunks();
  } catch (error) {
    console.error('上传新版本失败:', error);
    flash.error(`上传新版本失败：${error.message || '未知错误'}`);
  } finally {
    isUploadingVersion.value = false;
    event.target.value = '';
  }
};

const startIngestionForDocument = async (documentId) => {
  if (!documentId || isSubmittingTask.value) {
    return;
  }

  isSubmittingTask.value = true;
  try {
    const ingestResult = await kbApi.ingestDocument(documentId);
    if (documentId === selectedDocumentId.value && ingestResult.document) {
      selectedDocumentDetail.value = ingestResult.document;
    }
    flash.success(ingestResult.message || '入库任务已提交。');
    await fetchDocuments();
    if (documentId === selectedDocumentId.value) {
      await refreshSelectedDocument();
      await refreshSelectedChunks();
    }
  } catch (error) {
    console.error('启动入库任务失败:', error);
    flash.error(`启动入库失败：${error.message || '未知错误'}`);
  } finally {
    isSubmittingTask.value = false;
  }
};

const selectDocument = async (item) => {
  if (!item?.id) {
    return;
  }

  selectedDocumentId.value = item.id;
  selectedDocumentDetail.value = item;
  activeTab.value = 'processing';
  expandedChunkIds.value = [];
  await refreshSelectedDocument();
  await refreshSelectedVersions();
  await refreshSelectedChunks();
};

const createDataset = async () => {
  if (!datasetForm.value.name.trim()) {
    flash.error('请输入数据集名称。');
    return;
  }

  isCreatingDataset.value = true;
  try {
    const dataset = await kbApi.createDataset(datasetForm.value);
    flash.success(`数据集“${dataset.name}”已创建。`);
    datasetForm.value = { name: '', description: '' };
    isDatasetComposerOpen.value = false;
    await fetchDatasets();
    selectedDatasetId.value = String(dataset.id);
    currentPage.value = 1;
    await fetchDocuments();
  } catch (error) {
    console.error('创建数据集失败:', error);
    flash.error(`创建数据集失败：${error.message || '未知错误'}`);
  } finally {
    isCreatingDataset.value = false;
  }
};

const openLink = (url) => {
  if (!url) {
    flash.error('当前文档没有可访问的文件链接。');
    return;
  }
  window.open(url, '_blank', 'noopener');
};

const handleRowAction = async ({ item, action }) => {
  if (action.id === 'retry') {
    await startIngestionForDocument(item.id);
    return;
  }

  if (action.id === 'view-error') {
    await selectDocument(item);
    activeTab.value = 'errors';
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
  if (checkedDocumentIds.value.length === 0) {
    return;
  }

  try {
    const payload = await kbApi.batchIngestDocuments(checkedDocumentIds.value);
    flash.success(summarizeBatchResult(payload, '批量重新入库'));
    await fetchDocuments();
    await refreshSelectedDocument();
  } catch (error) {
    console.error('批量入库失败:', error);
    flash.error(`批量入库失败：${error.message || '未知错误'}`);
  }
};

const handleBatchDelete = async () => {
  if (checkedDocumentIds.value.length === 0) {
    return;
  }

  try {
    const payload = await kbApi.batchDeleteDocuments(checkedDocumentIds.value);
    flash.success(summarizeBatchResult(payload, '批量删除'));
    const deletedIds = (payload.results || [])
      .filter((item) => item.status === 'deleted')
      .map((item) => item.document_id);
    checkedDocumentIds.value = buildSelectionAfterBatchDelete(checkedDocumentIds.value, deletedIds);
    if (deletedIds.includes(selectedDocumentId.value)) {
      selectedDocumentId.value = '';
      selectedDocumentDetail.value = null;
      chunks.value = [];
    }
    await fetchDocuments();
  } catch (error) {
    console.error('批量删除失败:', error);
    flash.error(`批量删除失败：${error.message || '未知错误'}`);
  }
};

const startPolling = () => {
  pollInterval = setInterval(async () => {
    if (activeProcessingCount.value === 0) {
      return;
    }
    try {
      await fetchDocuments();
      if (selectedDocumentId.value) {
        await refreshSelectedDocument();
        await refreshSelectedChunks();
      }
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
    <input ref="versionFileInput" type="file" hidden @change="handleVersionFileChange" />

    <section class="kb-overview">
      <div class="kb-overview__copy">
        <p class="eyebrow">{{ pageModeLabel }}</p>
        <h2>知识库管理</h2>
        <p class="kb-overview__text">
          以知识库、文档、向量入库状态为主线组织操作区，先看资产概况，再完成筛选、上传、入库与明细追踪。
        </p>
      </div>
      <div class="kb-overview__stats">
        <article
          v-for="card in summaryCards"
          :key="card.id"
          :class="['stat-card', `stat-card--${card.tone}`]"
        >
          <span class="stat-card__icon" aria-hidden="true"></span>
          <div>
            <span class="stat-label">{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
            <small>{{ card.delta }}</small>
          </div>
        </article>
      </div>
    </section>

    <div class="kb-command-grid">
      <main class="kb-command-grid__main">
        <section class="kb-ledger-panel">
          <div class="kb-tabs">
            <button class="kb-tab active" type="button">知识库列表</button>
            <button class="kb-tab" type="button">数据源管理</button>
          </div>

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
            :selected-document-id="selectedDocumentId"
            :is-loading="isLoading"
            :page="pagination.page"
            :total-pages="pagination.totalPages"
            :total="pagination.total"
            @select="selectDocument"
            @toggle-row="toggleRow"
            @toggle-all="toggleAll"
            @row-action="handleRowAction"
            @change-page="changePage"
          />
        </section>

        <section class="kb-detail-panel">
          <header class="kb-detail-panel__header">
            <div>
              <p class="eyebrow">Document inspector</p>
              <h3>文档详情与切块</h3>
            </div>
            <span>{{ selectedDocument ? selectedDocument.processStep.label : '未选择文档' }}</span>
          </header>
          <KnowledgeBaseDetailPanel
            :document="selectedDocument"
            :primary-action="selectedIngestionAction"
            :active-tab="activeTab"
            :task-hint-text="taskHintText"
            :is-submitting-task="isSubmittingTask"
            :versions="versionHistory"
            :is-loading-versions="isLoadingVersions"
            :is-uploading-version="isUploadingVersion"
            :chunks="chunks"
            :expanded-chunk-ids="expandedChunkIds"
            :is-loading-chunks="isLoadingChunks"
            :empty-state="emptyDetailState"
            @ingest="startIngestionForDocument(selectedDocument?.id)"
            @upload-version="triggerVersionUpload"
            @preview="isPreviewOpen = true"
            @open-original="openLink(selectedDocument?.originalUrl)"
            @change-tab="activeTab = $event"
            @toggle-chunk="expandedChunkIds = buildChunkExpansionState(expandedChunkIds, $event)"
          />
        </section>
      </main>

      <KnowledgeBaseMetricsRail
        v-if="showAdminMetrics"
        :documents="decoratedItems"
        :datasets="datasets"
        :total-documents="pagination.total"
        :active-count="activeProcessingCount"
        :indexed-count="indexedCount"
        :failed-count="failedCount"
      />
    </div>

    <KnowledgeBasePreviewModal
      v-model="isPreviewOpen"
      :preview-state="previewState"
    />
  </div>
</template>

<style scoped>
.kb-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-height: 0;
  color: var(--text-secondary);
}

.kb-overview,
.kb-dataset-composer,
.kb-batchbar,
.kb-ledger-panel,
.kb-detail-panel {
  border: 1px solid var(--line-soft);
  background: var(--surface-2);
  box-shadow: var(--shadow-md);
}

.kb-overview {
  padding: 22px;
  border-radius: 22px;
  background:
    linear-gradient(135deg, rgba(36, 87, 197, 0.1), transparent 34%),
    var(--surface-2);
}

.eyebrow {
  margin: 0 0 8px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--brand);
}

.kb-overview h2,
.kb-dataset-composer h3 {
  margin: 0;
  color: var(--text-primary);
  letter-spacing: -0.02em;
}

.kb-overview__text,
.kb-dataset-composer p {
  margin: 10px 0 0;
  color: var(--text-secondary);
  line-height: 1.75;
}

.kb-overview__stats {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
  margin-top: 18px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 104px;
  padding: 18px;
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: color-mix(in srgb, var(--surface-2) 88%, var(--brand-soft));
}

.stat-card__icon {
  width: 48px;
  height: 48px;
  flex: 0 0 auto;
  border-radius: 15px;
  background: linear-gradient(135deg, #2457c5, #7ca6f2);
  box-shadow: 0 16px 30px -24px rgba(36, 87, 197, 0.65);
}

.stat-card--violet .stat-card__icon {
  background: linear-gradient(135deg, #44318d, #7f63f4);
}

.stat-card--green .stat-card__icon {
  background: linear-gradient(135deg, #1f7a64, #58c896);
}

.stat-card--amber .stat-card__icon {
  background: linear-gradient(135deg, #8a5a20, #d99731);
}

.stat-card--purple .stat-card__icon {
  background: linear-gradient(135deg, #4b357e, #9a78f4);
}

.stat-label {
  display: block;
  color: var(--text-muted);
  font-size: 12px;
  margin-bottom: 6px;
}

.stat-card strong {
  display: block;
  color: var(--text-primary);
  font-size: clamp(20px, 2vw, 26px);
  line-height: 1.1;
}

.stat-card small {
  display: block;
  margin-top: 8px;
  color: var(--success);
  font-size: 12px;
}

.kb-command-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 18px;
  align-items: start;
  min-height: 0;
}

.kb-page--admin .kb-command-grid {
  grid-template-columns: minmax(0, 1fr) 286px;
}

.kb-command-grid__main {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-width: 0;
}

.kb-ledger-panel,
.kb-detail-panel {
  border-radius: 18px;
  overflow: hidden;
}

.kb-tabs {
  display: flex;
  align-items: flex-end;
  gap: 24px;
  min-height: 50px;
  padding: 0 18px;
  border-bottom: 1px solid var(--line-soft);
}

.kb-tab {
  height: 50px;
  border: 0;
  border-bottom: 3px solid transparent;
  background: transparent;
  color: var(--text-muted);
  font-weight: 700;
  cursor: pointer;
}

.kb-tab.active {
  border-bottom-color: var(--brand);
  color: var(--brand);
}

.kb-dataset-composer {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, 0.95fr);
  gap: 20px;
  margin: 0 18px 18px;
  padding: 18px;
  border-radius: 16px;
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
  font: inherit;
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
  padding: 14px 18px;
  margin: 0 18px 16px;
  border-radius: 14px;
}

.kb-batchbar span {
  color: var(--text-primary);
  font-weight: 700;
}

.kb-primary-btn,
.kb-secondary-btn,
.kb-danger-btn {
  min-height: 40px;
  padding: 0 16px;
  border-radius: 10px;
  font-weight: 700;
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

.kb-detail-panel {
  padding: 18px;
}

.kb-detail-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 14px;
}

.kb-detail-panel__header h3 {
  margin: 0;
  color: var(--text-primary);
}

.kb-detail-panel__header span {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 10px;
  border-radius: 999px;
  background: var(--brand-soft);
  color: var(--brand);
  font-size: 12px;
  font-weight: 700;
}

@media (max-width: 1180px) {
  .kb-page--admin .kb-command-grid,
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
