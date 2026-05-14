<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import { ElMessageBox } from 'element-plus';

import { kbApi } from '../api/knowledgebase.js';
import { riskApi } from '../api/risk.js';
import { useFlash } from '../lib/flash.js';
import { normalizeRiskAnalytics } from '../lib/risk-workspace.js';
import AppIcon from './ui/AppIcon.vue';

const flash = useFlash();
const fmt = new Intl.NumberFormat('zh-CN');

const buildDefaultFilters = () => ({
  company_name: '',
  risk_type: '',
  risk_level: '',
  review_status: '',
  period_start: '',
  period_end: '',
});

const filters = ref(buildDefaultFilters());
const events = ref([]);
const analyticsPayload = ref(null);

const isEventsLoading = ref(false);
const isAnalyticsLoading = ref(false);
const isUploading = ref(false);
const reviewingId = ref(null);

const eventsErrorMsg = ref('');
const analyticsErrorMsg = ref('');

const fileInput = ref(null);
const reviewQueueSection = ref(null);
const eventsDrawerOpen = ref(false);
const activeDocument = ref(null);
const createPipelineRunState = () => ({
  status: 'idle',
  fileName: '',
  documentId: null,
  detail: '等待新文档',
  uploadProgress: 0,
  ingestLabel: '待开始',
  ingestProgress: 0,
  extractLabel: '待开始',
  extractStatus: 'IDLE',
  extractProgress: 0,
  createdCount: 0,
  reviewReady: false,
  failureCode: '',
});
const pipelineRun = ref(createPipelineRunState());
const sourceMode = ref('upload');
const knowledgebaseSearch = ref('');
const knowledgebaseDocs = ref([]);
const selectedKnowledgebaseId = ref('');
const isKnowledgebaseLoading = ref(false);

let workspaceAbort = null;

const analytics = computed(() => normalizeRiskAnalytics(analyticsPayload.value));
const riskTypeDist = computed(() => analytics.value.risk_type_distribution || []);
const pendingReviews = computed(() => analytics.value.summary.pending_reviews || 0);
const selectedKnowledgeDocument = computed(() => (
  knowledgebaseDocs.value.find((doc) => String(doc.id) === String(selectedKnowledgebaseId.value)) || null
));

const eventsByType = computed(() => {
  const groups = {};
  events.value.forEach((event) => {
    if (!groups[event.risk_type]) {
      groups[event.risk_type] = [];
    }
    groups[event.risk_type].push(event);
  });
  return groups;
});

const dominantLevelMap = computed(() => {
  const priority = { critical: 4, high: 3, medium: 2, low: 1 };
  const groups = {};

  Object.entries(eventsByType.value).forEach(([type, typeEvents]) => {
    groups[type] = typeEvents.reduce((best, event) => (
      (priority[event.risk_level] || 0) > (priority[best] || 0) ? event.risk_level : best
    ), 'low');
  });

  return groups;
});

const groupedRiskResults = computed(() => riskTypeDist.value.map((item) => {
  const relatedEvents = eventsByType.value[item.key] || [];
  return {
    key: item.key,
    count: item.value,
    dominantLevel: dominantLevelMap.value[item.key] || 'low',
    summary: relatedEvents[0]?.summary || '暂无摘要',
    evidence: relatedEvents[0]?.evidence_text || '暂无证据文本。',
  };
}));

const reviewQueueEvents = computed(() => events.value
  .filter((event) => (event.review_status || 'pending').toLowerCase() === 'pending')
  .slice(0, 8));

const canReturnToReviewQueue = computed(() => (
  pipelineRun.value.reviewReady
  || pendingReviews.value > 0
  || reviewQueueEvents.value.length > 0
));

const sourceDoc = computed(() => {
  const currentDocument = activeDocument.value;
  const firstEvent = events.value[0];
  const fileSize = currentDocument
    ? Number.parseFloat(currentDocument.size) || 0
    : (firstEvent?.document_file_size || 0);

  return {
    title: currentDocument?.title || firstEvent?.document_title || firstEvent?.document_filename || '暂无文档',
    company: firstEvent?.company_name || '未识别公司',
    size: currentDocument?.size || (fileSize > 0 ? `${(fileSize / 1024 / 1024).toFixed(1)} MB` : '--'),
    date: currentDocument?.sourceDate || firstEvent?.document_source_date || '--',
  };
});

