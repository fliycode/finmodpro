<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import KnowledgeBaseDetailPanel from '../../components/knowledgebase/KnowledgeBaseDetailPanel.vue';
import { kbApi } from '../../api/knowledgebase.js';
import { useFlash } from '../../lib/flash.js';
import { getIngestionAction } from '../../lib/knowledgebase-actions.js';
import { buildChunkExpansionState, buildPreviewState } from '../../lib/knowledgebase-workspace.js';

const route = useRoute();
const router = useRouter();
const flash = useFlash();

const document = ref(null);
const isSubmittingTask = ref(false);
const isUploadingVersion = ref(false);
const isLoadingVersions = ref(false);
const isLoadingChunks = ref(false);
const activeTab = ref('processing');
const versionHistory = ref([]);
const chunks = ref([]);
const expandedChunkIds = ref([]);
const fileInput = ref(null);

const statusTone = {
  uploaded: 'neutral',
  queued: 'neutral',
  parsing: 'accent',
  chunking: 'accent',
  indexing: 'accent',
  indexed: 'success',
  failed: 'danger',
};

const decoratedDocument = computed(() => {
  if (!document.value) return null;
  return {
    ...document.value,
    statusTone: statusTone[document.value.processStep?.code] || 'neutral',
  };
});

const ingestionAction = computed(() => getIngestionAction(decoratedDocument.value));
const previewState = computed(() => buildPreviewState(decoratedDocument.value));

const taskHintText = computed(() => {
  const doc = document.value;
  if (!doc) return '';
  const code = doc.processStep?.code || '';
  if (['queued', 'parsing', 'chunking', 'indexing'].includes(code)) {
    return '任务已启动，后台正在执行解析、切块和向量写入，完成后列表与详情会自动刷新。';
  }
  return `上传只保存原始文件；点击"${ingestionAction.value?.label || '启动入库'}"后，后台才会异步完成解析、切块和写入向量库。`;
});

const fetchDocument = async () => {
  try {
    document.value = await kbApi.getDocumentDetail(route.params.id);
  } catch (error) {
    flash.error(`加载文档详情失败：${error.message || '未知错误'}`);
  }
};

const fetchChunks = async () => {
  isLoadingChunks.value = true;
  try {
    chunks.value = await kbApi.getDocumentChunks(route.params.id);
  } catch (error) {
    chunks.value = [];
  } finally {
    isLoadingChunks.value = false;
  }
};

const fetchVersions = async () => {
  if (!document.value?.rootDocumentId) return;
  isLoadingVersions.value = true;
  try {
    const payload = await kbApi.listDocumentVersions(document.value.rootDocumentId);
    versionHistory.value = payload.versions || [];
  } catch (error) {
    versionHistory.value = [];
  } finally {
    isLoadingVersions.value = false;
  }
};

const startIngestion = async () => {
  if (isSubmittingTask.value) return;
  isSubmittingTask.value = true;
  try {
    const result = await kbApi.ingestDocument(route.params.id);
    if (result.document) document.value = result.document;
    flash.success(result.message || '入库任务已提交。');
    await fetchDocument();
    await fetchChunks();
  } catch (error) {
    flash.error(`启动入库失败：${error.message || '未知错误'}`);
  } finally {
    isSubmittingTask.value = false;
  }
};

const handleVersionUpload = async (event) => {
  const file = event.target.files?.[0];
  if (!file) return;
  isUploadingVersion.value = true;
  try {
    const result = await kbApi.uploadNewVersion(document.value.rootDocumentId, file, {
      title: file.name,
      sourceLabel: file.name,
      sourceMetadata: { replaced_document_id: Number(route.params.id) },
    });
    if (result.document) {
      document.value = result.document;
      activeTab.value = 'versions';
    }
    flash.success(result.message || '新版本已上传。');
    await fetchDocument();
    await fetchVersions();
  } catch (error) {
    flash.error(`上传新版本失败：${error.message || '未知错误'}`);
  } finally {
    isUploadingVersion.value = false;
    event.target.value = '';
  }
};

const openLink = (url) => {
  if (!url) {
    flash.error('当前文档没有可访问的文件链接。');
    return;
  }
  window.open(url, '_blank', 'noopener');
};

const goBack = () => router.push('/workspace/knowledge');

let pollInterval = null;

onMounted(async () => {
  await fetchDocument();
  await fetchChunks();
  pollInterval = setInterval(async () => {
    const doc = document.value;
    if (!doc) return;
    const code = doc.processStep?.code || '';
    if (!['queued', 'parsing', 'chunking', 'indexing'].includes(code)) return;
    await fetchDocument();
    await fetchChunks();
  }, 3000);
});

onUnmounted(() => {
  if (pollInterval) clearInterval(pollInterval);
});
</script>

<template>
  <div class="detail-page">
    <button class="back-btn" type="button" @click="goBack">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
      返回知识库列表
    </button>
    <input ref="fileInput" type="file" hidden @change="handleVersionUpload" />
    <KnowledgeBaseDetailPanel
      :document="decoratedDocument"
      :primary-action="ingestionAction"
      :active-tab="activeTab"
      :task-hint-text="taskHintText"
      :is-submitting-task="isSubmittingTask"
      :versions="versionHistory"
      :is-loading-versions="isLoadingVersions"
      :is-uploading-version="isUploadingVersion"
      :chunks="chunks"
      :expanded-chunk-ids="expandedChunkIds"
      :is-loading-chunks="isLoadingChunks"
      :empty-state="{ title: '加载中...', detail: '' }"
      @ingest="startIngestion"
      @upload-version="fileInput?.click()"
      @preview="isPreviewOpen = true"
      @open-original="openLink(document?.originalUrl)"
      @change-tab="activeTab = $event"
      @toggle-chunk="expandedChunkIds = buildChunkExpansionState(expandedChunkIds, $event)"
    />
  </div>
</template>

<style scoped>
.detail-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  width: fit-content;
  padding: 8px 14px;
  border: 1px solid var(--line-soft);
  border-radius: 10px;
  background: var(--surface-2);
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.back-btn:hover {
  background: var(--brand-soft);
  color: var(--brand);
}
</style>
