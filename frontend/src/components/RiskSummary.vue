<script setup>
import { computed, ref } from 'vue';
import { ElMessageBox } from 'element-plus';

import { kbApi } from '../api/knowledgebase.js';
import { riskApi } from '../api/risk.js';
import { useFlash } from '../lib/flash.js';
import AppIcon from './ui/AppIcon.vue';

const flash = useFlash();
const fmt = new Intl.NumberFormat('zh-CN');
const levelPriority = { critical: 4, high: 3, medium: 2, low: 1 };

const fileInput = ref(null);
const isUploading = ref(false);
const activeDocument = ref(null);
const resultEvents = ref([]);
const resultErrorMsg = ref('');

const createPipelineRunState = () => ({
  status: 'idle',
  fileName: '',
  documentId: null,
  detail: '等待上传文档',
  uploadProgress: 0,
  ingestProgress: 0,
  extractProgress: 0,
  createdCount: 0,
  failureCode: '',
});

const pipelineRun = ref(createPipelineRunState());

const groupedRiskResults = computed(() => {
  const groups = new Map();

  resultEvents.value.forEach((event) => {
    const key = event.risk_type || '未分类风险';
    const current = groups.get(key);

    if (!current) {
      groups.set(key, {
        key,
        count: 1,
        dominantLevel: event.risk_level || 'low',
        summary: event.summary || '暂无摘要',
        evidence: event.evidence_text || event.summary || '暂无证据文本。',
      });
      return;
    }

    current.count += 1;
    if ((levelPriority[event.risk_level] || 0) > (levelPriority[current.dominantLevel] || 0)) {
      current.dominantLevel = event.risk_level || current.dominantLevel;
      current.summary = event.summary || current.summary;
      current.evidence = event.evidence_text || event.summary || current.evidence;
    }
  });

  return Array.from(groups.values()).sort((left, right) => {
    const levelGap = (levelPriority[right.dominantLevel] || 0) - (levelPriority[left.dominantLevel] || 0);
    if (levelGap !== 0) {
      return levelGap;
    }
    return right.count - left.count;
  });
});

const pipelinePercent = computed(() => {
  if (pipelineRun.value.status === 'idle' && !pipelineRun.value.fileName) {
    return 0;
  }

  const weighted =
    (pipelineRun.value.uploadProgress * 0.3)
    + (pipelineRun.value.ingestProgress * 0.35)
    + (pipelineRun.value.extractProgress * 0.35);

  return Math.max(
    pipelineRun.value.status === 'idle' ? 0 : 6,
    Math.min(100, Math.round(weighted)),
  );
});

const pipelineStatusText = computed(() => ({
  idle: '待命',
  uploading: '上传中',
  ingesting: '入库中',
  extracting: '提取中',
  succeeded: '已完成',
  busy: '系统繁忙',
  timed_out: '已超时',
  failed: '已中断',
}[pipelineRun.value.status] || '处理中'));

const pipelineTone = computed(() => ({
  idle: 'muted',
  uploading: 'active',
  ingesting: 'active',
  extracting: 'active',
  succeeded: 'success',
  busy: 'warning',
  timed_out: 'warning',
  failed: 'danger',
}[pipelineRun.value.status] || 'muted'));

const uploadButtonLabel = computed(() => {
  if (!isUploading.value) {
    return '上传文档';
  }

  return `处理中 ${Math.max(1, pipelinePercent.value)}%`;
});

const resultSubline = computed(() => {
  if (resultErrorMsg.value) {
    return resultErrorMsg.value;
  }

  if (!activeDocument.value && !pipelineRun.value.fileName) {
    return '上传文档后，这里只显示当前文档的提取结果。';
  }

  if (isUploading.value || ['uploading', 'ingesting', 'extracting'].includes(pipelineRun.value.status)) {
    return pipelineRun.value.detail;
  }

  if (!groupedRiskResults.value.length) {
    return pipelineRun.value.status === 'succeeded'
      ? '这份文档暂未识别到风险事件。'
      : '等待开始提取。';
  }

  return `${fmt.format(groupedRiskResults.value.length)} 类风险，${fmt.format(resultEvents.value.length)} 条事件`;
});

const isProcessing = computed(() => ['uploading', 'ingesting', 'extracting'].includes(pipelineRun.value.status));

const updatePipelineRun = (patch) => {
  pipelineRun.value = {
    ...pipelineRun.value,
    ...patch,
  };
};