const extractionQuality = computed(() => {
  const firstEvent = events.value.find((event) => event.extraction_metadata);
  if (!firstEvent) {
    return null;
  }

  return {
    rounds: firstEvent.extraction_metadata.rounds_completed,
    verified: firstEvent.extraction_metadata.verification_passed,
    filteredChunks: firstEvent.extraction_metadata.filtered_chunks,
    totalChunks: firstEvent.extraction_metadata.total_chunks,
  };
});

const pipelinePercent = computed(() => {
  if (pipelineRun.value.status === 'idle' && !pipelineRun.value.fileName) {
    return 0;
  }

  const weighted =
    (pipelineRun.value.uploadProgress * 0.2)
    + (pipelineRun.value.ingestProgress * 0.35)
    + (pipelineRun.value.extractProgress * 0.35)
    + ((pipelineRun.value.reviewReady ? 100 : 0) * 0.1);

  return Math.max(
    pipelineRun.value.status === 'idle' ? 0 : 6,
    Math.min(100, Math.round(weighted)),
  );
});

const pipelineStatusText = computed(() => ({
  idle: '待命',
  uploading: '上传中',
  ingesting: '入库中',
  extracting: '抽取中',
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
    return '选择文档并开始';
  }
  return `处理中 ${Math.max(1, pipelinePercent.value)}%`;
});

const isAbortError = (error) => error?.name === 'AbortError';
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const updatePipelineRun = (patch) => {
  pipelineRun.value = {
    ...pipelineRun.value,
    ...patch,
  };
};

const resetPipelineRun = () => {
  pipelineRun.value = createPipelineRunState();
  activeDocument.value = null;
};

const startPipelineRun = (file) => {
  pipelineRun.value = {
    ...createPipelineRunState(),
    status: 'uploading',
    fileName: file.name,
    detail: '正在接收文件',
  };
  activeDocument.value = null;
};

const fetchEvents = async (signal) => {
  isEventsLoading.value = true;
  eventsErrorMsg.value = '';
  try {
    const data = await riskApi.getEvents(filters.value, { signal });
    events.value = data.data?.risk_events || data.risk_events || [];
  } catch (error) {
    if (isAbortError(error)) {
      return;
    }
    eventsErrorMsg.value = error.message || '加载风险事件失败';
  } finally {
    isEventsLoading.value = false;
  }
};

const fetchAnalytics = async (signal) => {
  isAnalyticsLoading.value = true;
  analyticsErrorMsg.value = '';
  try {
    analyticsPayload.value = await riskApi.getAnalytics(filters.value, { signal });
  } catch (error) {
    if (isAbortError(error)) {
      return;
    }
    analyticsErrorMsg.value = error.message || '加载风险分析失败';
  } finally {
    isAnalyticsLoading.value = false;
  }
};

const fetchKnowledgebaseDocuments = async () => {
  isKnowledgebaseLoading.value = true;
  try {
    const result = await kbApi.listDocuments({
      searchKeyword: knowledgebaseSearch.value,
      statusFilter: 'indexed',
      pageSize: 8,
    });
    knowledgebaseDocs.value = result.documents || [];
    if (!knowledgebaseDocs.value.some((doc) => String(doc.id) === String(selectedKnowledgebaseId.value))) {
      selectedKnowledgebaseId.value = activeDocument.value?.id
        ? String(activeDocument.value.id)
        : String(knowledgebaseDocs.value[0]?.id || '');
    }
  } catch (error) {
    flash.error(error.message || '加载知识库文档失败');
  } finally {
    isKnowledgebaseLoading.value = false;
  }
};

const refreshWorkspace = async () => {
  if (workspaceAbort) {
    workspaceAbort.abort();
  }

  const controller = new AbortController();
  workspaceAbort = controller;

  try {
    await Promise.all([
      fetchEvents(controller.signal),
      fetchAnalytics(controller.signal),
    ]);
  } finally {
    if (workspaceAbort === controller) {
      workspaceAbort = null;
    }
  }
};

