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
const isSubmittingTask = ref(false);
const selectedDocumentId = ref('');
const selectedDocumentDetail = ref(null);
const isLoadingDetail = ref(false);
const searchKeyword = ref('');
const statusFilter = ref('all');
const timeRange = ref('all');
const checkedDocumentIds = ref([]);
const fileInput = ref(null);
const currentPage = ref(1);
const pagination = ref({ total: 0, page: 1, pageSize: 10, totalPages: 0 });
const isPreviewOpen = ref(false);
const activeTab = ref('processing');
const chunks = ref([]);
const isLoadingChunks = ref(false);
const expandedChunkIds = ref([]);
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

const taskHintText = computed(() => {
  if (isIngestionInFlight(selectedDocument.value)) {
    return '任务已启动，后台正在执行解析、切块和向量写入，完成后列表与详情会自动刷新。';
  }

  return `上传只保存原始文件；点击“${selectedIngestionAction.value?.label || '启动入库'}”后，后台才会异步完成解析、切块和写入向量库。`;
});

const syncSelectionWithPage = () => {
  if (!selectedDocumentId.value) {
    selectedDocumentDetail.value = null;
    return;
  }

  if (!items.value.some((item) => item.id === selectedDocumentId.value)) {
    selectedDocumentId.value = '';
    selectedDocumentDetail.value = null;
    chunks.value = [];
    expandedChunkIds.value = [];
  }
};

const fetchDocuments = async () => {
  isLoading.value = true;
  try {
    const result = await kbApi.listDocuments({
      searchKeyword: searchKeyword.value,
      statusFilter: statusFilter.value,
      timeRange: timeRange.value,
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

const triggerUpload = () => {
  fileInput.value?.click();
};

const handleFileChange = async (event) => {
  const file = event.target.files?.[0];
  if (!file) {
    return;
  }

  isUploading.value = true;
  try {
    const uploadResult = await kbApi.uploadDocument(file);
    if (uploadResult.document?.id) {
      selectedDocumentId.value = uploadResult.document.id;
      selectedDocumentDetail.value = uploadResult.document;
      activeTab.value = 'processing';
    }
    flash.success('文件已上传。请启动入库任务，后台会异步完成解析、切块和向量化。');
    await fetchDocuments();
    await refreshSelectedDocument();
    await refreshSelectedChunks();
  } catch (error) {
    console.error('上传文档失败:', error);
    flash.error(`上传失败：${error.message || '未知错误'}`);
  } finally {
    isUploading.value = false;
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
  await refreshSelectedChunks();
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

watch([searchKeyword, statusFilter, timeRange], async () => {
  currentPage.value = 1;
  await fetchDocuments();
});

onMounted(async () => {
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
      </div>
    </section>

    <KnowledgeBaseToolbar
      :search-keyword="searchKeyword"
      :status-filter="statusFilter"
      :time-range="timeRange"
      :is-uploading="isUploading"
      @update:search-keyword="searchKeyword = $event"
      @update:status-filter="statusFilter = $event"
      @update:time-range="timeRange = $event"
      @upload="triggerUpload"
    />

    <div v-if="checkedDocumentIds.length > 0" class="kb-batchbar ui-card">
      <span>已选择 {{ checkedDocumentIds.length }} 个文档</span>
      <div class="kb-batchbar__actions">
        <button class="kb-secondary-btn" @click="handleBatchIngest">批量重新入库</button>
        <button class="kb-danger-btn" @click="handleBatchDelete">批量删除</button>
      </div>
    </div>

    <input ref="fileInput" type="file" hidden @change="handleFileChange" />

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
        :chunks="chunks"
        :expanded-chunk-ids="expandedChunkIds"
        :is-loading-chunks="isLoadingChunks"
        :empty-state="emptyDetailState"
        @ingest="startIngestionForDocument(selectedDocument?.id)"
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
  grid-template-columns: repeat(2, minmax(0, 1fr));
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
  .kb-batchbar {
    grid-template-columns: 1fr;
  }

  .kb-batchbar {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
