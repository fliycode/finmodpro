<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';

import { kbApi } from '../api/knowledgebase.js';
import KnowledgeBaseDetailPanel from './knowledgebase/KnowledgeBaseDetailPanel.vue';
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
  <div class="kb-page page-stack">
    <section class="kb-overview ui-card">
      <div class="kb-overview__copy">
        <p class="eyebrow">知识库总览</p>
        <h2>文档处理状态监控</h2>
        <p class="kb-overview__text">
          聚焦上传、处理、入库全流程；文档完成切块并写入 Milvus 后，才会进入“已入库”并可参与检索。
        </p>
      </div>
      <div class="kb-overview__stats">
        <div class="stat-card">
          <span class="stat-label">文档总数</span>
          <strong>{{ pagination.total }}</strong>
        </div>
        <div class="stat-card">
          <span class="stat-label">处理中</span>
          <strong>{{ activeProcessingCount }}</strong>
        </div>
        <div class="stat-card">
          <span class="stat-label">已入库</span>
          <strong>{{ indexedCount }}</strong>
        </div>
        <div class="stat-card">
          <span class="stat-label">失败</span>
          <strong>{{ failedCount }}</strong>
        </div>
        <div class="stat-card">
          <span class="stat-label">数据集</span>
          <strong>{{ datasets.length }}</strong>
        </div>
      </div>
    </section>

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

    <section v-if="isDatasetComposerOpen" class="kb-dataset-composer ui-card">
      <div class="kb-dataset-composer__copy">
        <p class="eyebrow">数据集管理</p>
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

    <div v-if="checkedDocumentIds.length > 0" class="kb-batchbar ui-card">
      <span>已选择 {{ checkedDocumentIds.length }} 个文档</span>
      <div class="kb-batchbar__actions">
        <button class="kb-secondary-btn" @click="handleBatchIngest">批量重新入库</button>
        <button class="kb-danger-btn" @click="handleBatchDelete">批量删除</button>
      </div>
    </div>

    <input ref="fileInput" type="file" hidden @change="handleFileChange" />
    <input ref="versionFileInput" type="file" hidden @change="handleVersionFileChange" />

    <section class="kb-layout">
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

    <KnowledgeBasePreviewModal
      v-model="isPreviewOpen"
      :preview-state="previewState"
    />
  </div>
</template>

<style scoped>
.kb-page {
  gap: 18px;
}

.kb-overview,
.kb-batchbar {
  background: #fff;
}

.kb-overview {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(340px, 0.9fr);
  gap: 24px;
  padding: 28px;
}

.eyebrow {
  margin: 0 0 8px;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #6b7b93;
}

.kb-overview h2 {
  margin: 0;
  color: #142033;
}

.kb-overview__text {
  margin: 10px 0 0;
  color: #5a677d;
  line-height: 1.7;
}

.kb-overview__stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.stat-card {
  border: 1px solid rgba(20, 32, 51, 0.08);
  border-radius: 18px;
  padding: 16px;
  background: #f7f9fc;
}

.stat-label {
  display: block;
  color: #6b7b93;
  font-size: 12px;
  margin-bottom: 6px;
}

.stat-card strong {
  color: #142033;
  font-size: 20px;
}

.kb-batchbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 18px;
}

.kb-batchbar__actions {
  display: flex;
  gap: 10px;
}

.kb-dataset-composer {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, 0.9fr);
  gap: 20px;
  padding: 22px;
  background: #fff;
}

.kb-dataset-composer h3 {
  margin: 0 0 8px;
  color: #142033;
}

.kb-dataset-composer p {
  margin: 0;
  color: #5a677d;
  line-height: 1.7;
}

.kb-dataset-composer__form {
  display: grid;
  gap: 12px;
}

.kb-textarea {
  border: 1px solid rgba(20, 32, 51, 0.12);
  border-radius: 14px;
  padding: 12px 14px;
  font: inherit;
  color: #142033;
  resize: vertical;
}

.kb-dataset-composer__actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.kb-secondary-btn,
.kb-danger-btn {
  height: 40px;
  border-radius: 12px;
  padding: 0 16px;
  font-weight: 700;
  cursor: pointer;
}

.kb-secondary-btn {
  border: 1px solid rgba(20, 32, 51, 0.12);
  background: #fff;
  color: #142033;
}

.kb-danger-btn {
  border: 1px solid rgba(181, 58, 58, 0.18);
  background: rgba(181, 58, 58, 0.08);
  color: #9b3131;
}

.kb-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(380px, 0.95fr);
  gap: 18px;
  align-items: start;
}

@media (max-width: 1080px) {
  .kb-overview,
  .kb-layout,
  .kb-batchbar,
  .kb-dataset-composer {
    grid-template-columns: 1fr;
  }

  .kb-batchbar {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