const resetPipelineRun = () => {
  pipelineRun.value = createPipelineRunState();
  activeDocument.value = null;
  resultEvents.value = [];
  resultErrorMsg.value = '';
};

const triggerUpload = () => fileInput.value?.click();

const startPipelineRun = (file) => {
  pipelineRun.value = {
    ...createPipelineRunState(),
    status: 'uploading',
    fileName: file.name,
    detail: '正在接收文件',
  };
  activeDocument.value = null;
  resultEvents.value = [];
  resultErrorMsg.value = '';
};

const syncActiveDocument = async (documentId) => {
  const document = await kbApi.getDocumentDetail(documentId);
  activeDocument.value = document;

  updatePipelineRun({
    documentId,
    status: document.processStep?.code === 'failed'
      ? 'failed'
      : (pipelineRun.value.status === 'uploading' ? 'ingesting' : pipelineRun.value.status),
    ingestProgress: document.processStep?.progress ?? pipelineRun.value.ingestProgress,
    detail: document.processStep?.detail || pipelineRun.value.detail,
  });

  return document;
};

const fetchDocumentEvents = async (documentId) => {
  const data = await riskApi.getEvents({ document_id: documentId });
  resultEvents.value = data.data?.risk_events || data.risk_events || [];
};

const applyExtractionProgress = (payload = {}) => {
  const status = String(payload.status || '').toUpperCase();
  const errorCode = payload.error_code || '';
  const resolvedProgress = Number.isFinite(Number(payload.progress))
    ? Math.max(0, Math.min(100, Number(payload.progress)))
    : ({
      QUEUED: 6,
      RUNNING: 72,
      SUCCESS: 100,
      FAILURE: 100,
      BUSY: 100,
      TIMED_OUT: 100,
    }[status] || pipelineRun.value.extractProgress);

  const pipelineStatus = status === 'BUSY'
    ? 'busy'
    : (status === 'TIMED_OUT'
      || ['risk_extraction_timeout', 'risk_extraction_stage_timeout', 'risk_extraction_queue_timeout', 'risk_extraction_poll_timeout'].includes(errorCode)
      ? 'timed_out'
      : (status === 'FAILURE'
        ? 'failed'
        : (status === 'SUCCESS' ? 'succeeded' : 'extracting')));

  updatePipelineRun({
    status: pipelineStatus,
    extractProgress: resolvedProgress,
    detail: payload.message || pipelineRun.value.detail,
    createdCount: payload.result?.created_count ?? pipelineRun.value.createdCount,
    failureCode: errorCode,
  });
};

const applyPipelineFailure = (error) => {
  const failureCode = error?.code || error?.data?.error_code || '';
  const nextStatus = failureCode === 'risk_extraction_busy'
    ? 'busy'
    : ([
      'risk_extraction_timeout',
      'risk_extraction_stage_timeout',
      'risk_extraction_queue_timeout',
      'risk_extraction_poll_timeout',
    ].includes(failureCode)
      ? 'timed_out'
      : 'failed');

  updatePipelineRun({
    status: nextStatus,
    detail: error?.message || '提取失败',
    failureCode,
  });
  resultErrorMsg.value = error?.message || '提取失败';
};

const notifyPipelineFailure = (error, fallback) => {
  if (pipelineRun.value.status === 'busy' || pipelineRun.value.status === 'timed_out') {
    flash.warning(error.message || fallback);
    return;
  }

  flash.error(error.message || fallback);
};

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const pollDocumentIndexed = async (documentId, { timeout = 60000, interval = 2000 } = {}) => {
  const deadline = Date.now() + timeout;

  while (Date.now() < deadline) {
    const document = await syncActiveDocument(documentId);
    const status = String(document.status || '').toLowerCase();

    if (status === 'indexed') {
      return document;
    }

    if (status === 'failed') {
      throw new Error(document.processError || '文档处理失败');
    }

    await sleep(interval);
  }

  throw new Error('文档处理超时，请稍后重试');
};

