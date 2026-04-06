<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue';

import { kbApi } from '../api/knowledgebase.js';
import { useFlash } from '../lib/flash.js';

const items = ref([]);
const isLoading = ref(false);
const isUploading = ref(false);
const selectedDocumentId = ref('');
const selectedDocumentDetail = ref(null);
const isLoadingDetail = ref(false);
const searchKeyword = ref('');
const fileInput = ref(null);
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

const filteredItems = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase();
  if (!keyword) {
    return items.value;
  }
  return items.value.filter((item) =>
    [
      item.title,
      item.filename,
      item.uploaderName,
      item.processResult,
      item.processStep?.label,
    ].some((value) => String(value || '').toLowerCase().includes(keyword)),
  );
});

const selectedDocument = computed(() => {
  if (selectedDocumentDetail.value?.id === selectedDocumentId.value) {
    return selectedDocumentDetail.value;
  }
  return items.value.find((item) => item.id === selectedDocumentId.value) || null;
});

const activeProcessingCount = computed(() =>
  items.value.filter((item) => kbApi.isProcessingStatus(item.status)).length,
);

const indexedCount = computed(() =>
  items.value.filter((item) => item.isSearchReady).length,
);

const failedCount = computed(() =>
  items.value.filter((item) => item.status === 'failed').length,
);

const keepSelectionFresh = () => {
  if (!selectedDocumentId.value) {
    selectedDocumentId.value = items.value[0]?.id || '';
    return;
  }
  if (!items.value.some((item) => item.id === selectedDocumentId.value)) {
    selectedDocumentId.value = items.value[0]?.id || '';
    selectedDocumentDetail.value = null;
  }
};

const fetchDocuments = async () => {
  isLoading.value = true;
  try {
    items.value = await kbApi.listDocuments();
    keepSelectionFresh();
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
    selectedDocumentDetail.value =
      items.value.find((item) => item.id === selectedDocumentId.value) || null;
  } finally {
    isLoadingDetail.value = false;
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
    }
    flash.success('文件已上传，正在创建入库任务。');

    if (uploadResult.document?.id) {
      const ingestResult = await kbApi.ingestDocument(uploadResult.document.id);
      if (ingestResult.document) {
        selectedDocumentDetail.value = ingestResult.document;
      }
      flash.success(ingestResult.message || '入库任务已提交。');
    }

    await fetchDocuments();
    await refreshSelectedDocument();
  } catch (error) {
    console.error('上传文档失败:', error);
    flash.error(`上传失败：${error.message || '未知错误'}`);
  } finally {
    isUploading.value = false;
    event.target.value = '';
  }
};

const selectDocument = async (item) => {
  if (!item?.id || item.id === selectedDocumentId.value) {
    return;
  }
  selectedDocumentId.value = item.id;
  selectedDocumentDetail.value = item;
  await refreshSelectedDocument();
};

const openLink = (url) => {
  if (!url) {
    flash.error('当前文档没有可访问的文件链接。');
    return;
  }
  window.open(url, '_blank', 'noopener');
};

const startPolling = () => {
  pollInterval = setInterval(async () => {
    if (activeProcessingCount.value === 0) {
      return;
    }
    try {
      items.value = await kbApi.listDocuments();
      keepSelectionFresh();
      if (selectedDocumentId.value) {
        const freshSelected = items.value.find((item) => item.id === selectedDocumentId.value);
        if (freshSelected) {
          selectedDocumentDetail.value = {
            ...(selectedDocumentDetail.value || {}),
            ...freshSelected,
          };
        }
      }
    } catch (error) {
      console.error('轮询知识库失败:', error);
    }
  }, 3000);
};

