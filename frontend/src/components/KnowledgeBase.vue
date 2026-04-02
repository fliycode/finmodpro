<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { kbApi } from "../api/knowledgebase.js";
import { useFlash } from "../lib/flash.js";

const items = ref([]);
const isLoading = ref(false);
const fileInput = ref(null);
const isUploading = ref(false);
const selectedDocumentId = ref("");
const selectedDocumentDetail = ref(null);
const isLoadingDetail = ref(false);
const searchKeyword = ref("");
const flash = useFlash();

let pollInterval = null;

const getStatusColor = (status) => {
  const colors = {
    uploaded: '#3b82f6',
    parsed: '#8b5cf6',
    chunked: '#f59e0b',
    indexed: '#10b981',
    failed: '#ef4444',
  };
  return colors[status] || '#64748b';
};

const getStatusText = (status) => {
  const texts = {
    uploaded: '已上传',
    parsed: '解析中',
    chunked: '切块中',
    indexed: '已索引',
    failed: '处理失败',
  };
  return texts[status] || status;
};

const filteredItems = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase();
  if (!keyword) {
    return items.value;
  }

  return items.value.filter((item) => {
    return [item.name, item.uploader, item.processResult, item.processStep?.label]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(keyword));
  });
});

const selectedDocument = computed(() => {
  if (selectedDocumentDetail.value) {
    return selectedDocumentDetail.value;
  }

  return items.value.find((item) => item.id === selectedDocumentId.value) || null;
});

const refreshSelectedDocument = async () => {
  if (!selectedDocumentId.value) {
    selectedDocumentDetail.value = null;
    return;
  }

  isLoadingDetail.value = true;
  try {
    selectedDocumentDetail.value = await kbApi.getDocumentDetail(selectedDocumentId.value);
  } catch (error) {
    console.error('Failed to fetch document detail:', error);
    selectedDocumentDetail.value = items.value.find((item) => item.id === selectedDocumentId.value) || null;
  } finally {
    isLoadingDetail.value = false;
  }
};

const keepSelectionFresh = () => {
  if (!selectedDocumentId.value) {
    return;
  }

  const stillExists = items.value.some((item) => item.id === selectedDocumentId.value);
  if (!stillExists) {
    selectedDocumentId.value = items.value[0]?.id || '';
    selectedDocumentDetail.value = null;
    return;
  }

  if (!selectedDocumentDetail.value) {
    selectedDocumentDetail.value = items.value.find((item) => item.id === selectedDocumentId.value) || null;
  }
};

const fetchDocuments = async () => {
  isLoading.value = true;
  try {
    items.value = await kbApi.listDocuments();
    if (!selectedDocumentId.value && items.value.length > 0) {
      selectedDocumentId.value = items.value[0].id;
    }
    keepSelectionFresh();
  } catch (error) {
    console.error("Failed to fetch documents:", error);
    flash.error(`加载文档失败：${error.message || '未知错误'}`);
  } finally {
    isLoading.value = false;
  }
};

const triggerUpload = () => {
  fileInput.value?.click();
};

const handleFileChange = async (event) => {
  const file = event.target.files[0];
  if (!file) return;

  isUploading.value = true;
  try {
    const res = await kbApi.uploadDocument(file);
    if (res.success && res.document?.id) {
      selectedDocumentId.value = res.document.id;
      selectedDocumentDetail.value = res.document;
      flash.success('文档已上传，已创建处理任务。');
      try {
        const ingestResult = await kbApi.ingestDocument(res.document.id);
        const taskMessage = ingestResult?.message || ingestResult?.task_id || '后台处理中';
        flash.success(`处理任务已启动：${taskMessage}`);
      } catch (ingestError) {
        console.error('Ingest failed:', ingestError);
        flash.error(`文档已上传，但触发处理任务失败：${ingestError.message || '未知错误'}`);
      }
    }
    await fetchDocuments();
    await refreshSelectedDocument();
  } catch (error) {
    console.error('Upload failed:', error);
    flash.error(`上传失败：${error.message || '未知错误'}`);
  } finally {
    isUploading.value = false;
    event.target.value = '';
  }
};