const handleKnowledgebaseExtract = async () => {
  if (!selectedKnowledgebaseId.value) {
    flash.warning('请先选择一份知识库文档');
    return;
  }

  isUploading.value = true;
  try {
    const document = selectedKnowledgeDocument.value || await kbApi.getDocumentDetail(selectedKnowledgebaseId.value);
    activeDocument.value = document;
    updatePipelineRun({
      ...createPipelineRunState(),
      status: 'extracting',
      fileName: document.title,
      documentId: document.id,
      uploadProgress: 100,
      ingestProgress: document.status === 'indexed' ? 100 : 0,
      ingestLabel: document.status === 'indexed' ? '已完成' : '待开始',
      detail: '使用知识库已有文档开始风险提取',
    });
    await runRiskPipeline(document.id);
  } catch (error) {
    applyPipelineFailure(error);
    if (pipelineRun.value.status === 'busy' || pipelineRun.value.status === 'timed_out') {
      flash.warning(error.message || '知识库提取失败');
    } else {
      flash.error(error.message || '知识库提取失败');
    }
  } finally {
    isUploading.value = false;
  }
};

const handleReview = async (event, status) => {
  const eventId = event.id || event.event_id;
  if (reviewingId.value === eventId) {
    return;
  }

  reviewingId.value = eventId;
  try {
    await riskApi.reviewEvent(eventId, status);
    flash.success(`风险事件已${status === 'approved' ? '确认' : '忽略'}`);
    await refreshWorkspace();
  } catch (error) {
    flash.error(error.message || '审核失败');
  } finally {
    reviewingId.value = null;
  }
};

const applyFilters = () => refreshWorkspace();
const resetFilters = () => {
  filters.value = buildDefaultFilters();
  refreshWorkspace();
};

const triggerUpload = () => fileInput.value?.click();
const scrollToReviewQueue = async () => {
  await nextTick();
  reviewQueueSection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' });
};

const syncActiveDocument = async (documentId) => {
  const document = await kbApi.getDocumentDetail(documentId);
  activeDocument.value = document;
  updatePipelineRun({
    documentId,
    status: document.processStep.code === 'failed'
      ? 'failed'
      : (pipelineRun.value.status === 'uploading' ? 'ingesting' : pipelineRun.value.status),
    ingestLabel: document.processStep.label,
    ingestProgress: document.processStep.progress,
    detail: document.processStep.detail,
  });
  return document;
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

  const nextLabel = ({
    QUEUED: '已排队',
    RUNNING: '抽取中',
    SUCCESS: '已完成',
    FAILURE: '已失败',
    BUSY: '系统繁忙',
    TIMED_OUT: '执行超时',
  }[status] || pipelineRun.value.extractLabel);

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
    extractStatus: status || pipelineRun.value.extractStatus,
    extractLabel: nextLabel,
    extractProgress: resolvedProgress,
    detail: payload.message || pipelineRun.value.detail,
    createdCount: payload.result?.created_count ?? pipelineRun.value.createdCount,
    reviewReady: status === 'SUCCESS',
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
    detail: error?.message || '上传或提取失败',
    failureCode,
  });
};

const pollDocumentIndexed = async (documentId, { timeout = 60000, interval = 2000 } = {}) => {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const document = await syncActiveDocument(documentId);
    const status = (document.status || '').toLowerCase();

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
        ingestLabel: ingestPayload.document.processStep.label,
        ingestProgress: ingestPayload.document.processStep.progress,
        detail: ingestPayload.document.processStep.detail,
      });
    }
    await pollDocumentIndexed(documentId);
  } else {
    updatePipelineRun({
      status: 'extracting',
      documentId,
      ingestLabel: '已完成',
      ingestProgress: 100,
      detail: '知识库中已有可用文档，直接开始风险提取',
    });
  }

  updatePipelineRun({
    status: 'extracting',
    extractLabel: '已提交',
    extractProgress: 6,
    detail: '文档已入库，准备抽取风险',
  });
  const result = await riskApi.extractDocumentWithPolling(documentId, {
    onProgress: applyExtractionProgress,
  });
  applyExtractionProgress({
    status: 'SUCCESS',
    progress: 100,
    message: result.message || (result.created_count ? '风险抽取完成' : '未识别到风险事件'),
    result,
  });
  flash.success('风险提取完成');
  await Promise.all([
    refreshWorkspace(),
    fetchKnowledgebaseDocuments(),
  ]);
  await scrollToReviewQueue();
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
        ingestLabel: result.document.processStep.label,
        ingestProgress: result.document.processStep.progress,
        detail: '文件已保存，正在提交入库任务',
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
        return;
      }

      try {
        updatePipelineRun({
          fileName: error.existingDocument.filename || error.existingDocument.title || file.name,
          uploadProgress: 100,
          documentId: error.existingDocument.id,
          status: 'ingesting',
          detail: '正在切换到知识库已有文档',
        });
        await syncActiveDocument(error.existingDocument.id);
        await runRiskPipeline(error.existingDocument.id);
      } catch (versionError) {
        applyPipelineFailure(versionError);
        if (pipelineRun.value.status === 'busy' || pipelineRun.value.status === 'timed_out') {
          flash.warning(versionError.message || '使用已有文档失败');
        } else {
          flash.error(versionError.message || '使用已有文档失败');
        }
      }
      return;
    }

    applyPipelineFailure(error);
    if (pipelineRun.value.status === 'busy' || pipelineRun.value.status === 'timed_out') {
      flash.warning(error.message || '上传或提取失败');
    } else {
      flash.error(error.message || '上传或提取失败');
    }
  } finally {
    isUploading.value = false;
    if (event.target) {
      event.target.value = '';
    }
  }
};

