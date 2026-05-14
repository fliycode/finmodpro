<script setup>
import { computed, ref } from 'vue';
import { ElMessageBox } from 'element-plus';

import { kbApi } from '../api/knowledgebase.js';
import { riskApi } from '../api/risk.js';
import { useFlash } from '../lib/flash.js';
import { buildRiskSummaryExportDownload, downloadTextFile } from '../lib/risk-summary-export.js';
import AppSectionCard from './ui/AppSectionCard.vue';
import AppIcon from './ui/AppIcon.vue';

const flash = useFlash();
const fmt = new Intl.NumberFormat('zh-CN');
const levelPriority = { critical: 4, high: 3, medium: 2, low: 1 };
const riskTagTypeMap = { high: 'danger', critical: 'danger', medium: 'warning', low: 'success' };
const riskLevelTextMap = { critical: '严重', high: '高', medium: '中', low: '低' };

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
const documentDisplayTitle = computed(() => activeDocument.value?.title || pipelineRun.value.fileName || '上传文档后，结果会显示在这里。');
const documentTitle = computed(() => activeDocument.value?.title || pipelineRun.value.fileName || '当前文档');
const canExportResults = computed(() => (
  !isProcessing.value
  && !resultErrorMsg.value
  && pipelineRun.value.status === 'succeeded'
  && Boolean(activeDocument.value?.id || pipelineRun.value.fileName)
));
const exportHint = computed(() => (
  canExportResults.value
    ? '导出 Markdown，包含摘要、证据与原始事件。'
    : '提取完成后可导出当前文档结果。'
));
const summaryItems = computed(() => {
  const createdCount = Number.isFinite(Number(pipelineRun.value.createdCount))
    ? Number(pipelineRun.value.createdCount)
    : 0;

  return [
    {
      label: '风险类别',
      value: groupedRiskResults.value.length ? `${fmt.format(groupedRiskResults.value.length)} 类` : '未识别',
      note: groupedRiskResults.value.length
        ? `${getRiskLevelText(groupedRiskResults.value[0].dominantLevel)}风险优先呈现`
        : '完成后自动聚合展示',
    },
    {
      label: '事件总数',
      value: pipelineRun.value.status === 'succeeded' ? `${fmt.format(resultEvents.value.length)} 条` : '等待结果',
      note: createdCount
        ? `本次新增 ${fmt.format(createdCount)} 条`
        : (pipelineRun.value.status === 'succeeded' ? '当前文档未识别到新事件' : '仅统计当前文档命中事件'),
    },
    {
      label: '当前阶段',
      value: pipelineStatusText.value,
      note: resultSubline.value,
    },
    {
      label: '导出准备',
      value: canExportResults.value ? '已就绪' : '未就绪',
      note: exportHint.value,
    },
  ];
});

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

const getRiskTagType = (level) => riskTagTypeMap[level] || 'info';
const getRiskLevelText = (level) => riskLevelTextMap[level] || level;

const handleExport = () => {
  if (!canExportResults.value) {
    flash.warning('提取完成后才可导出结果');
    return;
  }

  try {
    downloadTextFile(buildRiskSummaryExportDownload({
      documentTitle: documentTitle.value,
      statusText: pipelineStatusText.value,
      detail: resultSubline.value,
      groupedResults: groupedRiskResults.value,
      resultEvents: resultEvents.value,
      createdCount: pipelineRun.value.createdCount || resultEvents.value.length,
    }));
    flash.success('导出文件已生成');
  } catch (error) {
    console.error('导出风险提取结果失败:', error);
    flash.error('导出结果失败，请稍后重试');
  }
};
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

    <section class="risk-page__command">
      <div class="risk-page__command-copy">
        <span class="risk-page__eyebrow">风险提取工作台</span>
        <h2>上传一份文档，直接得到可审阅的风险摘要</h2>
        <p>把上传、入库、提取与导出放在同一视线里，只保留当前文档最需要确认的风险信号。</p>
      </div>
      <div class="risk-page__command-side">
        <div class="risk-page__toolbar">
          <el-button type="primary" :loading="isUploading" @click="triggerUpload">
            <AppIcon name="upload" />
            {{ uploadButtonLabel }}
          </el-button>
          <el-button plain :disabled="!canExportResults" @click="handleExport">
            <AppIcon name="download" />
            导出结果
          </el-button>
        </div>
        <p class="risk-page__command-note">{{ exportHint }}</p>
      </div>
    </section>

    <AppSectionCard
      class="risk-page__results-card"
      title="提取结果"
      :desc="documentDisplayTitle"
      icon="shield"
    >
      <template #header>
        <div class="risk-page__heading-meta">
          <span class="risk-page__status" :data-tone="pipelineTone">{{ pipelineStatusText }}</span>
          <span class="risk-page__heading-note">{{ resultSubline }}</span>
        </div>
      </template>

      <div class="risk-page__summary-rail">
        <div
          v-for="item in summaryItems"
          :key="item.label"
          class="risk-page__summary-item"
        >
          <span class="risk-page__summary-label">{{ item.label }}</span>
          <strong class="risk-page__summary-value">{{ item.value }}</strong>
          <span class="risk-page__summary-note">{{ item.note }}</span>
        </div>
      </div>

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

      <ol v-else class="risk-page__result-list">
        <li
          v-for="(item, index) in groupedRiskResults"
          :key="item.key"
          class="risk-page__result-item"
        >
          <div class="risk-page__result-index">{{ String(index + 1).padStart(2, '0') }}</div>
          <div class="risk-page__result-body">
            <div class="risk-page__result-head">
              <div class="risk-page__result-copy">
                <strong>{{ item.key }}</strong>
                <p>{{ item.summary }}</p>
              </div>
              <div class="risk-page__result-meta">
                <el-tag :type="getRiskTagType(item.dominantLevel)" size="small">
                  {{ getRiskLevelText(item.dominantLevel) }}
                </el-tag>
                <span>{{ item.count }} 条事件</span>
              </div>
            </div>
            <p class="risk-page__evidence">{{ item.evidence }}</p>
          </div>
        </li>
      </ol>
    </AppSectionCard>
  </div>