const selectDocument = async (item) => {
  if (!item?.id) {
    return;
  }

  selectedDocumentId.value = item.id;
  selectedDocumentDetail.value = item;
  await refreshSelectedDocument();
};

const openLink = (url) => {
  if (!url) {
    flash.error('后端暂未返回可访问链接。');
    return;
  }

  window.open(url, '_blank', 'noopener');
};

const startPolling = () => {
  pollInterval = setInterval(async () => {
    const hasActiveItems = items.value.some((item) => kbApi.isProcessingStatus(item.status));
    if (!hasActiveItems) {
      return;
    }

    try {
      const updatedItems = await kbApi.listDocuments();
      items.value = updatedItems;
      keepSelectionFresh();
      if (selectedDocumentId.value) {
        const current = updatedItems.find((item) => item.id === selectedDocumentId.value);
        if (current && kbApi.isProcessingStatus(current.status)) {
          selectedDocumentDetail.value = current;
        }
      }
    } catch (error) {
      console.error('Polling documents failed:', error);
    }
  }, 3000);
};

onMounted(async () => {
  await fetchDocuments();
  if (selectedDocumentId.value) {
    await refreshSelectedDocument();
  }
  startPolling();
});

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval);
});
</script>

<template>
  <div class="knowledge-base-shell">
    <div class="toolbar">
      <input v-model="searchKeyword" type="text" placeholder="搜索文档名、上传者、处理状态..." class="search-input" />
      <input type="file" ref="fileInput" style="display: none" @change="handleFileChange" />
      <button class="primary-btn" @click="triggerUpload" :disabled="isUploading">
        <span v-if="isUploading" class="loader-small"></span>
        {{ isUploading ? '上传中...' : '上传文档' }}
      </button>
    </div>

    <div class="content-area">
      <div v-if="isLoading && items.length === 0" class="state-msg">加载中...</div>

      <div v-else-if="items.length === 0" class="state-msg empty">
        <div class="empty-icon">📁</div>
        <p>暂无文档。请点击上方按钮上传文档。</p>
      </div>

      <div v-else class="knowledge-layout">
        <div class="doc-list-panel">
          <div class="doc-list-header">
            <div class="col-name">文档名称</div>
            <div class="col-owner">上传者/归属</div>
            <div class="col-status">处理任务</div>
            <div class="col-time">上传时间</div>
          </div>
          <button
            v-for="item in filteredItems"
            :key="item.id"
            type="button"
            class="doc-list-item"
            :class="{ active: item.id === selectedDocumentId }"
            @click="selectDocument(item)"
          >
            <div class="col-name name-cell">
              <svg class="file-icon" viewBox="0 0 24 24" fill="none"><path d="M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9l-7-7z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M13 2v7h7" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
              <div class="name-stack">
                <span class="file-name-text">{{ item.name }}</span>
                <span class="file-meta">{{ item.size }} · {{ item.sourceType }}</span>
              </div>
            </div>
            <div class="col-owner owner-cell">
              <span class="owner-name">{{ item.uploader }}</span>
            </div>
            <div class="col-status status-cell">
              <span class="status-badge" :style="{ backgroundColor: getStatusColor(item.status) + '1A', color: getStatusColor(item.status), border: `1px solid ${getStatusColor(item.status)}40` }">
                <span class="status-dot" :style="{ backgroundColor: getStatusColor(item.status) }"></span>
                {{ getStatusText(item.status) }}
              </span>
              <span class="status-detail">{{ item.processResult }}</span>
            </div>
            <div class="col-time">{{ item.uploadTime }}</div>
          </button>
          <div v-if="filteredItems.length === 0" class="inline-empty">没有匹配的文档。</div>
        </div>

        <div class="detail-panel">
          <div v-if="selectedDocument" class="detail-card">
            <div class="detail-header">
              <div>
                <h3>{{ selectedDocument.name }}</h3>
                <p>{{ selectedDocument.processStep?.detail || selectedDocument.processResult }}</p>
              </div>
              <span class="status-badge large" :style="{ backgroundColor: getStatusColor(selectedDocument.status) + '1A', color: getStatusColor(selectedDocument.status), border: `1px solid ${getStatusColor(selectedDocument.status)}40` }">
                <span class="status-dot" :style="{ backgroundColor: getStatusColor(selectedDocument.status) }"></span>
                {{ getStatusText(selectedDocument.status) }}
              </span>
            </div>

            <div class="progress-card">
              <div class="progress-header">
                <span>处理任务状态</span>
                <span>{{ selectedDocument.processStep?.progress || 0 }}%</span>
              </div>
              <div class="progress-bar">
                <div class="progress-value" :style="{ width: `${selectedDocument.processStep?.progress || 0}%`, backgroundColor: getStatusColor(selectedDocument.status) }"></div>
              </div>
              <p class="progress-detail">{{ selectedDocument.processResult }}</p>
            </div>

            <div class="meta-grid">
              <div class="meta-item">
                <span class="meta-label">上传者 / 归属</span>
                <span class="meta-value">{{ selectedDocument.uploader }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">上传时间</span>
                <span class="meta-value">{{ selectedDocument.uploadTime }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">文档大小</span>
                <span class="meta-value">{{ selectedDocument.size }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">切块数量</span>
                <span class="meta-value">{{ selectedDocument.chunkCount ?? '后端未返回' }}</span>
              </div>
            </div>

            <div class="action-row">
              <button type="button" class="secondary-btn" @click="openLink(selectedDocument.previewUrl)">查看预览</button>
              <button type="button" class="secondary-btn" @click="openLink(selectedDocument.originalUrl)">查看原文</button>
            </div>

            <div class="section-card">
              <div class="section-title">处理结果</div>
              <div class="section-content">{{ selectedDocument.processResult || '后端暂未返回处理结果。' }}</div>
            </div>

            <div class="section-card">
              <div class="section-title">文档详情 / 原文摘录</div>
              <pre class="preview-box">{{ selectedDocument.extractedText || '后端暂未返回正文或预览内容。' }}</pre>
            </div>

            <div v-if="isLoadingDetail" class="detail-loading">正在刷新详情...</div>
          </div>

          <div v-else class="state-msg detail-empty">
            <p>请选择左侧文档查看详情。</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.knowledge-base-shell { background: white; border-radius: 12px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); min-height: 500px; display: flex; flex-direction: column; }
.toolbar { display: flex; gap: 16px; margin-bottom: 24px; }
.search-input { flex: 1; padding: 10px 16px; border: 1px solid #e2e8f0; border-radius: 8px; outline: none; transition: border-color 0.2s; font-family: inherit; }
.search-input:focus { border-color: #6366f1; }
.primary-btn { padding: 0 24px; height: 42px; background: #6366f1; color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; transition: background 0.2s; display: flex; align-items: center; justify-content: center; gap: 8px; white-space: nowrap; }
.primary-btn:hover:not(:disabled) { background: #4f46e5; }
.primary-btn:disabled { opacity: 0.7; cursor: not-allowed; }
.secondary-btn { padding: 0 16px; height: 38px; background: white; color: #334155; border: 1px solid #cbd5e1; border-radius: 8px; cursor: pointer; font-weight: 600; }
.secondary-btn:hover { background: #f8fafc; }
.loader-small { width: 14px; height: 14px; border: 2px solid #ffffff; border-bottom-color: transparent; border-radius: 50%; display: inline-block; animation: rotation 1s linear infinite; }
@keyframes rotation { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
.content-area { flex: 1; display: flex; flex-direction: column; }
.state-msg { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 48px; text-align: center; color: #94a3b8; border: 2px dashed #e2e8f0; border-radius: 8px; background: #f8fafc; }
.empty-icon { font-size: 48px; margin-bottom: 16px; opacity: 0.5; }
.knowledge-layout { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(320px, 0.9fr); gap: 20px; min-height: 540px; }
.doc-list-panel, .detail-panel { min-width: 0; }
.doc-list-panel { display: flex; flex-direction: column; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; background: #fff; }
.doc-list-header { display: grid; grid-template-columns: minmax(0, 2fr) 160px minmax(180px, 1.4fr) 160px; gap: 12px; background: #f8fafc; padding: 12px 16px; font-weight: 600; color: #475569; font-size: 13px; border-bottom: 1px solid #e2e8f0; }
.doc-list-item { display: grid; grid-template-columns: minmax(0, 2fr) 160px minmax(180px, 1.4fr) 160px; gap: 12px; width: 100%; padding: 16px; align-items: center; border: none; border-bottom: 1px solid #f1f5f9; background: white; text-align: left; transition: background 0.2s, box-shadow 0.2s; cursor: pointer; }
.doc-list-item:last-of-type { border-bottom: none; }
.doc-list-item:hover { background: #f8fafc; }
.doc-list-item.active { background: #eef2ff; box-shadow: inset 3px 0 0 #6366f1; }
.name-cell { display: flex; align-items: center; gap: 12px; min-width: 0; }
.name-stack { display: flex; flex-direction: column; min-width: 0; gap: 4px; }
.file-icon { width: 20px; height: 20px; color: #94a3b8; flex-shrink: 0; }
.file-name-text { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: #1e293b; font-weight: 600; }
.file-meta, .status-detail, .detail-header p, .progress-detail, .meta-label, .detail-loading, .inline-empty { color: #64748b; font-size: 13px; }
.owner-cell, .col-time { color: #475569; font-size: 13px; }
.status-cell { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.status-badge { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 9999px; font-size: 12px; font-weight: 600; white-space: nowrap; width: fit-content; }
.status-badge.large { font-size: 13px; padding: 6px 12px; }
.status-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.inline-empty { padding: 24px 16px; }
.detail-card { border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; background: #fff; display: flex; flex-direction: column; gap: 16px; min-height: 100%; }
.detail-header { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.detail-header h3 { margin: 0 0 8px; font-size: 20px; color: #0f172a; }
.detail-header p { margin: 0; }
.progress-card, .section-card { border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px 16px; background: #f8fafc; }
.progress-header { display: flex; justify-content: space-between; margin-bottom: 10px; color: #334155; font-weight: 600; font-size: 13px; }
.progress-bar { height: 8px; border-radius: 9999px; background: #e2e8f0; overflow: hidden; }
.progress-value { height: 100%; border-radius: inherit; transition: width 0.2s ease; }
.meta-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.meta-item { border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px 14px; background: white; display: flex; flex-direction: column; gap: 6px; }
.meta-value { color: #0f172a; font-weight: 600; }
.action-row { display: flex; gap: 12px; flex-wrap: wrap; }
.section-title { font-size: 13px; font-weight: 700; color: #334155; margin-bottom: 8px; }
.section-content { color: #1e293b; line-height: 1.6; }
.preview-box { margin: 0; padding: 12px; border-radius: 8px; background: white; border: 1px solid #e2e8f0; color: #334155; font-family: inherit; white-space: pre-wrap; word-break: break-word; max-height: 280px; overflow: auto; }
.detail-empty { min-height: 100%; }
@media (max-width: 1200px) {
  .knowledge-layout { grid-template-columns: 1fr; }
}
@media (max-width: 900px) {
  .doc-list-header, .doc-list-item { grid-template-columns: minmax(0, 1.4fr) 120px minmax(150px, 1fr); }
  .col-time { display: none; }
  .meta-grid { grid-template-columns: 1fr; }
}
</style>