const runRiskPipeline = async (documentId) => {
  const currentDocument = activeDocument.value?.id === documentId
    ? activeDocument.value
    : await syncActiveDocument(documentId);
  const currentStatus = String(currentDocument?.status || '').toLowerCase();

  if (currentStatus !== 'indexed') {
    const ingestPayload = await kbApi.ingestDocument(documentId);

    if (ingestPayload.document) {
      activeDocument.value = ingestPayload.document;
      updatePipelineRun({
        status: 'ingesting',
        documentId,
        ingestProgress: ingestPayload.document.processStep?.progress ?? pipelineRun.value.ingestProgress,
        detail: ingestPayload.document.processStep?.detail || '文件已保存，正在提交入库任务',
      });
    }

    await pollDocumentIndexed(documentId);
  } else {
    updatePipelineRun({
      status: 'extracting',
      documentId,
      ingestProgress: 100,
      detail: '文档已入库，准备开始风险提取',
    });
  }

  updatePipelineRun({
    status: 'extracting',
    extractProgress: 6,
    detail: '正在分析文档中的风险事件',
  });

  const result = await riskApi.extractDocumentWithPolling(documentId, {
    onProgress: applyExtractionProgress,
  });

  applyExtractionProgress({
    status: 'SUCCESS',
    progress: 100,
    message: result.message || (result.created_count ? '风险提取完成' : '未识别到风险事件'),
    result,
  });

  await fetchDocumentEvents(documentId);
  flash.success('风险提取完成');
};

const useExistingDocument = async (documentInfo, fallbackName) => {
  isUploading.value = true;
  resultEvents.value = [];
  resultErrorMsg.value = '';

  updatePipelineRun({
    ...createPipelineRunState(),
    fileName: documentInfo.filename || documentInfo.title || fallbackName,
    uploadProgress: 100,
    documentId: documentInfo.id,
    status: 'ingesting',
    detail: '正在切换到已存在的文档',
  });

  try {
    await syncActiveDocument(documentInfo.id);
    await runRiskPipeline(documentInfo.id);
  } catch (error) {
    applyPipelineFailure(error);
    notifyPipelineFailure(error, '使用已有文档失败');
  } finally {
    isUploading.value = false;
  }
};

const handleFileChange = async (event) => {
  const file = event.target.files?.[0];

  if (!file) {
    return;
  }

  isUploading.value = true;
  startPipelineRun(file);

  try {
    const result = await kbApi.uploadDocument(file, {
      onProgress: (progress) => {
        updatePipelineRun({
          status: 'uploading',
          uploadProgress: progress,
          detail: '文件正在上传',
        });
      },
    });
    const documentId = result.document?.id;

    if (documentId) {
      activeDocument.value = result.document;
      updatePipelineRun({
        uploadProgress: 100,
        status: 'ingesting',
        documentId,
        ingestProgress: result.document.processStep?.progress ?? 0,
        detail: '文件已保存，正在准备提取',
      });
      await runRiskPipeline(documentId);
    }
  } catch (error) {
    if (error.code === 'DUPLICATE' && error.existingDocument) {
      try {
        await ElMessageBox.confirm(
          `知识库已存在《${error.existingDocument.title}》，是否直接使用这份文档进行风险提取？`,
          '使用已有文档',
          { confirmButtonText: '直接使用', cancelButtonText: '取消', type: 'info' },
        );
      } catch {
        resetPipelineRun();
        if (event.target) {
          event.target.value = '';
        }
        isUploading.value = false;
        return;
      }

      await useExistingDocument(error.existingDocument, file.name);
      if (event.target) {
        event.target.value = '';
      }
      return;
    }

    applyPipelineFailure(error);
    notifyPipelineFailure(error, '上传或提取失败');
  } finally {
    isUploading.value = false;
    if (event.target) {
      event.target.value = '';
    }
  }
};

const getRiskTagType = (level) => ({ high: 'danger', critical: 'danger', medium: 'warning', low: 'success' }[level] || 'info');
const getRiskLevelText = (level) => ({ critical: '严重', high: '高', medium: '中', low: '低' }[level] || level);
</script>