const formatDate = (value) => {
  try {
    return value ? new Date(value).toLocaleString() : '--';
  } catch {
    return value;
  }
};

const getRiskTagType = (level) => ({ high: 'danger', critical: 'danger', medium: 'warning', low: 'success' }[level] || 'info');
const getReviewTagType = (status) => ({ approved: 'success', rejected: 'danger', pending: 'warning' }[status] || 'info');
const getReviewStatusText = (status) => ({ pending: '待审核', approved: '已确认', rejected: '已忽略' }[status?.toLowerCase()] || status || '待审核');
const getRiskLevelText = (level) => ({ critical: '严重', high: '高', medium: '中', low: '低' }[level] || level);

const formatConfidence = (score) => `${Math.round((parseFloat(score) || 0) * 100)}%`;
const getConfidenceClass = (score) => {
  const value = parseFloat(score) || 0;
  if (value >= 0.8) return 'confidence-high';
  if (value >= 0.5) return 'confidence-mid';
  return 'confidence-low';
};

const getSourceTooltip = (event) => {
  const meta = event.extraction_metadata;
  if (!meta) {
    return `Chunk #${event.chunk_id}`;
  }

  return [
    `Chunk #${event.chunk_id}`,
    `提取轮次: ${meta.rounds_completed}`,
    `验证: ${meta.verification_passed ? '通过' : '未通过'}`,
    `筛选切块: ${meta.filtered_chunks || '?'}/${meta.total_chunks || '?'}`,
  ].join('\n');
};

onMounted(() => {
  refreshWorkspace();
  fetchKnowledgebaseDocuments();
});

onBeforeUnmount(() => {
  if (workspaceAbort) {
    workspaceAbort.abort();
  }
});
</script>