onMounted(async () => {
  await fetchDocuments();
  await refreshSelectedDocument();
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
        <h2>上传、处理、入库三段状态分离展示</h2>
        <p class="kb-overview__text">
          只有文档完成切块并写入 Milvus 后，状态才会变为“已入库”，此时才能参与问答检索。
        </p>
      </div>
      <div class="kb-overview__stats">
        <div class="stat-card">
          <span class="stat-label">文档总数</span>
          <strong>{{ items.length }}</strong>
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

    <section class="kb-toolbar ui-card">
      <input
        v-model="searchKeyword"
        class="kb-search"
        type="text"
        placeholder="搜索文档名、上传者、处理状态"
      />
      <input ref="fileInput" type="file" hidden @change="handleFileChange" />
      <button class="kb-primary-btn" :disabled="isUploading" @click="triggerUpload">
        {{ isUploading ? '上传中...' : '上传文档' }}
      </button>
    </section>

    <section class="kb-layout">
      <div class="kb-list ui-card">
        <div class="kb-list__header">
          <span>文档</span>
          <span>上传者</span>
          <span>当前状态</span>
          <span>上传时间</span>
        </div>

        <div v-if="isLoading && items.length === 0" class="kb-empty">正在加载知识库...</div>
        <div v-else-if="filteredItems.length === 0" class="kb-empty">当前没有符合条件的文档。</div>

        <button
          v-for="item in filteredItems"
          :key="item.id"
          type="button"
          :class="['kb-row', { active: item.id === selectedDocumentId }]"
          @click="selectDocument(item)"
        >
          <div class="kb-row__title">
            <strong>{{ item.title }}</strong>
            <span>{{ item.filename }}</span>
          </div>
          <div>{{ item.uploaderName }}</div>
          <div class="kb-row__status">
            <span :class="['status-chip', `tone-${statusTone[item.processStep.code] || 'neutral'}`]">
              {{ item.processStep.label }}
            </span>
            <small>{{ item.processResult }}</small>
          </div>
          <div>{{ item.uploadTime }}</div>
        </button>
      </div>

      <div class="kb-detail ui-card">
        <template v-if="selectedDocument">
          <div class="kb-detail__header">
            <div>
              <p class="eyebrow">文档详情</p>
              <h3>{{ selectedDocument.title }}</h3>
              <p class="kb-detail__summary">{{ selectedDocument.processResult }}</p>
            </div>
            <span :class="['status-chip', `tone-${statusTone[selectedDocument.processStep.code] || 'neutral'}`]">
              {{ selectedDocument.processStep.label }}
            </span>
          </div>

          <div class="kb-progress">
            <div class="kb-progress__meta">
              <span>处理进度</span>
              <span>{{ selectedDocument.processStep.progress }}%</span>
            </div>
            <div class="kb-progress__track">
              <div class="kb-progress__value" :style="{ width: `${selectedDocument.processStep.progress}%` }" />
            </div>
          </div>

          <div class="kb-meta-grid">
            <div class="meta-card">
              <span>上传者</span>
              <strong>{{ selectedDocument.uploaderName }}</strong>
            </div>
            <div class="meta-card">
              <span>归属人</span>
              <strong>{{ selectedDocument.ownerName }}</strong>
            </div>
            <div class="meta-card">
              <span>上传时间</span>
              <strong>{{ selectedDocument.uploadTime }}</strong>
            </div>
            <div class="meta-card">
              <span>更新时间</span>
              <strong>{{ selectedDocument.updateTime }}</strong>
            </div>
            <div class="meta-card">
              <span>切块数量</span>
              <strong>{{ selectedDocument.chunkCount }}</strong>
            </div>
            <div class="meta-card">
              <span>向量数量</span>
              <strong>{{ selectedDocument.vectorCount }}</strong>
            </div>
          </div>

          <div class="kb-task-card">
            <div class="section-head">
              <h4>处理任务</h4>
              <span v-if="selectedDocument.isSearchReady" class="task-ready">可检索</span>
            </div>
            <div class="task-grid">
              <div>
                <span class="meta-label">任务状态</span>
                <strong>{{ selectedDocument.latestTask?.status || '未创建' }}</strong>
              </div>
              <div>
                <span class="meta-label">当前步骤</span>
                <strong>{{ selectedDocument.latestTask?.current_step || '未开始' }}</strong>
              </div>
              <div>
                <span class="meta-label">开始时间</span>
                <strong>{{ selectedDocument.latestTask?.startedAtText || 'N/A' }}</strong>
              </div>
              <div>
                <span class="meta-label">完成时间</span>
                <strong>{{ selectedDocument.latestTask?.finishedAtText || 'N/A' }}</strong>
              </div>
            </div>
            <p v-if="selectedDocument.processError" class="task-error">{{ selectedDocument.processError }}</p>
          </div>

          <div class="kb-actions">
            <button class="kb-secondary-btn" @click="openLink(selectedDocument.previewUrl)">查看预览</button>
            <button class="kb-secondary-btn" @click="openLink(selectedDocument.originalUrl)">查看原文</button>
          </div>

          <div class="kb-preview-card">
            <div class="section-head">
              <h4>抽取文本</h4>
              <span v-if="isLoadingDetail">刷新中...</span>
            </div>
            <pre>{{ selectedDocument.extractedText || selectedDocument.parsedTextPreview || '当前暂无抽取文本。' }}</pre>
          </div>
        </template>

        <div v-else class="kb-empty">请选择左侧文档查看详情。</div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.kb-page {
  gap: 18px;
}

.kb-overview,
.kb-toolbar,
.kb-list,
.kb-detail {
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

.kb-overview h2,
.kb-detail h3 {
  margin: 0;
  color: #142033;
}

.kb-overview__text,
.kb-detail__summary {
  margin: 10px 0 0;
  color: #5a677d;
  line-height: 1.7;
}

.kb-overview__stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.stat-card,
.meta-card {
  border: 1px solid rgba(20, 32, 51, 0.08);
  border-radius: 18px;
  padding: 16px;
  background: #f7f9fc;
}

.stat-label,
.meta-card span,
.meta-label {
  display: block;
  color: #6b7b93;
  font-size: 12px;
  margin-bottom: 6px;
}

.stat-card strong,
.meta-card strong,
.task-grid strong {
  color: #142033;
  font-size: 20px;
}

.kb-toolbar {
  display: flex;
  gap: 16px;
  padding: 18px 22px;
}

.kb-search {
  flex: 1;
  height: 44px;
  border: 1px solid rgba(20, 32, 51, 0.12);
  border-radius: 14px;
  padding: 0 14px;
  background: #fff;
  color: #142033;
}

.kb-primary-btn,
.kb-secondary-btn {
  height: 44px;
  border-radius: 14px;
  padding: 0 18px;
  font-weight: 700;
  cursor: pointer;
}

.kb-primary-btn {
  border: none;
  background: #2457c5;
  color: #fff;
}

.kb-primary-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.kb-secondary-btn {
  border: 1px solid rgba(20, 32, 51, 0.12);
  background: #fff;
  color: #142033;
}

.kb-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(360px, 0.95fr);
  gap: 18px;
}

.kb-list {
  overflow: hidden;
}

.kb-list__header,
.kb-row {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) 120px minmax(0, 1.2fr) 140px;
  gap: 12px;
  align-items: center;
  padding: 16px 18px;
}

.kb-list__header {
  border-bottom: 1px solid rgba(20, 32, 51, 0.08);
  background: #f7f9fc;
  color: #6b7b93;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.kb-row {
  width: 100%;
  border: none;
  border-bottom: 1px solid rgba(20, 32, 51, 0.06);
  background: #fff;
  text-align: left;
  cursor: pointer;
}

.kb-row:hover,
.kb-row.active {
  background: #f4f7fb;
}

.kb-row__title,
.kb-row__status {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.kb-row__title strong,
.kb-row__status small,
.kb-task-card h4 {
  color: #142033;
}

.kb-row__title span,
.kb-row__status small,
.kb-empty,
.task-error,
.kb-preview-card pre {
  color: #5a677d;
}

.status-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 72px;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.tone-neutral {
  background: #eef2f7;
  color: #516176;
}

.tone-accent {
  background: #e6eefb;
  color: #2457c5;
}

.tone-success {
  background: #e8f7ef;
  color: #0e7a43;
}

.tone-danger {
  background: #fdecec;
  color: #b42318;
}

.kb-detail {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 22px;
}

.kb-detail__header,
.section-head,
.kb-progress__meta,
.kb-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.kb-progress__track {
  margin-top: 10px;
  height: 10px;
  border-radius: 999px;
  background: #edf2f8;
  overflow: hidden;
}

.kb-progress__value {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #2457c5, #4a79d8);
}

.kb-meta-grid,
.task-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.kb-task-card,
.kb-preview-card {
  border: 1px solid rgba(20, 32, 51, 0.08);
  border-radius: 18px;
  padding: 16px;
  background: #f7f9fc;
}

.task-ready {
  color: #0e7a43;
  font-size: 12px;
  font-weight: 700;
}

.task-error {
  margin: 12px 0 0;
  color: #b42318;
}

.kb-preview-card pre {
  margin: 12px 0 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  line-height: 1.7;
}

.kb-empty {
  padding: 48px 20px;
  text-align: center;
}

@media (max-width: 1100px) {
  .kb-overview,
  .kb-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .kb-toolbar {
    flex-direction: column;
  }

  .kb-list__header,
  .kb-row {
    grid-template-columns: 1fr;
  }

  .kb-meta-grid,
  .task-grid,
  .kb-overview__stats {
    grid-template-columns: 1fr;
  }
}
</style>