</template>

<style scoped>
.risk-page {
  display: grid;
  gap: 18px;
  min-width: 0;
}

.risk-page__file-input {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}

.risk-page__command {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(280px, 0.95fr);
  gap: 24px;
  padding: 24px 28px;
  border: 1px solid var(--line-soft);
  border-radius: 24px;
  background: var(--surface-1);
  box-shadow: 0 18px 44px -30px rgba(16, 24, 40, 0.18);
}

.risk-page__command-copy,
.risk-page__command-side {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.risk-page__command-copy {
  align-content: start;
}

.risk-page__eyebrow {
  color: var(--text-muted);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.risk-page__command-copy h2 {
  margin: 0;
  max-width: 18ch;
  color: var(--text-primary);
  font-size: 1.55rem;
  line-height: 1.2;
}

.risk-page__command-copy p,
.risk-page__command-note,
.risk-page__heading-note,
.risk-page__summary-note,
.risk-page__state p,
.risk-page__result-head p,
.risk-page__evidence {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.risk-page__command-side {
  align-content: end;
  justify-items: start;
}

.risk-page__toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.risk-page__command-note {
  max-width: 30ch;
}

.risk-page__results-card {
  min-width: 0;
}

.risk-page__results-card :deep(.el-card__body) {
  display: grid;
  gap: 18px;
}

.risk-page__heading-meta {
  display: grid;
  justify-items: end;
  gap: 8px;
  max-width: 34ch;
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
  background: var(--brand);
  transition: width 180ms ease;
}

.risk-page__summary-rail {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  border: 1px solid var(--line-soft);
  border-radius: 20px;
  overflow: hidden;
  background: var(--surface-2);
}

.risk-page__summary-item {
  display: grid;
  gap: 6px;
  min-width: 0;
  padding: 16px 18px;
}

.risk-page__summary-item + .risk-page__summary-item {
  border-left: 1px solid var(--line-soft);
}

.risk-page__summary-label {
  color: var(--text-muted);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.risk-page__summary-value {
  color: var(--text-primary);
  font-size: 1rem;
}

.risk-page__state {
  display: grid;
  align-content: center;
  gap: 8px;
  min-height: 260px;
  padding: 28px;
  border-radius: 20px;
  background: var(--surface-2);
}

.risk-page__state strong,
.risk-page__result-head strong {
  color: var(--text-primary);
}

.risk-page__state--error {
  color: var(--risk);
  background: rgba(196, 73, 61, 0.06);
}

.risk-page__result-list {
  display: grid;
  gap: 0;
  margin: 0;
  padding: 0;
  list-style: none;
}

.risk-page__result-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 16px;
  padding: 22px 0;
}

.risk-page__result-item + .risk-page__result-item {
  border-top: 1px solid var(--line-soft);
}

.risk-page__result-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: var(--surface-3);
  color: var(--text-muted);
  font-size: 0.8125rem;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.risk-page__result-body,
.risk-page__result-copy {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.risk-page__result-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.risk-page__result-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  color: var(--text-muted);
  font-size: 0.75rem;
}

.risk-page__evidence {
  padding: 14px 16px;
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: var(--surface-3);
}

@media (max-width: 1100px) {
  .risk-page__command {
    grid-template-columns: minmax(0, 1fr);
  }

  .risk-page__command-copy h2,
  .risk-page__command-note {
    max-width: none;
  }
}

@media (max-width: 900px) {
  .risk-page__heading-meta,
  .risk-page__summary-rail,
  .risk-page__result-head {
    grid-template-columns: minmax(0, 1fr);
  }

  .risk-page__heading-meta {
    justify-items: start;
  }

  .risk-page__summary-item + .risk-page__summary-item {
    border-left: 0;
    border-top: 1px solid var(--line-soft);
  }

  .risk-page__result-item,
  .risk-page__result-head {
    grid-template-columns: minmax(0, 1fr);
    flex-direction: column;
  }

  .risk-page__result-index {
    width: 36px;
    height: 36px;
  }

  .risk-page__result-meta {
    align-items: flex-start;
  }
}
</style>