<template>
  <div class="risk-page">
    <input
      ref="fileInput"
      type="file"
      accept=".pdf,.docx,.txt"
      class="risk-page__file-input"
      @change="handleFileChange"
      aria-hidden="true"
      tabindex="-1"
    />

    <div class="risk-page__toolbar">
      <el-button type="primary" :loading="isUploading" @click="triggerUpload">
        <AppIcon name="upload" />
        {{ uploadButtonLabel }}
      </el-button>
    </div>

    <section class="risk-page__results">
      <header class="risk-page__results-head">
        <div class="risk-page__results-copy">
          <h2>提取结果</h2>
          <p>{{ activeDocument?.title || pipelineRun.fileName || '上传文档后，结果会显示在这里。' }}</p>
        </div>
        <span class="risk-page__status" :data-tone="pipelineTone">{{ pipelineStatusText }}</span>
      </header>

      <div v-if="pipelinePercent > 0" class="risk-page__progress" aria-hidden="true">
        <span :style="{ width: `${pipelinePercent}%` }" />
      </div>

      <div v-if="resultErrorMsg" class="risk-page__state risk-page__state--error">
        <strong>提取失败</strong>
        <p>{{ resultSubline }}</p>
      </div>

      <div v-else-if="!activeDocument && !pipelineRun.fileName" class="risk-page__state">
        <strong>还没有文档</strong>
        <p>{{ resultSubline }}</p>
      </div>

      <div v-else-if="isProcessing" class="risk-page__state">
        <strong>{{ pipelineRun.fileName || activeDocument?.title || '正在处理文档' }}</strong>
        <p>{{ resultSubline }}</p>
      </div>

      <div v-else-if="!groupedRiskResults.length" class="risk-page__state">
        <strong>{{ activeDocument?.title || '当前文档' }}</strong>
        <p>{{ resultSubline }}</p>
      </div>

      <div v-else class="risk-page__result-list">
        <article
          v-for="item in groupedRiskResults"
          :key="item.key"
          class="risk-page__result-item"
        >
          <div class="risk-page__result-head">
            <div>
              <strong>{{ item.key }}</strong>
              <p>{{ item.summary }}</p>
            </div>
            <div class="risk-page__result-meta">
              <el-tag :type="getRiskTagType(item.dominantLevel)" size="small">
                {{ getRiskLevelText(item.dominantLevel) }}
              </el-tag>
              <span>{{ item.count }} 条</span>
            </div>
          </div>
          <p class="risk-page__evidence">{{ item.evidence }}</p>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped>
.risk-page {
  display: grid;
  gap: 16px;
  min-width: 0;
}

.risk-page__file-input {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}

.risk-page__toolbar {
  display: flex;
  justify-content: flex-start;
}

.risk-page__results {
  display: grid;
  gap: 16px;
  padding: 20px 22px;
  border: 1px solid var(--line-strong);
  border-radius: 24px;
  background: var(--surface-1);
  min-height: 420px;
}

.risk-page__results-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.risk-page__results-copy {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.risk-page__results-copy h2 {
  margin: 0;
  color: var(--text-primary);
}

.risk-page__results-copy p,
.risk-page__state p,
.risk-page__result-head p,
.risk-page__evidence {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.risk-page__status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  white-space: nowrap;
}

.risk-page__status[data-tone='muted'] {
  background: rgba(125, 135, 152, 0.12);
  color: var(--text-muted);
}

.risk-page__status[data-tone='active'] {
  background: rgba(36, 87, 197, 0.12);
  color: var(--brand);
}

.risk-page__status[data-tone='success'] {
  background: rgba(33, 129, 92, 0.12);
  color: var(--success);
}

.risk-page__status[data-tone='warning'] {
  background: rgba(186, 128, 40, 0.14);
  color: var(--warning);
}

.risk-page__status[data-tone='danger'] {
  background: rgba(196, 73, 61, 0.12);
  color: var(--risk);
}

.risk-page__progress {
  position: relative;
  overflow: hidden;
  height: 8px;
  border-radius: 999px;
  background: var(--surface-3);
}

.risk-page__progress > span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, rgba(36, 87, 197, 0.42), rgba(36, 87, 197, 0.92));
  transition: width 180ms ease;
}

.risk-page__state {
  display: grid;
  align-content: center;
  gap: 8px;
  min-height: 280px;
  padding: 12px 0;
}

.risk-page__state strong,
.risk-page__result-head strong {
  color: var(--text-primary);
}

.risk-page__state--error {
  color: var(--risk);
}

.risk-page__result-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.risk-page__result-item {
  display: grid;
  gap: 10px;
  padding: 16px;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  background: var(--surface-2);
}

.risk-page__result-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.risk-page__result-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  color: var(--text-muted);
  font-size: 0.75rem;
  white-space: nowrap;
}

.risk-page__evidence {
  padding: 12px 14px;
  border-radius: 14px;
  background: var(--surface-3);
}

@media (max-width: 900px) {
  .risk-page__results-head,
  .risk-page__result-head {
    flex-direction: column;
  }

  .risk-page__result-meta {
    align-items: flex-start;
  }
}
</style>