<template>
  <div class="page-stack risk-page">
    <el-alert
      v-if="eventsErrorMsg || analyticsErrorMsg"
      :title="eventsErrorMsg || analyticsErrorMsg"
      type="error"
      show-icon
      :closable="false"
    />

    <section class="risk-page__hero">
      <input
        ref="fileInput"
        type="file"
        accept=".pdf,.docx,.txt"
        class="risk-page__file-input"
        @change="handleFileChange"
        aria-hidden="true"
        tabindex="-1"
      />

      <div class="risk-page__hero-copy">
        <h2>先选文档，再提取风险</h2>
        <p>主任务只有一件事，选一份文档，完成提取，然后回到审核队列。</p>
      </div>

      <ol class="risk-page__task-flow" aria-label="风险提取任务流程">
        <li>
          <strong>选文档</strong>
          <span>上传本地文件，或从知识库挑一份已入库文档。</span>
        </li>
        <li>
          <strong>开始提取</strong>
          <span>系统会自动完成入库、抽取和结果汇总。</span>
        </li>
        <li>
          <strong>回到审核队列</strong>
          <span>结果出来后，直接处理下方待审核事件。</span>
        </li>
      </ol>

      <div class="risk-page__runline">
        <span class="risk-page__run-badge" :data-tone="pipelineTone">{{ pipelineStatusText }}</span>
        <strong>{{ pipelineRun.fileName || selectedKnowledgeDocument?.title || '还未选择文档' }}</strong>
        <span>{{ pipelineRun.detail }}</span>
      </div>

      <div class="risk-page__progress-rail" aria-hidden="true">
        <span :style="{ width: `${pipelinePercent}%` }" />
      </div>

      <div class="risk-page__launcher">
        <div class="risk-page__launcher-head">
          <div>
            <h3>第一步，先确定文档来源</h3>
            <p>{{ sourceMode === 'upload' ? '选择文件后会立即开始处理。' : '选中知识库文档后即可直接开始提取。' }}</p>
          </div>
          <div class="risk-page__source-switch">
            <span>文档来源</span>
            <el-radio-group v-model="sourceMode" size="small">
              <el-radio-button label="upload">上传文档</el-radio-button>
              <el-radio-button label="knowledgebase">知识库文档</el-radio-button>
            </el-radio-group>
          </div>
        </div>

        <div v-if="sourceMode === 'upload'" class="risk-page__launcher-body">
          <div class="risk-page__dropzone">
            <div class="risk-page__dropzone-mark">
              <AppIcon name="upload" />
            </div>
            <div>
              <strong>{{ pipelineRun.fileName || 'PDF / DOCX / TXT' }}</strong>
              <span>{{ sourceDoc.size !== '--' ? sourceDoc.size : '单次 50 MB 内' }}</span>
            </div>
          </div>
          <div class="risk-page__launcher-actions">
            <el-button type="primary" :loading="isUploading" @click="triggerUpload">
              <AppIcon name="upload" />
              {{ uploadButtonLabel }}
            </el-button>
            <el-button
              v-if="canReturnToReviewQueue"
              :disabled="!canReturnToReviewQueue"
              @click="scrollToReviewQueue"
            >
              前往审核队列
            </el-button>
            <el-button :loading="isEventsLoading || isAnalyticsLoading" @click="refreshWorkspace">
              <AppIcon name="refresh" />
              刷新结果
            </el-button>
          </div>
        </div>

        <div v-else class="risk-page__launcher-body">
          <div class="risk-page__knowledge-search">
            <el-input
              v-model="knowledgebaseSearch"
              placeholder="搜索知识库文档"
              clearable
              @keyup.enter="fetchKnowledgebaseDocuments"
            />
            <el-button :loading="isKnowledgebaseLoading" @click="fetchKnowledgebaseDocuments">
              <AppIcon name="refresh" />
              刷新
            </el-button>
          </div>

          <div class="risk-page__knowledge-list">
            <button
              v-for="doc in knowledgebaseDocs"
              :key="doc.id"
              type="button"
              class="risk-page__knowledge-item"
              :data-active="String(doc.id) === String(selectedKnowledgebaseId)"
              @click="selectedKnowledgebaseId = String(doc.id)"
            >
              <div>
                <strong>{{ doc.title }}</strong>
                <span>{{ doc.datasetName }} · {{ doc.size }}</span>
              </div>
              <small>{{ doc.processStep.label }}</small>
            </button>
            <div v-if="!knowledgebaseDocs.length && !isKnowledgebaseLoading" class="risk-page__empty">
              暂无已入库文档。
            </div>
          </div>

          <div class="risk-page__launcher-actions">
            <el-button
              type="primary"
              :loading="isUploading"
              :disabled="!selectedKnowledgebaseId"
              @click="handleKnowledgebaseExtract"
            >
              用这份文档提取
            </el-button>
            <el-button
              v-if="canReturnToReviewQueue"
              :disabled="!canReturnToReviewQueue"
              @click="scrollToReviewQueue"
            >
              前往审核队列
            </el-button>
            <el-button :loading="isEventsLoading || isAnalyticsLoading" @click="refreshWorkspace">
              <AppIcon name="refresh" />
              刷新结果
            </el-button>
          </div>
        </div>
      </div>
    </section>

    <div class="risk-page__main">
      <section class="risk-page__panel">
        <header class="risk-page__panel-head">
          <div>
            <h3>提取结果</h3>
            <p>提取完成后先看风险类型和证据，再进入下方审核队列。</p>
          </div>
        </header>

        <div v-if="isEventsLoading" class="risk-page__empty">正在加载提取结果...</div>
        <div v-else-if="!groupedRiskResults.length" class="risk-page__empty">
          上传文档后，提取结果会出现在这里。
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

      <section ref="reviewQueueSection" class="risk-page__panel">
        <header class="risk-page__panel-head">
          <div>
            <h3>审核队列</h3>
            <p>这里只保留待审核事件，处理完当前队列就可以离开本页。</p>
          </div>
          <el-button text @click="eventsDrawerOpen = true">展开全量队列</el-button>
        </header>

        <el-table
          :data="reviewQueueEvents"
          size="small"
          v-loading="isEventsLoading"
          empty-text="暂无待审核事件"
        >
          <el-table-column prop="company_name" label="公司" min-width="120" show-overflow-tooltip />
          <el-table-column prop="risk_type" label="类型" min-width="110" show-overflow-tooltip />
          <el-table-column label="等级" width="82">
            <template #default="{ row }">
              <el-tag :type="getRiskTagType(row.risk_level)" size="small">
                {{ getRiskLevelText(row.risk_level) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="摘要" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.summary || row.evidence_text || '--' }}
            </template>
          </el-table-column>
          <el-table-column label="审核" width="88">
            <template #default="{ row }">
              <el-tag :type="getReviewTagType((row.review_status || 'pending').toLowerCase())" size="small">
                {{ getReviewStatusText(row.review_status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="148" align="right">
            <template #default="{ row }">
              <div v-if="(row.review_status || 'pending').toLowerCase() === 'pending'" class="risk-page__actions">
                <el-button
                  type="success"
                  plain
                  size="small"
                  :loading="reviewingId === (row.id || row.event_id)"
                  :disabled="reviewingId !== null"
                  @click="handleReview(row, 'approved')"
                >
                  确认
                </el-button>
                <el-button
                  type="danger"
                  plain
                  size="small"
                  :loading="reviewingId === (row.id || row.event_id)"
                  :disabled="reviewingId !== null"
                  @click="handleReview(row, 'rejected')"
                >
                  忽略
                </el-button>
              </div>
              <span v-else class="risk-page__muted-text">-</span>
            </template>
          </el-table-column>
        </el-table>
      </section>
    </div>

    <el-drawer
      v-model="eventsDrawerOpen"
      direction="rtl"
      size="720px"
      :with-header="false"
      destroy-on-close
      aria-label="风险事件列表"
    >
      <div class="risk-events-drawer">
        <div class="risk-events-drawer__head">
          <div>
            <h3>风险事件列表</h3>
            <div v-if="extractionQuality" class="risk-events-drawer__quality">
              <span>{{ extractionQuality.rounds }} 轮提取</span>
              <span v-if="extractionQuality.verified">验证通过</span>
            </div>
          </div>
          <el-button text @click="eventsDrawerOpen = false">关闭</el-button>
        </div>

        <el-form :inline="true" class="risk-filter-row">
          <el-form-item>
            <el-input v-model="filters.company_name" placeholder="公司名称" size="small" clearable />
          </el-form-item>
          <el-form-item>
            <el-input v-model="filters.risk_type" placeholder="风险类型" size="small" clearable />
          </el-form-item>
          <el-form-item>
            <el-select v-model="filters.risk_level" placeholder="等级" size="small" clearable>
              <el-option label="严重" value="critical" />
              <el-option label="高" value="high" />
              <el-option label="中" value="medium" />
              <el-option label="低" value="low" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-select v-model="filters.review_status" placeholder="状态" size="small" clearable>
              <el-option label="待审核" value="pending" />
              <el-option label="已确认" value="approved" />
              <el-option label="已忽略" value="rejected" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" size="small" :loading="isEventsLoading" @click="applyFilters">查询</el-button>
            <el-button size="small" @click="resetFilters">重置</el-button>
          </el-form-item>
        </el-form>

        <el-table
          :data="events"
          stripe
          size="small"
          v-loading="isEventsLoading"
          max-height="calc(100vh - 220px)"
          empty-text="暂无风险事件"
        >
          <el-table-column prop="company_name" label="公司" min-width="140" show-overflow-tooltip />
          <el-table-column label="类型" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">
              <el-tag size="small" effect="plain">{{ row.risk_type }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="等级" width="82">
            <template #default="{ row }">
              <el-tag :type="getRiskTagType(row.risk_level)" size="small">
                {{ getRiskLevelText(row.risk_level) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="时间" min-width="150">
            <template #default="{ row }">
              {{ formatDate(row.event_time || row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="摘要" min-width="240" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.summary || '--' }}
            </template>
          </el-table-column>
          <el-table-column label="置信度" width="88">
            <template #default="{ row }">
              <span :class="getConfidenceClass(row.confidence_score)">
                {{ formatConfidence(row.confidence_score) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="来源" width="96">
            <template #default="{ row }">
              <el-tooltip v-if="row.chunk_id" :content="getSourceTooltip(row)" placement="top">
                <span class="risk-source-chip">Chunk #{{ row.chunk_id }}</span>
              </el-tooltip>
              <span v-else class="risk-source-chip risk-source-chip--muted">--</span>
            </template>
          </el-table-column>
          <el-table-column label="审核" width="88">
            <template #default="{ row }">
              <el-tag :type="getReviewTagType((row.review_status || 'pending').toLowerCase())" size="small">
                {{ getReviewStatusText(row.review_status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="144">
            <template #default="{ row }">
              <template v-if="(row.review_status || 'pending').toLowerCase() === 'pending'">
                <el-button
                  type="success"
                  plain
                  size="small"
                  :loading="reviewingId === (row.id || row.event_id)"
                  :disabled="reviewingId !== null"
                  @click="handleReview(row, 'approved')"
                >
                  确认
                </el-button>
                <el-button
                  type="danger"
                  plain
                  size="small"
                  :loading="reviewingId === (row.id || row.event_id)"
                  :disabled="reviewingId !== null"
                  @click="handleReview(row, 'rejected')"
                >
                  忽略
                </el-button>
              </template>
              <span v-else class="risk-page__muted-text">-</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.risk-page {
  min-width: 0;
}

.risk-page__hero,
.risk-page__panel {
  padding: 20px 22px;
  border: 1px solid var(--line-strong);
  border-radius: 24px;
  background: var(--surface-1);
}

.risk-page__hero {
  display: grid;
  gap: 16px;
  min-width: 0;
}

.risk-page__hero-copy {
  max-width: 720px;
}

.risk-page__hero-copy h2,
.risk-page__launcher-head h3,
.risk-page__panel-head h3 {
  margin: 0;
  color: var(--text-primary);
}

.risk-page__task-flow {
  margin: 0;
  padding: 0 0 0 18px;
  display: grid;
  gap: 8px;
  color: var(--text-secondary);
}

.risk-page__task-flow li {
  display: grid;
  gap: 2px;
  padding-left: 4px;
}

.risk-page__task-flow strong {
  color: var(--text-primary);
  font-size: 0.9375rem;
}

.risk-page__runline {
  display: grid;
  gap: 6px;
  padding: 18px 20px;
  border: 1px solid var(--line-soft);
  border-radius: 20px;
  background: rgba(36, 87, 197, 0.04);
}

.risk-page__runline strong,
.risk-page__dropzone strong,
.risk-page__knowledge-item strong {
  color: var(--text-primary);
}

.risk-page__runline span:last-child,
.risk-page__dropzone span {
  color: var(--text-secondary);
}

.risk-page__run-badge {
  display: inline-flex;
  width: fit-content;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.risk-page__run-badge[data-tone='muted'] {
  background: rgba(125, 135, 152, 0.12);
  color: var(--text-muted);
}

.risk-page__run-badge[data-tone='active'] {
  background: rgba(36, 87, 197, 0.12);
  color: var(--brand);
}

.risk-page__run-badge[data-tone='success'] {
  background: rgba(33, 129, 92, 0.12);
  color: var(--success);
}

.risk-page__run-badge[data-tone='danger'] {
  background: rgba(196, 73, 61, 0.12);
  color: var(--risk);
}

.risk-page__progress-rail {
  position: relative;
  overflow: hidden;
  height: 10px;
  border-radius: 999px;
  background: var(--surface-3);
}

.risk-page__progress-rail > span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, rgba(36, 87, 197, 0.4), rgba(36, 87, 197, 1));
  transition: width 180ms ease;
}

.risk-page__knowledge-list {
  display: grid;
  gap: 12px;
}

.risk-page__dropzone {
  display: grid;
  gap: 6px;
  padding: 16px 18px;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  background: var(--surface-2);
}

.risk-page__dropzone {
  grid-template-columns: auto 1fr;
  align-items: center;
}

.risk-page__dropzone-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 14px;
  background: rgba(36, 87, 197, 0.12);
  color: var(--brand);
}

.risk-page__hero-copy p,
.risk-page__launcher-head p,
.risk-page__panel-head p,
.risk-page__result-head p,
.risk-page__evidence,
.risk-page__evidence-item p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.risk-page__actions,
.risk-page__knowledge-item {
  display: flex;
  gap: 10px;
}

.risk-page__launcher-actions,
.risk-page__actions {
  flex-wrap: wrap;
}

.risk-page__file-input {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}

.risk-page__source-switch > span,
.risk-page__muted-text,
.risk-events-drawer__quality {
  color: var(--text-muted);
  font-size: 0.75rem;
}

.risk-page__main {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.risk-page__launcher {
  display: grid;
  gap: 14px;
  padding: 16px 18px;
  border: 1px solid var(--line-soft);
  border-radius: 20px;
  background: var(--surface-2);
}

.risk-page__launcher-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.risk-page__source-switch {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
}

.risk-page__knowledge-item span,
.risk-page__knowledge-item small {
  color: var(--text-muted);
  font-size: 0.75rem;
}

.risk-page__launcher-body {
  display: grid;
  gap: 12px;
}

.risk-page__launcher-actions {
  display: flex;
  gap: 10px;
}

.risk-page__knowledge-search {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
}

.risk-page__knowledge-item {
  appearance: none;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: var(--surface-1);
  text-align: left;
  cursor: pointer;
  transition: border-color 160ms ease, background-color 160ms ease, transform 160ms ease;
}

.risk-page__knowledge-item:hover,
.risk-page__knowledge-item[data-active='true'] {
  border-color: rgba(36, 87, 197, 0.24);
  background: rgba(36, 87, 197, 0.06);
  transform: translateY(-1px);
}

.risk-page__knowledge-item > div {
  display: grid;
  gap: 4px;
}

.risk-page__panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.risk-page__panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.risk-page__result-list,
.risk-page__evidence-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.risk-page__result-item,
.risk-page__evidence-item {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  background: var(--surface-2);
}

.risk-page__result-head,
.risk-page__evidence-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.risk-page__result-head strong,
.risk-page__evidence-head strong,
.risk-page__task-flow strong {
  color: var(--text-primary);
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

.risk-page__evidence-head span {
  color: var(--text-muted);
  font-size: 0.75rem;
}

.risk-page__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 180px;
  color: var(--text-secondary);
  text-align: center;
}

.risk-events-drawer {
  padding: 20px;
}

.risk-events-drawer__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.risk-events-drawer__head h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: 1.125rem;
}

.risk-filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 14px;
}

.confidence-high {
  color: var(--success);
  font-weight: 600;
}

.confidence-mid {
  color: var(--warning);
  font-weight: 600;
}

.confidence-low {
  color: var(--risk);
  font-weight: 600;
}

.risk-source-chip {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(36, 87, 197, 0.1);
  color: var(--brand);
  font-size: 0.75rem;
}

.risk-source-chip--muted {
  background: rgba(125, 135, 152, 0.1);
  color: var(--text-muted);
}

.risk-page :deep(.el-table) {
  --el-table-border-color: var(--line-soft);
  --el-table-header-bg-color: transparent;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
}

.risk-page :deep(.el-table__inner-wrapper::before) {
  display: none;
}

.risk-page :deep(.el-table th.el-table__cell) {
  height: 40px;
  padding-block: 6px;
  color: var(--text-muted);
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  background: transparent;
}

.risk-page :deep(.el-input__wrapper),
.risk-page :deep(.el-select__wrapper),
.risk-page :deep(.el-textarea__inner) {
  min-height: 36px;
  background: var(--surface-2);
  box-shadow: inset 0 0 0 1px var(--line-strong);
  border-radius: 12px;
}

.risk-page :deep(.el-radio-button__inner) {
  border-radius: 12px;
}

@media (max-width: 1200px) {
  .risk-page__hero,
  .risk-page__main,
  .risk-page__knowledge-list {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .risk-page__hero,
  .risk-page__panel-head,
  .risk-page__launcher-head,
  .risk-page__knowledge-search {
    grid-template-columns: 1fr;
  }

  .risk-page__panel-head {
    display: flex;
    flex-direction: column;
  }

  .risk-page__source-switch,
  .risk-page__launcher-actions,
  .risk-page__knowledge-item {
    align-items: flex-start;
  }
}
</style>
